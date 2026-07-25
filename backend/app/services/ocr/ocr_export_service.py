"""Safe temporary JSON/TXT exports for OCR results."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.core.config import Settings
from app.models.user import User
from app.repositories.ocr_block_repository import OCRBlockRepository
from app.repositories.ocr_page_result_repository import (
    OCRPageResultRepository,
)
from app.repositories.ocr_run_repository import OCRRunRepository
from app.services.auth.auth_service import RequestMetadata
from app.services.documents.base import document_error
from app.services.ocr.ocr_result_service import (
    OCRResultService,
    ocr_block_response,
    ocr_page_response,
)


@dataclass(frozen=True, slots=True)
class OCRExportArtifact:
    path: str
    filename: str
    media_type: str


class OCRExportService:
    """Export authorized OCR content without exposing storage paths."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        self.session = session
        self.settings = settings
        self.user = user
        self.metadata = metadata
        self.runs = OCRRunRepository(session)
        self.pages = OCRPageResultRepository(session)
        self.blocks = OCRBlockRepository(session)
        self.results = OCRResultService(
            session,
            settings,
            user,
            metadata,
        )

    async def export(
        self,
        run_id: UUID,
        *,
        export_format: str,
    ) -> OCRExportArtifact:
        normalized_format = export_format.strip().lower()
        if normalized_format not in {"json", "txt"}:
            raise document_error(
                "OCR export format must be json or txt.",
                field="format",
                title="Unsupported OCR export format.",
            )
        run_response = await self.results.get_run(run_id)
        run = await self.runs.get_by_id(run_id)
        assert run is not None
        page_rows, _ = await self.pages.list_by_run(
            run.id,
            offset=0,
            limit=max(1, run.page_count_requested),
        )
        maximum_blocks = int(
            getattr(
                self.settings,
                "ocr_export_max_blocks",
                getattr(
                    self.settings,
                    "extraction_export_max_blocks",
                    2_000_000,
                ),
            )
        )
        if run.total_blocks > maximum_blocks:
            raise document_error(
                "The OCR result exceeds the configured export block limit.",
                title="OCR export is too large.",
            )

        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix="ocr-export-",
            suffix=f".{normalized_format}",
        )
        os.close(file_descriptor)
        path = Path(temporary_name)
        try:
            if normalized_format == "json":
                await self._write_json(
                    path,
                    run_response.model_dump(
                        mode="json",
                        by_alias=True,
                    ),
                    page_rows,
                )
                media_type = "application/json"
            else:
                self._write_text(
                    path,
                    page_rows,
                )
                media_type = "text/plain; charset=utf-8"
            await self.results.audit(
                action=AuditAction.EXPORT_OCR_RESULT,
                entity_type="OCRRun",
                entity_id=run.id,
                description="OCR result exported.",
                new_values={
                    "documentFileId": str(run.document_file_id),
                    "format": normalized_format,
                },
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            remove_ocr_export_artifact(path)
            raise
        return OCRExportArtifact(
            path=str(path),
            filename=f"ocr-{run.id}.{normalized_format}",
            media_type=media_type,
        )

    async def _write_json(
        self,
        path: Path,
        run_payload: dict[str, object],
        pages: list[object],
    ) -> None:
        with path.open("w", encoding="utf-8", newline="\n") as output:
            output.write('{"run":')
            _write_json_value(output, run_payload)
            output.write(',"pages":[')
            first = True
            for page in pages:
                from app.models.ocr_page_result import OCRPageResult

                if not isinstance(page, OCRPageResult):
                    raise TypeError("Expected an OCRPageResult model.")
                if not first:
                    output.write(",")
                output.write('{"page":')
                _write_json_value(
                    output,
                    ocr_page_response(page).model_dump(
                        mode="json",
                        by_alias=True,
                    ),
                )
                output.write(',"blocks":[')
                first_block = True
                offset = 0
                while True:
                    rows, total = await self.blocks.list_by_run(
                        page.ocr_run_id,
                        page_number=page.page_number,
                        offset=offset,
                        limit=500,
                    )
                    for block, block_page in rows:
                        if not first_block:
                            output.write(",")
                        _write_json_value(
                            output,
                            ocr_block_response(
                                block,
                                block_page,
                            ).model_dump(mode="json", by_alias=True),
                        )
                        first_block = False
                    offset += len(rows)
                    if offset >= total or not rows:
                        break
                output.write("]}")
                first = False
            output.write("]}\n")

    @staticmethod
    def _write_text(
        path: Path,
        pages: list[object],
    ) -> None:
        from app.models.ocr_page_result import OCRPageResult

        with path.open("w", encoding="utf-8", newline="\n") as output:
            for index, page in enumerate(pages):
                if not isinstance(page, OCRPageResult):
                    raise TypeError("Expected an OCRPageResult model.")
                if index:
                    output.write("\n")
                output.write(f"[OCR PAGE {page.page_number}]\n")
                output.write(page.raw_text)
                output.write("\n")


def _write_json_value(output: object, payload: object) -> None:
    json.dump(
        payload,
        output,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def remove_ocr_export_artifact(path: Path) -> None:
    """Delete only the exact temporary export path passed by the endpoint."""
    try:
        if path.is_file() or path.is_symlink():
            path.unlink(missing_ok=True)
    except OSError:
        return
