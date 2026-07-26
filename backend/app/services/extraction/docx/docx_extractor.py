"""DOCX extraction preserving body paragraph/table order."""

from datetime import date, datetime
from pathlib import Path
from typing import cast
from zipfile import BadZipFile, ZipFile

from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from pydantic import JsonValue

from app.schemas.extraction import (
    ExtractedContainerData,
    ExtractedContainerType,
    ExtractedDocumentData,
    ExtractionResultStatus,
)
from app.services.extraction.base_extractor import (
    BaseDocumentExtractor,
    ExtractionError,
    ExtractionResourceLimitError,
)
from app.services.extraction.docx.docx_element_iterator import iter_docx_elements
from app.services.extraction.docx.docx_header_footer_extractor import (
    extract_headers_and_footers,
)
from app.services.extraction.docx.docx_paragraph_extractor import (
    extract_docx_paragraph,
)
from app.services.extraction.docx.docx_table_extractor import extract_docx_table
from app.services.extraction.text_normalizer import (
    count_characters,
    count_words,
    normalize_text,
)

_UNSUPPORTED_MARKERS = (
    (b"<w:txbxContent", "Text boxes may not be fully extracted."),
    (b"<w:object", "Embedded objects were not extracted."),
    (b"<m:oMath", "Equation content may not be fully extracted."),
    (b"<w:sdt", "Complex content controls may not be fully extracted."),
    (b"<w:del", "Tracked deleted content was not extracted."),
    (b"<w:drawing", "Drawing content may not be fully extracted."),
)


class DOCXExtractor(BaseDocumentExtractor):
    """Extract body, headings, tables, headers, and footers from DOCX."""

    extractor_version = "1.0.0"

    def supports(self, extension: str) -> bool:
        return self.normalize_extension(extension) == "docx"

    async def inspect(self, file_path: Path) -> dict[str, JsonValue]:
        file_size = self.validate_source_path(file_path)
        package_warnings, package_metadata = _inspect_package_features(file_path)
        document = self._open_document(file_path)
        return {
            "fileSize": file_size,
            "sectionCount": len(document.sections),
            "bodyParagraphCount": len(document.paragraphs),
            "bodyTableCount": len(document.tables),
            "coreProperties": _core_properties(document),
            "warnings": cast(JsonValue, package_warnings),
            **package_metadata,
        }

    async def extract(
        self,
        file_path: Path,
        context: dict[str, object],
    ) -> ExtractedDocumentData:
        extraction_context = self.resolve_context(context)
        file_size = self.validate_source_path(file_path, extraction_context)
        package_warnings, package_metadata = _inspect_package_features(file_path)
        document = self._open_document(file_path)
        try:
            body_blocks = []
            body_tables = []
            raw_parts: list[str] = []
            paragraph_count = 0
            table_count = 0
            table_cell_count = 0
            block_order = 1
            total_elements = sum(1 for _ in iter_docx_elements(document))
            processed_elements = 0

            for element_kind, element in iter_docx_elements(document):
                if processed_elements % 100 == 0:
                    await self.checkpoint(
                        extraction_context,
                        10
                        + int(
                            65 * processed_elements / max(1, total_elements)
                        ),
                        (
                            f"Reading DOCX body element "
                            f"{processed_elements + 1} of {total_elements}"
                        ),
                    )
                processed_elements += 1
                if element_kind == "paragraph":
                    paragraph_count += 1
                    _enforce_docx_limits(
                        extraction_context,
                        paragraphs=paragraph_count,
                        tables=table_count,
                        cells=table_cell_count,
                    )
                    block = extract_docx_paragraph(
                        element,
                        paragraph_index=paragraph_count,
                        block_order=block_order,
                    )
                    if block is not None:
                        body_blocks.append(block)
                        raw_parts.append(block.text)
                        block_order += 1
                    continue

                table_count += 1
                _enforce_docx_limits(
                    extraction_context,
                    paragraphs=paragraph_count,
                    tables=table_count,
                    cells=table_cell_count,
                )
                result = extract_docx_table(
                    element,
                    table_index=table_count,
                    block_order=block_order,
                    maximum_logical_cells=max(
                        0,
                        extraction_context.docx_max_table_cells
                        - table_cell_count,
                    ),
                )
                table_cell_count += result.logical_cell_count
                _enforce_docx_limits(
                    extraction_context,
                    paragraphs=paragraph_count,
                    tables=table_count,
                    cells=table_cell_count,
                )
                body_tables.append(result.table)
                body_blocks.extend(result.blocks)
                raw_parts.append(result.table.raw_text)
                block_order = result.next_block_order

            raw_text = "\n".join(part for part in raw_parts if part)
            normalised_text = normalize_text(raw_text)
            body_container = ExtractedContainerData(
                container_type=ExtractedContainerType.DOCX_BODY,
                container_index=1,
                name="body",
                title=_first_heading(body_blocks),
                raw_text=raw_text,
                normalised_text=normalised_text,
                character_count=count_characters(normalised_text),
                word_count=count_words(normalised_text),
                metadata={
                    "sourceOrder": True,
                    "pageNumbersGuaranteed": False,
                    "bodyElementCount": total_elements,
                },
                blocks=body_blocks,
                tables=body_tables,
            )

            header_footer_result = extract_headers_and_footers(
                document,
                first_container_index=2,
                context=extraction_context,
                starting_paragraph_count=paragraph_count,
                starting_table_count=table_count,
                starting_table_cell_count=table_cell_count,
            )
            paragraph_count += header_footer_result.paragraph_count
            table_count += header_footer_result.table_count
            table_cell_count += header_footer_result.table_cell_count
            _enforce_docx_limits(
                extraction_context,
                paragraphs=paragraph_count,
                tables=table_count,
                cells=table_cell_count,
            )
            containers = [
                body_container,
                *header_footer_result.containers,
            ]
            if not any(container.normalised_text for container in containers):
                raise ExtractionError(
                    "DOCX_EMPTY",
                    "The DOCX does not contain extractable text or tables.",
                )

            await self.checkpoint(
                extraction_context,
                75,
                "DOCX extraction completed",
            )
            status = (
                ExtractionResultStatus.PARTIALLY_COMPLETED
                if package_warnings
                else ExtractionResultStatus.COMPLETED
            )
            metadata: dict[str, JsonValue] = {
                "fileSize": file_size,
                "sectionCount": len(document.sections),
                "totalParagraphs": paragraph_count,
                "totalTables": table_count,
                "totalTableCells": table_cell_count,
                "coreProperties": _core_properties(document),
                **package_metadata,
            }
            return ExtractedDocumentData(
                extractor_type="DOCX",
                extractor_version=self.extractor_version,
                status=status,
                metadata=metadata,
                containers=containers,
                warnings=package_warnings,
                requires_ocr=False,
                has_selectable_text=True,
            )
        except ExtractionError:
            raise
        except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as exc:
            raise ExtractionError(
                "DOCX_EXTRACTION_FAILED",
                "The DOCX content could not be extracted.",
            ) from exc

    @staticmethod
    def _open_document(file_path: Path):
        try:
            return Document(str(file_path))
        except (BadZipFile, PackageNotFoundError, KeyError, ValueError) as exc:
            raise ExtractionError(
                "DOCX_CORRUPT",
                "The DOCX is corrupt or is not a valid DOCX document.",
            ) from exc


def _enforce_docx_limits(
    context,
    *,
    paragraphs: int,
    tables: int,
    cells: int,
) -> None:
    if paragraphs > context.docx_max_paragraphs:
        raise ExtractionResourceLimitError(
            "DOCX_EXTRACTION_FAILED",
            "The DOCX exceeds the configured paragraph limit.",
            details={
                "maximumParagraphs": context.docx_max_paragraphs,
                "actualParagraphs": paragraphs,
            },
        )
    if tables > context.docx_max_tables:
        raise ExtractionResourceLimitError(
            "DOCX_EXTRACTION_FAILED",
            "The DOCX exceeds the configured table limit.",
            details={
                "maximumTables": context.docx_max_tables,
                "actualTables": tables,
            },
        )
    if cells > context.docx_max_table_cells:
        raise ExtractionResourceLimitError(
            "DOCX_EXTRACTION_FAILED",
            "The DOCX exceeds the configured table-cell limit.",
            details={
                "maximumTableCells": context.docx_max_table_cells,
                "actualTableCells": cells,
            },
        )


def _inspect_package_features(
    file_path: Path,
) -> tuple[list[str], dict[str, JsonValue]]:
    try:
        with ZipFile(file_path) as archive:
            names = set(archive.namelist())
            _reject_unsafe_xml_declarations(archive, names)
            if any(
                name.lower().endswith("vbaproject.bin")
                for name in names
            ):
                raise ExtractionError(
                    "DOCX_UNSUPPORTED_CONTENT",
                    "Macro-enabled Word content is not supported.",
                )
            warnings: list[str] = []
            relevant_names = [
                name
                for name in names
                if name.startswith(
                    ("word/document.xml", "word/header", "word/footer")
                )
            ]
            content = b"".join(archive.read(name) for name in relevant_names)
            for marker, warning in _UNSUPPORTED_MARKERS:
                if marker in content:
                    warnings.append(warning)
            if "word/comments.xml" in names:
                warnings.append("Comments were not extracted.")
            if any(name.startswith("word/embeddings/") for name in names):
                warnings.append("Embedded files were not extracted.")
            relationship_content = b"".join(
                archive.read(name)
                for name in names
                if name.endswith(".rels")
            )
            external_relationship_count = relationship_content.count(
                b'TargetMode="External"'
            ) + relationship_content.count(b"TargetMode='External'")
            return list(dict.fromkeys(warnings)), {
                "externalRelationshipCount": external_relationship_count,
                "externalRelationshipsFollowed": False,
            }
    except ExtractionError:
        raise
    except (BadZipFile, KeyError, OSError, RuntimeError) as exc:
        raise ExtractionError(
            "DOCX_CORRUPT",
            "The DOCX is corrupt or is not a valid DOCX document.",
        ) from exc


def _reject_unsafe_xml_declarations(
    archive: ZipFile,
    names: set[str],
) -> None:
    """Reject OOXML DTD/entity declarations before library parsing."""
    forbidden_markers = (b"<!doctype", b"<!entity")
    for name in names:
        if not name.lower().endswith((".xml", ".rels")):
            continue
        overlap = b""
        with archive.open(name) as source:
            while chunk := source.read(64 * 1024):
                search_buffer = (overlap + chunk).lower()
                if any(
                    marker in search_buffer for marker in forbidden_markers
                ):
                    raise ExtractionError(
                        "DOCX_CORRUPT",
                        "The DOCX contains unsafe XML declarations.",
                    )
                overlap = search_buffer[-32:]


def _core_properties(document) -> dict[str, JsonValue]:
    properties = document.core_properties
    names = (
        "title",
        "subject",
        "author",
        "keywords",
        "comments",
        "last_modified_by",
        "revision",
        "category",
        "content_status",
        "identifier",
        "language",
        "version",
        "created",
        "modified",
    )
    result: dict[str, JsonValue] = {}
    for name in names:
        value = getattr(properties, name, None)
        if value in (None, ""):
            continue
        key = "".join(
            word if index == 0 else word.title()
            for index, word in enumerate(name.split("_"))
        )
        if isinstance(value, (datetime, date)):
            result[key] = value.isoformat()
        elif isinstance(value, (str, int, float, bool)):
            result[key] = value
        else:
            result[key] = str(value)
    return result


def _first_heading(blocks) -> str | None:
    for block in blocks:
        if block.block_type.value == "HEADING" and block.normalised_text:
            return block.normalised_text[:1000]
    return None
