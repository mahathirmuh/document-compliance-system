"""Bounded JSON/TXT export for durable extracted content."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.core.config import Settings
from app.models.extracted_container import ExtractedContainerType
from app.models.extraction_run import ExtractionRun
from app.models.user import User
from app.services.auth.auth_service import RequestMetadata
from app.services.documents.base import document_error
from app.services.extraction.extraction_content_service import (
    ExtractionContentService,
    block_response,
    cell_response,
    container_export_response,
    extraction_run_response,
    table_export_response,
)


@dataclass(frozen=True, slots=True)
class ExtractionExportArtifact:
    """One private temporary export ready for a streaming response."""

    path: Path
    filename: str
    media_type: str


class ExtractionExportService(ExtractionContentService):
    """Build bounded exports without loading an entire result into memory."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, settings, user, metadata)

    async def export(
        self,
        run_id: UUID,
        *,
        export_format: str,
    ) -> ExtractionExportArtifact:
        run = await self._run(run_id)
        normalized_format = export_format.strip().lower()
        if normalized_format not in {"json", "txt"}:
            raise document_error(
                "Export format must be either json or txt.",
                field="format",
                title="Extraction export format is invalid.",
            )

        total_blocks = await self.blocks.count(run.id)
        if total_blocks > self.settings.extraction_export_max_blocks:
            raise document_error(
                "The extraction result exceeds the configured export limit.",
                status_code=413,
                title="Extraction result is too large to export.",
            )

        descriptor, raw_path = tempfile.mkstemp(
            prefix="document-extraction-",
            suffix=f".{normalized_format}",
        )
        os.close(descriptor)
        path = Path(raw_path)
        try:
            if normalized_format == "json":
                await self._write_json(path, run)
                media_type = "application/json"
            else:
                await self._write_text(path, run)
                media_type = "text/plain; charset=utf-8"

            await self.audit(
                action=AuditAction.EXPORT_EXTRACTED_CONTENT,
                entity_type="ExtractionRun",
                entity_id=run.id,
                description="Extracted document content exported.",
                new_values={
                    "format": normalized_format,
                    "documentFileId": str(run.document_file_id),
                },
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            remove_export_artifact(path)
            raise

        return ExtractionExportArtifact(
            path=path,
            filename=(
                f"{_safe_filename(run.revision.full_document_code)}"
                f"_extraction.{normalized_format}"
            ),
            media_type=media_type,
        )

    async def _write_json(
        self,
        path: Path,
        run: ExtractionRun,
    ) -> None:
        with path.open("w", encoding="utf-8", newline="\n") as output:
            output.write('{"run":')
            _write_json_value(
                output,
                extraction_run_response(run).model_dump(
                    by_alias=True,
                    mode="json",
                ),
            )
            output.write(',"containers":[')
            await self._write_containers_json(output, run)
            output.write('],"blocks":[')
            await self._write_blocks_json(output, run)
            output.write('],"tables":[')
            await self._write_tables_json(output, run)
            output.write("]}")

    async def _write_containers_json(
        self,
        output: object,
        run: ExtractionRun,
    ) -> None:
        first = True
        page = 1
        while True:
            items, total = await self.containers.list(
                run.id,
                page=page,
                page_size=500,
            )
            for item in items:
                if not first:
                    output.write(",")  # type: ignore[attr-defined]
                _write_json_value(
                    output,
                    container_export_response(item).model_dump(
                        by_alias=True,
                        mode="json",
                    ),
                )
                first = False
            if page * 500 >= total:
                break
            page += 1

    async def _write_blocks_json(
        self,
        output: object,
        run: ExtractionRun,
    ) -> None:
        first = True
        page = 1
        while True:
            items, total = await self.blocks.list(
                run.id,
                page=page,
                page_size=500,
            )
            for item in items:
                if not first:
                    output.write(",")  # type: ignore[attr-defined]
                _write_json_value(
                    output,
                    block_response(item).model_dump(
                        by_alias=True,
                        mode="json",
                    ),
                )
                first = False
            if page * 500 >= total:
                break
            page += 1

    async def _write_tables_json(
        self,
        output: object,
        run: ExtractionRun,
    ) -> None:
        first_table = True
        page = 1
        while True:
            tables, total = await self.tables.list(
                run.id,
                include_cells=False,
                page=page,
                page_size=100,
            )
            for table in tables:
                if not first_table:
                    output.write(",")  # type: ignore[attr-defined]
                payload = table_export_response(
                    table,
                    include_cells=False,
                ).model_dump(by_alias=True, mode="json")
                payload.pop("cells", None)
                prefix = json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                output.write(prefix[:-1])  # type: ignore[attr-defined]
                output.write(',"cells":[')  # type: ignore[attr-defined]
                first_cell = True
                cell_page = 1
                while True:
                    cells, cell_total = await self.tables.list_cells(
                        table.id,
                        page=cell_page,
                        page_size=500,
                    )
                    for cell in cells:
                        if not first_cell:
                            output.write(",")  # type: ignore[attr-defined]
                        _write_json_value(
                            output,
                            cell_response(cell).model_dump(
                                by_alias=True,
                                mode="json",
                            ),
                        )
                        first_cell = False
                    if cell_page * 500 >= cell_total:
                        break
                    cell_page += 1
                output.write("]}")  # type: ignore[attr-defined]
                first_table = False
            if page * 100 >= total:
                break
            page += 1

    async def _write_text(
        self,
        path: Path,
        run: ExtractionRun,
    ) -> None:
        with path.open("w", encoding="utf-8", newline="\n") as output:
            page = 1
            while True:
                containers, total = await self.containers.list(
                    run.id,
                    page=page,
                    page_size=100,
                )
                for container in containers:
                    output.write(_container_heading(container.container_type, container))
                    output.write("\n")
                    block_page = 1
                    while True:
                        blocks, block_total = await self.blocks.list(
                            run.id,
                            container_id=container.id,
                            page=block_page,
                            page_size=500,
                        )
                        for block in blocks:
                            if (
                                container.container_type
                                is ExtractedContainerType.XLSX_WORKSHEET
                            ):
                                output.write(f"{block.source_reference}: ")
                            output.write(block.text)
                            output.write("\n")
                        if block_page * 500 >= block_total:
                            break
                        block_page += 1
                    output.write("\n")
                if page * 100 >= total:
                    break
                page += 1


def _container_heading(
    container_type: ExtractedContainerType,
    container: object,
) -> str:
    index = getattr(container, "container_index", 0)
    name = getattr(container, "name", None)
    if container_type is ExtractedContainerType.PDF_PAGE:
        return f"[PAGE {index}]"
    if container_type is ExtractedContainerType.XLSX_WORKSHEET:
        return f"[WORKSHEET: {name or index}]"
    if container_type is ExtractedContainerType.DOCX_BODY:
        return "[DOCX BODY]"
    if container_type is ExtractedContainerType.DOCX_HEADER:
        return f"[HEADER: {name or index}]"
    return f"[FOOTER: {name or index}]"


def _write_json_value(output: object, value: object) -> None:
    json.dump(
        value,
        output,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _safe_filename(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return normalized[:180] or "document"


def remove_export_artifact(path: Path) -> None:
    """Delete only the exact worker-created export artifact."""
    try:
        if path.is_file() or path.is_symlink():
            path.unlink(missing_ok=True)
    except OSError:
        return
