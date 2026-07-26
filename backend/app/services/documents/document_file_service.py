"""Secure physical-file metadata, download, replacement, and retention."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from http import HTTPStatus
from typing import cast
from urllib.parse import quote
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError

from app.core.authorization import AuditAction, Permission, has_permission
from app.core.config import Settings
from app.models.document_file import DocumentFile, DocumentFileStatus
from app.models.upload_session import UploadSessionType
from app.models.upload_session_item import UploadProposedAction
from app.repositories.document_file_repository import DocumentFileRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_revision_repository import (
    DocumentRevisionRepository,
)
from app.schemas.document_file import (
    DocumentFileDeleteRequest,
    DocumentFileDetailResponse,
    DocumentFileListItem,
    DocumentFileListResponse,
    DocumentFileRestoreRequest,
)
from app.schemas.document_revision import UserReference
from app.schemas.document_upload import (
    UploadActionMetadata,
    UploadConfirmationItem,
    UploadConfirmationRequest,
)
from app.services.documents.base import (
    DocumentServiceBase,
    document_conflict,
    document_error,
    document_not_found,
    revision_not_found,
)
from app.services.documents.date_filter import created_at_utc_bounds
from app.services.storage.base_storage import BaseStorage
from app.services.storage.file_stream_service import stream_storage
from app.services.storage.storage_factory import StorageFactory
from app.services.storage.storage_path_service import StoragePathService
from app.utils.datetime import utc_now


@dataclass(frozen=True, slots=True)
class FileDownload:
    filename: str
    media_type: str
    content_length: int
    content_disposition: str
    body: object


class DocumentFileService(DocumentServiceBase):
    """Apply department policy while keeping provider paths private."""

    def __init__(
        self,
        session,
        settings: Settings,
        user,
        metadata,
        *,
        storage: BaseStorage | None = None,
    ) -> None:
        super().__init__(session, user, metadata)
        self.settings = settings
        self.storage = storage or StorageFactory.get_storage(settings)
        self.paths = StoragePathService(settings)
        self.files = DocumentFileRepository(session)
        self.documents = DocumentRepository(session)
        self.revisions = DocumentRevisionRepository(session)

    async def get(self, file_id: UUID) -> DocumentFileDetailResponse:
        document_file = await self._file(file_id)
        self._ensure_history_access(document_file)
        return self._detail(document_file)

    async def list_document(
        self,
        document_id: UUID,
    ) -> list[DocumentFileListItem]:
        document = await self.documents.get_by_id(document_id)
        if document is None:
            raise document_not_found()
        self.policy.ensure_document_access(document)
        include_history = self._can_view_history
        files = await self.files.list_by_document(
            document_id,
            include_deleted=include_history,
        )
        if not include_history:
            files = [
                item
                for item in files
                if item.file_status == DocumentFileStatus.AVAILABLE
                and item.is_current
            ]
        return [self._item(item) for item in files]

    async def list_revision(
        self,
        document_id: UUID,
        revision_id: UUID,
    ) -> list[DocumentFileListItem]:
        document = await self.documents.get_by_id(document_id)
        if document is None:
            raise document_not_found()
        self.policy.ensure_document_access(document)
        revision = await self.revisions.get_by_id(
            revision_id,
            document_id=document.id,
        )
        if revision is None:
            raise revision_not_found()
        include_history = self._can_view_history
        files = await self.files.list_by_revision(
            revision.id,
            include_deleted=include_history,
        )
        if not include_history:
            files = [
                item
                for item in files
                if item.file_status == DocumentFileStatus.AVAILABLE
                and item.is_current
            ]
        return [self._item(item) for item in files]

    async def history(
        self,
        *,
        document_id: UUID | None,
        revision_id: UUID | None,
        department_id: UUID | None,
        uploaded_by: UUID | None,
        file_status: DocumentFileStatus | None,
        file_extension: str | None,
        uploaded_from: date | None,
        uploaded_to: date | None,
        search: str | None,
        page: int,
        page_size: int,
    ) -> DocumentFileListResponse:
        if not self._can_view_history:
            raise document_error(
                "File history permission is required.",
                status_code=HTTPStatus.FORBIDDEN,
                title="Authorization failed.",
            )
        if (
            department_id is not None
            and not self.policy.view_all_departments
            and department_id != self.policy.scope_department_id
        ):
            raise document_error(
                "This department is outside your data scope.",
                status_code=HTTPStatus.FORBIDDEN,
                title="Authorization failed.",
            )
        uploaded_start, uploaded_end = created_at_utc_bounds(
            uploaded_from,
            uploaded_to,
            self.settings.application_timezone,
        )
        items, total = await self.files.list_history(
            document_id=document_id,
            revision_id=revision_id,
            department_id=department_id,
            uploaded_by=uploaded_by,
            file_status=file_status,
            file_extension=file_extension,
            uploaded_from=uploaded_start,
            uploaded_to=uploaded_end,
            search=search,
            scope_all_departments=self.policy.view_all_departments,
            scope_department_id=self.policy.scope_department_id,
            page=page,
            page_size=page_size,
        )
        return DocumentFileListResponse(
            items=[self._item(item) for item in items],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=(total + page_size - 1) // page_size if total else 0,
        )

    async def prepare_download(self, file_id: UUID) -> FileDownload:
        document_file = await self._file(file_id)
        if document_file.file_status == DocumentFileStatus.DELETED:
            raise document_error(
                "Deleted files cannot be downloaded.",
                status_code=HTTPStatus.CONFLICT,
                title="File could not be downloaded.",
            )
        if document_file.file_status not in {
            DocumentFileStatus.AVAILABLE,
            DocumentFileStatus.REPLACED,
        }:
            raise document_error(
                "File is not available for download.",
                status_code=HTTPStatus.CONFLICT,
                title="File could not be downloaded.",
            )
        if (
            document_file.file_status == DocumentFileStatus.REPLACED
            and not self._can_view_history
        ):
            raise document_error(
                "File history permission is required.",
                status_code=HTTPStatus.FORBIDDEN,
                title="Authorization failed.",
            )
        if not await self.storage.exists(document_file.storage_key):
            raise document_error(
                "Stored file content was not found.",
                status_code=HTTPStatus.NOT_FOUND,
                title="File could not be downloaded.",
            )
        await self.audit(
            action=AuditAction.DOWNLOAD_DOCUMENT_FILE,
            entity_type="document_file",
            entity_id=document_file.id,
            description=(
                f"Downloaded {document_file.sanitized_filename}."
            ),
            new_values=self._audit_values(document_file),
        )
        await self.session.commit()
        chunk_size = self.settings.file_download_chunk_size_kb * 1024
        safe_name = document_file.sanitized_filename
        encoded_name = quote(safe_name, safe="")
        return FileDownload(
            filename=safe_name,
            media_type=document_file.detected_mime_type,
            content_length=document_file.file_size,
            content_disposition=(
                f'attachment; filename="{safe_name}"; '
                f"filename*=UTF-8''{encoded_name}"
            ),
            body=stream_storage(
                self.storage,
                document_file.storage_key,
                chunk_size=chunk_size,
            ),
        )

    async def prepare_current_revision_download(
        self,
        document_id: UUID,
        revision_id: UUID,
    ) -> FileDownload:
        document = await self.documents.get_by_id(document_id)
        if document is None:
            raise document_not_found()
        self.policy.ensure_document_access(document)
        revision = await self.revisions.get_by_id(
            revision_id,
            document_id=document.id,
        )
        if revision is None:
            raise revision_not_found()
        current = await self.files.get_current_by_revision(revision.id)
        if current is None:
            raise document_error(
                "No current physical file is available for this revision.",
                status_code=HTTPStatus.NOT_FOUND,
                title="File was not found.",
            )
        return await self.prepare_download(current.id)

    async def replace(
        self,
        file_id: UUID,
        upload: UploadFile,
        reason: str,
    ) -> DocumentFileDetailResponse:
        current = await self._mutable_file(file_id)
        if not current.is_current or (
            current.file_status != DocumentFileStatus.AVAILABLE
        ):
            raise document_conflict(
                "Only the current available file can be replaced.",
                title="File could not be replaced.",
            )
        from app.services.documents.document_upload_service import (
            DocumentUploadService,
        )

        upload_service = DocumentUploadService(
            self.session,
            self.settings,
            self.user,
            self.metadata,
            storage=self.storage,
        )
        preview = await upload_service.preview_single(
            upload,
            document_id=current.document_id,
            revision_id=current.document_revision_id,
            session_type=UploadSessionType.REPLACE,
            replace_file_id=current.id,
        )
        item = preview.items[0]
        result = await upload_service.confirm(
            preview.session_id,
            UploadConfirmationRequest(
                items=[
                    UploadConfirmationItem(
                        upload_item_id=item.upload_item_id,
                        action=UploadProposedAction.REPLACE_CURRENT_FILE,
                        document_id=current.document_id,
                        revision_id=current.document_revision_id,
                        metadata=UploadActionMetadata(reason=reason),
                    )
                ]
            ),
            expected_session_types={UploadSessionType.REPLACE},
        )
        result_item = result.items[0]
        if result_item.document_file_id is None:
            raise document_error(
                result_item.error or "File replacement failed.",
                title="File could not be replaced.",
            )
        replacement = await self.files.get_by_id(
            result_item.document_file_id
        )
        assert replacement is not None
        return self._detail(replacement)

    async def delete(
        self,
        file_id: UUID,
        payload: DocumentFileDeleteRequest,
    ) -> DocumentFileDetailResponse:
        document_file = await self._mutable_file(file_id)
        if document_file.file_status == DocumentFileStatus.DELETED:
            raise document_conflict(
                "File is already deleted.",
                title="File could not be deleted.",
            )
        if document_file.file_status not in {
            DocumentFileStatus.AVAILABLE,
            DocumentFileStatus.REPLACED,
        }:
            raise document_conflict(
                "Only available or replaced files can be deleted.",
                title="File could not be deleted.",
            )
        old_key = document_file.storage_key
        old_audit_values = cast(
            dict[str, object],
            self._audit_values(document_file),
        )
        deleted_key = self.paths.deleted_key(
            document_file.document_id,
            document_file.document_revision_id,
            document_file.id,
            document_file.sanitized_filename,
        )
        await self.storage.move(old_key, deleted_key)
        now = utc_now()
        try:
            metadata = dict(document_file.metadata_json or {})
            metadata["preDeleteStorageKey"] = old_key
            document_file.metadata_json = metadata
            document_file.storage_key = deleted_key
            await self.files.soft_delete(
                document_file,
                deleted_at=now,
                deleted_by=self.user.id,
                reason=payload.reason,
            )
            await self.audit(
                action=AuditAction.DELETE_DOCUMENT_FILE,
                entity_type="document_file",
                entity_id=document_file.id,
                description=(
                    f"Soft-deleted {document_file.sanitized_filename}."
                ),
                old_values=old_audit_values,
                new_values={
                    **cast(
                        dict[str, object],
                        self._audit_values(document_file),
                    ),
                    "reason": payload.reason,
                },
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            if await self.storage.exists(deleted_key):
                await self.storage.move(deleted_key, old_key)
            raise
        result = await self.files.get_by_id(document_file.id)
        assert result is not None
        return self._detail(result)

    async def restore(
        self,
        file_id: UUID,
        payload: DocumentFileRestoreRequest,
    ) -> DocumentFileDetailResponse:
        document_file = await self._mutable_file(file_id)
        if document_file.file_status != DocumentFileStatus.DELETED:
            raise document_conflict(
                "Only deleted files can be restored.",
                title="File could not be restored.",
            )
        current = await self.files.get_current_by_revision(
            document_file.document_revision_id,
            for_update=True,
        )
        if current is not None and not payload.replace_current:
            raise document_conflict(
                "The revision already has a current file.",
                title="File could not be restored.",
            )
        deleted_key = document_file.storage_key
        previous_key = (document_file.metadata_json or {}).get(
            "preDeleteStorageKey"
        )
        original_key = (
            str(previous_key)
            if isinstance(previous_key, str) and previous_key
            else self.paths.original_key(
                document_file.document_id,
                document_file.document_revision_id,
                document_file.id,
                document_file.sanitized_filename,
            )
        )
        await self.storage.move(deleted_key, original_key)
        now = utc_now()
        try:
            old_current_values = (
                self._audit_values(current)
                if current is not None
                else None
            )
            if current is not None:
                await self.files.mark_replaced(
                    current,
                    replacement_id=document_file.id,
                    replaced_at=now,
                )
            document_file.storage_key = original_key
            metadata = dict(document_file.metadata_json or {})
            metadata.pop("preDeleteStorageKey", None)
            if payload.reason:
                metadata["restoreReason"] = payload.reason
            document_file.metadata_json = metadata or None
            await self.files.restore(document_file, is_current=True)
            await self.audit(
                action=AuditAction.RESTORE_DOCUMENT_FILE,
                entity_type="document_file",
                entity_id=document_file.id,
                description=(
                    f"Restored {document_file.sanitized_filename}."
                ),
                old_values={
                    "fileStatus": DocumentFileStatus.DELETED.value,
                    "replacedCurrent": old_current_values,
                },
                new_values={
                    **cast(
                        dict[str, object],
                        self._audit_values(document_file),
                    ),
                    "reason": payload.reason,
                },
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            if await self.storage.exists(original_key):
                await self.storage.move(original_key, deleted_key)
            raise document_conflict(
                "The revision already has a current file.",
                title="File could not be restored.",
            ) from exc
        except Exception:
            await self.session.rollback()
            if await self.storage.exists(original_key):
                await self.storage.move(original_key, deleted_key)
            raise
        result = await self.files.get_by_id(document_file.id)
        assert result is not None
        return self._detail(result)

    async def _file(
        self,
        file_id: UUID,
        *,
        for_update: bool = False,
    ) -> DocumentFile:
        document_file = await self.files.get_by_id(
            file_id,
            for_update=for_update,
        )
        if document_file is None:
            raise document_error(
                "Document file was not found.",
                status_code=HTTPStatus.NOT_FOUND,
                title="File was not found.",
            )
        self.policy.ensure_document_access(document_file.document)
        return document_file

    async def _mutable_file(self, file_id: UUID) -> DocumentFile:
        """Lock Document before File and revalidate archived state."""
        candidate = await self._file(file_id)
        document = await self.documents.get_by_id(
            candidate.document_id,
            for_update=True,
        )
        if document is None:
            raise document_not_found()
        self.policy.ensure_document_access(document)
        if document.is_archived:
            raise document_conflict(
                "Files on an archived document are read-only.",
                title="Document file could not be changed.",
            )
        document_file = await self._file(file_id, for_update=True)
        if document_file.document_id != document.id:
            raise document_conflict(
                "Document file ownership changed during the request.",
                title="Document file could not be changed.",
            )
        return document_file

    def _ensure_history_access(self, document_file: DocumentFile) -> None:
        if (
            document_file.file_status
            in {DocumentFileStatus.REPLACED, DocumentFileStatus.DELETED}
            and not self._can_view_history
        ):
            raise document_error(
                "File history permission is required.",
                status_code=HTTPStatus.FORBIDDEN,
                title="Authorization failed.",
            )

    @property
    def _can_view_history(self) -> bool:
        return has_permission(
            self.user.role,
            Permission.DOCUMENTS_VIEW_FILE_HISTORY,
            is_superuser=self.user.is_superuser,
        )

    @staticmethod
    def _user_reference(user) -> UserReference | None:
        if user is None:
            return None
        return UserReference(id=user.id, name=user.name)

    @classmethod
    def _item(cls, document_file: DocumentFile) -> DocumentFileListItem:
        return DocumentFileListItem(
            id=document_file.id,
            document_id=document_file.document_id,
            document_revision_id=document_file.document_revision_id,
            original_filename=document_file.original_filename,
            sanitized_filename=document_file.sanitized_filename,
            file_extension=document_file.file_extension,
            mime_type=document_file.mime_type,
            detected_mime_type=document_file.detected_mime_type,
            file_size=document_file.file_size,
            sha256_hash=document_file.sha256_hash,
            storage_provider=document_file.storage_provider,
            file_status=document_file.file_status,
            is_primary=document_file.is_primary,
            is_current=document_file.is_current,
            uploaded_by=cls._user_reference(document_file.uploader),
            uploaded_at=document_file.uploaded_at,
            replaced_at=document_file.replaced_at,
            replaced_by_file_id=document_file.replaced_by_file_id,
            deleted_at=document_file.deleted_at,
            deletion_reason=document_file.deletion_reason,
            base_document_code=(
                document_file.document.base_document_code
            ),
            document_title=document_file.document.title,
            revision_code=document_file.revision.revision_code,
            full_document_code=document_file.revision.full_document_code,
        )

    @classmethod
    def _detail(
        cls,
        document_file: DocumentFile,
    ) -> DocumentFileDetailResponse:
        item = cls._item(document_file)
        return DocumentFileDetailResponse(
            **item.model_dump(),
            deleted_by=cls._user_reference(document_file.deleter),
            metadata=cls._public_metadata(document_file.metadata_json),
            created_at=document_file.created_at,
            updated_at=document_file.updated_at,
        )

    @staticmethod
    def _public_metadata(
        metadata: dict[str, object] | None,
    ) -> dict[str, object] | None:
        """Expose an explicit business allowlist, never internal storage keys."""
        if not metadata:
            return None
        allowed = {
            key: metadata[key]
            for key in ("replacementReason", "restoreReason")
            if key in metadata
        }
        return allowed or None

    @staticmethod
    def _audit_values(
        document_file: DocumentFile | None,
    ) -> dict[str, object] | None:
        if document_file is None:
            return None
        return {
            "fileId": str(document_file.id),
            "documentId": str(document_file.document_id),
            "revisionId": str(document_file.document_revision_id),
            "filename": document_file.sanitized_filename,
            "fileSize": document_file.file_size,
            "sha256Hash": document_file.sha256_hash,
            "fileStatus": document_file.file_status.value,
            "isCurrent": document_file.is_current,
        }
