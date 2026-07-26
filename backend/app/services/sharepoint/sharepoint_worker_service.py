"""Celery-side SharePoint transfer, delta discovery, and durable state changes."""

from __future__ import annotations

import base64
import hashlib
import tempfile
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any, BinaryIO, cast
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.database.session import AsyncSessionFactory
from app.integrations.microsoft_graph.graph_error_mapper import GraphError
from app.integrations.microsoft_graph.sharepoint._paths import (
    join_remote_path,
)
from app.integrations.microsoft_graph.sharepoint.sharepoint_delta_service import (
    SharePointDeltaService,
    SharePointDeltaTokenInvalid,
)
from app.integrations.microsoft_graph.sharepoint.sharepoint_download_service import (
    SharePointDownloadService,
)
from app.integrations.microsoft_graph.sharepoint.sharepoint_file_service import (
    SharePointFileService,
)
from app.integrations.microsoft_graph.sharepoint.sharepoint_folder_service import (
    SharePointFolderService,
)
from app.integrations.microsoft_graph.sharepoint.sharepoint_metadata_service import (
    SharePointMetadataService,
)
from app.integrations.microsoft_graph.sharepoint.sharepoint_upload_service import (
    SharePointUploadService,
)
from app.models.document_file import (
    DocumentFile,
    DocumentFileStatus,
    RemoteSyncStatus,
)
from app.models.document_revision import DocumentRevision
from app.models.sharepoint_connection import SharePointConnection
from app.models.sharepoint_enums import (
    DeletePolicy,
    SharePointConnectionStatus,
    SharePointSyncJobStatus,
    SyncConflictType,
    SyncDirection,
    SyncItemOperation,
    SyncItemStatus,
    SyncJobType,
)
from app.models.sharepoint_file_version import SharePointFileVersion
from app.models.sharepoint_sync_conflict import SharePointSyncConflict
from app.models.sharepoint_sync_item import SharePointSyncItem
from app.models.sharepoint_sync_job import SharePointSyncJob
from app.models.sharepoint_sync_profile import SharePointSyncProfile
from app.repositories.document_file_repository import DocumentFileRepository
from app.repositories.document_revision_repository import (
    DocumentRevisionRepository,
)
from app.repositories.sharepoint_conflict_repository import (
    SharePointConflictRepository,
)
from app.repositories.sharepoint_connection_repository import (
    SharePointConnectionRepository,
)
from app.repositories.sharepoint_file_version_repository import (
    SharePointFileVersionRepository,
)
from app.repositories.sharepoint_mapping_repository import (
    SharePointMappingRepository,
)
from app.repositories.sharepoint_sync_repository import (
    SharePointSyncRepository,
)
from app.services.secrets.encryption_service import (
    AesGcmEncryptionService,
)
from app.services.security_scanning.base_malware_scanner import (
    BaseMalwareScanner,
    MalwareScanResult,
    MalwareScannerFailPolicy,
)
from app.services.security_scanning.clamav_malware_scanner import (
    ClamAvMalwareScanner,
)
from app.services.security_scanning.no_op_malware_scanner import (
    NoOpMalwareScanner,
)
from app.services.sharepoint.delta_state_service import (
    SharePointDeltaStateService,
)
from app.services.sharepoint.graph_factory import create_graph_client
from app.services.sharepoint.sync_engine import (
    LocalSyncState,
    RemoteSyncState,
    SharePointSyncEngine,
    SyncBaseline,
)
from app.services.storage.base_storage import BaseStorage
from app.services.storage.local_storage import LocalStorage
from app.services.storage.storage_factory import StorageFactory
from app.services.storage.storage_path_service import StoragePathService
from app.utils.datetime import utc_now


class TransientSharePointWorkerError(RuntimeError):
    """Infrastructure failure eligible for bounded Celery retry."""


@dataclass(slots=True)
class _DownloadedRemoteArtifact:
    source: BinaryIO
    metadata: dict[str, Any]
    versions: list[dict[str, Any]]
    sha256_hash: str
    size: int
    scan: MalwareScanResult


class SharePointWorkerService:
    def __init__(
        self,
        settings: Settings,
        *,
        session_factory: async_sessionmaker[AsyncSession] = (
            AsyncSessionFactory
        ),
        local_storage: BaseStorage | None = None,
        malware_scanner: BaseMalwareScanner | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        # Inbound sync must write only to the durable local leg. Passing a
        # HybridStorage here would mirror the downloaded content back to
        # SharePoint and cause a second, unintended remote mutation.
        self.local_storage = local_storage or LocalStorage(
            settings.storage_root
        )
        self.paths = StoragePathService(settings)
        self.malware_scanner = malware_scanner or self._scanner(settings)

    async def process_job(
        self,
        job_id: UUID,
        *,
        worker_reference: str,
    ) -> SharePointSyncJobStatus:
        try:
            snapshot = await self._claim_job(job_id, worker_reference)
            if snapshot is None:
                return SharePointSyncJobStatus.FAILED
            if isinstance(snapshot, SharePointSyncJobStatus):
                return snapshot
            job_type, file_id = snapshot
            if job_type is SyncJobType.SINGLE_FILE_PUSH:
                if file_id is None:
                    raise ValueError("Single-file push has no file scope.")
                await self._push_file(job_id, file_id)
            elif job_type is SyncJobType.SINGLE_FILE_PULL:
                if file_id is None:
                    raise ValueError("Single-file pull has no file scope.")
                await self._pull_file(job_id, file_id)
            elif job_type is SyncJobType.RECONCILIATION and file_id is not None:
                await self._reconcile_file(job_id, file_id)
            else:
                await self._discover_delta(job_id)
            return await self._final_status(job_id)
        except GraphError as exc:
            await self.fail_job(
                job_id,
                error_code=exc.code,
                error_message=(
                    "SharePoint synchronization failed at the Microsoft "
                    "Graph boundary."
                ),
            )
            if exc.status_code not in {429, 500, 502, 503, 504}:
                return SharePointSyncJobStatus.FAILED
            raise TransientSharePointWorkerError(
                "SharePoint is temporarily unavailable."
            ) from exc
        except (OSError, TimeoutError) as exc:
            await self.fail_job(
                job_id,
                error_code="SHAREPOINT_SERVICE_UNAVAILABLE",
                error_message=(
                    "SharePoint synchronization failed due to a transient "
                    "external service error."
                ),
            )
            raise TransientSharePointWorkerError(
                "SharePoint is temporarily unavailable."
            ) from exc
        except Exception as exc:  # noqa: BLE001 - terminal job boundary
            await self.fail_job(
                job_id,
                error_code=getattr(exc, "code", "SHAREPOINT_SYNC_FAILED"),
                error_message=(
                    "SharePoint synchronization failed. Review sanitized "
                    "worker diagnostics."
                ),
            )
            return SharePointSyncJobStatus.FAILED

    async def process_item(self, item_id: UUID) -> SyncItemStatus:
        async with self.session_factory() as session:
            repository = SharePointSyncRepository(session)
            item = await repository.get_item(item_id, for_update=True)
            if item is None:
                return SyncItemStatus.FAILED
            job = await repository.get_job(item.sync_job_id)
            if job is None:
                item.status = SyncItemStatus.FAILED
                item.error_code = "SHAREPOINT_SYNC_FAILED"
                item.error_message = "Parent SharePoint sync job was not found."
                await session.commit()
                return item.status
            profile = await repository.get_profile(job.sync_profile_id)
            file_id = item.document_file_id
            operation = item.operation
            delete_policy = (
                profile.delete_policy
                if profile is not None
                else DeletePolicy.IGNORE_REMOTE_DELETE
            )
            document_id = item.document_id
            revision_id = item.document_revision_id
            remote_drive_id = item.remote_drive_id
            remote_item_id = item.remote_item_id
            item.status = SyncItemStatus.PROCESSING
            item.started_at = utc_now()
            await session.commit()
        if file_id is None:
            if (
                operation is SyncItemOperation.CREATE_LOCAL
                and document_id is not None
                and revision_id is not None
                and remote_drive_id
                and remote_item_id
            ):
                await self._create_local_file(
                    job_id=job.id,
                    sync_item_id=item_id,
                    document_id=document_id,
                    revision_id=revision_id,
                    drive_id=remote_drive_id,
                    item_id=remote_item_id,
                )
            else:
                async with self.session_factory() as session:
                    item = await SharePointSyncRepository(session).get_item(
                        item_id,
                        for_update=True,
                    )
                    if item is None:
                        return SyncItemStatus.FAILED
                    item.status = SyncItemStatus.FAILED
                    item.error_code = "SHAREPOINT_INBOUND_MAPPING_REQUIRED"
                    item.error_message = (
                        "Remote item cannot be mapped to an internal document."
                    )
                    item.completed_at = utc_now()
                    await session.commit()
                    failed_status = item.status
                await self._refresh_parent_job(job.id)
                return failed_status
        elif operation in {
            SyncItemOperation.CREATE_REMOTE,
            SyncItemOperation.UPDATE_REMOTE,
        }:
            safe_copy_suffix = (
                str((item.metadata_json or {}).get("safeCopySuffix") or "")
                if operation is SyncItemOperation.CREATE_REMOTE
                else ""
            )
            await self._push_file(
                job.id,
                file_id,
                safe_copy_suffix=safe_copy_suffix or None,
            )
        elif operation is SyncItemOperation.UPDATE_LOCAL:
            await self._pull_file(job.id, file_id)
        elif operation is SyncItemOperation.UPDATE_REMOTE_METADATA:
            await self._push_metadata(job.id, file_id)
        elif operation is SyncItemOperation.REMOTE_DELETE_DETECTED:
            await self._apply_remote_delete_policy(
                job_id=job.id,
                file_id=file_id,
                drive_id=item.remote_drive_id or "",
                item_id=item.remote_item_id or "",
                remote={
                    "id": item.remote_item_id,
                    "name": (item.metadata_json or {}).get("name"),
                    "deleted": {"state": "deleted"},
                },
                delete_policy=delete_policy,
            )
        async with self.session_factory() as session:
            item = await SharePointSyncRepository(session).get_item(
                item_id,
                for_update=True,
            )
            if item is None:
                return SyncItemStatus.FAILED
            item.status = (
                SyncItemStatus.SKIPPED
                if operation is SyncItemOperation.SKIP
                else SyncItemStatus.COMPLETED
            )
            item.completed_at = utc_now()
            await session.commit()
            final_status = item.status
        await self._refresh_parent_job(job.id)
        return final_status

    async def reconcile_file(
        self,
        file_id: UUID,
        *,
        worker_reference: str,
    ) -> SharePointSyncJobStatus:
        async with self.session_factory() as session:
            document_file = await DocumentFileRepository(session).get_by_id(
                file_id
            )
            if document_file is None:
                return SharePointSyncJobStatus.FAILED
            repository = SharePointSyncRepository(session)
            profile = await repository.resolve_profile(
                department_id=document_file.document.department_id,
                section_id=document_file.document.section_id,
                document_type_id=document_file.document.document_type_id,
                required_direction=None,
            )
            if profile is None:
                return SharePointSyncJobStatus.FAILED
            active = await repository.active_job(profile.id)
            if active is not None:
                return active.status
            job = SharePointSyncJob(
                sync_profile_id=profile.id,
                sharepoint_connection_id=profile.sharepoint_connection_id,
                job_type=SyncJobType.RECONCILIATION,
                direction=SyncDirection.BIDIRECTIONAL,
                status=SharePointSyncJobStatus.QUEUED,
                progress=0,
                current_stage="Queued for reconciliation",
                scope_json={"documentFileId": str(file_id)},
                maximum_attempts=max(
                    1,
                    int(
                        getattr(
                            self.settings,
                            "sharepoint_max_retries",
                            3,
                        )
                    )
                    + 1,
                ),
            )
            await repository.add_job(job)
            await session.commit()
        return await self.process_job(
            job.id,
            worker_reference=worker_reference,
        )

    async def fail_job(
        self,
        job_id: UUID,
        *,
        error_code: str,
        error_message: str,
    ) -> None:
        async with self.session_factory() as session:
            job = await SharePointSyncRepository(session).get_job(
                job_id,
                for_update=True,
            )
            if job is None or job.status in {
                SharePointSyncJobStatus.COMPLETED,
                SharePointSyncJobStatus.CANCELLED,
            }:
                return
            job.status = SharePointSyncJobStatus.FAILED
            job.progress = min(job.progress, 99)
            job.current_stage = "Failed"
            job.failed_at = utc_now()
            job.error_code = error_code[:100]
            job.error_message = error_message[:2000]
            await session.commit()

    async def fail_item(
        self,
        item_id: UUID,
        *,
        error_code: str,
        error_message: str,
    ) -> None:
        parent_job_id: UUID | None = None
        async with self.session_factory() as session:
            item = await SharePointSyncRepository(session).get_item(
                item_id,
                for_update=True,
            )
            if item is None or item.status in {
                SyncItemStatus.COMPLETED,
                SyncItemStatus.CANCELLED,
                SyncItemStatus.DEAD_LETTER,
            }:
                return
            item.status = SyncItemStatus.FAILED
            item.completed_at = utc_now()
            item.error_code = error_code[:100]
            item.error_message = error_message[:2000]
            parent_job_id = item.sync_job_id
            await session.commit()
        if parent_job_id is not None:
            await self._refresh_parent_job(parent_job_id)

    async def _claim_job(
        self,
        job_id: UUID,
        worker_reference: str,
    ) -> (
        tuple[SyncJobType, UUID | None]
        | SharePointSyncJobStatus
        | None
    ):
        async with self.session_factory() as session:
            repository = SharePointSyncRepository(session)
            job = await repository.get_job(job_id, for_update=True)
            if job is None:
                return None
            if job.status is SharePointSyncJobStatus.CANCEL_REQUESTED:
                job.status = SharePointSyncJobStatus.CANCELLED
                job.cancelled_at = utc_now()
                job.progress = 100
                await session.commit()
                return job.status
            if job.status in {
                SharePointSyncJobStatus.COMPLETED,
                SharePointSyncJobStatus.PARTIALLY_COMPLETED,
                SharePointSyncJobStatus.CANCELLED,
                SharePointSyncJobStatus.DEAD_LETTER,
            }:
                return job.status
            summary = dict(job.result_summary_json or {})
            claimed_by = summary.get("workerReference")
            if (
                job.status in {
                    SharePointSyncJobStatus.AUTHENTICATING,
                    SharePointSyncJobStatus.DISCOVERING,
                    SharePointSyncJobStatus.COMPARING,
                    SharePointSyncJobStatus.TRANSFERRING,
                    SharePointSyncJobStatus.UPDATING_METADATA,
                    SharePointSyncJobStatus.RESOLVING_CONFLICTS,
                    SharePointSyncJobStatus.PERSISTING,
                }
                and claimed_by
                and claimed_by != worker_reference
            ):
                return job.status
            job.status = SharePointSyncJobStatus.AUTHENTICATING
            job.progress = 5
            job.current_stage = "Authenticating with Microsoft Graph"
            job.started_at = job.started_at or utc_now()
            summary["workerReference"] = worker_reference
            job.result_summary_json = summary
            await session.commit()
            return job.job_type, self._file_scope(job)

    async def _push_file(
        self,
        job_id: UUID,
        file_id: UUID,
        *,
        safe_copy_suffix: str | None = None,
    ) -> None:
        async with self.session_factory() as session:
            job, connection, document_file = await self._job_context(
                session,
                job_id,
                file_id,
            )
            repository = SharePointMappingRepository(session)
            mapping = await repository.resolve_folder(
                connection_id=connection.id,
                department_id=document_file.document.department_id,
                section_id=document_file.document.section_id,
                document_type_id=document_file.document.document_type_id,
            )
            mappings = await repository.active_metadata_for_connection(
                connection.id
            )
            remote_folder = join_remote_path(
                connection.root_folder_path,
                mapping.remote_folder_path if mapping is not None else "",
            )
            remote_filename = self._remote_filename(document_file, mapping)
            if safe_copy_suffix:
                remote_filename = self._copy_filename(
                    remote_filename,
                    safe_copy_suffix,
                )
            remote_path = join_remote_path(remote_folder, remote_filename)
            storage_key = document_file.storage_key
            storage_provider = str(document_file.storage_provider).upper()
            was_linked = bool(
                getattr(document_file, "remote_item_id", None)
            )
            file_size = document_file.file_size
            job.status = SharePointSyncJobStatus.TRANSFERRING
            job.progress = 25
            job.current_stage = "Uploading file to SharePoint"
            await session.commit()

        graph = create_graph_client(self.settings)
        try:
            folders = SharePointFolderService(graph)
            if mapping is not None and mapping.create_folder_if_missing:
                await folders.ensure_path(
                    drive_id=self._drive_id(connection),
                    folder_path=remote_folder,
                )
            source_storage = self.local_storage
            close_source_storage = False
            if not await source_storage.exists(storage_key):
                if storage_provider.endswith(("SHAREPOINT", "HYBRID")):
                    source_storage = StorageFactory.get_storage(self.settings)
                    close_source_storage = True
                else:
                    raise FileNotFoundError(
                        "The local synchronization source is unavailable."
                    )
            stream = await source_storage.open(storage_key)
            try:
                upload = await SharePointUploadService(
                    graph,
                    simple_upload_max_bytes=int(
                        getattr(
                            self.settings,
                            "sharepoint_simple_upload_max_mb",
                            4,
                        )
                    )
                    * 1024
                    * 1024,
                    chunk_size_bytes=int(
                        getattr(
                            self.settings,
                            "sharepoint_upload_chunk_size_mb",
                            10,
                        )
                    )
                    * 1024
                    * 1024,
                    maximum_file_size_bytes=int(
                        getattr(
                            self.settings,
                            "sharepoint_upload_max_file_size_mb",
                            10_240,
                        )
                    )
                    * 1024
                    * 1024,
                ).upload(
                    drive_id=self._drive_id(connection),
                    remote_path=remote_path,
                    source=stream,
                    file_size=file_size,
                    conflict_behavior=(
                        "rename"
                        if safe_copy_suffix
                        else (
                            "replace"
                            if getattr(document_file, "remote_item_id", None)
                            else "fail"
                        )
                    ),
                )
            finally:
                stream.close()
                if close_source_storage:
                    await source_storage.close()
            if mappings:
                metadata_service = SharePointMetadataService(graph)
                fields = self._mapped_fields(
                    document_file,
                    mappings,
                    metadata_service=metadata_service,
                )
                if fields:
                    await metadata_service.update_fields(
                        drive_id=self._drive_id(connection),
                        item_id=self._remote_id(upload),
                        fields=fields,
                    )
            versions = await SharePointFileService(graph).list_versions(
                drive_id=self._drive_id(connection),
                item_id=self._remote_id(upload),
            )
        finally:
            await graph.close()

        async with self.session_factory() as session:
            job, _, current = await self._job_context(
                session,
                job_id,
                file_id,
            )
            self._apply_remote_metadata(
                current,
                connection_id=connection.id,
                drive_id=self._drive_id(connection),
                remote_path=remote_path,
                metadata=upload,
            )
            await self._record_version(
                session,
                document_file=current,
                job_id=job.id,
                metadata=upload,
                versions=versions,
            )
            if self._standalone_job(job):
                job.status = SharePointSyncJobStatus.COMPLETED
                job.progress = 100
                job.current_stage = "Completed"
                job.completed_at = utc_now()
                job.items_discovered = max(1, job.items_discovered)
                job.items_processed = max(1, job.items_processed)
                if was_linked:
                    job.items_updated = max(1, job.items_updated)
                else:
                    job.items_created = max(1, job.items_created)
            else:
                job.status = SharePointSyncJobStatus.TRANSFERRING
                job.current_stage = "Processing SharePoint sync items"
            await session.commit()

    async def _pull_file(self, job_id: UUID, file_id: UUID) -> None:
        async with self.session_factory() as session:
            job, _connection, document_file = await self._job_context(
                session,
                job_id,
                file_id,
            )
            drive_id = getattr(document_file, "remote_drive_id", None)
            item_id = getattr(document_file, "remote_item_id", None)
            if not drive_id or not item_id:
                raise ValueError("Document file has no SharePoint remote link.")
            job.status = SharePointSyncJobStatus.TRANSFERRING
            job.progress = 25
            job.current_stage = "Downloading file from SharePoint"
            await session.commit()

        artifact = await self._download_remote_artifact(
            drive_id=drive_id,
            item_id=item_id,
        )
        temporary = artifact.source
        remote = artifact.metadata
        versions = artifact.versions
        scan = artifact.scan
        size = artifact.size
        remote_name = str(
            remote.get("name") or document_file.original_filename
        )
        sanitized = self.paths.sanitize_filename(remote_name)
        new_file_id = uuid4()
        storage_key = self.paths.original_key(
            document_file.document_id,
            document_file.document_revision_id,
            new_file_id,
            sanitized,
        )
        stored = False
        try:
            await self.local_storage.save(temporary, storage_key)
            stored = True
            async with self.session_factory() as session:
                repository = DocumentFileRepository(session)
                old = await repository.get_by_id(file_id, for_update=True)
                loaded_job = await SharePointSyncRepository(session).get_job(
                    job_id,
                    for_update=True,
                )
                if old is None or loaded_job is None:
                    raise ValueError("SharePoint pull source no longer exists.")
                job = loaded_job
                extension = PurePosixPath(sanitized).suffix.lower().lstrip(".")
                if extension not in {"pdf", "docx", "xlsx"}:
                    raise ValueError("Remote SharePoint file type is unsupported.")
                await repository.prepare_replacement(
                    old,
                    replaced_at=utc_now(),
                )
                new_file = DocumentFile(
                    id=new_file_id,
                    document_id=old.document_id,
                    document_revision_id=old.document_revision_id,
                    original_filename=remote_name,
                    sanitized_filename=sanitized,
                    file_extension=extension,
                    mime_type=self._remote_mime(remote, old.mime_type),
                    detected_mime_type=self._remote_mime(
                        remote,
                        old.detected_mime_type,
                    ),
                    file_size=size,
                    sha256_hash=artifact.sha256_hash,
                    storage_provider="HYBRID",
                    storage_key=storage_key,
                    storage_bucket=None,
                    file_status=DocumentFileStatus.AVAILABLE,
                    is_primary=True,
                    is_current=True,
                    uploaded_by=job.requested_by,
                    metadata_json={
                        "sharePointInbound": True,
                        "sourceDocumentFileId": str(old.id),
                        "malwareScanStatus": scan.status.value,
                    },
                )
                self._apply_remote_metadata(
                    new_file,
                    connection_id=job.sharepoint_connection_id,
                    drive_id=drive_id,
                    remote_path=str(
                        remote.get("parentReference", {}).get("path", "")
                    ),
                    metadata=remote,
                )
                await repository.create(new_file)
                await repository.link_replacement(
                    old,
                    replacement_id=new_file.id,
                )
                await self._record_version(
                    session,
                    document_file=new_file,
                    job_id=job.id,
                    metadata=remote,
                    versions=versions,
                )
                if self._standalone_job(job):
                    job.status = SharePointSyncJobStatus.COMPLETED
                    job.progress = 100
                    job.current_stage = "Completed"
                    job.completed_at = utc_now()
                    job.items_discovered = max(1, job.items_discovered)
                    job.items_processed = max(1, job.items_processed)
                    job.items_created = max(1, job.items_created)
                else:
                    job.status = SharePointSyncJobStatus.TRANSFERRING
                    job.current_stage = "Processing SharePoint sync items"
                await session.commit()
        except Exception:
            if stored and await self.local_storage.exists(storage_key):
                await self.local_storage.delete(storage_key)
            raise
        finally:
            temporary.close()

    async def _download_remote_artifact(
        self,
        *,
        drive_id: str,
        item_id: str,
    ) -> _DownloadedRemoteArtifact:
        graph = create_graph_client(self.settings)
        temporary = tempfile.SpooledTemporaryFile(  # noqa: SIM115
            max_size=8 * 1024 * 1024,
            mode="w+b",
        )
        digest = hashlib.sha256()
        size = 0
        try:
            try:
                remote = await SharePointFileService(graph).get_metadata(
                    drive_id=drive_id,
                    item_id=item_id,
                )
                async for chunk in SharePointDownloadService(graph).stream(
                    drive_id=drive_id,
                    item_id=item_id,
                ):
                    temporary.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                temporary.seek(0)
                scan = await self.malware_scanner.scan(
                    self._temporary_chunks(temporary),
                    filename=str(remote.get("name") or ""),
                )
                temporary.seek(0)
                if not scan.allowed:
                    raise ValueError("FILE_QUARANTINED")
                versions = await SharePointFileService(
                    graph
                ).list_versions(
                    drive_id=drive_id,
                    item_id=item_id,
                )
                return _DownloadedRemoteArtifact(
                    source=cast(BinaryIO, temporary),
                    metadata=remote,
                    versions=versions,
                    sha256_hash=digest.hexdigest(),
                    size=size,
                    scan=scan,
                )
            finally:
                await graph.close()
        except BaseException:
            temporary.close()
            raise

    async def _create_local_file(
        self,
        *,
        job_id: UUID,
        sync_item_id: UUID,
        document_id: UUID,
        revision_id: UUID,
        drive_id: str,
        item_id: str,
    ) -> None:
        artifact = await self._download_remote_artifact(
            drive_id=drive_id,
            item_id=item_id,
        )
        remote_name = str(
            artifact.metadata.get("name") or "sharepoint-document"
        )
        sanitized = self.paths.sanitize_filename(remote_name)
        extension = PurePosixPath(sanitized).suffix.lower().lstrip(".")
        if extension not in {"pdf", "docx", "xlsx"}:
            artifact.source.close()
            raise ValueError("Remote SharePoint file type is unsupported.")
        new_file_id = uuid4()
        storage_key = self.paths.original_key(
            document_id,
            revision_id,
            new_file_id,
            sanitized,
        )
        stored = False
        try:
            await self.local_storage.save(artifact.source, storage_key)
            stored = True
            async with self.session_factory() as session:
                job = await SharePointSyncRepository(session).get_job(
                    job_id,
                    for_update=True,
                )
                item = await SharePointSyncRepository(session).get_item(
                    sync_item_id,
                    for_update=True,
                )
                revision = await DocumentRevisionRepository(
                    session
                ).get_by_id(
                    revision_id,
                    document_id=document_id,
                )
                if job is None or item is None or revision is None:
                    raise ValueError(
                        "Inbound SharePoint mapping no longer exists."
                    )
                files = DocumentFileRepository(session)
                old = await files.get_current_by_revision(
                    revision_id,
                    for_update=True,
                )
                if old is not None:
                    await files.prepare_replacement(
                        old,
                        replaced_at=utc_now(),
                    )
                new_file = DocumentFile(
                    id=new_file_id,
                    document_id=document_id,
                    document_revision_id=revision_id,
                    original_filename=remote_name,
                    sanitized_filename=sanitized,
                    file_extension=extension,
                    mime_type=self._remote_mime(
                        artifact.metadata,
                        "application/octet-stream",
                    ),
                    detected_mime_type=self._remote_mime(
                        artifact.metadata,
                        "application/octet-stream",
                    ),
                    file_size=artifact.size,
                    sha256_hash=artifact.sha256_hash,
                    storage_provider="HYBRID",
                    storage_key=storage_key,
                    storage_bucket=None,
                    file_status=DocumentFileStatus.AVAILABLE,
                    is_primary=True,
                    is_current=True,
                    uploaded_by=job.requested_by,
                    metadata_json={
                        "sharePointInbound": True,
                        "malwareScanStatus": artifact.scan.status.value,
                    },
                )
                self._apply_remote_metadata(
                    new_file,
                    connection_id=job.sharepoint_connection_id,
                    drive_id=drive_id,
                    remote_path=str(
                        artifact.metadata.get(
                            "parentReference",
                            {},
                        ).get("path", "")
                    ),
                    metadata=artifact.metadata,
                )
                await files.create(new_file)
                if old is not None:
                    await files.link_replacement(
                        old,
                        replacement_id=new_file.id,
                    )
                item.document_file_id = new_file.id
                await self._record_version(
                    session,
                    document_file=new_file,
                    job_id=job.id,
                    metadata=artifact.metadata,
                    versions=artifact.versions,
                )
                await session.commit()
        except Exception:
            if stored and await self.local_storage.exists(storage_key):
                await self.local_storage.delete(storage_key)
            raise
        finally:
            artifact.source.close()

    async def _push_metadata(self, job_id: UUID, file_id: UUID) -> None:
        async with self.session_factory() as session:
            job, connection, document_file = await self._job_context(
                session,
                job_id,
                file_id,
            )
            remote_item_id = getattr(
                document_file,
                "remote_item_id",
                None,
            )
            if not remote_item_id:
                raise ValueError(
                    "Document file has no SharePoint metadata target."
                )
            mappings = await SharePointMappingRepository(
                session
            ).active_metadata_for_connection(connection.id)
            await session.commit()
        graph = create_graph_client(self.settings)
        try:
            metadata_service = SharePointMetadataService(graph)
            fields = self._mapped_fields(
                document_file,
                mappings,
                metadata_service=metadata_service,
            )
            if fields:
                await metadata_service.update_fields(
                    drive_id=self._drive_id(connection),
                    item_id=remote_item_id,
                    fields=fields,
                )
        finally:
            await graph.close()
        async with self.session_factory() as session:
            loaded_job = await SharePointSyncRepository(session).get_job(
                job_id,
                for_update=True,
            )
            loaded_document_file = await DocumentFileRepository(
                session
            ).get_by_id(
                file_id,
                for_update=True,
            )
            if loaded_job is None or loaded_document_file is None:
                return
            job = loaded_job
            document_file = loaded_document_file
            document_file.remote_sync_status = RemoteSyncStatus.SYNCED
            document_file.last_synced_at = utc_now()
            if self._standalone_job(job):
                job.status = SharePointSyncJobStatus.COMPLETED
                job.progress = 100
                job.current_stage = "SharePoint metadata updated"
                job.completed_at = utc_now()
            else:
                job.status = SharePointSyncJobStatus.TRANSFERRING
                job.current_stage = "Processing SharePoint sync items"
            await session.commit()

    async def _reconcile_file(self, job_id: UUID, file_id: UUID) -> None:
        async with self.session_factory() as session:
            job, _, document_file = await self._job_context(
                session,
                job_id,
                file_id,
            )
            profile = await SharePointSyncRepository(session).get_profile(
                job.sync_profile_id
            )
            if profile is None:
                raise ValueError("SharePoint sync profile was not found.")
            drive_id = getattr(document_file, "remote_drive_id", None)
            item_id = getattr(document_file, "remote_item_id", None)
            if not drive_id or not item_id:
                await session.commit()
                await self._push_file(job_id, file_id)
                return
            baseline_etag = getattr(document_file, "remote_etag", None)
            versions, _ = await SharePointFileVersionRepository(
                session
            ).list_page(
                file_id,
                page=1,
                page_size=1,
            )
            baseline_hash = (
                versions[0].local_sha256_hash if versions else None
            )
            local_hash = document_file.sha256_hash
            local_modified_at = document_file.uploaded_at
            local_path = getattr(document_file, "remote_path", None)
            await session.commit()
        graph = create_graph_client(self.settings)
        try:
            try:
                remote = await SharePointFileService(graph).get_metadata(
                    drive_id=drive_id,
                    item_id=item_id,
                )
            except GraphError as exc:
                if exc.status_code != 404:
                    raise
                remote = {
                    "id": item_id,
                    "deleted": {"state": "deleted"},
                    "name": document_file.original_filename,
                }
        finally:
            await graph.close()
        engine = SharePointSyncEngine()
        decision = engine.decide(
            direction=SyncDirection.BIDIRECTIONAL,
            conflict_policy=profile.conflict_policy,
            local=LocalSyncState(
                document_file_id=str(file_id),
                content_hash=local_hash,
                modified_at=local_modified_at,
                path=local_path,
            ),
            remote=RemoteSyncState(
                item_id=item_id,
                etag=(
                    str(remote["eTag"]) if remote.get("eTag") else None
                ),
                modified_at=self._parse_datetime(
                    remote.get("lastModifiedDateTime")
                ),
                path=self._remote_path(remote),
                deleted="deleted" in remote,
                content_hash=self._remote_hash(remote),
            ),
            baseline=(
                SyncBaseline(
                    local_content_hash=baseline_hash,
                    remote_etag=versions[0].remote_etag,
                )
                if versions
                else None
            ),
        )
        if decision.operation is SyncItemOperation.UPDATE_REMOTE:
            await self._push_file(job_id, file_id)
            return
        if decision.operation is SyncItemOperation.UPDATE_LOCAL:
            await self._pull_file(job_id, file_id)
            return
        if decision.create_copy:
            await self._push_file(
                job_id,
                file_id,
                safe_copy_suffix=f"conflict-{str(job_id)[:8]}",
            )
            return
        if decision.operation is SyncItemOperation.SKIP:
            await self._complete_reconciliation(
                job_id,
                stage="No changes detected",
            )
            return
        if decision.operation is SyncItemOperation.REMOTE_DELETE_DETECTED:
            await self._apply_remote_delete_policy(
                job_id=job_id,
                file_id=file_id,
                drive_id=drive_id,
                item_id=item_id,
                remote=remote,
                delete_policy=profile.delete_policy,
            )
            return
        await self._record_reconciliation_conflict(
            job_id=job_id,
            file_id=file_id,
            drive_id=drive_id,
            item_id=item_id,
            local_hash=local_hash,
            baseline_hash=baseline_hash,
            baseline_etag=baseline_etag,
            remote=remote,
            conflict_type=(
                decision.conflict_type or SyncConflictType.VERSION_MISMATCH
            ),
        )

    async def _complete_reconciliation(
        self,
        job_id: UUID,
        *,
        stage: str,
    ) -> None:
        async with self.session_factory() as session:
            job = await SharePointSyncRepository(session).get_job(
                job_id,
                for_update=True,
            )
            if job is None:
                return
            job.status = SharePointSyncJobStatus.COMPLETED
            job.progress = 100
            job.current_stage = stage
            job.completed_at = utc_now()
            job.items_discovered = 1
            job.items_processed = 1
            job.items_skipped = 1
            await session.commit()

    async def _apply_remote_delete_policy(
        self,
        *,
        job_id: UUID,
        file_id: UUID,
        drive_id: str,
        item_id: str,
        remote: dict[str, Any],
        delete_policy: DeletePolicy,
    ) -> None:
        async with self.session_factory() as session:
            repository = SharePointSyncRepository(session)
            job = await repository.get_job(job_id, for_update=True)
            document_file = await DocumentFileRepository(session).get_by_id(
                file_id,
                for_update=True,
            )
            if job is None or document_file is None:
                raise ValueError("SharePoint delete context no longer exists.")
            key = SharePointSyncEngine.idempotency_key(
                sync_profile_id=str(job.sync_profile_id),
                remote_item_id=item_id,
                remote_etag=None,
                local_content_hash=document_file.sha256_hash,
                operation=SyncItemOperation.REMOTE_DELETE_DETECTED,
            )
            if await repository.get_item_by_idempotency(key) is None:
                await repository.add_item(
                    SharePointSyncItem(
                        sync_job_id=job.id,
                        document_id=document_file.document_id,
                        document_revision_id=(
                            document_file.document_revision_id
                        ),
                        document_file_id=document_file.id,
                        remote_drive_id=drive_id,
                        remote_item_id=item_id,
                        remote_path=self._remote_path(remote),
                        operation=SyncItemOperation.REMOTE_DELETE_DETECTED,
                        status=SyncItemStatus.COMPLETED,
                        idempotency_key=key,
                        local_hash_before=document_file.sha256_hash,
                        metadata_json={"deletePolicy": delete_policy.value},
                        completed_at=utc_now(),
                    )
                )
            stage = "Remote delete ignored by policy"
            if delete_policy is DeletePolicy.MARK_MISSING:
                document_file.remote_sync_status = (
                    RemoteSyncStatus.REMOTE_MISSING
                )
                stage = "Remote file marked missing"
            elif delete_policy is DeletePolicy.ARCHIVE_LOCAL:
                document_file.document.is_archived = True
                document_file.document.archived_at = utc_now()
                document_file.document.archived_by = job.requested_by
                document_file.document.archive_reason = (
                    "Archived by configured SharePoint remote-delete policy."
                )
                document_file.remote_sync_status = (
                    RemoteSyncStatus.REMOTE_MISSING
                )
                stage = "Local document archived by remote-delete policy"
            elif delete_policy is DeletePolicy.DELETE_LOCAL_SOFT:
                document_file.is_current = False
                document_file.file_status = DocumentFileStatus.DELETED
                document_file.deleted_at = utc_now()
                document_file.deleted_by = job.requested_by
                document_file.deletion_reason = (
                    "Soft-deleted by configured SharePoint remote-delete "
                    "policy."
                )
                document_file.remote_sync_status = (
                    RemoteSyncStatus.REMOTE_MISSING
                )
                stage = "Local file soft-deleted by remote-delete policy"
            if self._standalone_job(job):
                job.status = SharePointSyncJobStatus.COMPLETED
                job.progress = 100
                job.current_stage = stage
                job.completed_at = utc_now()
                job.items_discovered = 1
                job.items_processed = 1
                job.items_updated = (
                    0
                    if delete_policy is DeletePolicy.IGNORE_REMOTE_DELETE
                    else 1
                )
                job.items_skipped = (
                    1
                    if delete_policy is DeletePolicy.IGNORE_REMOTE_DELETE
                    else 0
                )
            else:
                job.status = SharePointSyncJobStatus.TRANSFERRING
                job.current_stage = "Processing SharePoint sync items"
            await session.commit()

    async def _record_reconciliation_conflict(
        self,
        *,
        job_id: UUID,
        file_id: UUID,
        drive_id: str,
        item_id: str,
        local_hash: str,
        baseline_hash: str | None,
        baseline_etag: str | None,
        remote: dict[str, Any],
        conflict_type: SyncConflictType,
    ) -> None:
        remote_etag = (
            str(remote["eTag"]) if remote.get("eTag") else None
        )
        async with self.session_factory() as session:
            repository = SharePointSyncRepository(session)
            job = await repository.get_job(job_id, for_update=True)
            document_file = await DocumentFileRepository(session).get_by_id(
                file_id,
                for_update=True,
            )
            if job is None or document_file is None:
                raise ValueError("SharePoint conflict context no longer exists.")
            idempotency_key = SharePointSyncEngine.idempotency_key(
                sync_profile_id=str(job.sync_profile_id),
                remote_item_id=item_id,
                remote_etag=remote_etag,
                local_content_hash=local_hash,
                operation=SyncItemOperation.CONFLICT,
            )
            existing = await repository.get_item_by_idempotency(
                idempotency_key
            )
            if existing is not None:
                job.status = SharePointSyncJobStatus.PARTIALLY_COMPLETED
                job.progress = 100
                job.current_stage = "Existing conflict requires review"
                job.completed_at = utc_now()
                job.items_conflicted = 1
                await session.commit()
                return
            item = SharePointSyncItem(
                sync_job_id=job.id,
                document_id=document_file.document_id,
                document_revision_id=document_file.document_revision_id,
                document_file_id=document_file.id,
                remote_drive_id=drive_id,
                remote_item_id=item_id,
                remote_path=self._remote_path(remote),
                operation=SyncItemOperation.CONFLICT,
                status=SyncItemStatus.CONFLICT,
                idempotency_key=idempotency_key,
                local_hash_before=baseline_hash,
                local_hash_after=local_hash,
                remote_etag_before=baseline_etag,
                remote_etag_after=remote_etag,
                remote_size=int(remote.get("size", 0) or 0),
                metadata_json={"reason": "Both sides changed since last sync."},
                completed_at=utc_now(),
            )
            await repository.add_item(item)
            conflict = SharePointSyncConflict(
                sync_job_id=job.id,
                sync_item_id=item.id,
                document_id=document_file.document_id,
                document_revision_id=document_file.document_revision_id,
                document_file_id=document_file.id,
                remote_item_id=item_id,
                conflict_type=conflict_type,
                local_version_json={
                    "sha256": local_hash,
                    "baselineSha256": baseline_hash,
                    "filename": document_file.original_filename,
                },
                remote_version_json={
                    "eTag": remote_etag,
                    "baselineETag": baseline_etag,
                    "size": int(remote.get("size", 0) or 0),
                    "lastModifiedDateTime": remote.get(
                        "lastModifiedDateTime"
                    ),
                    "name": remote.get("name"),
                },
            )
            await SharePointConflictRepository(session).add(conflict)
            item.conflict_id = conflict.id
            job.status = SharePointSyncJobStatus.PARTIALLY_COMPLETED
            job.progress = 100
            job.current_stage = "Remote change requires conflict review"
            job.completed_at = utc_now()
            job.items_discovered = 1
            job.items_processed = 1
            job.items_conflicted = 1
            await session.commit()

    async def _discover_delta(self, job_id: UUID) -> None:
        cipher = self._integration_cipher()
        delta_link: str | None = None
        async with self.session_factory() as session:
            repository = SharePointSyncRepository(session)
            job = await repository.get_job(job_id, for_update=True)
            if job is None:
                return
            profile = await repository.get_profile(job.sync_profile_id)
            connection = await SharePointConnectionRepository(
                session
            ).get_by_id(job.sharepoint_connection_id)
            if profile is None or connection is None:
                raise ValueError("SharePoint sync configuration was not found.")
            drive_id = self._drive_id(connection)
            state_service = (
                SharePointDeltaStateService(session, cipher)
                if cipher is not None
                else None
            )
            if (
                state_service is not None
                and job.job_type
                in {
                    SyncJobType.MANUAL_INCREMENTAL,
                    SyncJobType.SCHEDULED_INCREMENTAL,
                    SyncJobType.WEBHOOK_INCREMENTAL,
                }
            ):
                delta_link = await state_service.load(
                    profile_id=profile.id,
                    drive_id=drive_id,
                    folder_item_id=None,
                )
                state = await repository.get_delta_state(
                    profile_id=profile.id,
                    drive_id=drive_id,
                    folder_item_id=None,
                )
                if state is not None and state.is_valid:
                    job.delta_token_before = state.delta_token_hash
            job.status = SharePointSyncJobStatus.DISCOVERING
            job.progress = 15
            job.current_stage = "Discovering SharePoint changes"
            await session.commit()

        graph = create_graph_client(self.settings)
        try:
            # Full jobs deliberately start from root; incremental jobs use a
            # previously encrypted cursor once the root integration supplies it.
            result = await SharePointDeltaService(graph).collect_changes(
                drive_id=drive_id,
                delta_link=delta_link,
            )
        except SharePointDeltaTokenInvalid:
            async with self.session_factory() as session:
                if cipher is not None:
                    await SharePointDeltaStateService(
                        session,
                        cipher,
                    ).invalidate(
                        profile_id=profile.id,
                        drive_id=drive_id,
                        folder_item_id=None,
                        reason="Microsoft Graph rejected the delta token.",
                    )
                    await session.commit()
            result = await SharePointDeltaService(graph).collect_changes(
                drive_id=drive_id,
                delta_link=None,
            )
        finally:
            await graph.close()

        queued_item_ids: list[UUID] = []
        async with self.session_factory() as session:
            repository = SharePointSyncRepository(session)
            job = await repository.get_job(job_id, for_update=True)
            current_profile = (
                await repository.get_profile(job.sync_profile_id)
                if job is not None
                else None
            )
            if job is None or current_profile is None:
                return
            if job.status is SharePointSyncJobStatus.CANCEL_REQUESTED:
                job.status = SharePointSyncJobStatus.CANCELLED
                job.cancelled_at = utc_now()
                job.progress = 100
                await session.commit()
                return
            job.status = SharePointSyncJobStatus.COMPARING
            job.progress = 45
            job.current_stage = "Comparing discovered SharePoint items"
            discovered = skipped = conflicted = failed = 0
            seen_file_ids: set[UUID] = set()
            for remote in result.items:
                if "folder" in remote:
                    continue
                item_id = str(remote.get("id") or "")
                if not item_id:
                    continue
                remote_etag = (
                    str(remote["eTag"]) if remote.get("eTag") else None
                )
                deleted = "deleted" in remote
                document_file = (
                    await repository.get_document_file_by_remote(
                        drive_id=drive_id,
                        item_id=item_id,
                    )
                )
                matched_revision: DocumentRevision | None = None
                if (
                    document_file is None
                    and not deleted
                    and job.direction is not SyncDirection.OUTBOUND
                ):
                    (
                        matched_revision,
                        document_file,
                    ) = await self._resolve_inbound_target(
                        session,
                        repository=repository,
                        profile=current_profile,
                        connection_id=job.sharepoint_connection_id,
                        drive_id=drive_id,
                        item_id=item_id,
                        remote=remote,
                    )
                if document_file is not None:
                    seen_file_ids.add(document_file.id)
                baseline_hash: str | None = None
                decision_operation: SyncItemOperation
                conflict_type: SyncConflictType | None = None
                create_copy = False
                if document_file is None:
                    decision = SharePointSyncEngine().decide(
                        direction=job.direction,
                        conflict_policy=current_profile.conflict_policy,
                        local=None,
                        remote=RemoteSyncState(
                            item_id=item_id,
                            etag=remote_etag,
                            modified_at=self._parse_datetime(
                                remote.get("lastModifiedDateTime")
                            ),
                            path=self._remote_path(remote),
                            deleted=deleted,
                            content_hash=self._remote_hash(remote),
                        ),
                        baseline=None,
                    )
                    decision_operation = decision.operation
                else:
                    versions, _ = await SharePointFileVersionRepository(
                        session
                    ).list_page(
                        document_file.id,
                        page=1,
                        page_size=1,
                    )
                    baseline_hash = (
                        versions[0].local_sha256_hash if versions else None
                    )
                    decision = SharePointSyncEngine().decide(
                        direction=job.direction,
                        conflict_policy=current_profile.conflict_policy,
                        local=LocalSyncState(
                            document_file_id=str(document_file.id),
                            content_hash=document_file.sha256_hash,
                            modified_at=document_file.uploaded_at,
                            path=getattr(
                                document_file,
                                "remote_path",
                                None,
                            ),
                        ),
                        remote=RemoteSyncState(
                            item_id=item_id,
                            etag=remote_etag,
                            modified_at=self._parse_datetime(
                                remote.get("lastModifiedDateTime")
                            ),
                            path=self._remote_path(remote),
                            deleted=deleted,
                            content_hash=self._remote_hash(remote),
                        ),
                        baseline=(
                            SyncBaseline(
                                local_content_hash=baseline_hash,
                                remote_etag=versions[0].remote_etag,
                            )
                            if versions
                            else None
                        ),
                    )
                    decision_operation = decision.operation
                    conflict_type = decision.conflict_type
                    create_copy = decision.create_copy
                local_hash = (
                    document_file.sha256_hash
                    if document_file is not None
                    else None
                )
                key = SharePointSyncEngine.idempotency_key(
                    sync_profile_id=str(job.sync_profile_id),
                    remote_item_id=item_id,
                    remote_etag=remote_etag,
                    local_content_hash=local_hash,
                    operation=decision_operation,
                )
                if await repository.get_item_by_idempotency(key) is not None:
                    skipped += 1
                    continue
                is_unmapped = (
                    document_file is None
                    and matched_revision is None
                    and decision_operation is SyncItemOperation.CREATE_LOCAL
                )
                item_status = (
                    SyncItemStatus.SKIPPED
                    if decision_operation is SyncItemOperation.SKIP
                    else (
                        SyncItemStatus.CONFLICT
                        if decision_operation is SyncItemOperation.CONFLICT
                        else (
                            SyncItemStatus.FAILED
                            if is_unmapped
                            else SyncItemStatus.QUEUED
                        )
                    )
                )
                item = SharePointSyncItem(
                    sync_job_id=job.id,
                    document_id=(
                        document_file.document_id
                        if document_file is not None
                        else (
                            matched_revision.document_id
                            if matched_revision is not None
                            else None
                        )
                    ),
                    document_revision_id=(
                        document_file.document_revision_id
                        if document_file is not None
                        else (
                            matched_revision.id
                            if matched_revision is not None
                            else None
                        )
                    ),
                    document_file_id=(
                        document_file.id
                        if document_file is not None
                        else None
                    ),
                    remote_drive_id=drive_id,
                    remote_item_id=item_id,
                    remote_path=self._remote_path(remote),
                    operation=decision_operation,
                    status=item_status,
                    idempotency_key=key,
                    local_hash_before=baseline_hash,
                    local_hash_after=local_hash,
                    remote_etag_before=(
                        getattr(document_file, "remote_etag", None)
                        if document_file is not None
                        else None
                    ),
                    remote_etag_after=remote_etag,
                    remote_size=int(remote.get("size", 0) or 0),
                    error_code=(
                        "SHAREPOINT_INBOUND_MAPPING_REQUIRED"
                        if is_unmapped
                        else None
                    ),
                    error_message=(
                        "Remote item requires an internal document mapping."
                        if is_unmapped
                        else None
                    ),
                    metadata_json={
                        "deleted": deleted,
                        "name": remote.get("name"),
                        "deletePolicy": current_profile.delete_policy.value,
                        **(
                            {
                                "safeCopySuffix": (
                                    f"conflict-{str(job.id)[:8]}"
                                )
                            }
                            if create_copy
                            else {}
                        ),
                    },
                    completed_at=(
                        utc_now()
                        if item_status
                        in {
                            SyncItemStatus.SKIPPED,
                            SyncItemStatus.CONFLICT,
                            SyncItemStatus.FAILED,
                        }
                        else None
                    ),
                )
                await repository.add_item(item)
                discovered += 1
                if item_status is SyncItemStatus.SKIPPED:
                    skipped += 1
                elif item_status is SyncItemStatus.CONFLICT:
                    conflicted += 1
                    conflict = SharePointSyncConflict(
                        sync_job_id=job.id,
                        sync_item_id=item.id,
                        document_id=item.document_id,
                        document_revision_id=item.document_revision_id,
                        document_file_id=item.document_file_id,
                        remote_item_id=item_id,
                        conflict_type=(
                            conflict_type
                            or SyncConflictType.VERSION_MISMATCH
                        ),
                        local_version_json={
                            "sha256": local_hash,
                            "baselineSha256": baseline_hash,
                        },
                        remote_version_json={
                            "eTag": remote_etag,
                            "size": item.remote_size,
                            "name": remote.get("name"),
                        },
                    )
                    await SharePointConflictRepository(session).add(conflict)
                    item.conflict_id = conflict.id
                elif item_status is SyncItemStatus.FAILED:
                    failed += 1
                else:
                    queued_item_ids.append(item.id)
            (
                local_item_ids,
                local_discovered,
                local_skipped,
                local_conflicted,
            ) = await self._plan_local_profile_items(
                session,
                repository=repository,
                job=job,
                profile=current_profile,
                drive_id=drive_id,
                seen_file_ids=seen_file_ids,
            )
            queued_item_ids.extend(local_item_ids)
            discovered += local_discovered
            skipped += local_skipped
            conflicted += local_conflicted
            job.items_discovered = discovered
            job.items_skipped = skipped
            job.items_conflicted = conflicted
            job.items_failed = failed
            job.status = (
                SharePointSyncJobStatus.TRANSFERRING
                if queued_item_ids
                else (
                    SharePointSyncJobStatus.PARTIALLY_COMPLETED
                    if conflicted or failed
                    else SharePointSyncJobStatus.COMPLETED
                )
            )
            job.current_stage = (
                "Processing mapped SharePoint changes"
                if queued_item_ids
                else (
                    "Some changes require review or mapping"
                    if conflicted or failed
                    else "Completed"
                )
            )
            job.progress = 60 if queued_item_ids else 100
            if not queued_item_ids:
                job.completed_at = utc_now()
            job.result_summary_json = {
                **(job.result_summary_json or {}),
                "deltaTokenCandidateHash": hashlib.sha256(
                    result.delta_link.encode()
                ).hexdigest(),
                "deltaTokenPersisted": False,
                "deltaPageCount": result.page_count,
            }
            await session.commit()

        for index, queued_item_id in enumerate(queued_item_ids):
            if await self._cancel_job_if_requested(
                job_id,
                queued_item_ids[index:],
            ):
                return
            await self.process_item(queued_item_id)
        if await self._cancel_job_if_requested(job_id, []):
            return

        async with self.session_factory() as session:
            repository = SharePointSyncRepository(session)
            job = await repository.get_job(job_id, for_update=True)
            if job is None:
                return
            items, _ = await repository.list_items(
                job_id,
                page=1,
                page_size=max(1, job.items_discovered),
            )
            job.items_processed = sum(
                item.status
                in {
                    SyncItemStatus.COMPLETED,
                    SyncItemStatus.SKIPPED,
                    SyncItemStatus.CONFLICT,
                    SyncItemStatus.FAILED,
                }
                for item in items
            )
            job.items_failed = sum(
                item.status is SyncItemStatus.FAILED for item in items
            )
            job.items_conflicted = sum(
                item.status is SyncItemStatus.CONFLICT for item in items
            )
            job.items_skipped = sum(
                item.status is SyncItemStatus.SKIPPED for item in items
            )
            job.items_created = sum(
                item.status is SyncItemStatus.COMPLETED
                and item.operation
                in {
                    SyncItemOperation.CREATE_LOCAL,
                    SyncItemOperation.CREATE_REMOTE,
                }
                for item in items
            )
            job.items_updated = sum(
                item.status is SyncItemStatus.COMPLETED
                and item.operation
                in {
                    SyncItemOperation.UPDATE_LOCAL,
                    SyncItemOperation.UPDATE_REMOTE,
                    SyncItemOperation.UPDATE_LOCAL_METADATA,
                    SyncItemOperation.UPDATE_REMOTE_METADATA,
                    SyncItemOperation.REMOTE_DELETE_DETECTED,
                }
                for item in items
            )
            job.status = (
                SharePointSyncJobStatus.PARTIALLY_COMPLETED
                if job.items_failed or job.items_conflicted
                else SharePointSyncJobStatus.COMPLETED
            )
            job.progress = 100
            job.current_stage = (
                "Some changes require review or mapping"
                if job.status is SharePointSyncJobStatus.PARTIALLY_COMPLETED
                else "Completed"
            )
            job.completed_at = utc_now()
            if (
                job.status is SharePointSyncJobStatus.COMPLETED
                and cipher is not None
            ):
                await SharePointDeltaStateService(
                    session,
                    cipher,
                ).commit_after_success(
                    job=job,
                    drive_id=drive_id,
                    folder_item_id=None,
                    delta_link=result.delta_link,
                )
                result_summary = dict(job.result_summary_json or {})
                result_summary["deltaTokenPersisted"] = True
                job.result_summary_json = result_summary
            elif (
                job.status is SharePointSyncJobStatus.COMPLETED
                and bool(
                    getattr(
                        self.settings,
                        "sharepoint_delta_sync_enabled",
                        True,
                    )
                )
            ):
                job.status = SharePointSyncJobStatus.PARTIALLY_COMPLETED
                job.error_code = "ENCRYPTION_FAILED"
                job.error_message = (
                    "Delta cursor was not persisted because integration "
                    "state encryption is unavailable."
                )
            await session.commit()

    async def _cancel_job_if_requested(
        self,
        job_id: UUID,
        remaining_item_ids: list[UUID],
    ) -> bool:
        async with self.session_factory() as session:
            repository = SharePointSyncRepository(session)
            job = await repository.get_job(job_id, for_update=True)
            if (
                job is None
                or job.status
                not in {
                    SharePointSyncJobStatus.CANCEL_REQUESTED,
                    SharePointSyncJobStatus.CANCELLED,
                }
            ):
                return False
            now = utc_now()
            for item_id in remaining_item_ids:
                item = await repository.get_item(item_id, for_update=True)
                if item is not None and item.status is SyncItemStatus.QUEUED:
                    item.status = SyncItemStatus.CANCELLED
                    item.completed_at = now
            job.status = SharePointSyncJobStatus.CANCELLED
            job.cancelled_at = job.cancelled_at or now
            job.progress = 100
            job.current_stage = "Cancelled"
            await session.commit()
            return True

    async def _refresh_parent_job(self, job_id: UUID) -> None:
        async with self.session_factory() as session:
            repository = SharePointSyncRepository(session)
            job = await repository.get_job(job_id, for_update=True)
            if job is None or self._standalone_job(job):
                return
            if job.status in {
                SharePointSyncJobStatus.CANCEL_REQUESTED,
                SharePointSyncJobStatus.CANCELLED,
                SharePointSyncJobStatus.DEAD_LETTER,
            }:
                return
            items = await repository.list_all_items(job_id)
            if any(
                item.status
                in {
                    SyncItemStatus.QUEUED,
                    SyncItemStatus.PROCESSING,
                }
                for item in items
            ):
                job.status = SharePointSyncJobStatus.TRANSFERRING
                job.current_stage = "Processing SharePoint sync items"
                await session.commit()
                return
            terminal_statuses = {
                SyncItemStatus.COMPLETED,
                SyncItemStatus.SKIPPED,
                SyncItemStatus.CONFLICT,
                SyncItemStatus.FAILED,
                SyncItemStatus.CANCELLED,
                SyncItemStatus.DEAD_LETTER,
            }
            job.items_discovered = max(job.items_discovered, len(items))
            job.items_processed = sum(
                item.status in terminal_statuses for item in items
            )
            job.items_failed = sum(
                item.status
                in {
                    SyncItemStatus.FAILED,
                    SyncItemStatus.DEAD_LETTER,
                }
                for item in items
            )
            job.items_conflicted = sum(
                item.status is SyncItemStatus.CONFLICT for item in items
            )
            job.items_skipped = sum(
                item.status is SyncItemStatus.SKIPPED for item in items
            )
            job.items_created = sum(
                item.status is SyncItemStatus.COMPLETED
                and item.operation
                in {
                    SyncItemOperation.CREATE_LOCAL,
                    SyncItemOperation.CREATE_REMOTE,
                }
                for item in items
            )
            job.items_updated = sum(
                item.status is SyncItemStatus.COMPLETED
                and item.operation
                in {
                    SyncItemOperation.UPDATE_LOCAL,
                    SyncItemOperation.UPDATE_REMOTE,
                    SyncItemOperation.UPDATE_LOCAL_METADATA,
                    SyncItemOperation.UPDATE_REMOTE_METADATA,
                    SyncItemOperation.REMOTE_DELETE_DETECTED,
                }
                for item in items
            )
            job.status = (
                SharePointSyncJobStatus.PARTIALLY_COMPLETED
                if job.items_failed or job.items_conflicted
                else SharePointSyncJobStatus.COMPLETED
            )
            job.progress = 100
            job.current_stage = (
                "Some changes require review or mapping"
                if job.status is SharePointSyncJobStatus.PARTIALLY_COMPLETED
                else "Completed"
            )
            job.completed_at = utc_now()
            await session.commit()

    async def _resolve_inbound_target(
        self,
        session: AsyncSession,
        *,
        repository: SharePointSyncRepository,
        profile: SharePointSyncProfile,
        connection_id: UUID,
        drive_id: str,
        item_id: str,
        remote: dict[str, Any],
    ) -> tuple[DocumentRevision | None, DocumentFile | None]:
        """Map an inbound item only when an exact scoped revision is known."""

        candidates: list[str] = []
        list_item = remote.get("listItem")
        fields = (
            list_item.get("fields")
            if isinstance(list_item, dict)
            else None
        )
        if isinstance(fields, dict):
            for key in (
                "FullDocumentCode",
                "fullDocumentCode",
                "DocumentCode",
            ):
                value = fields.get(key)
                if isinstance(value, str) and value.strip():
                    candidates.append(value.strip())
        remote_name = remote.get("name")
        if isinstance(remote_name, str) and remote_name.strip():
            candidates.append(PurePosixPath(remote_name.strip()).stem)

        seen: set[str] = set()
        files = DocumentFileRepository(session)
        for candidate in candidates:
            normalized = candidate.casefold()
            if normalized in seen:
                continue
            seen.add(normalized)
            revision = await repository.get_profile_revision_by_full_code(
                profile,
                full_document_code=candidate,
            )
            if revision is None:
                continue
            current = await files.get_current_by_revision(
                revision.id,
                for_update=True,
            )
            if (
                current is not None
                and current.remote_item_id is not None
                and current.remote_item_id != item_id
            ):
                return None, None
            if current is not None:
                current.sharepoint_connection_id = connection_id
                current.remote_drive_id = drive_id
                current.remote_item_id = item_id
                current.remote_path = self._remote_path(remote)
                current.remote_sync_status = RemoteSyncStatus.PENDING
            return revision, current
        return None, None

    async def _plan_local_profile_items(
        self,
        session: AsyncSession,
        *,
        repository: SharePointSyncRepository,
        job: SharePointSyncJob,
        profile: SharePointSyncProfile,
        drive_id: str,
        seen_file_ids: set[UUID],
    ) -> tuple[list[UUID], int, int, int]:
        """Add local-only and locally changed files to the durable job plan."""

        if job.direction is SyncDirection.INBOUND:
            return [], 0, 0, 0
        queued: list[UUID] = []
        discovered = skipped = conflicted = 0
        engine = SharePointSyncEngine()
        for document_file in await repository.list_profile_document_files(
            profile,
            drive_id=drive_id,
        ):
            if document_file.id in seen_file_ids:
                continue
            versions, _ = await SharePointFileVersionRepository(
                session
            ).list_page(
                document_file.id,
                page=1,
                page_size=1,
            )
            baseline = (
                SyncBaseline(
                    local_content_hash=versions[0].local_sha256_hash,
                    remote_etag=versions[0].remote_etag,
                )
                if versions
                else None
            )
            remote_item_id = getattr(
                document_file,
                "remote_item_id",
                None,
            )
            decision = engine.decide(
                direction=job.direction,
                conflict_policy=profile.conflict_policy,
                local=LocalSyncState(
                    document_file_id=str(document_file.id),
                    content_hash=document_file.sha256_hash,
                    modified_at=document_file.uploaded_at,
                    path=getattr(document_file, "remote_path", None),
                ),
                remote=(
                    RemoteSyncState(
                        item_id=remote_item_id,
                        etag=getattr(document_file, "remote_etag", None),
                        modified_at=getattr(
                            document_file,
                            "remote_last_modified_at",
                            None,
                        ),
                        path=getattr(document_file, "remote_path", None),
                        content_hash=None,
                    )
                    if remote_item_id
                    else None
                ),
                baseline=baseline,
            )
            key = engine.idempotency_key(
                sync_profile_id=str(job.sync_profile_id),
                remote_item_id=(
                    remote_item_id or f"local:{document_file.id}"
                ),
                remote_etag=getattr(
                    document_file,
                    "remote_etag",
                    None,
                ),
                local_content_hash=document_file.sha256_hash,
                operation=decision.operation,
            )
            if await repository.get_item_by_idempotency(key) is not None:
                skipped += 1
                continue
            status = (
                SyncItemStatus.SKIPPED
                if decision.operation is SyncItemOperation.SKIP
                else (
                    SyncItemStatus.CONFLICT
                    if decision.operation is SyncItemOperation.CONFLICT
                    else SyncItemStatus.QUEUED
                )
            )
            item = SharePointSyncItem(
                sync_job_id=job.id,
                document_id=document_file.document_id,
                document_revision_id=document_file.document_revision_id,
                document_file_id=document_file.id,
                remote_drive_id=drive_id,
                remote_item_id=remote_item_id,
                remote_path=getattr(document_file, "remote_path", None),
                operation=decision.operation,
                status=status,
                idempotency_key=key,
                local_hash_before=(
                    versions[0].local_sha256_hash if versions else None
                ),
                local_hash_after=document_file.sha256_hash,
                remote_etag_before=(
                    versions[0].remote_etag if versions else None
                ),
                remote_etag_after=getattr(
                    document_file,
                    "remote_etag",
                    None,
                ),
                remote_size=getattr(document_file, "remote_size", None),
                metadata_json={
                    "source": "local-profile-scan",
                    **(
                        {
                            "safeCopySuffix": (
                                f"conflict-{str(job.id)[:8]}"
                            )
                        }
                        if decision.create_copy
                        else {}
                    ),
                },
                completed_at=(
                    utc_now()
                    if status
                    in {
                        SyncItemStatus.SKIPPED,
                        SyncItemStatus.CONFLICT,
                    }
                    else None
                ),
            )
            await repository.add_item(item)
            discovered += 1
            if status is SyncItemStatus.SKIPPED:
                skipped += 1
            elif status is SyncItemStatus.CONFLICT:
                conflicted += 1
                conflict = SharePointSyncConflict(
                    sync_job_id=job.id,
                    sync_item_id=item.id,
                    document_id=document_file.document_id,
                    document_revision_id=(
                        document_file.document_revision_id
                    ),
                    document_file_id=document_file.id,
                    remote_item_id=remote_item_id,
                    conflict_type=(
                        decision.conflict_type
                        or SyncConflictType.VERSION_MISMATCH
                    ),
                    local_version_json={
                        "sha256": document_file.sha256_hash,
                        "baselineSha256": (
                            versions[0].local_sha256_hash
                            if versions
                            else None
                        ),
                    },
                    remote_version_json={
                        "eTag": getattr(
                            document_file,
                            "remote_etag",
                            None,
                        ),
                        "size": getattr(
                            document_file,
                            "remote_size",
                            None,
                        ),
                    },
                )
                await SharePointConflictRepository(session).add(conflict)
                item.conflict_id = conflict.id
            else:
                queued.append(item.id)
        return queued, discovered, skipped, conflicted

    async def _job_context(
        self,
        session: AsyncSession,
        job_id: UUID,
        file_id: UUID,
    ) -> tuple[SharePointSyncJob, SharePointConnection, DocumentFile]:
        job = await SharePointSyncRepository(session).get_job(
            job_id,
            for_update=True,
        )
        connection = (
            await SharePointConnectionRepository(session).get_by_id(
                job.sharepoint_connection_id
            )
            if job is not None
            else None
        )
        document_file = await DocumentFileRepository(session).get_by_id(
            file_id,
            for_update=True,
        )
        if job is None or connection is None or document_file is None:
            raise ValueError("SharePoint sync context is incomplete.")
        if (
            not connection.is_active
            or connection.status is SharePointConnectionStatus.DISABLED
        ):
            raise ValueError("SharePoint connection is disabled.")
        if document_file.file_status is not DocumentFileStatus.AVAILABLE:
            raise ValueError("FILE_QUARANTINED")
        return job, connection, document_file

    async def _record_version(
        self,
        session: AsyncSession,
        *,
        document_file: DocumentFile,
        job_id: UUID,
        metadata: dict[str, Any],
        versions: list[dict[str, Any]],
    ) -> None:
        version = versions[0] if versions else {}
        modified = self._parse_datetime(metadata.get("lastModifiedDateTime"))
        identity = metadata.get("lastModifiedBy")
        display_name: str | None = None
        if isinstance(identity, dict):
            user = identity.get("user")
            if isinstance(user, dict) and user.get("displayName"):
                display_name = str(user["displayName"])
        await SharePointFileVersionRepository(session).add(
            SharePointFileVersion(
                document_file_id=document_file.id,
                remote_drive_id=str(
                    getattr(document_file, "remote_drive_id", "")
                    or metadata.get("parentReference", {}).get("driveId", "")
                ),
                remote_item_id=self._remote_id(metadata),
                remote_version_id=str(
                    version.get("id")
                    or metadata.get("eTag")
                    or metadata.get("cTag")
                    or "unknown"
                ),
                remote_etag=(
                    str(metadata["eTag"]) if metadata.get("eTag") else None
                ),
                remote_last_modified_at=modified,
                remote_last_modified_by=display_name,
                remote_size=int(metadata.get("size", 0) or 0),
                local_sha256_hash=document_file.sha256_hash,
                sync_job_id=job_id,
            )
        )

    @staticmethod
    def _apply_remote_metadata(
        document_file: DocumentFile,
        *,
        connection_id: UUID,
        drive_id: str,
        remote_path: str,
        metadata: dict[str, Any],
    ) -> None:
        fields = {
            "storage_provider": "HYBRID",
            "sharepoint_connection_id": connection_id,
            "remote_drive_id": drive_id,
            "remote_item_id": metadata.get("id"),
            "remote_parent_item_id": (
                metadata.get("parentReference", {}).get("id")
                if isinstance(metadata.get("parentReference"), dict)
                else None
            ),
            "remote_path": remote_path,
            "remote_web_url": metadata.get("webUrl"),
            "remote_etag": metadata.get("eTag"),
            "remote_ctag": metadata.get("cTag"),
            "remote_version_id": (
                metadata.get("eTag") or metadata.get("cTag")
            ),
            "remote_last_modified_at": (
                SharePointWorkerService._parse_datetime(
                    metadata.get("lastModifiedDateTime")
                )
            ),
            "remote_last_modified_by": (
                SharePointWorkerService._modified_by(metadata)
            ),
            "remote_size": int(metadata.get("size", 0) or 0),
            "remote_mime_type": SharePointWorkerService._remote_mime(
                metadata,
                document_file.mime_type,
            ),
            "remote_sync_status": "SYNCED",
            "last_synced_at": utc_now(),
            "sync_error_code": None,
            "sync_error_message": None,
        }
        for field, value in fields.items():
            if hasattr(type(document_file), field):
                setattr(document_file, field, value)

    @staticmethod
    def _mapped_fields(
        document_file: DocumentFile,
        mappings: list[Any],
        *,
        metadata_service: SharePointMetadataService,
    ) -> dict[str, Any]:
        values = {
            "baseDocumentCode": document_file.document.base_document_code,
            "document.title": document_file.document.title,
            "revisionCode": document_file.revision.revision_code,
            "documentStatus.code": (
                document_file.revision.document_status.code
                if document_file.revision.document_status is not None
                else None
            ),
        }
        fields: dict[str, Any] = {}
        for mapping in mappings:
            value = values.get(mapping.document_field)
            if value is None:
                value = mapping.default_value
            if value is None and mapping.is_required:
                raise ValueError(
                    "A required SharePoint metadata value is unavailable."
                )
            if value is not None:
                fields[mapping.sharepoint_field_internal_name] = (
                    metadata_service.transform(
                        mapping.transformer_code
                        or mapping.data_type.value,
                        value,
                    )
                )
        return fields

    @staticmethod
    def _remote_filename(
        document_file: DocumentFile,
        mapping: Any,
    ) -> str:
        if mapping is None or not mapping.filename_pattern:
            return document_file.sanitized_filename
        allowed = {
            "baseDocumentCode": document_file.document.base_document_code,
            "revisionCode": document_file.revision.revision_code,
            "filename": document_file.sanitized_filename,
        }
        result = mapping.filename_pattern
        for key, value in allowed.items():
            result = result.replace(f"{{{key}}}", str(value))
        if "{" in result or "}" in result:
            raise ValueError("Filename pattern contains an unknown placeholder.")
        return StoragePathService.sanitize_filename(result)

    @staticmethod
    def _copy_filename(filename: str, suffix: str) -> str:
        path = PurePosixPath(filename)
        safe_suffix = StoragePathService.sanitize_filename(suffix).strip("._-")
        if not safe_suffix:
            raise ValueError("Conflict copy suffix is invalid.")
        result = f"{path.stem}-{safe_suffix}{path.suffix}"
        return StoragePathService.sanitize_filename(result)

    @staticmethod
    def _file_scope(job: SharePointSyncJob) -> UUID | None:
        value = (job.scope_json or {}).get("documentFileId")
        try:
            return UUID(str(value)) if value else None
        except ValueError:
            return None

    @staticmethod
    def _standalone_job(job: SharePointSyncJob) -> bool:
        return job.job_type in {
            SyncJobType.SINGLE_FILE_PUSH,
            SyncJobType.SINGLE_FILE_PULL,
            SyncJobType.RECONCILIATION,
        }

    async def _final_status(
        self,
        job_id: UUID,
    ) -> SharePointSyncJobStatus:
        async with self.session_factory() as session:
            job = await SharePointSyncRepository(session).get_job(job_id)
            return (
                job.status
                if job is not None
                else SharePointSyncJobStatus.FAILED
            )

    @staticmethod
    def _drive_id(connection: SharePointConnection) -> str:
        if not connection.drive_id:
            raise ValueError("SharePoint connection has no resolved drive.")
        return connection.drive_id

    @staticmethod
    def _remote_id(metadata: dict[str, Any]) -> str:
        value = metadata.get("id")
        if not isinstance(value, str) or not value:
            raise ValueError("Graph item metadata has no identifier.")
        return value

    @staticmethod
    def _remote_path(metadata: dict[str, Any]) -> str | None:
        parent = metadata.get("parentReference")
        path = parent.get("path") if isinstance(parent, dict) else None
        name = metadata.get("name")
        if isinstance(path, str) and isinstance(name, str):
            return f"{path}/{name}"
        return name if isinstance(name, str) else None

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _modified_by(metadata: dict[str, Any]) -> str | None:
        identity = metadata.get("lastModifiedBy")
        if not isinstance(identity, dict):
            return None
        user = identity.get("user")
        if not isinstance(user, dict):
            return None
        value = user.get("displayName")
        return str(value) if value else None

    @staticmethod
    def _remote_mime(metadata: dict[str, Any], fallback: str) -> str:
        file_facet = metadata.get("file")
        if isinstance(file_facet, dict) and file_facet.get("mimeType"):
            return str(file_facet["mimeType"])
        return fallback

    @staticmethod
    def _remote_hash(metadata: dict[str, Any]) -> str | None:
        file_facet = metadata.get("file")
        hashes = (
            file_facet.get("hashes")
            if isinstance(file_facet, dict)
            else None
        )
        if not isinstance(hashes, dict):
            return None
        for key in ("sha256Hash", "sha1Hash", "quickXorHash"):
            value = hashes.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    @staticmethod
    async def _temporary_chunks(
        source,
        *,
        chunk_size: int = 1024 * 1024,
    ) -> AsyncIterator[bytes]:
        source.seek(0)
        while chunk := source.read(chunk_size):
            yield chunk
        source.seek(0)

    @staticmethod
    def _scanner(settings: Settings) -> BaseMalwareScanner:
        if not bool(getattr(settings, "malware_scanning_enabled", False)):
            return NoOpMalwareScanner()
        return ClamAvMalwareScanner(
            host=str(getattr(settings, "clamav_host", "clamav")),
            port=int(getattr(settings, "clamav_port", 3310)),
            timeout_seconds=float(
                getattr(settings, "malware_scan_timeout_seconds", 120)
            ),
            fail_policy=MalwareScannerFailPolicy(
                str(
                    getattr(
                        settings,
                        "malware_scanner_failure_policy",
                        "FAIL_CLOSED",
                    )
                )
            ),
        )

    def _integration_cipher(self) -> AesGcmEncryptionService | None:
        configured = getattr(self.settings, "encryption_key", None)
        if configured is None:
            return None
        raw = (
            configured.get_secret_value()
            if hasattr(configured, "get_secret_value")
            else str(configured)
        )
        try:
            key = base64.b64decode(raw, validate=True)
        except (ValueError, TypeError):
            return None
        version = str(
            getattr(self.settings, "encryption_key_version", "v1")
        )
        try:
            return AesGcmEncryptionService(
                {version: key},
                active_key_version=version,
            )
        except (ValueError, RuntimeError):
            return None
