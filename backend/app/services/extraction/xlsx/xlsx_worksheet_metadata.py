"""Stream worksheet-only metadata omitted by openpyxl read-only mode.

The caller performs the OOXML DTD/entity preflight before invoking this
module.  Relationship targets are retained as strings and are never opened.
"""

import posixpath
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from xml.etree.ElementTree import iterparse
from zipfile import BadZipFile, ZipFile

from app.services.extraction.base_extractor import ExtractionError


@dataclass(frozen=True, slots=True)
class XLSXWorksheetPackageMetadata:
    """Bounded worksheet presentation and relationship metadata."""

    reported_dimension: str | None = None
    freeze_pane: str | None = None
    sheet_protected: bool = False
    hidden_rows: frozenset[int] = frozenset()
    hidden_column_ranges: tuple[tuple[int, int], ...] = ()
    table_names: tuple[str, ...] = ()
    hyperlinks: dict[str, str | None] = field(default_factory=dict)

    def is_column_hidden(self, column_number: int) -> bool:
        return any(
            minimum <= column_number <= maximum
            for minimum, maximum in self.hidden_column_ranges
        )


def read_worksheet_package_metadata(
    file_path: Path,
    worksheet_paths: dict[str, str],
) -> dict[str, XLSXWorksheetPackageMetadata]:
    """Read dimensions, hidden state, freeze panes, tables, and hyperlinks."""
    results: dict[str, XLSXWorksheetPackageMetadata] = {}
    try:
        with ZipFile(file_path) as archive:
            archive_names = set(archive.namelist())
            for sheet_name, raw_sheet_path in worksheet_paths.items():
                sheet_path = raw_sheet_path.lstrip("/")
                if sheet_path not in archive_names:
                    results[sheet_name] = XLSXWorksheetPackageMetadata()
                    continue
                relationships = _read_relationships(
                    archive,
                    archive_names,
                    sheet_path,
                )
                results[sheet_name] = _read_sheet(
                    archive,
                    archive_names,
                    sheet_path,
                    relationships,
                )
    except ExtractionError:
        raise
    except (BadZipFile, KeyError, OSError, RuntimeError, ValueError) as exc:
        raise ExtractionError(
            "XLSX_CORRUPT",
            "The XLSX worksheet metadata could not be read safely.",
        ) from exc
    return results


def _read_sheet(
    archive: ZipFile,
    archive_names: set[str],
    sheet_path: str,
    relationships: dict[str, tuple[str, str, str]],
) -> XLSXWorksheetPackageMetadata:
    reported_dimension = None
    freeze_pane = None
    sheet_protected = False
    hidden_rows: set[int] = set()
    hidden_columns: list[tuple[int, int]] = []
    table_relationship_ids: list[str] = []
    hyperlink_relationship_ids: dict[str, str] = {}
    hyperlink_locations: dict[str, str | None] = {}

    with archive.open(sheet_path) as source:
        for event, element in iterparse(source, events=("start", "end")):
            if event == "end":
                element.clear()
                continue
            local_name = _local_name(element.tag)
            attributes = {
                _local_name(key): value for key, value in element.attrib.items()
            }
            if local_name == "dimension":
                reported_dimension = attributes.get("ref")
            elif local_name == "pane":
                freeze_pane = attributes.get("topLeftCell")
            elif local_name == "sheetProtection":
                sheet_protected = attributes.get("sheet", "1") not in {
                    "0",
                    "false",
                    "False",
                }
            elif local_name == "row" and attributes.get("hidden") in {
                "1",
                "true",
                "True",
            }:
                row_number = _safe_positive_int(attributes.get("r"))
                if row_number is not None:
                    hidden_rows.add(row_number)
            elif local_name == "col" and attributes.get("hidden") in {
                "1",
                "true",
                "True",
            }:
                minimum = _safe_positive_int(attributes.get("min"))
                maximum = _safe_positive_int(attributes.get("max"))
                if minimum is not None and maximum is not None:
                    hidden_columns.append((minimum, maximum))
            elif local_name == "tablePart":
                relationship_id = attributes.get("id")
                if relationship_id:
                    table_relationship_ids.append(relationship_id)
            elif local_name == "hyperlink":
                reference = attributes.get("ref")
                if not reference:
                    continue
                relationship_id = attributes.get("id")
                if relationship_id:
                    hyperlink_relationship_ids[reference] = relationship_id
                else:
                    hyperlink_locations[reference] = attributes.get("location")

    table_names = _table_names(
        archive,
        archive_names,
        relationships,
        table_relationship_ids,
        sheet_path,
    )
    hyperlinks = dict(hyperlink_locations)
    for reference, relationship_id in hyperlink_relationship_ids.items():
        relationship = relationships.get(relationship_id)
        hyperlinks[reference] = relationship[0] if relationship else None
    return XLSXWorksheetPackageMetadata(
        reported_dimension=reported_dimension,
        freeze_pane=freeze_pane,
        sheet_protected=sheet_protected,
        hidden_rows=frozenset(hidden_rows),
        hidden_column_ranges=tuple(hidden_columns),
        table_names=tuple(table_names),
        hyperlinks=hyperlinks,
    )


def _read_relationships(
    archive: ZipFile,
    archive_names: set[str],
    sheet_path: str,
) -> dict[str, tuple[str, str, str]]:
    path = PurePosixPath(sheet_path)
    relationships_path = (
        path.parent / "_rels" / f"{path.name}.rels"
    ).as_posix()
    if relationships_path not in archive_names:
        return {}
    relationships: dict[str, tuple[str, str, str]] = {}
    with archive.open(relationships_path) as source:
        for event, element in iterparse(source, events=("start", "end")):
            if event == "end":
                element.clear()
                continue
            if _local_name(element.tag) != "Relationship":
                continue
            attributes = {
                _local_name(key): value for key, value in element.attrib.items()
            }
            relationship_id = attributes.get("Id")
            target = attributes.get("Target")
            if relationship_id and target:
                relationships[relationship_id] = (
                    target,
                    attributes.get("TargetMode", "Internal"),
                    attributes.get("Type", ""),
                )
    return relationships


def _table_names(
    archive: ZipFile,
    archive_names: set[str],
    relationships: dict[str, tuple[str, str, str]],
    relationship_ids: list[str],
    sheet_path: str,
) -> list[str]:
    names: list[str] = []
    for relationship_id in relationship_ids:
        relationship = relationships.get(relationship_id)
        if relationship is None:
            continue
        target, target_mode, relationship_type = relationship
        if (
            target_mode.lower() == "external"
            or not relationship_type.endswith("/table")
        ):
            continue
        table_path = _resolve_internal_target(sheet_path, target)
        if table_path is None or table_path not in archive_names:
            continue
        with archive.open(table_path) as source:
            for event, element in iterparse(source, events=("start",)):
                del event
                if _local_name(element.tag) != "table":
                    continue
                table_name = (
                    element.attrib.get("displayName")
                    or element.attrib.get("name")
                )
                if table_name:
                    names.append(str(table_name))
                break
    return list(dict.fromkeys(names))


def _resolve_internal_target(source_path: str, target: str) -> str | None:
    if "\x00" in target or "\\" in target:
        return None
    if target.startswith("/"):
        normalized = posixpath.normpath(target.lstrip("/"))
    else:
        normalized = posixpath.normpath(
            posixpath.join(posixpath.dirname(source_path), target)
        )
    if normalized.startswith("../") or normalized == "..":
        return None
    return normalized


def _local_name(value: str) -> str:
    return value.rsplit("}", 1)[-1]


def _safe_positive_int(value: str | None) -> int | None:
    try:
        converted = int(value) if value is not None else 0
    except ValueError:
        return None
    return converted if converted > 0 else None
