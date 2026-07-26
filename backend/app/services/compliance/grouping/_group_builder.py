"""Private deterministic builders for immutable translation-group contracts."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast
from uuid import UUID

from app.schemas.compliance_internal import (
    TranslationGroupData,
    TranslationGroupMemberData,
)
from app.services.compliance._compat import (
    enum_value,
    first,
    float_value,
    int_value,
    language_code,
    mapping,
    read,
    string_value,
)
from app.services.compliance.grouping.group_order_service import (
    GroupOrderService,
)


def member_from_block(
    block: object,
    *,
    language: str | None = None,
    maximum_snapshot_characters: int = 500,
) -> TranslationGroupMemberData:
    location = mapping(
        first(block, "location", "location_json", "position", default={}),
    )
    metadata = mapping(
        first(block, "metadata", "metadata_json", default={}),
    )
    annotation = mapping(read(metadata, "languageAnnotation", {}))
    source_type = enum_value(
        first(
            block,
            "source_type",
            default=first(
                metadata,
                "languageSourceType",
                "sourceType",
                default=read(annotation, "sourceType", ""),
            ),
        ),
    ).upper()
    source_block_id = first(
        block,
        "extracted_block_id",
        "ocr_block_id",
        default=first(
            metadata,
            "languageSourceBlockId",
            default=read(block, "id", None),
        ),
    )
    extracted_block_id = first(
        block,
        "extracted_block_id",
        default=first(
            metadata,
            "extractedBlockId",
            default=read(annotation, "extractedBlockId", None),
        ),
    )
    ocr_block_id = first(
        block,
        "ocr_block_id",
        default=first(
            metadata,
            "ocrBlockId",
            default=read(annotation, "ocrBlockId", None),
        ),
    )
    if extracted_block_id is None and ocr_block_id is None:
        if source_type == "OCR":
            ocr_block_id = source_block_id
        else:
            extracted_block_id = source_block_id
    language_result_id = first(
        block,
        "language_block_result_id",
        default=first(
            metadata,
            "languageBlockResultId",
            default=read(annotation, "languageBlockResultId", None),
        ),
    )
    position = {
        **location,
        **{
            key: value
            for key, value in {
                "row": first(
                    metadata,
                    "row",
                    "rowIndex",
                    default=read(block, "row_index", None),
                ),
                "column": first(
                    metadata,
                    "column",
                    "columnIndex",
                    default=read(block, "column_index", None),
                ),
                "coordinate": first(
                    metadata,
                    "coordinate",
                    default=read(block, "coordinate", None),
                ),
            }.items()
            if value is not None
        },
    }
    confidence = float_value(
        first(
            block,
            "language_confidence",
            "confidence",
            default=0.0,
        ),
    )
    return TranslationGroupMemberData(
        block_id=cast(UUID | None, read(block, "id", None)),
        extracted_block_id=cast(UUID | None, extracted_block_id),
        ocr_block_id=cast(UUID | None, ocr_block_id),
        language_block_result_id=cast(UUID | None, language_result_id),
        language_code=(language or language_code(block)).casefold(),
        block_order=int_value(
            first(
                block,
                "block_order",
                "row_index",
                default=0,
            ),
        ),
        text_snapshot=string_value(
            first(block, "text", "normalised_text", default=""),
        )[:maximum_snapshot_characters],
        confidence=max(0.0, min(1.0, confidence)),
        source_reference=(
            string_value(read(block, "source_reference", ""))
            or string_value(read(metadata, "languageSourceReference", ""))
        ),
        source_type=source_type or None,
        position=position,
    )


def build_group(
    members: Sequence[TranslationGroupMemberData],
    *,
    group_index: int,
    group_type: str,
    expected_languages: Sequence[str],
    container_id: object | None,
    source_reference: str,
    confidence: float,
    detected_section_code: str | None = None,
    metrics: dict[str, object] | None = None,
    allow_missing_before_order_check: bool = False,
) -> TranslationGroupData:
    order_service = GroupOrderService()
    expected = tuple(language.casefold() for language in expected_languages)
    language_order = tuple(member.language_code for member in members)
    detected = tuple(dict.fromkeys(language_order))
    orders = [member.block_order for member in members]
    return TranslationGroupData(
        container_id=cast(UUID | None, container_id),
        group_index=group_index,
        group_type=group_type,
        source_reference=source_reference,
        expected_languages=list(expected),
        detected_languages=list(detected),
        language_order=list(language_order),
        members=list(members),
        is_complete=order_service.is_complete(detected, expected),
        is_order_valid=order_service.is_valid(
            language_order,
            expected,
            allow_missing=allow_missing_before_order_check,
        ),
        confidence=round(max(0.0, min(1.0, confidence)), 6),
        detected_section_code=detected_section_code,
        start_block_order=min(orders, default=0),
        end_block_order=max(orders, default=0),
        metrics=metrics or {},
    )


def container_id_for(value: object) -> UUID | None:
    return cast(UUID | None, read(value, "container_id", None))


def source_reference_for(
    values: Sequence[object],
    *,
    fallback: str,
) -> str:
    references = [
        string_value(read(value, "source_reference", ""))
        for value in values
        if string_value(read(value, "source_reference", ""))
    ]
    if not references:
        return fallback
    if len(references) == 1:
        return references[0]
    return f"{references[0]}..{references[-1]}"
