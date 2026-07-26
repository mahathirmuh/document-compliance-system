"""Build the immutable, prerequisite-resolved input for the pure engine."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import cast
from uuid import UUID

from app.schemas.compliance_internal import (
    ComplianceBlockData,
    ComplianceContainerData,
    ComplianceTableCellData,
    ComplianceTableData,
    ComplianceValidationContext,
    DetectedSectionData,
    SectionAliasData,
    TranslationGroupData,
    ValidationRuleSnapshot,
)
from app.services.compliance._compat import (
    enum_value,
    first,
    float_value,
    int_value,
    mapping,
    read,
    sequence,
    string_value,
)
from app.services.compliance.compliance_score_service import (
    ComplianceScoreService,
)

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_XLSX_SHEET_RE = re.compile(r"XLSX:sheet=([^:]+)", re.IGNORECASE)
_CELL_RE = re.compile(r":cell=([^:]+)", re.IGNORECASE)
_SUPPORTED_FORMATS = {"PDF", "DOCX", "XLSX"}


class ComplianceContextBuildError(ValueError):
    code = "COMPLIANCE_CONTEXT_BUILD_FAILED"


class ComplianceContextService:
    """Normalize Phase 6/7 DTOs without reading a binary or database."""

    def __init__(self, *, maximum_blocks: int = 2_000_000) -> None:
        if maximum_blocks < 1:
            raise ValueError("maximum_blocks must be positive.")
        self.maximum_blocks = maximum_blocks
        self.score_service = ComplianceScoreService()

    def build(
        self,
        *,
        rule: object,
        source_format: str,
        blocks: Sequence[object] = (),
        containers: Sequence[object] = (),
        tables: Sequence[object] = (),
        section_aliases: Sequence[object] = (),
        detected_sections: Sequence[object] = (),
        translation_groups: Sequence[object] = (),
        language_results: Sequence[object] = (),
        prerequisites: Mapping[str, object] | None = None,
        warnings: Sequence[str] = (),
        document_id: object | None = None,
        document_revision_id: object | None = None,
        document_file_id: object | None = None,
        extraction_run_id: object | None = None,
        ocr_run_id: object | None = None,
        language_detection_run_id: object | None = None,
        document_code: str | None = None,
        expected_document_code: str | None = None,
        source_content_hash: str | None = None,
    ) -> ComplianceValidationContext:
        normalized_format = source_format.strip().upper().lstrip(".")
        if normalized_format not in _SUPPORTED_FORMATS:
            raise ComplianceContextBuildError(
                "Compliance source format must be PDF, DOCX, or XLSX.",
            )
        if source_content_hash is not None and not _HASH_RE.fullmatch(
            source_content_hash,
        ):
            raise ComplianceContextBuildError(
                "source_content_hash must be a lowercase SHA-256 digest.",
            )
        snapshot = self.snapshot_rule(rule)
        normalized_containers = [
            self._container(container) for container in containers
        ]
        normalized_blocks = [self._block(block) for block in blocks]
        normalized_annotations = [
            self._block(annotation) for annotation in language_results
        ]
        if normalized_annotations:
            normalized_blocks = self._merge_language_annotations(
                normalized_blocks,
                normalized_annotations,
            )
        if not normalized_blocks and normalized_containers:
            normalized_blocks = [
                block
                for container in normalized_containers
                for block in container.blocks
            ]
        if len(normalized_blocks) > self.maximum_blocks:
            raise ComplianceContextBuildError(
                "Compliance source exceeds the configured block limit.",
            )
        if not normalized_containers and normalized_blocks:
            normalized_containers = self._derive_containers(normalized_blocks)
        normalized_tables = [self._table(table) for table in tables]
        if normalized_annotations:
            normalized_tables = self._annotate_tables(
                normalized_tables,
                normalized_annotations,
            )
        default_prerequisites: dict[str, object] = {
            "extractionAvailable": True,
            "ocrRequired": False,
            "ocrCompleted": True,
            "languageDetectionAvailable": True,
            "contextComplete": True,
        }
        if prerequisites:
            default_prerequisites.update(dict(prerequisites))
        try:
            return ComplianceValidationContext(
                document_id=cast(UUID | None, document_id),
                document_revision_id=cast(UUID | None, document_revision_id),
                document_file_id=cast(UUID | None, document_file_id),
                extraction_run_id=cast(UUID | None, extraction_run_id),
                ocr_run_id=cast(UUID | None, ocr_run_id),
                language_detection_run_id=cast(
                    UUID | None,
                    language_detection_run_id,
                ),
                document_code=document_code,
                expected_document_code=expected_document_code,
                source_format=normalized_format,
                source_content_hash=source_content_hash,
                blocks=normalized_blocks,
                containers=normalized_containers,
                tables=normalized_tables,
                rule=snapshot,
                section_aliases=[
                    alias
                    if isinstance(alias, SectionAliasData)
                    else SectionAliasData.model_validate(alias)
                    for alias in section_aliases
                ],
                detected_sections=[
                    section
                    if isinstance(section, DetectedSectionData)
                    else DetectedSectionData.model_validate(section)
                    for section in detected_sections
                ],
                translation_groups=[
                    group
                    if isinstance(group, TranslationGroupData)
                    else TranslationGroupData.model_validate(group)
                    for group in translation_groups
                ],
                prerequisites=default_prerequisites,
                warnings=list(warnings),
            )
        except (TypeError, ValueError) as exc:
            raise ComplianceContextBuildError(
                f"Unable to build compliance context: {exc}",
            ) from exc

    build_context = build

    def snapshot_rule(self, rule: object) -> ValidationRuleSnapshot:
        if isinstance(rule, ValidationRuleSnapshot):
            snapshot = rule.model_copy(deep=True)
            self.score_service.validate_weights(snapshot)
            return snapshot
        values: dict[str, object] = {}
        for field_name, field in ValidationRuleSnapshot.model_fields.items():
            del field
            aliases = [field_name]
            if field_name == "rule_id":
                aliases.append("id")
            elif field_name == "rule_code":
                aliases.append("code")
            elif field_name == "rule_name":
                aliases.append("name")
            elif field_name == "rule_version":
                aliases.append("version")
            elif field_name == "required_languages":
                aliases.append("required_languages_json")
            elif field_name == "required_sections":
                aliases.append("required_sections_json")
            elif field_name == "language_order":
                aliases.append("language_order_json")
            elif field_name == "minimum_language_block_coverage":
                aliases.append("minimum_language_block_coverage_json")
            elif field_name == "minimum_language_character_coverage":
                aliases.append("minimum_language_character_coverage_json")
            elif field_name == "validation_options":
                aliases.append("validation_options_json")
            value = first(rule, *aliases, default=None)
            if value is not None:
                values[field_name] = value
        values.setdefault("rule_code", "DEFAULT-COMPLIANCE")
        try:
            snapshot = ValidationRuleSnapshot.model_validate(values)
            self.score_service.validate_weights(snapshot)
        except (TypeError, ValueError) as exc:
            raise ComplianceContextBuildError(
                f"Validation rule snapshot is invalid: {exc}",
            ) from exc
        return snapshot

    @staticmethod
    def with_analysis(
        context: ComplianceValidationContext,
        *,
        detected_sections: Sequence[DetectedSectionData],
        translation_groups: Sequence[TranslationGroupData],
        warnings: Sequence[str] | None = None,
    ) -> ComplianceValidationContext:
        return context.model_copy(
            update={
                "detected_sections": list(detected_sections),
                "translation_groups": list(translation_groups),
                "warnings": (
                    list(warnings)
                    if warnings is not None
                    else list(context.warnings)
                ),
            },
            deep=True,
        )

    def _block(self, block: object) -> ComplianceBlockData:
        if isinstance(block, ComplianceBlockData):
            return block.model_copy(deep=True)
        persisted_result = read(block, "result", None)
        if persisted_result is not None:
            return self._language_read_row(block, persisted_result)
        nested_source = read(block, "source", None)
        nested_detection = read(block, "detection", None)
        if nested_source is not None and nested_detection is not None:
            source_metadata = mapping(
                read(nested_source, "source_metadata", {}),
            )
            eligibility = read(nested_detection, "eligibility", None)
            source_id = first(
                nested_source,
                "extracted_block_id",
                "ocr_block_id",
                default=None,
            )
            source_type = enum_value(
                read(nested_source, "source_type", ""),
            ).upper()
            source_metadata = {
                **source_metadata,
                "sourceType": source_type,
                "extractedBlockId": read(
                    nested_source,
                    "extracted_block_id",
                    None,
                ),
                "ocrBlockId": read(
                    nested_source,
                    "ocr_block_id",
                    None,
                ),
            }
            return ComplianceBlockData(
                id=cast(UUID | None, source_id),
                container_id=cast(
                    UUID | None,
                    read(nested_source, "container_id", None),
                ),
                container_type=enum_value(
                    read(nested_source, "container_type", ""),
                ),
                container_name=cast(
                    str | None,
                    read(nested_source, "container_name", None),
                ),
                container_index=int_value(
                    read(nested_source, "container_index", 0),
                ),
                block_order=int_value(
                    read(nested_source, "block_order", 0),
                ),
                block_type=enum_value(
                    first(
                        source_metadata,
                        "block_type",
                        "blockType",
                        default="TEXT",
                    ),
                ),
                source_reference=string_value(
                    read(nested_source, "source_reference", ""),
                ),
                text=string_value(read(nested_source, "text", "")),
                normalised_text=string_value(
                    read(nested_source, "normalised_text", ""),
                ),
                style_name=cast(
                    str | None,
                    first(
                        source_metadata,
                        "style_name",
                        "styleName",
                        default=None,
                    ),
                ),
                heading_level=cast(
                    int | None,
                    first(
                        source_metadata,
                        "heading_level",
                        "headingLevel",
                        default=None,
                    ),
                ),
                page_number=cast(
                    int | None,
                    read(nested_source, "page_number", None),
                ),
                language_code=enum_value(
                    read(nested_detection, "language_code", "unknown"),
                ),
                language_confidence=float_value(
                    read(nested_detection, "confidence", 0.0),
                ),
                character_count=int_value(
                    read(nested_detection, "character_count", 0),
                ),
                eligibility_status=enum_value(
                    read(eligibility, "status", "ELIGIBLE"),
                ),
                location=mapping(
                    first(
                        source_metadata,
                        "location",
                        default={},
                    ),
                ),
                metadata=source_metadata,
            )
        metadata = mapping(
            first(block, "metadata", "metadata_json", default={}),
        )
        location = mapping(
            first(block, "location", "location_json", default={}),
        )
        return ComplianceBlockData(
            id=cast(
                UUID | None,
                first(
                    block,
                    "id",
                    "extracted_block_id",
                    "ocr_block_id",
                    default=None,
                ),
            ),
            container_id=cast(
                UUID | None,
                read(block, "container_id", None),
            ),
            container_type=enum_value(
                read(block, "container_type", ""),
            ),
            container_name=cast(
                str | None,
                first(
                    block,
                    "container_name",
                    "container_title",
                    default=None,
                ),
            ),
            container_index=int_value(read(block, "container_index", 0)),
            block_order=int_value(read(block, "block_order", 0)),
            block_type=enum_value(read(block, "block_type", "TEXT")),
            source_reference=string_value(
                read(block, "source_reference", ""),
            ),
            text=string_value(read(block, "text", "")),
            normalised_text=string_value(
                first(block, "normalised_text", "text", default=""),
            ),
            style_name=cast(str | None, read(block, "style_name", None)),
            heading_level=cast(
                int | None,
                read(block, "heading_level", None),
            ),
            page_number=cast(
                int | None,
                first(
                    block,
                    "page_number",
                    default=first(location, "page", default=None),
                ),
            ),
            language_code=enum_value(
                read(block, "language_code", "unknown"),
            ),
            language_confidence=float_value(
                first(
                    block,
                    "language_confidence",
                    "confidence",
                    default=0.0,
                ),
            ),
            character_count=int_value(
                read(
                    block,
                    "character_count",
                    len(string_value(read(block, "text", ""))),
                ),
            ),
            eligibility_status=enum_value(
                read(block, "eligibility_status", "ELIGIBLE"),
            ),
            location=location,
            metadata=metadata,
        )

    @staticmethod
    def _language_read_row(
        row: object,
        persisted_result: object,
    ) -> ComplianceBlockData:
        metadata = mapping(
            first(
                persisted_result,
                "metadata_json",
                "metadata",
                default={},
            ),
        )
        source_metadata = mapping(read(metadata, "source", {}))
        reference = string_value(
            read(persisted_result, "source_reference", ""),
        )
        upper_reference = reference.upper()
        if upper_reference.startswith(("PDF:", "OCR:")):
            container_type = "PDF_PAGE"
        elif upper_reference.startswith("XLSX:"):
            container_type = "XLSX_WORKSHEET"
        else:
            container_type = "DOCX_BODY"
        page_number = first(
            metadata,
            "page_number",
            "pageNumber",
            default=None,
        )
        container_index = int_value(
            first(
                metadata,
                "container_index",
                "containerIndex",
                default=page_number or 0,
            ),
        )
        container_name: str | None = None
        if container_type == "PDF_PAGE" and page_number is not None:
            container_name = f"Page {page_number}"
        elif container_type == "XLSX_WORKSHEET":
            match = _XLSX_SHEET_RE.search(reference)
            container_name = match.group(1) if match else None
        source_id = first(
            persisted_result,
            "extracted_block_id",
            "ocr_block_id",
            default=None,
        )
        raw_text = string_value(read(row, "text", ""))
        source_metadata = {
            **source_metadata,
            "languageBlockResultId": string_value(
                read(persisted_result, "id", ""),
            ),
            "sourceType": enum_value(
                read(persisted_result, "source_type", ""),
            ).upper(),
            "extractedBlockId": read(
                persisted_result,
                "extracted_block_id",
                None,
            ),
            "ocrBlockId": read(
                persisted_result,
                "ocr_block_id",
                None,
            ),
            "sourceConfidence": read(row, "source_confidence", None),
        }
        return ComplianceBlockData(
            id=cast(UUID | None, source_id),
            container_id=cast(
                UUID | None,
                read(persisted_result, "container_id", None),
            ),
            container_type=container_type,
            container_name=container_name,
            container_index=container_index,
            block_order=int_value(
                first(
                    metadata,
                    "block_order",
                    "blockOrder",
                    default=0,
                ),
            ),
            block_type=enum_value(
                first(
                    source_metadata,
                    "block_type",
                    "blockType",
                    default=(
                        "CELL"
                        if container_type == "XLSX_WORKSHEET"
                        else "TEXT"
                    ),
                ),
            ),
            source_reference=reference,
            text=raw_text,
            normalised_text=" ".join(raw_text.split()),
            style_name=cast(
                str | None,
                first(
                    source_metadata,
                    "style_name",
                    "styleName",
                    default=None,
                ),
            ),
            heading_level=cast(
                int | None,
                first(
                    source_metadata,
                    "heading_level",
                    "headingLevel",
                    default=None,
                ),
            ),
            page_number=(
                int_value(page_number) if page_number is not None else None
            ),
            language_code=enum_value(
                read(persisted_result, "language_code", "unknown"),
            ),
            language_confidence=float_value(
                read(persisted_result, "confidence", 0.0),
            ),
            character_count=int_value(
                read(persisted_result, "character_count", len(raw_text)),
            ),
            eligibility_status=enum_value(
                read(
                    persisted_result,
                    "eligibility_status",
                    "ELIGIBLE",
                ),
            ),
            location=mapping(
                first(source_metadata, "location", default={}),
            ),
            metadata=source_metadata,
        )

    @staticmethod
    def _merge_language_annotations(
        blocks: Sequence[ComplianceBlockData],
        annotations: Sequence[ComplianceBlockData],
    ) -> list[ComplianceBlockData]:
        by_id = {
            annotation.id: annotation
            for annotation in annotations
            if annotation.id is not None
        }
        by_reference = {
            annotation.source_reference: annotation
            for annotation in annotations
            if annotation.source_reference
        }
        merged: list[ComplianceBlockData] = []
        for block in blocks:
            annotation = (
                by_id.get(block.id)
                if block.id is not None
                else None
            ) or by_reference.get(block.source_reference)
            if annotation is None:
                merged.append(block)
                continue
            merged.append(
                block.model_copy(
                    update={
                        "language_code": annotation.language_code,
                        "language_confidence": (
                            annotation.language_confidence
                        ),
                        "eligibility_status": (
                            annotation.eligibility_status
                        ),
                        "metadata": {
                            **block.metadata,
                            "languageAnnotation": annotation.metadata,
                            "languageSourceBlockId": annotation.id,
                            "languageSourceReference": (
                                annotation.source_reference
                            ),
                            "languageSourceType": read(
                                annotation.metadata,
                                "sourceType",
                                "",
                            ),
                            "languageBlockResultId": read(
                                annotation.metadata,
                                "languageBlockResultId",
                                None,
                            ),
                            "extractedBlockId": read(
                                annotation.metadata,
                                "extractedBlockId",
                                None,
                            ),
                            "ocrBlockId": read(
                                annotation.metadata,
                                "ocrBlockId",
                                None,
                            ),
                        },
                    },
                    deep=True,
                ),
            )
        return merged

    @staticmethod
    def _annotate_tables(
        tables: Sequence[ComplianceTableData],
        annotations: Sequence[ComplianceBlockData],
    ) -> list[ComplianceTableData]:
        by_sheet_coordinate: dict[
            tuple[str, str],
            ComplianceBlockData,
        ] = {}
        coordinate_counts: dict[str, int] = defaultdict(int)
        by_coordinate: dict[str, ComplianceBlockData] = {}
        for annotation in annotations:
            sheet_match = _XLSX_SHEET_RE.search(
                annotation.source_reference,
            )
            cell_match = _CELL_RE.search(annotation.source_reference)
            if cell_match is None:
                continue
            coordinate = cell_match.group(1).upper()
            sheet = sheet_match.group(1) if sheet_match else ""
            by_sheet_coordinate[(sheet.casefold(), coordinate)] = annotation
            coordinate_counts[coordinate] += 1
            by_coordinate[coordinate] = annotation
        annotated_tables: list[ComplianceTableData] = []
        for table in tables:
            sheet_match = _XLSX_SHEET_RE.search(table.source_reference)
            sheet = sheet_match.group(1).casefold() if sheet_match else ""
            cells: list[ComplianceTableCellData] = []
            for cell in table.cells:
                coordinate = (cell.coordinate or "").upper()
                matched_annotation = by_sheet_coordinate.get(
                    (sheet, coordinate),
                )
                if (
                    matched_annotation is None
                    and coordinate_counts.get(coordinate) == 1
                ):
                    matched_annotation = by_coordinate.get(coordinate)
                if matched_annotation is None:
                    cells.append(cell)
                    continue
                cells.append(
                    cell.model_copy(
                        update={
                            "language_code": matched_annotation.language_code,
                            "language_confidence": (
                                matched_annotation.language_confidence
                            ),
                            "metadata": {
                                **cell.metadata,
                                "languageSourceReference": (
                                    matched_annotation.source_reference
                                ),
                                "languageSourceBlockId": matched_annotation.id,
                                "languageSourceType": read(
                                    matched_annotation.metadata,
                                    "sourceType",
                                    "",
                                ),
                                "languageBlockResultId": read(
                                    matched_annotation.metadata,
                                    "languageBlockResultId",
                                    None,
                                ),
                                "extractedBlockId": read(
                                    matched_annotation.metadata,
                                    "extractedBlockId",
                                    None,
                                ),
                                "ocrBlockId": read(
                                    matched_annotation.metadata,
                                    "ocrBlockId",
                                    None,
                                ),
                                "coordinate": cell.coordinate,
                                "rowIndex": cell.row_index,
                                "columnIndex": cell.column_index,
                            },
                        },
                        deep=True,
                    ),
                )
            annotated_tables.append(
                table.model_copy(update={"cells": cells}, deep=True),
            )
        return annotated_tables

    def _container(self, container: object) -> ComplianceContainerData:
        if isinstance(container, ComplianceContainerData):
            return container.model_copy(deep=True)
        raw_blocks = sequence(read(container, "blocks", []))
        return ComplianceContainerData(
            id=cast(UUID | None, read(container, "id", None)),
            container_type=enum_value(
                read(container, "container_type", ""),
            ),
            container_name=cast(
                str | None,
                first(
                    container,
                    "container_name",
                    "name",
                    "title",
                    default=None,
                ),
            ),
            container_index=int_value(
                read(container, "container_index", 0),
            ),
            character_count=int_value(
                read(container, "character_count", 0),
            ),
            blocks=[self._block(block) for block in raw_blocks],
        )

    @staticmethod
    def _derive_containers(
        blocks: Sequence[ComplianceBlockData],
    ) -> list[ComplianceContainerData]:
        grouped: dict[
            tuple[UUID | None, str, str | None, int],
            list[ComplianceBlockData],
        ] = defaultdict(list)
        for block in blocks:
            grouped[
                (
                    block.container_id,
                    block.container_type,
                    block.container_name,
                    block.container_index,
                )
            ].append(block)
        return [
            ComplianceContainerData(
                id=container_id,
                container_type=container_type,
                container_name=container_name,
                container_index=container_index,
                character_count=sum(
                    block.character_count for block in container_blocks
                ),
                blocks=sorted(
                    container_blocks,
                    key=lambda item: item.block_order,
                ),
            )
            for (
                container_id,
                container_type,
                container_name,
                container_index,
            ), container_blocks in sorted(
                grouped.items(),
                key=lambda item: (item[0][3], str(item[0][0] or "")),
            )
        ]

    def _table(self, table: object) -> ComplianceTableData:
        if isinstance(table, ComplianceTableData):
            return table.model_copy(deep=True)
        cells = [
            self._cell(cell) for cell in sequence(read(table, "cells", []))
        ]
        return ComplianceTableData(
            id=cast(UUID | None, read(table, "id", None)),
            container_id=cast(
                UUID | None,
                read(table, "container_id", None),
            ),
            source_reference=string_value(
                read(table, "source_reference", ""),
            ),
            table_index=int_value(read(table, "table_index", 0)),
            row_count=int_value(read(table, "row_count", 0)),
            column_count=int_value(read(table, "column_count", 0)),
            cells=cells,
            metadata=mapping(
                first(table, "metadata", "metadata_json", default={}),
            ),
        )

    @staticmethod
    def _cell(cell: object) -> ComplianceTableCellData:
        if isinstance(cell, ComplianceTableCellData):
            return cell.model_copy(deep=True)
        return ComplianceTableCellData(
            id=cast(UUID | None, read(cell, "id", None)),
            row_index=int_value(read(cell, "row_index", 0)),
            column_index=int_value(read(cell, "column_index", 0)),
            row_span=int_value(read(cell, "row_span", 1), 1),
            column_span=int_value(read(cell, "column_span", 1), 1),
            coordinate=cast(
                str | None,
                read(cell, "coordinate", None),
            ),
            text=string_value(read(cell, "text", "")),
            normalised_text=string_value(
                first(cell, "normalised_text", "text", default=""),
            ),
            language_code=enum_value(
                read(cell, "language_code", "unknown"),
            ),
            language_confidence=float_value(
                first(
                    cell,
                    "language_confidence",
                    "confidence",
                    default=0.0,
                ),
            ),
            metadata=mapping(
                first(cell, "metadata", "metadata_json", default={}),
            ),
        )
