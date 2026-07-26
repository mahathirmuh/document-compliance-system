"""Detect multilingual row/column layouts and build structural cell groups."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Sequence

from app.schemas.compliance_internal import TranslationGroupData
from app.services.compliance._compat import (
    bool_value,
    enum_value,
    first,
    int_value,
    language_code,
    mapping,
    read,
    string_value,
)
from app.services.compliance.constants import (
    GROUP_TYPE_TABLE_ROW,
    GROUP_TYPE_XLSX_ROW,
)
from app.services.compliance.contracts import TableLayout
from app.services.compliance.grouping._group_builder import (
    build_group,
    member_from_block,
)
from app.services.compliance.sections.section_alias_service import (
    normalise_heading,
)

_NUMERIC_RE = re.compile(r"^[\s\d.,%()+\-/:]+$")
_LANGUAGE_HEADER_ALIASES: dict[str, frozenset[str]] = {
    "id": frozenset(
        {
            "id",
            "indonesia",
            "indonesian",
            "bahasa indonesia",
            "bahasa",
        },
    ),
    "en": frozenset({"en", "english", "inggris", "bahasa inggris"}),
    "zh": frozenset(
        {
            "zh",
            "chinese",
            "mandarin",
            "中文",
            "汉语",
            "漢語",
            "华语",
            "華語",
            "bahasa mandarin",
        },
    ),
}


class TableGroupingService:
    """Infer only layout and adjacency; it never compares translated meaning."""

    def detect_layout(
        self,
        table: object,
        expected_languages: Sequence[str] = ("id", "en", "zh"),
    ) -> TableLayout:
        cells = list(read(table, "cells", []) or [])
        expected = tuple(language.casefold() for language in expected_languages)
        if not cells:
            return TableLayout(layout="UNKNOWN_LAYOUT")

        row_indices = sorted({self._row(cell) for cell in cells})
        column_indices = sorted({self._column(cell) for cell in cells})
        first_row = row_indices[0]
        first_column = column_indices[0]

        header_columns: dict[str, int] = {}
        for cell in cells:
            if self._row(cell) != first_row:
                continue
            code = self._header_language(
                string_value(first(cell, "text", "normalised_text", default="")),
            )
            if code in expected and code not in header_columns:
                header_columns[code] = self._column(cell)

        header_rows: dict[str, int] = {}
        for cell in cells:
            if self._column(cell) != first_column:
                continue
            code = self._header_language(
                string_value(first(cell, "text", "normalised_text", default="")),
            )
            if code in expected and code not in header_rows:
                header_rows[code] = self._row(cell)

        column_mapping = header_columns or self._distribution_columns(
            cells,
            expected,
            exclude_row=first_row,
        )
        row_mapping = header_rows or self._distribution_rows(
            cells,
            expected,
            exclude_column=first_column,
        )
        column_count = len(column_mapping)
        row_count = len(row_mapping)
        if column_count < 2 and row_count < 2:
            return TableLayout(
                layout="UNKNOWN_LAYOUT",
                confidence=0.0,
                metrics={
                    "matchedLanguageColumns": column_count,
                    "matchedLanguageRows": row_count,
                },
            )

        if column_count == row_count and column_count >= 2:
            layout_name = "MIXED_LAYOUT"
            confidence = column_count / max(1, len(expected))
        elif column_count > row_count:
            layout_name = "LANGUAGES_AS_COLUMNS"
            confidence = column_count / max(1, len(expected))
        else:
            layout_name = "LANGUAGES_AS_ROWS"
            confidence = row_count / max(1, len(expected))

        active_mapping = (
            column_mapping
            if layout_name != "LANGUAGES_AS_ROWS"
            else row_mapping
        )
        header_order = tuple(
            language
            for language, _ in sorted(
                active_mapping.items(),
                key=lambda item: item[1],
            )
        )
        return TableLayout(
            layout=layout_name,
            language_columns=column_mapping,
            language_rows=row_mapping,
            confidence=round(min(1.0, confidence), 6),
            header_order=header_order,
            metrics={
                "headerEvidence": bool(header_columns or header_rows),
                "matchedLanguageColumns": column_count,
                "matchedLanguageRows": row_count,
                "semanticSimilarityEvaluated": False,
            },
        )

    def group(
        self,
        table: object,
        expected_languages: Sequence[str],
        *,
        start_index: int = 0,
        ignore_formula_only: bool = True,
        ignore_numeric_only: bool = True,
    ) -> list[TranslationGroupData]:
        layout = self.detect_layout(table, expected_languages)
        if layout.layout == "UNKNOWN_LAYOUT":
            return []
        if layout.layout == "LANGUAGES_AS_ROWS":
            return self._group_rows_layout(
                table,
                layout,
                expected_languages,
                start_index=start_index,
                ignore_formula_only=ignore_formula_only,
                ignore_numeric_only=ignore_numeric_only,
            )
        return self._group_columns_layout(
            table,
            layout,
            expected_languages,
            start_index=start_index,
            ignore_formula_only=ignore_formula_only,
            ignore_numeric_only=ignore_numeric_only,
        )

    def group_tables(
        self,
        tables: Sequence[object],
        expected_languages: Sequence[str],
        *,
        start_index: int = 0,
        ignore_formula_only: bool = True,
        ignore_numeric_only: bool = True,
    ) -> list[TranslationGroupData]:
        groups: list[TranslationGroupData] = []
        for table in tables:
            groups.extend(
                self.group(
                    table,
                    expected_languages,
                    start_index=start_index + len(groups),
                    ignore_formula_only=ignore_formula_only,
                    ignore_numeric_only=ignore_numeric_only,
                ),
            )
        return groups

    def _group_columns_layout(
        self,
        table: object,
        layout: TableLayout,
        expected: Sequence[str],
        *,
        start_index: int,
        ignore_formula_only: bool,
        ignore_numeric_only: bool,
    ) -> list[TranslationGroupData]:
        cells = list(read(table, "cells", []) or [])
        mapped_columns = set(layout.language_columns.values())
        if not mapped_columns:
            return []
        header_row = min(
            (
                self._row(cell)
                for cell in cells
                if self._column(cell) in mapped_columns
                and self._header_language(
                    string_value(read(cell, "text", "")),
                )
            ),
            default=-1,
        )
        by_position = {
            (self._row(cell), self._column(cell)): cell for cell in cells
        }
        data_rows = sorted(
            {
                self._row(cell)
                for cell in cells
                if self._row(cell) != header_row
                and self._column(cell) in mapped_columns
            },
        )
        groups: list[TranslationGroupData] = []
        for row in data_rows:
            members = []
            missing: list[str] = []
            missing_cells: dict[str, str | None] = {}
            for language in expected:
                column = layout.language_columns.get(language.casefold())
                cell = (
                    by_position.get((row, column))
                    if column is not None
                    else None
                )
                if cell is None or not self._is_meaningful(
                    cell,
                    ignore_formula_only=ignore_formula_only,
                    ignore_numeric_only=ignore_numeric_only,
                ):
                    missing.append(language.casefold())
                    missing_cells[language.casefold()] = (
                        string_value(read(cell, "coordinate", ""))
                        if cell is not None
                        else None
                    )
                    continue
                members.append(
                    member_from_block(cell, language=language.casefold()),
                )
            if not members and not missing:
                continue
            groups.append(
                build_group(
                    members,
                    group_index=start_index + len(groups),
                    group_type=self._group_type(table),
                    expected_languages=expected,
                    container_id=self._container_id(table),
                    source_reference=(
                        f"{self._table_reference(table)}:row={row}"
                    ),
                    confidence=layout.confidence,
                    metrics={
                        "strategy": "LANGUAGES_AS_COLUMNS",
                        "rowIndex": row,
                        "missingLanguages": tuple(missing),
                        "missingCells": missing_cells,
                        "languageColumns": layout.language_columns,
                        "headerOrder": layout.header_order,
                        "semanticSimilarityEvaluated": False,
                    },
                ),
            )
        return groups

    def _group_rows_layout(
        self,
        table: object,
        layout: TableLayout,
        expected: Sequence[str],
        *,
        start_index: int,
        ignore_formula_only: bool,
        ignore_numeric_only: bool,
    ) -> list[TranslationGroupData]:
        cells = list(read(table, "cells", []) or [])
        mapped_rows = set(layout.language_rows.values())
        by_position = {
            (self._row(cell), self._column(cell)): cell for cell in cells
        }
        label_column = min(
            (
                self._column(cell)
                for cell in cells
                if self._row(cell) in mapped_rows
                and self._header_language(
                    string_value(read(cell, "text", "")),
                )
            ),
            default=-1,
        )
        data_columns = sorted(
            {
                self._column(cell)
                for cell in cells
                if self._row(cell) in mapped_rows
                and self._column(cell) != label_column
            },
        )
        groups: list[TranslationGroupData] = []
        for column in data_columns:
            members = []
            missing: list[str] = []
            missing_cells: dict[str, str | None] = {}
            for language in expected:
                row = layout.language_rows.get(language.casefold())
                cell = (
                    by_position.get((row, column))
                    if row is not None
                    else None
                )
                if cell is None or not self._is_meaningful(
                    cell,
                    ignore_formula_only=ignore_formula_only,
                    ignore_numeric_only=ignore_numeric_only,
                ):
                    missing.append(language.casefold())
                    missing_cells[language.casefold()] = (
                        string_value(read(cell, "coordinate", ""))
                        if cell is not None
                        else None
                    )
                    continue
                members.append(
                    member_from_block(cell, language=language.casefold()),
                )
            if not members and not missing:
                continue
            groups.append(
                build_group(
                    members,
                    group_index=start_index + len(groups),
                    group_type=self._group_type(table),
                    expected_languages=expected,
                    container_id=self._container_id(table),
                    source_reference=(
                        f"{self._table_reference(table)}:column={column}"
                    ),
                    confidence=layout.confidence,
                    metrics={
                        "strategy": "LANGUAGES_AS_ROWS",
                        "columnIndex": column,
                        "missingLanguages": tuple(missing),
                        "missingCells": missing_cells,
                        "languageRows": layout.language_rows,
                        "headerOrder": layout.header_order,
                        "semanticSimilarityEvaluated": False,
                    },
                ),
            )
        return groups

    @staticmethod
    def _distribution_columns(
        cells: Sequence[object],
        expected: Sequence[str],
        *,
        exclude_row: int,
    ) -> dict[str, int]:
        counts: dict[int, Counter[str]] = defaultdict(Counter)
        for cell in cells:
            if TableGroupingService._row(cell) == exclude_row:
                continue
            code = language_code(cell)
            if code in expected:
                counts[TableGroupingService._column(cell)][code] += 1
        return TableGroupingService._unique_dominants(counts)

    @staticmethod
    def _distribution_rows(
        cells: Sequence[object],
        expected: Sequence[str],
        *,
        exclude_column: int,
    ) -> dict[str, int]:
        counts: dict[int, Counter[str]] = defaultdict(Counter)
        for cell in cells:
            if TableGroupingService._column(cell) == exclude_column:
                continue
            code = language_code(cell)
            if code in expected:
                counts[TableGroupingService._row(cell)][code] += 1
        return TableGroupingService._unique_dominants(counts)

    @staticmethod
    def _unique_dominants(
        counts: dict[int, Counter[str]],
    ) -> dict[str, int]:
        candidates: list[tuple[int, int, str]] = []
        for index, counter in counts.items():
            if not counter:
                continue
            language, count = counter.most_common(1)[0]
            candidates.append((-count, index, language))
        result: dict[str, int] = {}
        for _, index, language in sorted(candidates):
            result.setdefault(language, index)
        return result

    @staticmethod
    def _header_language(text: str) -> str | None:
        normalized = normalise_heading(text)
        for language, aliases in _LANGUAGE_HEADER_ALIASES.items():
            if normalized in aliases:
                return language
        return None

    @staticmethod
    def _is_meaningful(
        cell: object,
        *,
        ignore_formula_only: bool,
        ignore_numeric_only: bool,
    ) -> bool:
        text = string_value(first(cell, "text", "normalised_text", default=""))
        if not text.strip():
            return False
        metadata = mapping(
            first(cell, "metadata", "metadata_json", default={}),
        )
        block_type = enum_value(read(cell, "block_type", "")).upper()
        if ignore_formula_only and (
            block_type == "FORMULA"
            or bool_value(first(metadata, "isFormula", "is_formula", default=False))
        ):
            return False
        return not (ignore_numeric_only and _NUMERIC_RE.fullmatch(text))

    @staticmethod
    def _row(cell: object) -> int:
        metadata = mapping(
            first(cell, "metadata", "metadata_json", default={}),
        )
        return int_value(
            first(
                cell,
                "row_index",
                default=first(metadata, "row", default=0),
            ),
        )

    @staticmethod
    def _column(cell: object) -> int:
        metadata = mapping(
            first(cell, "metadata", "metadata_json", default={}),
        )
        return int_value(
            first(
                cell,
                "column_index",
                default=first(metadata, "column", default=0),
            ),
        )

    @staticmethod
    def _container_id(table: object) -> object | None:
        return read(table, "container_id", None)

    @staticmethod
    def _table_reference(table: object) -> str:
        return string_value(
            read(table, "source_reference", "TABLE"),
            "TABLE",
        )

    @staticmethod
    def _group_type(table: object) -> str:
        container_type = enum_value(
            read(table, "container_type", ""),
        ).upper()
        reference = TableGroupingService._table_reference(table).upper()
        if "XLSX" in reference or container_type == "XLSX_WORKSHEET":
            return GROUP_TYPE_XLSX_ROW
        return GROUP_TYPE_TABLE_ROW
