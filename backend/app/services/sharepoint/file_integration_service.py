"""Department-scoped document-file SharePoint actions and remote streaming."""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from typing import Any
from urllib.parse import quote, urlparse, urlunparse
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.document_file import DocumentFile, DocumentFileStatus
from app.models.sharepoint_enums import SyncDirection, SyncJobType
from app.models.user import User
from app.repositories.document_file_repository import DocumentFileRepository
from app.repositories.sharepoint_file_version_repository import (
    SharePointFileVersionRepository,
)
from app.repositories.sharepoint_sync_repository import (
    SharePointSyncRepository,
)
from app.schemas.sharepoint_sync import (
    SharePointFileStatusResponse,
    SharePointFileVersionListResponse,
    SharePointFileVersionResponse,
    SharePointSyncJobCreateRequest,
    SharePointSyncJobResponse,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.sharepoint._common import (
    SharePointServiceBase,
    sharepoint_error,
    total_pages,
)
from app.services.sharepoint.graph_factory import create_graph_client
from app.services.sharepoint.sync_job_service import (
    SharePointSyncJobService,
)


@dataclass(frozen=True, slots=True)
class SharePointRemoteDownload:
    filename: str
    media_type: str
    content_length: int | None
    content_disposition: str
    body: Any


class SharePointFileIntegrationService(SharePointServiceBase):
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.settings = settings
        self.files = DocumentFileRepository(session)
        self.versions = SharePointFileVersionRepository(session)
        self.sync = SharePointSyncRepository(session)

    async def push(self, file_id: UUID) -> SharePointSyncJobResponse:
        return await self._queue_file_job(
            file_id,
            direction=SyncDirection.OUTBOUND,
            job_type=SyncJobType.SINGLE_FILE_PUSH,
        )

    async def pull(self, file_id: UUID) -> SharePointSyncJobResponse:
        document_file = await self._file(file_id)
        if not getattr(document_file, "remote_item_id", None):
            raise sharepoint_error(
                "This document file is not linked to a SharePoint item.",
                code="SHAREPOINT_FILE_NOT_FOUND",
                status_code=HTTPStatus.NOT_FOUND,
            )
        return await self._queue_file_job(
            file_id,
            direction=SyncDirection.INBOUND,
            job_type=SyncJobType.SINGLE_FILE_PULL,
        )

    async def reconcile(self, file_id: UUID) -> SharePointSyncJobResponse:
        return await self._queue_file_job(
            file_id,
            direction=SyncDirection.BIDIRECTIONAL,
            job_type=SyncJobType.RECONCILIATION,
        )

    async def status(
        self,
        file_id: UUID,
    ) -> SharePointFileStatusResponse:
        document_file = await self._file(file_id)
        return SharePointFileStatusResponse(
            document_file_id=document_file.id,
            storage_provider=document_file.storage_provider,
            remote_sync_status=getattr(
                document_file,
                "remote_sync_status",
                None,
            ),
            sharepoint_connection_id=getattr(
                document_file,
                "sharepoint_connection_id",
                None,
            ),
            remote_drive_id=getattr(document_file, "remote_drive_id", None),
            remote_item_id=getattr(document_file, "remote_item_id", None),
            remote_path=getattr(document_file, "remote_path", None),
            remote_web_url=self._safe_remote_web_url(
                getattr(document_file, "remote_web_url", None)
            ),
            remote_etag=getattr(document_file, "remote_etag", None),
            remote_version_id=getattr(
                document_file,
                "remote_version_id",
                None,
            ),
            remote_last_modified_at=getattr(
                document_file,
                "remote_last_modified_at",
                None,
            ),
            remote_size=getattr(document_file, "remote_size", None),
            last_synced_at=getattr(document_file, "last_synced_at", None),
            sync_error_code=getattr(
                document_file,
                "sync_error_code",
                None,
            ),
            sync_error_message=getattr(
                document_file,
                "sync_error_message",
                None,
            ),
        )

    async def list_versions(
        self,
        file_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> SharePointFileVersionListResponse:
        await self._file(file_id)
        items, total = await self.versions.list_page(
            file_id,
            page=page,
            page_size=page_size,
        )
        return SharePointFileVersionListResponse(
            items=[
                SharePointFileVersionResponse.model_validate(item)
                for item in items
            ],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=total_pages(total, page_size),
        )

    async def prepare_download(
        self,
        file_id: UUID,
    ) -> SharePointRemoteDownload:
        document_file = await self._file(file_id)
        drive_id = getattr(document_file, "remote_drive_id", None)
        item_id = getattr(document_file, "remote_item_id", None)
        if not drive_id or not item_id:
            raise sharepoint_error(
                "This document file is not linked to SharePoint.",
                code="SHAREPOINT_FILE_NOT_FOUND",
                status_code=HTTPStatus.NOT_FOUND,
            )
        graph = create_graph_client(self.settings)

        async def body():
            from app.integrations.microsoft_graph.sharepoint.sharepoint_download_service import (
                SharePointDownloadService,
            )

            try:
                async for chunk in SharePointDownloadService(graph).stream(
                    drive_id=drive_id,
                    item_id=item_id,
                ):
                    yield chunk
            finally:
                await graph.close()

        ascii_filename = document_file.sanitized_filename
        encoded = quote(document_file.original_filename, safe="")
        disposition = (
            f'attachment; filename="{ascii_filename}"; '
            f"filename*=UTF-8''{encoded}"
        )
        return SharePointRemoteDownload(
            filename=document_file.original_filename,
            media_type=(
                getattr(document_file, "remote_mime_type", None)
                or document_file.mime_type
            ),
            content_length=getattr(document_file, "remote_size", None),
            content_disposition=disposition,
            body=body(),
        )

    async def _queue_file_job(
        self,
        file_id: UUID,
        *,
        direction: SyncDirection,
        job_type: SyncJobType,
    ) -> SharePointSyncJobResponse:
        document_file = await self._file(file_id)
        if document_file.file_status is not DocumentFileStatus.AVAILABLE:
            raise sharepoint_error(
                "Only available, non-quarantined files can be synchronized.",
                code="FILE_QUARANTINED",
                status_code=HTTPStatus.CONFLICT,
            )
        document = document_file.document
        profile = await self.sync.resolve_profile(
            department_id=document.department_id,
            section_id=document.section_id,
            document_type_id=document.document_type_id,
            required_direction=(
                None
                if direction is SyncDirection.BIDIRECTIONAL
                else direction
            ),
        )
        if profile is None:
            raise sharepoint_error(
                "No active SharePoint sync profile matches this document.",
                code="SHAREPOINT_SYNC_FAILED",
            )
        service = SharePointSyncJobService(
            self.session,
            self.settings,
            self.user,
            self.metadata,
        )
        return await service.queue_job(
            SharePointSyncJobCreateRequest(
                sync_profile_id=profile.id,
                job_type=job_type,
                direction=direction,
                scope={"documentFileId": str(document_file.id)},
            )
        )

    async def _file(self, file_id: UUID) -> DocumentFile:
        document_file = await self.files.get_by_id(file_id)
        if document_file is None:
            raise sharepoint_error(
                "Document file was not found.",
                code="SHAREPOINT_FILE_NOT_FOUND",
                status_code=HTTPStatus.NOT_FOUND,
            )
        self.policy.ensure_department(document_file.document.department_id)
        return document_file

    @staticmethod
    def _safe_remote_web_url(value: str | None) -> str | None:
        if not value:
            return None
        parsed = urlparse(value.strip())
        hostname = (parsed.hostname or "").lower()
        if (
            parsed.scheme.lower() != "https"
            or not hostname.endswith(".sharepoint.com")
            or parsed.username is not None
            or parsed.password is not None
        ):
            return None
        return urlunparse(
            (
                "https",
                parsed.netloc,
                parsed.path,
                "",
                "",
                "",
            )
        )
