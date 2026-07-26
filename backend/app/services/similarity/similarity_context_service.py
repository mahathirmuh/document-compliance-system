"""Resolve retained Phase 8 structural evidence for Phase 9 analysis."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.compliance_enums import ComplianceRunStatus
from app.models.compliance_run import ComplianceRun
from app.models.translation_group import TranslationGroup
from app.models.translation_group_member import TranslationGroupMember
from app.schemas.similarity_internal import (
    SimilarityContext,
    SimilarityOptions,
    SimilarityThresholds,
)
from app.services.quality_score_service import QualityScoreService
from app.services.similarity.alignment.translation_alignment_service import (
    TranslationAlignmentService,
)


class SimilarityContextError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class SimilarityContextService:
    def __init__(
        self,
        settings: object,
        *,
        alignment: TranslationAlignmentService | None = None,
    ) -> None:
        self.settings = settings
        self.alignment = alignment or TranslationAlignmentService()
        self.maximum_groups = int(
            getattr(
                settings,
                "compliance_max_translation_groups",
                1_000_000,
            )
        )

    async def build(
        self,
        session: AsyncSession,
        *,
        document_file_id: UUID,
        compliance_run_id: UUID,
        language_detection_run_id: UUID,
    ) -> SimilarityContext:
        compliance = await session.scalar(
            select(ComplianceRun).where(ComplianceRun.id == compliance_run_id)
        )
        if compliance is None:
            raise SimilarityContextError(
                "SIMILARITY_COMPLIANCE_RUN_REQUIRED",
                "A retained compliance result is required.",
            )
        if (
            compliance.document_file_id != document_file_id
            or compliance.language_detection_run_id
            != language_detection_run_id
            or compliance.status
            not in {
                ComplianceRunStatus.COMPLETED,
                ComplianceRunStatus.PARTIALLY_COMPLETED,
            }
        ):
            raise SimilarityContextError(
                "SIMILARITY_SOURCE_INCOMPATIBLE",
                "The compliance and language sources are not compatible.",
            )
        count = int(
            (
                await session.scalar(
                    select(func.count(TranslationGroup.id)).where(
                        TranslationGroup.compliance_run_id == compliance.id
                    )
                )
            )
            or 0
        )
        if count > self.maximum_groups:
            raise SimilarityContextError(
                "SIMILARITY_GROUP_LIMIT_EXCEEDED",
                "The retained translation groups exceed the configured limit.",
            )
        rows = await session.scalars(
            select(TranslationGroup)
            .where(TranslationGroup.compliance_run_id == compliance.id)
            .options(
                selectinload(TranslationGroup.members).joinedload(
                    TranslationGroupMember.extracted_block
                ),
                selectinload(TranslationGroup.members).joinedload(
                    TranslationGroupMember.ocr_block
                ),
                joinedload(TranslationGroup.detected_section),
            )
            .order_by(TranslationGroup.group_index, TranslationGroup.id)
        )
        groups = list(rows.unique().all())
        return SimilarityContext(
            document_id=compliance.document_id,
            document_revision_id=compliance.document_revision_id,
            document_file_id=compliance.document_file_id,
            compliance_run_id=compliance.id,
            language_detection_run_id=compliance.language_detection_run_id,
            source_content_hash=compliance.source_content_hash,
            groups=self.alignment.from_models(groups),
            options=self._options(compliance.rule_snapshot_json),
            warnings=[
                str(item) for item in (compliance.warnings_json or [])
            ],
            source_quality=self._source_quality(compliance.metrics_json),
            quality_configuration=self._quality_configuration(
                compliance.rule_snapshot_json
            ),
        )

    @staticmethod
    def _quality_configuration(
        snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        return QualityScoreService.configuration_from_rule_snapshot(
            snapshot
        )

    def _options(self, snapshot: dict[str, Any]) -> SimilarityOptions:
        raw_validation = _mapping(
            snapshot.get("validationOptions")
            or snapshot.get("validation_options")
        )
        raw = _mapping(
            raw_validation.get("translationSimilarity")
            or raw_validation.get("translation_similarity")
            or raw_validation.get("similarity")
            or raw_validation
        )
        raw_thresholds = _mapping(
            raw.get("thresholds")
            or raw.get("similarityThresholds")
            or raw.get("similarity_thresholds")
        )
        thresholds = SimilarityThresholds(
            high=float(
                raw_thresholds.get(
                    "high",
                    getattr(self.settings, "similarity_high_threshold", 0.85),
                )
            ),
            acceptable=float(
                raw_thresholds.get(
                    "acceptable",
                    getattr(
                        self.settings,
                        "similarity_acceptable_threshold",
                        0.72,
                    ),
                )
            ),
            review=float(
                raw_thresholds.get(
                    "review",
                    getattr(
                        self.settings,
                        "similarity_review_threshold",
                        0.58,
                    ),
                )
            ),
            critical_low=float(
                raw_thresholds.get(
                    "criticalLow",
                    raw_thresholds.get(
                        "critical_low",
                        getattr(
                            self.settings,
                            "similarity_critical_low_threshold",
                            0.35,
                        ),
                    ),
                )
            ),
        )
        return SimilarityOptions(
            primary_language=_optional_string(
                raw.get("primaryLanguage")
                or raw.get("primary_language")
            ),
            required_pairs=_pairs(
                raw.get("requiredPairs") or raw.get("required_pairs")
            ),
            optional_pairs=_pairs(
                raw.get("optionalPairs") or raw.get("optional_pairs")
            ),
            thresholds=thresholds,
            length_ratio_ranges=_mapping(
                raw.get("lengthRatioRanges")
                or raw.get("length_ratio_ranges")
            ),
            minimum_characters=int(
                raw.get(
                    "minimumCharacters",
                    raw.get(
                        "minimum_characters",
                        getattr(
                            self.settings,
                            "similarity_min_characters_per_text",
                            10,
                        ),
                    ),
                )
            ),
            minimum_group_confidence=float(
                raw.get(
                    "minimumGroupConfidence",
                    raw.get(
                        "minimum_group_confidence",
                        getattr(
                            self.settings,
                            "similarity_min_group_confidence",
                            0.65,
                        ),
                    ),
                )
            ),
            skip_code_like_text=bool(
                getattr(
                    self.settings,
                    "similarity_skip_code_like_text",
                    True,
                )
            ),
            skip_numeric_only_text=bool(
                getattr(
                    self.settings,
                    "similarity_skip_numeric_only_text",
                    True,
                )
            ),
        )

    @staticmethod
    def _source_quality(
        metrics: dict[str, Any] | None,
    ) -> dict[str, float | bool | None]:
        values = metrics or {}
        return {
            "extractionConfidence": _optional_float(
                values.get("extractionConfidence")
            ),
            "ocrConfidence": _optional_float(
                values.get("ocrConfidence")
            ),
            "sourceWasOcr": values.get("sourceWasOcr"),
        }


def _mapping(value: object) -> dict[str, Any]:
    return (
        {str(key): item for key, item in value.items()}
        if isinstance(value, dict)
        else {}
    )


def _pairs(value: object) -> list[tuple[str, str]]:
    output: list[tuple[str, str]] = []
    if not isinstance(value, list):
        return output
    for item in value:
        if (
            isinstance(item, (list, tuple))
            and len(item) == 2
            and all(isinstance(part, str) for part in item)
        ):
            output.append((str(item[0]), str(item[1])))
    return output


def _optional_string(value: object) -> str | None:
    return str(value) if value not in (None, "") else None


def _optional_float(value: object) -> float | None:
    try:
        return float(cast(Any, value)) if value is not None else None
    except (TypeError, ValueError):
        return None
