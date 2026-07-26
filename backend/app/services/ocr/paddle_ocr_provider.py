"""Lazy, process-local PaddleOCR integration for Latin and Chinese text."""

from __future__ import annotations

import asyncio
import importlib.metadata
import threading
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, ClassVar, cast

from app.models.ocr_job import OCRLanguageProfile
from app.models.ocr_page_result import OCRPageStatus
from app.schemas.ocr_internal import (
    OCRBlockData,
    OCRBoundingBox,
    OCRPageResult,
)
from app.services.extraction.text_normalizer import normalize_text
from app.services.ocr.base_ocr_provider import (
    BaseOCRProvider,
    OCRError,
    OCRProviderUnavailableError,
)

EngineFactory = Callable[[OCRLanguageProfile], object]


class PaddleOCRProvider(BaseOCRProvider):
    """PaddleOCR facade with no import/download work at module import time."""

    _model_cache: ClassVar[dict[tuple[str, ...], object]] = {}
    _model_lock: ClassVar[threading.Lock] = threading.Lock()
    _profiles: ClassVar[frozenset[OCRLanguageProfile]] = frozenset(OCRLanguageProfile)

    def __init__(
        self,
        *,
        engine_factory: EngineFactory | None = None,
        model_root: Path = Path("models/ocr"),
        detection_model_name: str = "PP-OCRv5_mobile_det",
        latin_recognition_model_name: str = "latin_PP-OCRv5_mobile_rec",
        chinese_recognition_model_name: str = "PP-OCRv5_mobile_rec",
        orientation_model_name: str = "PP-LCNet_x1_0_doc_ori",
    ) -> None:
        self.engine_factory = engine_factory
        self.model_root = model_root
        self.detection_model_name = detection_model_name
        self.latin_recognition_model_name = latin_recognition_model_name
        self.chinese_recognition_model_name = chinese_recognition_model_name
        self.orientation_model_name = orientation_model_name

    def supports_language_profile(self, language_profile: str) -> bool:
        try:
            return OCRLanguageProfile(language_profile) in self._profiles
        except ValueError:
            return False

    def get_provider_info(self) -> dict:
        try:
            version = importlib.metadata.version("paddleocr")
            installed = True
        except importlib.metadata.PackageNotFoundError:
            version = None
            installed = False
        return {
            "name": "paddleocr",
            "version": version,
            "installed": installed,
            "loadedProfiles": sorted(
                profile
                for root, profile, *_ in self._model_cache
                if root == str(self.model_root.resolve())
            ),
            "profiles": sorted(profile.value for profile in self._profiles),
            "processing": "local",
        }

    async def recognise_page(
        self,
        image_path: Path,
        language_profile: str,
        options: dict,
    ) -> OCRPageResult:
        try:
            profile = OCRLanguageProfile(language_profile)
        except ValueError as exc:
            raise OCRError(
                "OCR_PROVIDER_UNAVAILABLE",
                "The requested OCR language profile is not supported.",
                details={"languageProfile": language_profile},
            ) from exc
        if not image_path.is_file():
            raise OCRError(
                "OCR_RECOGNITION_FAILED",
                "The rendered OCR image is not available.",
            )

        if profile is OCRLanguageProfile.AUTO_MULTILINGUAL:
            return await self._recognise_auto(image_path, options)
        return await self._recognise_single(image_path, profile, options)

    async def _recognise_auto(
        self,
        image_path: Path,
        options: dict[str, Any],
    ) -> OCRPageResult:
        latin = await self._recognise_single(
            image_path,
            OCRLanguageProfile.LATIN,
            options,
        )
        latin_characters = sum(len(block.text) for block in latin.blocks)
        average = (
            sum(block.confidence for block in latin.blocks) / len(latin.blocks)
            if latin.blocks
            else 0.0
        )
        inspect_text = "".join(block.text for block in latin.blocks)
        contains_han = any("\u3400" <= char <= "\u9fff" for char in inspect_text)
        chinese_pass_enabled = self._boolean_option(
            options.get("auto_multilingual_chinese_pass"),
            default=True,
        )
        confidence_threshold = self._bounded_float_option(
            options.get("chinese_pass_confidence_threshold"),
            default=0.65,
            minimum=0.0,
            maximum=1.0,
        )
        minimum_characters = self._bounded_int_option(
            options.get("chinese_pass_minimum_characters"),
            default=20,
            minimum=0,
            maximum=100_000,
        )
        # Selecting AUTO_MULTILINGUAL is an explicit request to recognise both
        # supported script families.  A Latin-only first pass cannot reliably
        # signal that Chinese text was missed (it may return punctuation with a
        # high confidence), so heuristics alone are not sufficient here.
        trigger_reasons: list[str] = ["AUTO_MULTILINGUAL_PROFILE"]
        if self._boolean_option(options.get("force_chinese"), default=False):
            trigger_reasons.append("FORCED")
        if self._boolean_option(
            options.get("validation_requires_chinese"),
            default=False,
        ):
            trigger_reasons.append("VALIDATION_REQUIRES_CHINESE")
        if contains_han:
            trigger_reasons.append("HAN_DETECTED")
        if average < confidence_threshold:
            trigger_reasons.append("LOW_LATIN_CONFIDENCE")
        if latin_characters < minimum_characters:
            trigger_reasons.append("LOW_LATIN_CHARACTER_COUNT")
        run_chinese = chinese_pass_enabled and bool(trigger_reasons)
        if not run_chinese:
            latin.language_profile = OCRLanguageProfile.AUTO_MULTILINGUAL
            latin.metadata = {
                **(latin.metadata or {}),
                "passes": [OCRLanguageProfile.LATIN.value],
                "chinesePassEnabled": chinese_pass_enabled,
                "chinesePassTriggered": False,
            }
            return latin

        cancellation_checker = options.get("cancellation_checker")
        if callable(cancellation_checker):
            cancelled = cancellation_checker()
            if asyncio.iscoroutine(cancelled):
                cancelled = await cancelled
            if cancelled:
                from app.services.ocr.base_ocr_provider import (
                    OCRCancelledError,
                )

                raise OCRCancelledError

        chinese = await self._recognise_single(
            image_path,
            OCRLanguageProfile.CHINESE_SIMPLIFIED,
            options,
        )
        from app.services.ocr.ocr_merge_service import OCRMergeService

        blocks = OCRMergeService().deduplicate_provider_blocks(
            [*latin.blocks, *chinese.blocks]
        )
        status = OCRPageStatus.COMPLETED if blocks else OCRPageStatus.NO_TEXT_FOUND
        latin_orientation_detected = bool(
            (latin.metadata or {}).get("orientationDetected")
        )
        chinese_orientation_detected = bool(
            (chinese.metadata or {}).get("orientationDetected")
        )
        selected_rotation = (
            latin.rotation_applied
            if latin_orientation_detected or not chinese_orientation_detected
            else chinese.rotation_applied
        )
        return OCRPageResult(
            page_number=latin.page_number,
            status=status,
            language_profile=OCRLanguageProfile.AUTO_MULTILINGUAL,
            render_width=latin.render_width,
            render_height=latin.render_height,
            render_dpi=latin.render_dpi,
            rotation_applied=selected_rotation,
            blocks=blocks,
            warning_codes=list(
                dict.fromkeys([*latin.warning_codes, *chinese.warning_codes])
            ),
            metadata={
                "passes": [
                    OCRLanguageProfile.LATIN.value,
                    OCRLanguageProfile.CHINESE_SIMPLIFIED.value,
                ],
                "latinBlockCount": len(latin.blocks),
                "chineseBlockCount": len(chinese.blocks),
                "chinesePassEnabled": True,
                "chinesePassTriggered": True,
                "chinesePassReasons": trigger_reasons,
                "orientation": selected_rotation,
                "orientationDetected": (
                    latin_orientation_detected or chinese_orientation_detected
                ),
                "passOrientations": {
                    OCRLanguageProfile.LATIN.value: latin.rotation_applied,
                    OCRLanguageProfile.CHINESE_SIMPLIFIED.value: (
                        chinese.rotation_applied
                    ),
                },
                "orientationAgreement": (
                    latin.rotation_applied == chinese.rotation_applied
                    if latin_orientation_detected and chinese_orientation_detected
                    else None
                ),
            },
        )

    async def _recognise_single(
        self,
        image_path: Path,
        profile: OCRLanguageProfile,
        options: Mapping[str, Any],
    ) -> OCRPageResult:
        try:
            engine = await asyncio.to_thread(self._get_engine, profile)
            raw_result = await asyncio.to_thread(
                self._invoke_engine,
                engine,
                image_path,
            )
            orientation = self._parse_document_orientation(raw_result)
            blocks = self._parse_blocks(
                raw_result,
                profile,
                orientation=orientation or 0,
            )
        except OCRError:
            raise
        except (MemoryError, OSError, RuntimeError, TypeError, ValueError) as exc:
            raise OCRError(
                "OCR_RECOGNITION_FAILED",
                "The local OCR provider could not recognise this page.",
                details={"languageProfile": profile.value},
            ) from exc

        return OCRPageResult(
            page_number=int(options.get("page_number", 1)),
            status=(OCRPageStatus.COMPLETED if blocks else OCRPageStatus.NO_TEXT_FOUND),
            language_profile=profile,
            render_width=max(0, int(options.get("render_width", 0))),
            render_height=max(0, int(options.get("render_height", 0))),
            render_dpi=max(72, int(options.get("render_dpi", 300))),
            rotation_applied=orientation or 0,
            blocks=blocks,
            metadata={
                "pass": profile.value,
                "orientation": orientation or 0,
                "orientationDetected": orientation is not None,
            },
        )

    def _get_engine(self, profile: OCRLanguageProfile) -> object:
        model_profile = (
            OCRLanguageProfile.LATIN
            if profile is OCRLanguageProfile.AUTO_MULTILINGUAL
            else profile
        )
        if self.engine_factory is not None:
            return self.engine_factory(model_profile)
        recognition_model_name = (
            self.chinese_recognition_model_name
            if model_profile is OCRLanguageProfile.CHINESE_SIMPLIFIED
            else self.latin_recognition_model_name
        )
        cache_key = (
            str(self.model_root.resolve()),
            model_profile.value,
            self.detection_model_name,
            recognition_model_name,
            self.orientation_model_name,
        )
        with self._model_lock:
            cached = self._model_cache.get(cache_key)
            if cached is not None:
                return cached
            engine = self._load_engine(
                model_profile,
                self.model_root,
                detection_model_name=self.detection_model_name,
                recognition_model_name=recognition_model_name,
                orientation_model_name=self.orientation_model_name,
            )
            self._model_cache[cache_key] = engine
            return engine

    @staticmethod
    def _load_engine(
        profile: OCRLanguageProfile,
        model_root: Path,
        *,
        detection_model_name: str,
        recognition_model_name: str,
        orientation_model_name: str,
    ) -> object:
        profile_directory = model_root / (
            "chinese_simplified"
            if profile is OCRLanguageProfile.CHINESE_SIMPLIFIED
            else "latin"
        )
        detection_directory = profile_directory / "detection"
        recognition_directory = profile_directory / "recognition"
        required_directories = (
            detection_directory,
            recognition_directory,
        )
        if any(
            not directory.is_dir() or not any(directory.iterdir())
            for directory in required_directories
        ):
            raise OCRProviderUnavailableError(
                "OCR_MODEL_LOAD_FAILED",
                "Required local PaddleOCR model files are not installed.",
                details={
                    "languageProfile": profile.value,
                },
            )
        try:
            from paddleocr import PaddleOCR
        except (ImportError, OSError) as exc:
            raise OCRProviderUnavailableError(
                "OCR_PROVIDER_UNAVAILABLE",
                "PaddleOCR is not installed or its local runtime is unavailable.",
            ) from exc
        language = "ch" if profile is OCRLanguageProfile.CHINESE_SIMPLIFIED else "en"
        orientation_directory = model_root / "orientation"
        has_orientation_model = orientation_directory.is_dir() and any(
            orientation_directory.iterdir()
        )
        try:
            return PaddleOCR(
                text_detection_model_name=detection_model_name,
                text_detection_model_dir=str(detection_directory),
                text_recognition_model_name=recognition_model_name,
                text_recognition_model_dir=str(recognition_directory),
                doc_orientation_classify_model_name=(
                    orientation_model_name if has_orientation_model else None
                ),
                doc_orientation_classify_model_dir=(
                    str(orientation_directory) if has_orientation_model else None
                ),
                use_doc_orientation_classify=has_orientation_model,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                enable_mkldnn=False,
            )
        except TypeError:
            try:
                return PaddleOCR(
                    lang=language,
                    det_model_dir=str(detection_directory),
                    rec_model_dir=str(recognition_directory),
                    cls_model_dir=(
                        str(orientation_directory) if has_orientation_model else None
                    ),
                    use_angle_cls=has_orientation_model,
                    show_log=False,
                )
            except Exception as exc:
                raise OCRProviderUnavailableError(
                    "OCR_MODEL_LOAD_FAILED",
                    "The configured PaddleOCR model could not be loaded.",
                    details={"languageProfile": profile.value},
                ) from exc
        except Exception as exc:
            raise OCRProviderUnavailableError(
                "OCR_MODEL_LOAD_FAILED",
                "The configured PaddleOCR model could not be loaded.",
                details={"languageProfile": profile.value},
            ) from exc

    @staticmethod
    def _invoke_engine(engine: object, image_path: Path) -> object:
        legacy = getattr(engine, "ocr", None)
        if callable(legacy):
            try:
                return legacy(str(image_path), cls=True)
            except TypeError:
                return legacy(str(image_path))
        predict = getattr(engine, "predict", None)
        if callable(predict):
            return predict(input=str(image_path))
        raise TypeError("PaddleOCR engine exposes no recognition method.")

    @classmethod
    def _parse_blocks(
        cls,
        raw_result: object,
        profile: OCRLanguageProfile,
        *,
        orientation: int = 0,
    ) -> list[OCRBlockData]:
        candidates: list[tuple[object, object, object]] = []
        cls._collect_candidates(raw_result, candidates)
        blocks: list[OCRBlockData] = []
        for polygon_value, text_value, confidence_value in candidates:
            text = str(text_value).strip()
            if not text:
                continue
            polygon = cls._normalise_polygon(polygon_value)
            if len(polygon) < 4:
                continue
            confidence = min(
                1.0,
                max(0.0, float(cast(Any, confidence_value))),
            )
            xs = [point[0] for point in polygon]
            ys = [point[1] for point in polygon]
            blocks.append(
                OCRBlockData(
                    text=text,
                    normalised_text=normalize_text(text),
                    confidence=confidence,
                    polygon=polygon,
                    bbox=OCRBoundingBox(
                        x=min(xs),
                        y=min(ys),
                        width=max(xs) - min(xs),
                        height=max(ys) - min(ys),
                    ),
                    provider_model=(
                        "paddleocr-ch"
                        if profile is OCRLanguageProfile.CHINESE_SIMPLIFIED
                        else "paddleocr-latin"
                    ),
                    recognition_profile=profile,
                    orientation=orientation,
                )
            )
        return blocks

    @classmethod
    def _parse_document_orientation(cls, value: object) -> int | None:
        """Read the correction angle emitted by Paddle's document preprocessor."""
        return cls._find_document_orientation(value, visited=set())

    @classmethod
    def _find_document_orientation(
        cls,
        value: object,
        *,
        visited: set[int],
    ) -> int | None:
        if value is None or isinstance(value, (str, bytes, bytearray)):
            return None
        identity = id(value)
        if identity in visited:
            return None
        visited.add(identity)

        mapping = cls._mapping_value(value)
        if mapping is not None:
            document_result = mapping.get("doc_preprocessor_res")
            if document_result is not None:
                orientation = cls._orientation_from_preprocessor_result(document_result)
                if orientation is not None:
                    return orientation
            for wrapper_key in ("res", "result", "results", "data"):
                nested = mapping.get(wrapper_key)
                if nested is not None:
                    orientation = cls._find_document_orientation(
                        nested,
                        visited=visited,
                    )
                    if orientation is not None:
                        return orientation
            return None

        sequence = cls._sequence_value(value)
        if sequence is not None:
            for nested in sequence:
                orientation = cls._find_document_orientation(
                    nested,
                    visited=visited,
                )
                if orientation is not None:
                    return orientation
            return None

        json_value = getattr(value, "json", None)
        if callable(json_value):
            json_value = json_value()
        if json_value is not None:
            return cls._find_document_orientation(
                json_value,
                visited=visited,
            )
        return None

    @classmethod
    def _orientation_from_preprocessor_result(
        cls,
        value: object,
    ) -> int | None:
        mapping = cls._mapping_value(value)
        if mapping is None:
            json_value = getattr(value, "json", None)
            if callable(json_value):
                json_value = json_value()
            mapping = cls._mapping_value(json_value)
        if mapping is None:
            return None

        nested_result = mapping.get("res")
        if nested_result is not None:
            nested_mapping = cls._mapping_value(nested_result)
            if nested_mapping is not None:
                mapping = nested_mapping
        settings = cls._mapping_value(mapping.get("model_settings"))
        if (
            settings is not None
            and settings.get("use_doc_orientation_classify") is False
        ):
            return None
        return cls._normalise_orientation(mapping.get("angle"))

    @staticmethod
    def _normalise_orientation(value: object) -> int | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            numeric_value = float(cast(Any, value))
        except (TypeError, ValueError):
            return None
        if not numeric_value.is_integer():
            return None
        orientation = int(numeric_value) % 360
        return orientation if orientation in {0, 90, 180, 270} else None

    @staticmethod
    def _boolean_option(value: object, *, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "on"}:
                return True
            if normalized in {"false", "0", "no", "off"}:
                return False
        return bool(value)

    @staticmethod
    def _bounded_float_option(
        value: object,
        *,
        default: float,
        minimum: float,
        maximum: float,
    ) -> float:
        try:
            parsed = float(
                cast(Any, default if value is None else value)
            )
        except (TypeError, ValueError):
            parsed = default
        return min(maximum, max(minimum, parsed))

    @staticmethod
    def _bounded_int_option(
        value: object,
        *,
        default: int,
        minimum: int,
        maximum: int,
    ) -> int:
        try:
            parsed = int(cast(Any, default if value is None else value))
        except (TypeError, ValueError):
            parsed = default
        return min(maximum, max(minimum, parsed))

    @classmethod
    def _collect_candidates(
        cls,
        value: object,
        output: list[tuple[object, object, object]],
    ) -> None:
        mapping = cls._mapping_value(value)
        if mapping is not None:
            texts = cls._sequence_value(mapping.get("rec_texts"))
            scores = cls._sequence_value(mapping.get("rec_scores"))
            polygon_value = mapping.get("dt_polys")
            if polygon_value is None:
                polygon_value = mapping.get("rec_polys")
            polygons = cls._sequence_value(polygon_value)
            if texts and scores and polygons:
                output.extend(zip(polygons, texts, scores, strict=False))
                return
            for nested in mapping.values():
                cls._collect_candidates(nested, output)
            return

        sequence = cls._sequence_value(value)
        if sequence is None:
            json_value = getattr(value, "json", None)
            if callable(json_value):
                cls._collect_candidates(json_value(), output)
            elif json_value is not None:
                cls._collect_candidates(json_value, output)
            return
        if (
            len(sequence) == 2
            and cls._looks_like_polygon(sequence[0])
            and (recognition := cls._sequence_value(sequence[1]))
            and len(recognition) >= 2
            and isinstance(recognition[0], str)
        ):
            output.append((sequence[0], recognition[0], recognition[1]))
            return
        for nested in sequence:
            cls._collect_candidates(nested, output)

    @staticmethod
    def _mapping_value(value: object) -> Mapping[str, Any] | None:
        if isinstance(value, Mapping):
            return value
        value_dict = getattr(value, "res", None)
        return value_dict if isinstance(value_dict, Mapping) else None

    @staticmethod
    def _sequence_value(value: object) -> list[Any] | None:
        if isinstance(value, (str, bytes, bytearray)):
            return None
        if isinstance(value, Sequence):
            return list(value)
        to_list = getattr(value, "tolist", None)
        if callable(to_list):
            converted = to_list()
            return list(converted) if isinstance(converted, Sequence) else None
        return None

    @classmethod
    def _looks_like_polygon(cls, value: object) -> bool:
        points = cls._sequence_value(value)
        return bool(
            points
            and len(points) >= 4
            and all(
                (point_values := cls._sequence_value(point)) and len(point_values) >= 2
                for point in points
            )
        )

    @classmethod
    def _normalise_polygon(cls, value: object) -> list[list[float]]:
        points = cls._sequence_value(value) or []
        normalized: list[list[float]] = []
        for point in points:
            values = cls._sequence_value(point)
            if not values or len(values) < 2:
                continue
            normalized.append(
                [
                    max(0.0, float(values[0])),
                    max(0.0, float(values[1])),
                ]
            )
        return normalized
