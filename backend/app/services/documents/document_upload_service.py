"""Two-stage physical-document upload and confirmation workflows."""

from __future__ import annotations

import logging
from datetime import timedelta
from http import HTTPStatus
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError

from app.core.authorization import (
    AuditAction,
    Permission,
    UserRole,
    has_permission,
)
from app.core.exceptions import ApplicationError
from app.models.document import Document
from app.models.document_file import DocumentFile, DocumentFileStatus
from app.models.document_revision import DocumentRevision
from app.models.upload_session import (
    UploadSession,
    UploadSessionStatus,
    UploadSessionType,
)
from app.models.upload_session_item import (
    UploadIdentificationStatus,
    UploadProposedAction,
    UploadSessionItem,
    UploadSessionItemStatus,
)
from app.repositories.document_file_repository import DocumentFileRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_revision_repository import (
    DocumentRevisionRepository,
)
from app.repositories.upload_session_item_repository import (
    UploadSessionItemRepository,
)
from app.repositories.upload_session_repository import UploadSessionRepository
from app.schemas.common import ErrorDetail
from app.schemas.document import DocumentCreate
from app.schemas.document_revision import DocumentRevisionCreate
from app.schemas.document_upload import (
    BatchUploadResult,
    FileDuplicateWarning,
    MatchedDocumentReference,
    MatchedRevisionReference,
    ParsedDocumentMetadata,
    UploadActionMetadata,
    UploadConfirmationItem,
    UploadConfirmationItemResult,
    UploadConfirmationRequest,
    UploadConfirmationResult,
)
from app.schemas.upload_session import (
    BatchUploadResponse,
    UploadSessionItemResponse,
    UploadSessionResponse,
)
from app.services.documents.base import (
    DocumentServiceBase,
    document_conflict,
    document_error,
    document_not_found,
    revision_not_found,
)
from app.services.documents.document_file_service import DocumentFileService
from app.services.documents.document_revision_service import (
    DocumentRevisionService,
)
from app.services.documents.document_service import DocumentService
from app.services.documents.file_identification_service import (
    FileIdentificationOutcome,
    FileIdentificationService,
)
from app.services.documents.file_validation_service import (
    FileValidationResult,
    FileValidationService,
)
from app.services.storage.base_storage import BaseStorage
from app.services.storage.file_stream_service import (
    FileStreamService,
    StreamLimitExceededError,
)
from app.services.storage.storage_factory import StorageFactory
from app.services.storage.storage_path_service import (
    StoragePathService,
    UnsafeFilenameError,
)
from app.utils.datetime import ensure_utc, utc_now

logger = logging.getLogger(__name__)


class DocumentUploadService(DocumentServiceBase):
    """Stage files privately, preview identification, then commit safely."""

    def __init__(
        self,
        session,
        settings,
        user,
        metadata,
        *,
        storage: BaseStorage | None = None,
    ) -> None:
        super().__init__(session, user, metadata)
        self.user_id = user.id
        self.settings = settings
        self.storage = storage or StorageFactory.get_storage(settings)
        self.paths = StoragePathService(settings)
        self.validator = FileValidationService(settings)
        self.identification = FileIdentificationService(
            session,
            settings,
            user,
            metadata,
        )
        self.sessions = UploadSessionRepository(session)
        self.items = UploadSessionItemRepository(session)
        self.files = DocumentFileRepository(session)
        self.documents = DocumentRepository(session)
        self.revisions = DocumentRevisionRepository(session)

    async def preview_single(
        self,
        upload: UploadFile,
        *,
        document_id: UUID | None = None,
        revision_id: UUID | None = None,
        session_type: UploadSessionType = UploadSessionType.SINGLE,
        replace_file_id: UUID | None = None,
    ) -> UploadSessionResponse:
        await self._ensure_preview_target(document_id, revision_id)
        staged_keys: set[str] = set()
        try:
            upload_session = self._new_session(
                session_type=session_type,
                total_files=1,
                metadata={
                    "documentId": (
                        str(document_id)
                        if document_id is not None
                        else None
                    ),
                    "revisionId": (
                        str(revision_id)
                        if revision_id is not None
                        else None
                    ),
                    "replaceFileId": (
                        str(replace_file_id)
                        if replace_file_id is not None
                        else None
                    ),
                },
            )
            await self.sessions.create(upload_session)
            item, error = await self._stage_item(
                upload_session,
                upload,
                document_id=document_id,
                revision_id=revision_id,
                tracked_storage_keys=staged_keys,
            )
            upload_session.total_size = item.file_size or 0
            upload_session.status = (
                UploadSessionStatus.READY_FOR_CONFIRMATION
                if error is None
                else UploadSessionStatus.FAILED
            )
            await self.audit(
                action=AuditAction.UPLOAD_FILE_PREVIEW,
                entity_type="upload_session",
                entity_id=upload_session.id,
                description=(
                    f"Previewed upload {item.sanitized_filename}."
                ),
                new_values=self._preview_audit_values(
                    upload_session,
                    [item],
                ),
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            await self._compensate_staged_keys(staged_keys)
            raise
        if error is not None:
            raise error
        refreshed = await self.sessions.get_by_id(
            upload_session.id,
            user_id=self.user_id,
        )
        assert refreshed is not None
        return await self._session_response(refreshed)

    async def preview_batch(
        self,
        uploads: list[UploadFile],
    ) -> BatchUploadResponse:
        if not uploads:
            raise self._upload_error(
                "At least one file is required.",
                field="files",
            )
        if len(uploads) > self.settings.document_batch_max_files:
            raise self._upload_error(
                (
                    "Batch contains more files than the configured limit "
                    f"of {self.settings.document_batch_max_files}."
                ),
                field="files",
                status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )
        staged_keys: set[str] = set()
        staged: list[UploadSessionItem] = []
        try:
            upload_session = self._new_session(
                session_type=UploadSessionType.BATCH,
                total_files=len(uploads),
            )
            await self.sessions.create(upload_session)
            total_size = 0
            total_limit = (
                self.settings.document_batch_max_total_size_mb
                * 1024
                * 1024
            )
            for upload in uploads:
                item, error = await self._stage_item(
                    upload_session,
                    upload,
                    tracked_storage_keys=staged_keys,
                )
                staged.append(item)
                total_size += item.file_size or 0
                if total_size > total_limit and error is None:
                    await self._invalidate_staged_item(
                        upload_session,
                        item,
                        (
                            "Batch total size exceeds the configured limit "
                            "of "
                            f"{self.settings.document_batch_max_total_size_mb}"
                            " MB."
                        ),
                    )
            upload_session.total_size = total_size
            upload_session.status = (
                UploadSessionStatus.READY_FOR_CONFIRMATION
            )
            await self.audit(
                action=AuditAction.BATCH_UPLOAD_PREVIEW,
                entity_type="upload_session",
                entity_id=upload_session.id,
                description=(
                    f"Previewed batch with {len(staged)} files."
                ),
                new_values=self._preview_audit_values(
                    upload_session,
                    staged,
                ),
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            await self._compensate_staged_keys(staged_keys)
            raise
        refreshed = await self.sessions.get_by_id(
            upload_session.id,
            user_id=self.user_id,
        )
        assert refreshed is not None
        response = await self._session_response(refreshed)
        return BatchUploadResponse(**response.model_dump())

    async def cancel(self, session_id: UUID) -> UploadSessionResponse:
        upload_session = await self._owned_session(
            session_id,
            for_update=True,
        )
        if upload_session.status not in {
            UploadSessionStatus.CREATED,
            UploadSessionStatus.UPLOADING,
            UploadSessionStatus.READY_FOR_CONFIRMATION,
            UploadSessionStatus.FAILED,
        }:
            raise document_conflict(
                "Upload session can no longer be cancelled.",
                title="Upload session could not be cancelled.",
            )
        items = await self.items.list_by_session(upload_session.id)
        cleanup_items: list[UploadSessionItem] = []
        for item in items:
            if item.status in {
                UploadSessionItemStatus.PENDING,
                UploadSessionItemStatus.READY,
                UploadSessionItemStatus.FAILED,
            }:
                cleanup_items.append(item)
                item.status = UploadSessionItemStatus.CANCELLED
        await self.sessions.mark_cancelled(
            upload_session,
            cancelled_at=utc_now(),
        )
        await self.audit(
            action=AuditAction.CANCEL_FILE_UPLOAD,
            entity_type="upload_session",
            entity_id=upload_session.id,
            description="Cancelled upload session.",
            new_values={
                "sessionId": str(upload_session.id),
                "fileCount": len(items),
            },
        )
        await self.session.commit()
        await self._delete_pending_temporary_items(cleanup_items)
        refreshed = await self.sessions.get_by_id(
            upload_session.id,
            user_id=self.user_id,
        )
        assert refreshed is not None
        return await self._session_response(refreshed)

    async def confirm(
        self,
        session_id: UUID,
        payload: UploadConfirmationRequest,
        *,
        expected_session_types: set[UploadSessionType] | None = None,
    ) -> UploadConfirmationResult:
        result = await self._confirm_common(
            session_id,
            payload,
            expected_session_types=(
                expected_session_types
                or {UploadSessionType.SINGLE, UploadSessionType.REPLACE}
            ),
            batch=False,
        )
        assert isinstance(result, UploadConfirmationResult)
        return result

    async def confirm_batch(
        self,
        session_id: UUID,
        payload: UploadConfirmationRequest,
    ) -> BatchUploadResult:
        result = await self._confirm_common(
            session_id,
            payload,
            expected_session_types={UploadSessionType.BATCH},
            batch=True,
        )
        assert isinstance(result, BatchUploadResult)
        return result

    async def _confirm_common(
        self,
        session_id: UUID,
        payload: UploadConfirmationRequest,
        *,
        expected_session_types: set[UploadSessionType],
        batch: bool,
    ) -> UploadConfirmationResult | BatchUploadResult:
        if (
            batch
            and len(payload.items)
            > self.settings.document_batch_max_files
        ):
            raise self._upload_error(
                (
                    "Batch confirmation contains more items than the "
                    f"configured limit of "
                    f"{self.settings.document_batch_max_files}."
                ),
                field="items",
                status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )
        upload_session = await self._owned_session(
            session_id,
            for_update=True,
        )
        await self._ensure_confirmable(
            upload_session,
            expected_session_types,
        )
        items = await self.items.list_by_session(upload_session.id)
        item_map = {item.id: item for item in items}
        requested_ids = [item.upload_item_id for item in payload.items]
        if len(set(requested_ids)) != len(requested_ids):
            raise self._upload_error(
                "Each uploadItemId may only be confirmed once.",
                field="items",
            )
        unknown = [item_id for item_id in requested_ids if item_id not in item_map]
        if unknown:
            raise self._upload_error(
                "One or more upload items do not belong to this session.",
                field="items",
            )
        if not batch and (
            len(items) != 1
            or len(payload.items) != 1
            or requested_ids[0] != items[0].id
        ):
            raise self._upload_error(
                "Single upload confirmation must contain its one upload item.",
                field="items",
            )
        upload_session.status = UploadSessionStatus.UPLOADING
        await self.session.commit()

        requested = {
            item.upload_item_id: item for item in payload.items
        }
        results: list[UploadConfirmationItemResult] = []
        counters = {
            "documents_created": 0,
            "revisions_created": 0,
            "files_attached": 0,
            "files_replaced": 0,
        }
        for item in items:
            confirmation = requested.get(item.id)
            if confirmation is None:
                confirmation = UploadConfirmationItem(
                    upload_item_id=item.id,
                    action=UploadProposedAction.SKIP,
                )
            if confirmation.action == UploadProposedAction.SKIP:
                locked_item = await self.items.get_by_id(
                    item.id,
                    session_id=upload_session.id,
                    for_update=True,
                )
                assert locked_item is not None
                locked_item.status = UploadSessionItemStatus.SKIPPED
                await self.session.commit()
                await self._delete_pending_temporary_items([locked_item])
                results.append(
                    UploadConfirmationItemResult(
                        upload_item_id=item.id,
                        action=confirmation.action,
                        status=UploadSessionItemStatus.SKIPPED,
                    )
                )
                continue
            try:
                result, action_counts = await self._commit_item(
                    upload_session,
                    item,
                    confirmation,
                )
            except ApplicationError as exc:
                await self.session.rollback()
                await self.session.refresh(self.user)
                message = (
                    exc.errors[0].message
                    if exc.errors
                    else exc.message
                )
                await self._mark_item_failed(
                    confirmation.upload_item_id,
                    message,
                )
                if "Duplicate file" in message:
                    await self._persist_duplicate_audit(
                        confirmation.upload_item_id,
                        confirmation.revision_id,
                    )
                if not batch:
                    await self._mark_session_failed(session_id)
                    raise
                result = UploadConfirmationItemResult(
                    upload_item_id=confirmation.upload_item_id,
                    action=confirmation.action,
                    status=UploadSessionItemStatus.FAILED,
                    error=message,
                )
                action_counts = {}
            results.append(result)
            for key, value in action_counts.items():
                counters[key] += value

        committed = sum(
            item.status == UploadSessionItemStatus.COMMITTED
            for item in results
        )
        failed = sum(
            item.status == UploadSessionItemStatus.FAILED
            for item in results
        )
        skipped = sum(
            item.status == UploadSessionItemStatus.SKIPPED
            for item in results
        )
        final_status = (
            UploadSessionStatus.COMMITTED
            if failed == 0
            else (
                UploadSessionStatus.PARTIALLY_COMMITTED
                if committed > 0
                else UploadSessionStatus.FAILED
            )
        )
        upload_session = await self.sessions.get_by_id(
            session_id,
            user_id=self.user_id,
            for_update=True,
            with_items=False,
        )
        assert upload_session is not None
        await self.sessions.mark_committed(
            upload_session,
            status=final_status,
            committed_at=utc_now(),
        )
        await self.audit(
            action=(
                AuditAction.CONFIRM_BATCH_UPLOAD
                if batch
                else AuditAction.CONFIRM_FILE_UPLOAD
            ),
            entity_type="upload_session",
            entity_id=upload_session.id,
            description=(
                f"Confirmed upload session with {committed} committed, "
                f"{skipped} skipped, and {failed} failed items."
            ),
            new_values={
                "sessionId": str(upload_session.id),
                "status": final_status.value,
                "committed": committed,
                "skipped": skipped,
                "failed": failed,
            },
        )
        await self.session.commit()
        if batch:
            return BatchUploadResult(
                session_id=upload_session.id,
                status=final_status.value,
                total=len(results),
                committed=committed,
                skipped=skipped,
                failed=failed,
                documents_created=counters["documents_created"],
                revisions_created=counters["revisions_created"],
                files_attached=counters["files_attached"],
                files_replaced=counters["files_replaced"],
                items=results,
                committed_at=upload_session.committed_at,
            )
        return UploadConfirmationResult(
            session_id=upload_session.id,
            status=final_status.value,
            items=results,
        )

    async def _commit_item(
        self,
        upload_session: UploadSession,
        item: UploadSessionItem,
        confirmation: UploadConfirmationItem,
    ) -> tuple[UploadConfirmationItemResult, dict[str, int]]:
        locked_item = await self.items.get_by_id(
            item.id,
            session_id=upload_session.id,
            for_update=True,
        )
        if locked_item is None:
            raise self._upload_error("Upload item was not found.")
        if locked_item.status != UploadSessionItemStatus.READY:
            raise document_conflict(
                "Upload item is not ready for confirmation.",
                title="Upload item could not be confirmed.",
            )
        self._ensure_valid_item(locked_item)
        await self._revalidate_item(locked_item)
        locked_item_id = locked_item.id
        document: Document
        revision: DocumentRevision
        old_file: DocumentFile | None = None
        action_counts: dict[str, int] = {}
        metadata = confirmation.metadata or UploadActionMetadata()
        action = confirmation.action
        if action == UploadProposedAction.ATTACH_TO_EXISTING_REVISION:
            document, revision = await self._existing_target(
                confirmation,
                metadata,
                allow_archived_super_admin=True,
            )
            current = await self.files.get_current_by_revision(
                revision.id,
                for_update=True,
            )
            if current is not None:
                raise document_conflict(
                    "The revision already has a current file. Use replace.",
                    title="File could not be attached.",
                )
            action_counts["files_attached"] = 1
            audit_action = AuditAction.ATTACH_FILE_TO_REVISION
        elif action == UploadProposedAction.CREATE_DOCUMENT_AND_REVISION:
            self._require_permission(Permission.DOCUMENTS_CREATE)
            document, revision = await self._create_document(metadata)
            action_counts.update(
                documents_created=1,
                revisions_created=1,
                files_attached=1,
            )
            audit_action = AuditAction.CREATE_DOCUMENT_FROM_UPLOAD
        elif action == UploadProposedAction.ADD_NEW_REVISION:
            self._require_permission(Permission.DOCUMENTS_UPDATE)
            document, revision = await self._create_revision(
                confirmation,
                metadata,
            )
            action_counts.update(revisions_created=1, files_attached=1)
            audit_action = AuditAction.CREATE_REVISION_FROM_UPLOAD
        elif action == UploadProposedAction.REPLACE_CURRENT_FILE:
            self._require_permission(Permission.DOCUMENTS_REPLACE_FILE)
            document, revision = await self._existing_target(
                confirmation,
                metadata,
            )
            old_file = await self.files.get_current_by_revision(
                revision.id,
                for_update=True,
            )
            if old_file is None:
                raise document_conflict(
                    "The revision does not have a current file to replace.",
                    title="File could not be replaced.",
                )
            expected_file_id = self._expected_current_file_id(
                upload_session,
                locked_item_id,
            )
            if (
                expected_file_id is not None
                and old_file.id != expected_file_id
            ):
                raise document_conflict(
                    "The current file changed after preview. Upload the "
                    "replacement again.",
                    title="File could not be replaced.",
                )
            if (
                expected_file_id is None
                and locked_item.proposed_action
                == UploadProposedAction.REPLACE_CURRENT_FILE
            ):
                raise document_conflict(
                    "The replacement preview is missing its concurrency "
                    "baseline. Upload the replacement again.",
                    title="File could not be replaced.",
                )
            if not metadata.reason or not metadata.reason.strip():
                raise self._upload_error(
                    "A replacement reason is required.",
                    field="metadata.reason",
                )
            if locked_item.sha256_hash == old_file.sha256_hash:
                raise document_conflict(
                    "The replacement file is identical to the current file.",
                    title="File could not be replaced.",
                )
            self._ensure_sensitive_replacement(revision)
            action_counts["files_replaced"] = 1
            audit_action = AuditAction.REPLACE_DOCUMENT_FILE
        else:
            raise self._upload_error(
                "Manual review items require a concrete confirmation action.",
                field="action",
            )

        await self._recheck_duplicate(
            locked_item,
            revision,
            allow_duplicate=metadata.allow_duplicate,
        )
        file_id = uuid4()
        final_key = self.paths.original_key(
            document.id,
            revision.id,
            file_id,
            locked_item.sanitized_filename,
        )
        moved = False
        old_file_audit = DocumentFileService._audit_values(old_file)
        try:
            await self.storage.move(
                locked_item.temporary_storage_key,
                final_key,
            )
            moved = True
            locked_item.temporary_cleanup_pending = False
            document_file = DocumentFile(
                id=file_id,
                document_id=document.id,
                document_revision_id=revision.id,
                original_filename=locked_item.original_filename,
                sanitized_filename=locked_item.sanitized_filename,
                file_extension=locked_item.file_extension,
                mime_type=locked_item.mime_type,
                detected_mime_type=locked_item.detected_mime_type,
                file_size=locked_item.file_size,
                sha256_hash=locked_item.sha256_hash,
                storage_provider=self.settings.storage_provider,
                storage_key=final_key,
                storage_bucket=None,
                file_status=DocumentFileStatus.AVAILABLE,
                is_primary=True,
                is_current=True,
                uploaded_by=self.user_id,
                metadata_json={
                    "uploadSessionId": str(upload_session.id),
                    "uploadItemId": str(locked_item.id),
                    **(
                        {"replacementReason": metadata.reason}
                        if metadata.reason
                        else {}
                    ),
                },
            )
            if old_file is not None:
                await self.files.prepare_replacement(
                    old_file,
                    replaced_at=utc_now(),
                )
            await self.files.create(document_file)
            if old_file is not None:
                await self.files.link_replacement(
                    old_file,
                    replacement_id=document_file.id,
                )
            locked_item.status = UploadSessionItemStatus.COMMITTED
            await self.audit(
                action=audit_action,
                entity_type="document_file",
                entity_id=document_file.id,
                description=(
                    f"Attached {document_file.sanitized_filename} to "
                    f"{revision.full_document_code}."
                ),
                old_values=(
                    old_file_audit
                ),
                new_values={
                    **(
                        DocumentFileService._audit_values(document_file)
                        or {}
                    ),
                    "reason": metadata.reason,
                },
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            await self.session.refresh(self.user)
            if moved and await self.storage.exists(final_key):
                await self.storage.delete(final_key)
            await self._mark_item_failed(
                locked_item_id,
                "File metadata conflicts with an existing current file.",
            )
            raise document_conflict(
                "The revision already has a current primary file.",
                title="File could not be attached.",
            ) from exc
        except ApplicationError:
            await self.session.rollback()
            await self.session.refresh(self.user)
            if moved and await self.storage.exists(final_key):
                await self.storage.delete(final_key)
            raise
        except Exception as exc:
            await self.session.rollback()
            await self.session.refresh(self.user)
            if moved and await self.storage.exists(final_key):
                await self.storage.delete(final_key)
            await self._mark_item_failed(
                locked_item_id,
                "File could not be committed.",
            )
            raise self._upload_error(
                "File could not be committed.",
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            ) from exc
        return (
            UploadConfirmationItemResult(
                upload_item_id=locked_item_id,
                action=action,
                status=UploadSessionItemStatus.COMMITTED,
                document_id=document.id,
                revision_id=revision.id,
                document_file_id=file_id,
                base_document_code=document.base_document_code,
                revision_code=revision.revision_code,
                file_status=DocumentFileStatus.AVAILABLE.value,
            ),
            action_counts,
        )

    async def _existing_target(
        self,
        confirmation: UploadConfirmationItem,
        metadata: UploadActionMetadata,
        *,
        allow_archived_super_admin: bool = False,
    ) -> tuple[Document, DocumentRevision]:
        if confirmation.document_id is None or confirmation.revision_id is None:
            raise self._upload_error(
                "documentId and revisionId are required.",
                field="items",
            )
        document = await self.documents.get_by_id(
            confirmation.document_id,
            for_update=True,
        )
        if document is None:
            raise document_not_found()
        self.policy.ensure_document_access(document)
        is_super_admin = (
            self.user.is_superuser
            or self.user.role == UserRole.SUPER_ADMIN
        )
        archived_exception = (
            allow_archived_super_admin
            and is_super_admin
            and metadata.reason
            and metadata.reason.strip()
        )
        if document.is_archived and not archived_exception:
            raise self._upload_error(
                "Archived documents cannot receive physical files.",
                field="documentId",
            )
        revision = await self.revisions.get_by_id(
            confirmation.revision_id,
            document_id=document.id,
            for_update=True,
        )
        if revision is None:
            raise revision_not_found()
        return document, revision

    async def _ensure_preview_target(
        self,
        document_id: UUID | None,
        revision_id: UUID | None,
    ) -> None:
        """Reject known read-only targets before writing upload bytes."""
        if revision_id is not None and document_id is None:
            raise self._upload_error(
                "documentId is required when revisionId is provided.",
                field="documentId",
            )
        if document_id is None and revision_id is None:
            return
        revision = None
        if revision_id is not None:
            revision = await self.revisions.get_by_id(
                revision_id,
                document_id=document_id,
            )
            if revision is None:
                raise revision_not_found()
        resolved_document_id = (
            document_id
            if document_id is not None
            else revision.document_id
            if revision is not None
            else None
        )
        assert resolved_document_id is not None
        document = await self.documents.get_by_id(resolved_document_id)
        if document is None:
            raise document_not_found()
        self.policy.ensure_document_access(document)
        is_super_admin = (
            self.user.is_superuser
            or self.user.role == UserRole.SUPER_ADMIN
        )
        if document.is_archived and not is_super_admin:
            raise self._upload_error(
                "Archived documents cannot receive physical files.",
                field="documentId",
            )

    async def _create_document(
        self,
        metadata: UploadActionMetadata,
    ) -> tuple[Document, DocumentRevision]:
        required = {
            "departmentId": metadata.department_id,
            "documentTypeId": metadata.document_type_id,
            "documentNumber": metadata.document_number,
            "title": metadata.title,
            "revisionCode": metadata.revision_code,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise self._upload_error(
                f"{', '.join(missing)} required when creating a document.",
                field="metadata",
            )
        assert (
            metadata.department_id is not None
            and metadata.document_type_id is not None
            and metadata.document_number is not None
            and metadata.title is not None
            and metadata.revision_code is not None
        )
        response = await DocumentService(
            self.session,
            self.settings,
            self.user,
            self.metadata,
        ).create(
            DocumentCreate(
                company_code=metadata.company_code,
                department_id=metadata.department_id,
                section_id=metadata.section_id,
                document_type_id=metadata.document_type_id,
                document_number=metadata.document_number,
                title=metadata.title,
                description=metadata.description,
                initial_revision=self._revision_payload(metadata),
            ),
            commit=False,
        )
        if response.current_revision is None:
            raise RuntimeError("Created document has no initial revision.")
        document = await self.documents.get_by_id(
            response.id,
            for_update=True,
        )
        revision = await self.revisions.get_by_id(
            response.current_revision.id,
            document_id=response.id,
            for_update=True,
        )
        assert document is not None and revision is not None
        return document, revision

    async def _create_revision(
        self,
        confirmation: UploadConfirmationItem,
        metadata: UploadActionMetadata,
    ) -> tuple[Document, DocumentRevision]:
        if confirmation.document_id is None:
            raise self._upload_error(
                "documentId is required when adding a revision.",
                field="documentId",
            )
        if not metadata.revision_code:
            raise self._upload_error(
                "metadata.revisionCode is required.",
                field="metadata.revisionCode",
            )
        document = await self.documents.get_by_id(
            confirmation.document_id,
            for_update=True,
        )
        if document is None:
            raise document_not_found()
        self.policy.ensure_document_access(document)
        if document.is_archived:
            raise self._upload_error(
                "Archived documents cannot receive new revisions.",
                field="documentId",
            )
        response = await DocumentRevisionService(
            self.session,
            self.user,
            self.metadata,
        ).create(
            document.id,
            self._revision_payload(metadata),
            commit=False,
        )
        revision = await self.revisions.get_by_id(
            response.id,
            document_id=document.id,
            for_update=True,
        )
        assert revision is not None
        return document, revision

    @staticmethod
    def _revision_payload(
        metadata: UploadActionMetadata,
    ) -> DocumentRevisionCreate:
        assert metadata.revision_code is not None
        return DocumentRevisionCreate(
            revision_code=metadata.revision_code,
            document_status_id=metadata.document_status_id,
            validation_rule_id=metadata.validation_rule_id,
            issue_date=metadata.issue_date,
            effective_date=metadata.effective_date,
            review_date=metadata.review_date,
            expiry_date=metadata.expiry_date,
            sharepoint_url=(
                str(metadata.sharepoint_url)
                if metadata.sharepoint_url is not None
                else None
            ),
            external_reference=metadata.external_reference,
            remarks=metadata.remarks,
            set_as_current=metadata.set_as_current_revision,
        )

    async def _recheck_duplicate(
        self,
        item: UploadSessionItem,
        revision: DocumentRevision,
        *,
        allow_duplicate: bool,
    ) -> None:
        if not self.settings.enable_duplicate_file_hash_check:
            return
        assert item.sha256_hash is not None and item.file_size is not None
        duplicates = await self.files.find_by_hash(
            item.sha256_hash,
            item.file_size,
        )
        if any(
            duplicate.document_revision_id == revision.id
            for duplicate in duplicates
        ):
            await self._audit_duplicate(item, revision)
            raise document_conflict(
                "Duplicate file already exists.",
                title="File could not be attached.",
            )
        if duplicates and not allow_duplicate:
            await self._audit_duplicate(item, revision)
            raise document_conflict(
                "Duplicate file already exists. Explicit confirmation is "
                "required to continue.",
                title="File could not be attached.",
            )

    async def _revalidate_item(
        self,
        item: UploadSessionItem,
    ) -> None:
        """Distrust preview metadata and validate staged bytes at confirm."""
        try:
            validation = await self.validator.validate_storage(
                self.storage,
                item.temporary_storage_key,
                original_filename=item.original_filename,
                declared_mime_type=item.mime_type or "",
            )
        except FileNotFoundError as exc:
            raise document_conflict(
                "The staged file no longer exists.",
                title="Upload item could not be confirmed.",
            ) from exc
        expected = (
            item.sanitized_filename,
            item.file_extension,
            item.mime_type,
            item.detected_mime_type,
            item.file_size,
            item.sha256_hash,
        )
        actual = (
            validation.sanitized_filename,
            validation.extension,
            validation.declared_mime_type,
            validation.detected_mime_type,
            validation.file_size,
            validation.sha256_hash,
        )
        if actual != expected:
            raise document_conflict(
                "The staged file changed after preview and must be uploaded "
                "again.",
                title="Upload item could not be confirmed.",
            )

    async def _audit_duplicate(
        self,
        item: UploadSessionItem,
        revision: DocumentRevision | None,
    ) -> None:
        await self.audit(
            action=AuditAction.DUPLICATE_FILE_DETECTED,
            entity_type="upload_session_item",
            entity_id=item.id,
            description="Detected a duplicate physical file.",
            new_values={
                "uploadItemId": str(item.id),
                "targetRevisionId": (
                    str(revision.id) if revision is not None else None
                ),
                "sha256Hash": item.sha256_hash,
                "fileSize": item.file_size,
            },
        )

    async def _persist_duplicate_audit(
        self,
        item_id: UUID,
        revision_id: UUID | None,
    ) -> None:
        """Persist a race-time duplicate event after its business rollback."""
        item = await self.items.get_by_id(item_id)
        if item is None:
            return
        revision = (
            await self.revisions.get_by_id(revision_id)
            if revision_id is not None
            else None
        )
        await self._audit_duplicate(item, revision)
        await self.session.commit()

    def _ensure_sensitive_replacement(
        self,
        revision: DocumentRevision,
    ) -> None:
        status_code = revision.document_status.code.upper()
        if status_code not in {"FINAL", "EFFECTIVE"}:
            return
        if self.user.is_superuser or self.user.role in {
            UserRole.SUPER_ADMIN,
            UserRole.DOCUMENT_CONTROLLER,
        }:
            return
        raise document_error(
            "Only a Document Controller or Super Admin can replace a file "
            "on a final or effective revision.",
            status_code=HTTPStatus.FORBIDDEN,
            title="Authorization failed.",
        )

    async def _stage_item(
        self,
        upload_session: UploadSession,
        upload: UploadFile,
        *,
        document_id: UUID | None = None,
        revision_id: UUID | None = None,
        tracked_storage_keys: set[str] | None = None,
    ) -> tuple[UploadSessionItem, ApplicationError | None]:
        item_id = uuid4()
        original_filename = upload.filename or "document"
        sanitized = "invalid_upload"
        temp_key = self.paths._join(
            self.settings.storage_temp_prefix,
            str(upload_session.id),
            str(item_id),
        )
        try:
            sanitized, _, _ = self.validator.validate_upload_metadata(
                original_filename,
                upload.content_type or "",
            )
            temp_key = self.paths.temporary_key(
                upload_session.id,
                item_id,
                sanitized,
            )
            await FileStreamService.save_with_limit(
                self.storage,
                upload.file,
                temp_key,
                max_bytes=self.settings.document_max_file_size_mb
                * 1024
                * 1024,
            )
            if tracked_storage_keys is not None:
                tracked_storage_keys.add(temp_key)
            validation = await self.validator.validate_storage(
                self.storage,
                temp_key,
                original_filename=original_filename,
                declared_mime_type=upload.content_type or "",
            )
            outcome = await self.identification.identify(
                filename=validation.sanitized_filename,
                sha256_hash=validation.sha256_hash,
                file_size=validation.file_size,
                document_id=document_id,
                revision_id=revision_id,
            )
            await self._bind_expected_current_file(
                upload_session,
                item_id,
                outcome,
            )
            item = self._new_item(
                upload_session.id,
                item_id,
                temp_key,
                original_filename,
                validation=validation,
                outcome=outcome,
            )
            await self.items.create(item)
            if outcome.duplicate_warning is not None:
                await self._audit_duplicate(
                    item,
                    outcome.matched_revision,
                )
            return item, None
        except StreamLimitExceededError:
            error = self._upload_error(
                (
                    "File exceeds the configured maximum size of "
                    f"{self.settings.document_max_file_size_mb} MB."
                ),
                field="file",
                status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )
        except UnsafeFilenameError as exc:
            error = self._upload_error(
                str(exc),
                field="file",
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            )
        except ApplicationError as exc:
            error = exc
        stored_key = temp_key
        if await self.storage.exists(temp_key):
            if self.settings.enable_file_quarantine:
                quarantine_key = self.paths.quarantine_key(
                    upload_session.id,
                    item_id,
                    sanitized,
                )
                await self.storage.move(temp_key, quarantine_key)
                stored_key = quarantine_key
                if tracked_storage_keys is not None:
                    tracked_storage_keys.discard(temp_key)
                    tracked_storage_keys.add(quarantine_key)
                await self.audit(
                    action=AuditAction.QUARANTINE_DOCUMENT_FILE,
                    entity_type="upload_session_item",
                    entity_id=item_id,
                    description="Quarantined an invalid staged file.",
                    new_values={
                        "uploadItemId": str(item_id),
                        "reason": (
                            error.errors[0].message
                            if error.errors
                            else error.message
                        ),
                    },
                )
            else:
                await self.storage.delete(temp_key)
                if tracked_storage_keys is not None:
                    tracked_storage_keys.discard(temp_key)
        quarantine_reason = (
            error.errors[0].message if error.errors else error.message
        )
        cleanup_pending = await self.storage.exists(stored_key)
        item = UploadSessionItem(
            id=item_id,
            upload_session_id=upload_session.id,
            temporary_storage_key=stored_key,
            original_filename=original_filename,
            sanitized_filename=sanitized,
            identification_status=UploadIdentificationStatus.INVALID,
            proposed_action=UploadProposedAction.SKIP,
            warnings_json=[],
            errors_json=[quarantine_reason],
            quarantine_reason=(
                quarantine_reason if cleanup_pending else None
            ),
            temporary_cleanup_pending=cleanup_pending,
            status=UploadSessionItemStatus.FAILED,
        )
        await self.items.create(item)
        return item, error

    def _new_item(
        self,
        session_id: UUID,
        item_id: UUID,
        temp_key: str,
        original_filename: str,
        *,
        validation: FileValidationResult,
        outcome: FileIdentificationOutcome,
    ) -> UploadSessionItem:
        return UploadSessionItem(
            id=item_id,
            upload_session_id=session_id,
            temporary_storage_key=temp_key,
            original_filename=original_filename,
            sanitized_filename=validation.sanitized_filename,
            file_extension=validation.extension,
            mime_type=validation.declared_mime_type,
            detected_mime_type=validation.detected_mime_type,
            file_size=validation.file_size,
            sha256_hash=validation.sha256_hash,
            identification_status=outcome.identification_status,
            matched_document_id=(
                outcome.matched_document.id
                if outcome.matched_document is not None
                else None
            ),
            matched_revision_id=(
                outcome.matched_revision.id
                if outcome.matched_revision is not None
                else None
            ),
            proposed_action=outcome.proposed_action,
            parsed_metadata_json=(
                outcome.parsed_metadata.model_dump(
                    mode="json",
                    by_alias=True,
                    exclude_none=True,
                )
                if outcome.parsed_metadata is not None
                else None
            ),
            warnings_json=outcome.warnings,
            errors_json=outcome.errors,
            quarantine_reason=None,
            temporary_cleanup_pending=True,
            status=UploadSessionItemStatus.READY,
        )

    async def _invalidate_staged_item(
        self,
        upload_session: UploadSession,
        item: UploadSessionItem,
        message: str,
    ) -> None:
        if await self.storage.exists(item.temporary_storage_key):
            await self.storage.delete(item.temporary_storage_key)
        item.temporary_cleanup_pending = False
        item.identification_status = UploadIdentificationStatus.INVALID
        item.proposed_action = UploadProposedAction.SKIP
        item.errors_json = [message]
        item.status = UploadSessionItemStatus.FAILED

    async def _ensure_confirmable(
        self,
        upload_session: UploadSession,
        expected_types: set[UploadSessionType],
    ) -> None:
        if upload_session.session_type not in expected_types:
            raise document_conflict(
                "Upload session type does not match this endpoint.",
                title="Upload session could not be confirmed.",
            )
        if ensure_utc(upload_session.expires_at) <= utc_now():
            items = await self.items.list_by_session(upload_session.id)
            cleanup_items: list[UploadSessionItem] = []
            for item in items:
                if item.status in {
                    UploadSessionItemStatus.PENDING,
                    UploadSessionItemStatus.READY,
                    UploadSessionItemStatus.FAILED,
                }:
                    cleanup_items.append(item)
                    item.status = UploadSessionItemStatus.CANCELLED
            upload_session.status = UploadSessionStatus.EXPIRED
            await self.session.commit()
            await self._delete_pending_temporary_items(cleanup_items)
            raise document_conflict(
                "Upload session has expired.",
                title="Upload session could not be confirmed.",
            )
        if upload_session.status != UploadSessionStatus.READY_FOR_CONFIRMATION:
            raise document_conflict(
                "Upload session has already been processed or is not ready.",
                title="Upload session could not be confirmed.",
            )

    async def _owned_session(
        self,
        session_id: UUID,
        *,
        for_update: bool,
    ) -> UploadSession:
        upload_session = await self.sessions.get_by_id(
            session_id,
            user_id=self.user_id,
            for_update=for_update,
        )
        if upload_session is None:
            raise document_error(
                "Upload session was not found.",
                status_code=HTTPStatus.NOT_FOUND,
                title="Upload session was not found.",
            )
        return upload_session

    async def _mark_item_failed(
        self,
        item_id: UUID,
        message: str,
    ) -> None:
        item = await self.items.get_by_id(item_id, for_update=True)
        if item is not None:
            item.status = UploadSessionItemStatus.FAILED
            item.errors_json = [message]
            await self.session.commit()

    async def _mark_session_failed(self, session_id: UUID) -> None:
        await self.session.rollback()
        await self.session.refresh(self.user)
        upload_session = await self.sessions.get_by_id(
            session_id,
            user_id=self.user_id,
            for_update=True,
            with_items=False,
        )
        if upload_session is not None:
            upload_session.status = UploadSessionStatus.FAILED
            await self.session.commit()

    def _require_permission(self, permission: Permission) -> None:
        if not has_permission(
            self.user.role,
            permission,
            is_superuser=self.user.is_superuser,
        ):
            raise document_error(
                "You do not have permission to perform this upload action.",
                status_code=HTTPStatus.FORBIDDEN,
                title="Authorization failed.",
            )

    @staticmethod
    def _ensure_valid_item(item: UploadSessionItem) -> None:
        if (
            item.identification_status == UploadIdentificationStatus.INVALID
            or item.file_extension is None
            or item.mime_type is None
            or item.detected_mime_type is None
            or item.file_size is None
            or item.sha256_hash is None
        ):
            raise DocumentUploadService._upload_error(
                "Invalid upload items cannot be confirmed.",
                field="uploadItemId",
            )

    def _new_session(
        self,
        *,
        session_type: UploadSessionType,
        total_files: int,
        metadata: dict[str, object] | None = None,
    ) -> UploadSession:
        return UploadSession(
            id=uuid4(),
            user_id=self.user_id,
            session_type=session_type,
            status=UploadSessionStatus.UPLOADING,
            total_files=total_files,
            total_size=0,
            expires_at=utc_now()
            + timedelta(hours=self.settings.temp_file_retention_hours),
            metadata_json=metadata,
        )

    async def _bind_expected_current_file(
        self,
        upload_session: UploadSession,
        item_id: UUID,
        outcome: FileIdentificationOutcome,
    ) -> None:
        """Bind replacement confirmation to the file observed at preview."""
        metadata = dict(upload_session.metadata_json or {})
        expected = metadata.get("replaceFileId")
        if (
            expected is None
            and outcome.proposed_action
            != UploadProposedAction.REPLACE_CURRENT_FILE
        ):
            return
        if expected is None and outcome.matched_revision is not None:
            current = await self.files.get_current_by_revision(
                outcome.matched_revision.id
            )
            expected = str(current.id) if current is not None else None
        if not isinstance(expected, str):
            return
        raw_mapping = metadata.get("expectedCurrentFileIds")
        mapping = (
            dict(raw_mapping)
            if isinstance(raw_mapping, dict)
            else {}
        )
        mapping[str(item_id)] = expected
        metadata["expectedCurrentFileIds"] = mapping
        upload_session.metadata_json = metadata

    @staticmethod
    def _expected_current_file_id(
        upload_session: UploadSession,
        item_id: UUID,
    ) -> UUID | None:
        metadata = upload_session.metadata_json or {}
        raw_mapping = metadata.get("expectedCurrentFileIds")
        if not isinstance(raw_mapping, dict):
            return None
        value = raw_mapping.get(str(item_id))
        if not isinstance(value, str):
            return None
        try:
            return UUID(value)
        except ValueError:
            return None

    async def _session_response(
        self,
        upload_session: UploadSession,
    ) -> UploadSessionResponse:
        items = await self.items.list_by_session(upload_session.id)
        responses = [
            await self._item_response(item)
            for item in items
        ]
        return UploadSessionResponse(
            session_id=upload_session.id,
            session_type=upload_session.session_type,
            status=upload_session.status,
            total_files=upload_session.total_files,
            total_size=upload_session.total_size,
            expires_at=ensure_utc(upload_session.expires_at),
            committed_at=(
                ensure_utc(upload_session.committed_at)
                if upload_session.committed_at is not None
                else None
            ),
            cancelled_at=(
                ensure_utc(upload_session.cancelled_at)
                if upload_session.cancelled_at is not None
                else None
            ),
            items=responses,
        )

    async def _item_response(
        self,
        item: UploadSessionItem,
    ) -> UploadSessionItemResponse:
        duplicate_warning: FileDuplicateWarning | None = None
        if (
            self.settings.enable_duplicate_file_hash_check
            and item.identification_status
            == UploadIdentificationStatus.DUPLICATE_FILE
            and item.sha256_hash is not None
            and item.file_size is not None
        ):
            duplicates = await self.files.find_by_hash(
                item.sha256_hash,
                item.file_size,
            )
            same_revision = (
                item.matched_revision_id is not None
                and any(
                    duplicate.document_revision_id
                    == item.matched_revision_id
                    for duplicate in duplicates
                )
            )
            visible = next(
                (
                    duplicate
                    for duplicate in duplicates
                    if self.policy.view_all_departments
                    or duplicate.document.department_id
                    == self.user.department_id
                ),
                None,
            )
            duplicate_warning = FileDuplicateWarning(
                same_revision=same_revision,
                document_id=(
                    visible.document_id if visible is not None else None
                ),
                revision_id=(
                    visible.document_revision_id
                    if visible is not None
                    else None
                ),
                base_document_code=(
                    visible.document.base_document_code
                    if visible is not None
                    else None
                ),
            )
        parsed = (
            ParsedDocumentMetadata.model_validate(
                item.parsed_metadata_json
            )
            if item.parsed_metadata_json is not None
            else None
        )
        return UploadSessionItemResponse(
            upload_item_id=item.id,
            original_filename=item.original_filename,
            sanitized_filename=item.sanitized_filename,
            file_extension=item.file_extension,
            mime_type=item.mime_type,
            detected_mime_type=item.detected_mime_type,
            file_size=item.file_size,
            sha256_hash=item.sha256_hash,
            identification_status=item.identification_status,
            proposed_action=item.proposed_action,
            parsed_metadata=parsed,
            matched_document=(
                MatchedDocumentReference(
                    id=item.matched_document.id,
                    base_document_code=(
                        item.matched_document.base_document_code
                    ),
                    title=item.matched_document.title,
                )
                if item.matched_document is not None
                else None
            ),
            matched_revision=(
                MatchedRevisionReference(
                    id=item.matched_revision.id,
                    revision_code=item.matched_revision.revision_code,
                    full_document_code=(
                        item.matched_revision.full_document_code
                    ),
                )
                if item.matched_revision is not None
                else None
            ),
            duplicate_warning=duplicate_warning,
            warnings=list(item.warnings_json or []),
            errors=list(item.errors_json or []),
            quarantine_reason=item.quarantine_reason,
            status=item.status,
        )

    async def _delete_pending_temporary_items(
        self,
        items: list[UploadSessionItem],
    ) -> None:
        """Delete terminal temporary objects and persist retry markers."""
        cleaned = False
        for item in items:
            if not item.temporary_cleanup_pending:
                continue
            try:
                await self.storage.delete(item.temporary_storage_key)
            except Exception:
                logger.warning(
                    "Temporary upload cleanup failed for item %s; "
                    "scheduled cleanup will retry it.",
                    item.id,
                    exc_info=True,
                )
                continue
            item.temporary_cleanup_pending = False
            cleaned = True
        if cleaned:
            await self.session.commit()

    async def _compensate_staged_keys(
        self,
        storage_keys: set[str],
    ) -> None:
        """Best-effort removal when preview metadata never commits."""
        for storage_key in storage_keys:
            try:
                await self.storage.delete(storage_key)
            except Exception:
                logger.exception(
                    "Could not compensate uncommitted staged object %s.",
                    storage_key,
                )

    @staticmethod
    def _preview_audit_values(
        upload_session: UploadSession,
        items: list[UploadSessionItem],
    ) -> dict[str, object]:
        return {
            "sessionId": str(upload_session.id),
            "sessionType": upload_session.session_type.value,
            "totalFiles": len(items),
            "totalSize": sum(item.file_size or 0 for item in items),
            "items": [
                {
                    "uploadItemId": str(item.id),
                    "filename": item.sanitized_filename,
                    "identificationStatus": (
                        item.identification_status.value
                    ),
                    "proposedAction": item.proposed_action.value,
                }
                for item in items
            ],
        }

    @staticmethod
    def _upload_error(
        message: str,
        *,
        field: str | None = None,
        status_code: int = HTTPStatus.BAD_REQUEST,
    ) -> ApplicationError:
        return ApplicationError(
            "File could not be uploaded.",
            status_code=status_code,
            errors=[ErrorDetail(field=field, message=message)],
        )
