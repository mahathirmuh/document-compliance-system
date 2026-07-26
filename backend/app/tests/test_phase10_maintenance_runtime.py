"""Concrete maintenance retention handler regressions."""

from __future__ import annotations

import io
from datetime import timedelta
from types import SimpleNamespace
from typing import BinaryIO
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models.data_retention_policy import (
    DataRetentionPolicy,
    RetentionEntityType,
    RetentionScopeType,
)
from app.models.in_app_notification import InAppNotification
from app.models.notification_enums import (
    NotificationEventType,
    NotificationSeverity,
)
from app.models.upload_session import (
    UploadSession,
    UploadSessionStatus,
    UploadSessionType,
)
from app.models.upload_session_item import UploadSessionItem
from app.services.maintenance.maintenance_worker_service import (
    MaintenanceWorkerService,
)
from app.services.maintenance.retention_handlers import (
    TemporaryUploadRetentionHandler,
    create_default_retention_handlers,
)
from app.services.maintenance.runtime import (
    create_dead_letter_retry_publisher,
)
from app.services.storage.base_storage import BaseStorage, StorageSaveResult
from app.utils.datetime import utc_now


class MemoryStorage(BaseStorage):
    provider_name = "memory"

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def save(
        self,
        source: BinaryIO,
        storage_key: str,
    ) -> StorageSaveResult:
        value = source.read()
        self.objects[storage_key] = value
        return {
            "storage_key": storage_key,
            "storage_provider": self.provider_name,
            "size": len(value),
        }

    async def open(self, storage_key: str) -> BinaryIO:
        return io.BytesIO(self.objects[storage_key])

    async def exists(self, storage_key: str) -> bool:
        return storage_key in self.objects

    async def delete(self, storage_key: str) -> None:
        self.objects.pop(storage_key, None)

    async def move(
        self,
        source_key: str,
        destination_key: str,
    ) -> None:
        self.objects[destination_key] = self.objects.pop(source_key)

    async def get_size(self, storage_key: str) -> int:
        return len(self.objects[storage_key])


class RecordingCelery:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def send_task(
        self,
        name: str,
        *,
        args: list[str],
        queue: str,
        headers: dict[str, str],
    ) -> SimpleNamespace:
        self.calls.append(
            {
                "name": name,
                "args": args,
                "queue": queue,
                "headers": headers,
            }
        )
        return SimpleNamespace(id="dead-letter-retry-task")


@pytest.mark.asyncio
async def test_dead_letter_publisher_maps_only_allowlisted_tasks() -> None:
    celery = RecordingCelery()
    publisher = create_dead_letter_retry_publisher(
        get_settings(),
        celery=celery,
    )
    entity_id = uuid4()
    dead_letter_id = uuid4()
    provider_id = await publisher.publish(
        task_name=("app.workers.sharepoint_tasks.process_sharepoint_sync_job"),
        arguments={"entityId": str(entity_id)},
        dead_letter_job_id=dead_letter_id,
    )
    assert provider_id == "dead-letter-retry-task"
    assert celery.calls[0]["args"] == [str(entity_id)]
    assert celery.calls[0]["queue"] == "sharepoint"
    assert celery.calls[0]["headers"] == {"dead_letter_job_id": str(dead_letter_id)}

    with pytest.raises(ValueError, match="not approved"):
        await publisher.publish(
            task_name="app.workers.arbitrary.execute",
            arguments={"entityId": str(entity_id)},
            dead_letter_job_id=dead_letter_id,
        )
    assert len(celery.calls) == 1


@pytest.mark.asyncio
async def test_default_maintenance_handlers_cover_scheduled_entities(
    session_factory,
) -> None:
    async with session_factory() as session:
        handlers = create_default_retention_handlers(
            session,
            storage=MemoryStorage(),
        )
    assert set(handlers) == {
        RetentionEntityType.TEMP_UPLOAD,
        RetentionEntityType.REPORT_SNAPSHOT,
        RetentionEntityType.NOTIFICATION,
        RetentionEntityType.WEBHOOK_EVENT,
        RetentionEntityType.JOB_LOG,
        RetentionEntityType.DELETED_FILE,
    }


@pytest.mark.asyncio
async def test_notification_retention_soft_deletes_then_removes(
    session_factory,
    create_user,
) -> None:
    user = await create_user(email="retention-notification@example.com")
    old = utc_now() - timedelta(days=10)
    notification_id = None
    async with session_factory() as session:
        policy = DataRetentionPolicy(
            name="Old in-app notifications",
            entity_type=RetentionEntityType.NOTIFICATION,
            scope_type=RetentionScopeType.GLOBAL,
            retention_days=1,
            delete_after_days=1,
            is_active=True,
        )
        notification = InAppNotification(
            user_id=user.id,
            event_type=NotificationEventType.REPORT_GENERATED,
            title="Old report",
            message="The report is ready.",
            severity=NotificationSeverity.INFORMATION,
            created_at=old,
        )
        session.add_all([policy, notification])
        await session.commit()
        notification_id = notification.id

    service = MaintenanceWorkerService(
        session_factory=session_factory,
        storage=MemoryStorage(),
    )
    first = await service.cleanup(
        entity_type=RetentionEntityType.NOTIFICATION,
        dry_run=False,
        batch_size=100,
    )
    assert first["status"] == "COMPLETED"
    assert first["softDeletedCount"] == 1
    async with session_factory() as session:
        row = await session.get(InAppNotification, notification_id)
        assert row is not None
        assert row.dismissed_at is not None

    second = await service.cleanup(
        entity_type=RetentionEntityType.NOTIFICATION,
        dry_run=False,
        batch_size=100,
    )
    assert second["permanentlyDeletedCount"] == 1
    async with session_factory() as session:
        assert await session.get(InAppNotification, notification_id) is None


@pytest.mark.asyncio
async def test_temporary_upload_retention_removes_only_temporary_object(
    session_factory,
    create_user,
) -> None:
    user = await create_user(email="retention-upload@example.com")
    storage = MemoryStorage()
    storage.objects["temporary/session/file.pdf"] = b"test"
    old = utc_now() - timedelta(days=10)
    async with session_factory() as session:
        upload = UploadSession(
            user_id=user.id,
            session_type=UploadSessionType.SINGLE,
            status=UploadSessionStatus.CREATED,
            total_files=1,
            total_size=4,
            expires_at=old + timedelta(hours=1),
            created_at=old,
        )
        UploadSessionItem(
            upload_session=upload,
            temporary_storage_key="temporary/session/file.pdf",
            original_filename="file.pdf",
            sanitized_filename="file.pdf",
        )
        session.add(upload)
        await session.commit()
        upload_id = upload.id

    async with session_factory() as session:
        handler = TemporaryUploadRetentionHandler(
            session,
            storage=storage,
        )
        policy = DataRetentionPolicy(
            name="Temporary uploads",
            entity_type=RetentionEntityType.TEMP_UPLOAD,
            scope_type=RetentionScopeType.GLOBAL,
            retention_days=1,
        )
        candidates = await handler.list_candidates(
            policy=policy,
            archive_cutoff=None,
            delete_cutoff=utc_now() - timedelta(days=1),
            limit=10,
        )
        assert len(candidates) == 1
        await handler.soft_delete(candidates[0])
        await session.commit()

    assert storage.objects == {}
    async with session_factory() as session:
        row = await session.scalar(
            select(UploadSession).where(UploadSession.id == upload_id)
        )
        assert row is not None
        assert row.status == UploadSessionStatus.EXPIRED
