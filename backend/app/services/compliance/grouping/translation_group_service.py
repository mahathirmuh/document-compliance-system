"""Format router for structural translation grouping."""

from __future__ import annotations

from collections.abc import Sequence

from app.schemas.compliance_internal import TranslationGroupData
from app.services.compliance._compat import (
    enum_value,
    first,
    int_value,
    option,
    read,
    sequence,
    string_list,
)
from app.services.compliance.grouping.paragraph_grouping_service import (
    ParagraphGroupingService,
)
from app.services.compliance.grouping.positional_grouping_service import (
    PositionalGroupingService,
)
from app.services.compliance.grouping.table_grouping_service import (
    TableGroupingService,
)


class TranslationGroupLimitError(ValueError):
    """Raised when structural grouping would exceed the configured bound."""


class TranslationGroupService:
    """Create PDF/DOCX/XLSX groups without semantic translation claims."""

    def __init__(
        self,
        paragraph_service: ParagraphGroupingService | None = None,
        positional_service: PositionalGroupingService | None = None,
        table_service: TableGroupingService | None = None,
        *,
        maximum_groups: int = 500_000,
    ) -> None:
        self.paragraph_service = (
            paragraph_service or ParagraphGroupingService()
        )
        self.positional_service = (
            positional_service or PositionalGroupingService()
        )
        self.table_service = table_service or TableGroupingService()
        if maximum_groups < 1:
            raise ValueError("maximum_groups must be positive.")
        self.maximum_groups = maximum_groups

    def group(
        self,
        context_or_blocks: object,
        expected_languages: Sequence[str] | None = None,
        *,
        source_format: str | None = None,
        tables: Sequence[object] | None = None,
        sections: Sequence[object] | None = None,
    ) -> list[TranslationGroupData]:
        if isinstance(context_or_blocks, Sequence) and not isinstance(
            context_or_blocks,
            (str, bytes, bytearray),
        ):
            blocks = list(context_or_blocks)
            rule = {}
        else:
            blocks = sequence(read(context_or_blocks, "blocks", []))
            rule = read(context_or_blocks, "rule", {})
            if tables is None:
                tables = sequence(read(context_or_blocks, "tables", []))
            if sections is None:
                sections = sequence(
                    read(context_or_blocks, "detected_sections", []),
                )
            if source_format is None:
                source_format = enum_value(
                    first(
                        context_or_blocks,
                        "source_format",
                        "file_type",
                        default="",
                    ),
                )
            if expected_languages is None:
                expected_languages = string_list(
                    read(rule, "required_languages", ("id", "en", "zh")),
                )
        expected = tuple(expected_languages or ("id", "en", "zh"))
        inferred_format = (source_format or self._infer_format(blocks)).upper()
        groups: list[TranslationGroupData] = []

        if inferred_format == "PDF":
            groups.extend(
                self.positional_service.group(
                    blocks,
                    expected,
                    start_index=len(groups),
                ),
            )
        elif inferred_format == "XLSX":
            groups.extend(
                self.table_service.group_tables(
                    list(tables or []),
                    expected,
                    start_index=len(groups),
                    ignore_formula_only=bool(
                        option(rule, "ignore_formula_only_cells", True),
                    ),
                    ignore_numeric_only=bool(
                        option(rule, "ignore_numeric_only_cells", True),
                    ),
                ),
            )
        else:
            groups.extend(
                self.paragraph_service.group(
                    blocks,
                    expected,
                    start_index=len(groups),
                ),
            )
            groups.extend(
                self.table_service.group_tables(
                    list(tables or []),
                    expected,
                    start_index=len(groups),
                ),
            )

        if len(groups) > self.maximum_groups:
            raise TranslationGroupLimitError(
                "Translation group count exceeds the configured limit.",
            )
        assigned = self._assign_sections(groups, list(sections or []))
        return [
            group.model_copy(update={"group_index": index})
            for index, group in enumerate(assigned)
        ]

    def create_groups(
        self,
        context_or_blocks: object,
        expected_languages: Sequence[str] | None = None,
        **kwargs: object,
    ) -> list[TranslationGroupData]:
        return self.group(
            context_or_blocks,
            expected_languages,
            source_format=(
                str(kwargs["source_format"])
                if kwargs.get("source_format") is not None
                else None
            ),
            tables=kwargs.get("tables"),  # type: ignore[arg-type]
            sections=kwargs.get("sections"),  # type: ignore[arg-type]
        )

    @staticmethod
    def _infer_format(blocks: Sequence[object]) -> str:
        container_types = {
            enum_value(read(block, "container_type", "")).upper()
            for block in blocks
        }
        references = {
            str(read(block, "source_reference", "")).upper()
            for block in blocks[:20]
        }
        if any(item.startswith("PDF") for item in container_types) or any(
            reference.startswith("PDF:")
            for reference in references
        ):
            return "PDF"
        if "XLSX_WORKSHEET" in container_types or any(
            reference.startswith("XLSX:")
            for reference in references
        ):
            return "XLSX"
        return "DOCX"

    @staticmethod
    def _assign_sections(
        groups: Sequence[TranslationGroupData],
        sections: Sequence[object],
    ) -> list[TranslationGroupData]:
        if not sections:
            return list(groups)
        assigned: list[TranslationGroupData] = []
        for group in groups:
            first_order = min(
                (member.block_order for member in group.members),
                default=-1,
            )
            matched_code: str | None = None
            for section in sections:
                section_container = read(section, "container_id", None)
                if (
                    group.container_id is not None
                    and section_container is not None
                    and str(group.container_id) != str(section_container)
                ):
                    continue
                start = int_value(read(section, "start_block_order", 0))
                end = int_value(read(section, "end_block_order", -1))
                if start <= first_order <= end:
                    matched_code = str(
                        read(section, "canonical_code", ""),
                    )
                    break
            assigned.append(
                group.model_copy(
                    update={"detected_section_code": matched_code},
                ),
            )
        return assigned
