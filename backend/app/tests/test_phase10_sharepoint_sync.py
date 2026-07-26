"""SharePoint planning, metadata, delta-state, and webhook regressions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v1.endpoints.microsoft_graph_webhook import (
    microsoft_graph_webhook,
)
from app.core.config import get_settings
from app.integrations.microsoft_graph.sharepoint.sharepoint_metadata_service import (
    SharePointMetadataService,
)
from app.integrations.microsoft_graph.sharepoint.sharepoint_webhook_service import (
    SharePointWebhookService,
)
from app.models.department import Department
from app.models.document import Document
from app.models.document_file import DocumentFile, DocumentFileStatus
from app.models.document_revision import DocumentRevision
from app.models.document_status import DocumentStatus
from app.models.document_type import DocumentType
from app.models.graph_subscription import GraphSubscription
from app.models.graph_webhook_event import GraphWebhookEvent
from app.models.section import Section
from app.models.sharepoint_connection import SharePointConnection
from app.models.sharepoint_enums import (
    ConflictPolicy,
    FolderMappingScope,
    GraphSubscriptionStatus,
    MetadataDataType,
    SharePointSyncJobStatus,
    SyncConflictResolution,
    SyncConflictType,
    SyncDirection,
    SyncItemOperation,
    SyncJobType,
)
from app.models.sharepoint_folder_mapping import SharePointFolderMapping
from app.models.sharepoint_sync_job import SharePointSyncJob
from app.models.sharepoint_sync_profile import SharePointSyncProfile
from app.repositories.sharepoint_mapping_repository import (
    SharePointMappingRepository,
)
from app.repositories.sharepoint_sync_repository import (
    SharePointSyncRepository,
)
from app.schemas.sharepoint_sync import (
    SharePointFileStatusResponse,
    SharePointSyncJobResponse,
    SharePointSyncProfileCreateRequest,
)
from app.schemas.sharepoint_webhook import GraphSubscriptionCreateRequest
from app.services.secrets.encryption_service import AesGcmEncryptionService
from app.services.sharepoint.delta_state_service import (
    SharePointDeltaStateService,
)
from app.services.sharepoint.file_integration_service import (
    SharePointFileIntegrationService,
)
from app.services.sharepoint.scheduled_sync_service import (
    SharePointScheduledSyncService,
)
from app.services.sharepoint.sharepoint_worker_service import (
    SharePointWorkerService,
)
from app.services.sharepoint.subscription_service import (
    GraphSubscriptionService,
)
from app.services.sharepoint.sync_engine import (
    LocalSyncState,
    RemoteSyncState,
    SharePointSyncEngine,
    SyncBaseline,
)
from app.services.sharepoint.webhook_processing_service import (
    GraphWebhookProcessingService,
)


def _local(
    *,
    content_hash: str = "local-new",
    modified_at: datetime | None = None,
    deleted: bool = False,
) -> LocalSyncState:
    return LocalSyncState(
        document_file_id="file",
        content_hash=content_hash,
        modified_at=modified_at or datetime(2026, 1, 2, tzinfo=UTC),
        path="folder/file.pdf",
        deleted=deleted,
    )


def _remote(
    *,
    etag: str = "remote-new",
    modified_at: datetime | None = None,
    deleted: bool = False,
) -> RemoteSyncState:
    return RemoteSyncState(
        item_id="item",
        etag=etag,
        modified_at=modified_at or datetime(2026, 1, 3, tzinfo=UTC),
        path="folder/file.pdf",
        deleted=deleted,
    )


def test_sync_engine_directions_conflicts_deletions_and_idempotency() -> None:
    engine = SharePointSyncEngine()
    baseline = SyncBaseline(
        local_content_hash="local-old",
        remote_etag="remote-old",
    )

    outbound = engine.decide(
        direction=SyncDirection.OUTBOUND,
        conflict_policy=ConflictPolicy.MANUAL,
        local=_local(),
        remote=_remote(etag="remote-old"),
        baseline=baseline,
    )
    inbound = engine.decide(
        direction=SyncDirection.INBOUND,
        conflict_policy=ConflictPolicy.MANUAL,
        local=_local(content_hash="local-old"),
        remote=_remote(),
        baseline=baseline,
    )
    manual = engine.decide(
        direction=SyncDirection.BIDIRECTIONAL,
        conflict_policy=ConflictPolicy.MANUAL,
        local=_local(),
        remote=_remote(),
        baseline=baseline,
    )
    application_wins = engine.decide(
        direction=SyncDirection.BIDIRECTIONAL,
        conflict_policy=ConflictPolicy.APPLICATION_WINS,
        local=_local(),
        remote=_remote(),
        baseline=baseline,
    )
    sharepoint_wins = engine.decide(
        direction=SyncDirection.BIDIRECTIONAL,
        conflict_policy=ConflictPolicy.SHAREPOINT_WINS,
        local=_local(),
        remote=_remote(),
        baseline=baseline,
    )
    latest_wins = engine.decide(
        direction=SyncDirection.BIDIRECTIONAL,
        conflict_policy=ConflictPolicy.LATEST_MODIFIED_WINS,
        local=_local(modified_at=datetime(2026, 1, 2, tzinfo=UTC)),
        remote=_remote(modified_at=datetime(2026, 1, 3, tzinfo=UTC)),
        baseline=baseline,
    )
    remote_deleted = engine.decide(
        direction=SyncDirection.BIDIRECTIONAL,
        conflict_policy=ConflictPolicy.MANUAL,
        local=_local(),
        remote=_remote(etag="remote-old", deleted=True),
        baseline=baseline,
    )

    assert outbound.operation is SyncItemOperation.UPDATE_REMOTE
    assert inbound.operation is SyncItemOperation.UPDATE_LOCAL
    assert manual.operation is SyncItemOperation.CONFLICT
    assert manual.conflict_type is SyncConflictType.BOTH_MODIFIED
    assert application_wins.operation is SyncItemOperation.UPDATE_REMOTE
    assert sharepoint_wins.operation is SyncItemOperation.UPDATE_LOCAL
    assert latest_wins.operation is SyncItemOperation.UPDATE_LOCAL
    assert remote_deleted.conflict_type is (
        SyncConflictType.REMOTE_DELETED_LOCAL_MODIFIED
    )
    first_key = engine.idempotency_key(
        sync_profile_id="profile",
        remote_item_id="item",
        remote_etag="etag",
        local_content_hash="hash",
        operation=SyncItemOperation.UPDATE_LOCAL,
    )
    second_key = engine.idempotency_key(
        sync_profile_id="profile",
        remote_item_id="item",
        remote_etag="etag",
        local_content_hash="hash",
        operation=SyncItemOperation.UPDATE_LOCAL,
    )
    assert first_key == second_key
    assert len(first_key) == 64


def test_metadata_transformers_are_typed_and_allow_listed() -> None:
    transformer = SharePointMetadataService(cast(Any, SimpleNamespace()))

    assert transformer.transform(
        MetadataDataType.BOOLEAN.value,
        "false",
    ) is False
    assert transformer.transform(
        "UPPERCASE",
        "  hrm ",
    ) == "HRM"
    assert transformer.transform(
        MetadataDataType.JSON_STRING.value,
        {"revision": 2, "valid": True},
    ) == '{"revision":2,"valid":true}'
    assert transformer.transform(
        MetadataDataType.DATE.value,
        "2026-07-26",
    ) == "2026-07-26"
    with pytest.raises(ValueError, match="not registered"):
        transformer.transform(
            "__import__('os')",
            "value",
        )


class _DeltaRepository:
    def __init__(self) -> None:
        self.state = None

    async def get_delta_state(self, **_: Any):
        return self.state

    async def add_delta_state(self, state):
        self.state = state
        return state


@pytest.mark.asyncio
async def test_delta_state_is_encrypted_and_advances_only_after_success() -> None:
    session = SimpleNamespace(flush=AsyncMock())
    cipher = AesGcmEncryptionService(
        {"v1": b"k" * 32},
        active_key_version="v1",
    )
    service = SharePointDeltaStateService(
        cast(AsyncSession, session),
        cipher,
    )
    repository = _DeltaRepository()
    service.repository = cast(Any, repository)
    profile_id = uuid4()
    failed_job = SimpleNamespace(
        id=uuid4(),
        sync_profile_id=profile_id,
        status=SharePointSyncJobStatus.FAILED,
        delta_token_after=None,
    )
    with pytest.raises(ValueError, match="completed"):
        await service.commit_after_success(
            job=cast(SharePointSyncJob, failed_job),
            drive_id="drive",
            folder_item_id=None,
            delta_link="https://graph.microsoft.com/delta?token=secret",
        )

    completed_job = SimpleNamespace(
        id=uuid4(),
        sync_profile_id=profile_id,
        status=SharePointSyncJobStatus.COMPLETED,
        delta_token_after=None,
    )
    plaintext = "https://graph.microsoft.com/delta?token=secret"
    state = await service.commit_after_success(
        job=cast(SharePointSyncJob, completed_job),
        drive_id="drive",
        folder_item_id=None,
        delta_link=plaintext,
    )

    assert plaintext not in state.delta_link_encrypted
    assert len(state.delta_token_hash) == 64
    assert completed_job.delta_token_after == state.delta_token_hash
    assert await service.load(
        profile_id=profile_id,
        drive_id="drive",
        folder_item_id=None,
    ) == plaintext


@pytest.mark.asyncio
async def test_webhook_validation_token_is_exact_plain_text() -> None:
    response = await microsoft_graph_webhook(
        session=cast(AsyncSession, SimpleNamespace()),
        settings=cast(Any, SimpleNamespace()),
        payload=None,
        validation_token="opaque validation token",
    )
    assert response.media_type == "text/plain"
    assert response.body == b"opaque validation token"
    assert response.headers["cache-control"] == "no-store"


class _WebhookRepository:
    def __init__(self, subscription: Any) -> None:
        self.subscription = subscription
        self.events: dict[str, GraphWebhookEvent] = {}

    async def get_by_remote_id(self, _: str, **__: Any):
        return self.subscription

    async def get_event_by_payload(
        self,
        *,
        subscription_id: str,
        payload_hash: str,
    ):
        return self.events.get(f"{subscription_id}:{payload_hash}")

    async def add_event(self, event: GraphWebhookEvent):
        event.id = uuid4()
        self.events[f"{event.subscription_id}:{event.payload_hash}"] = event
        return event


@pytest.mark.asyncio
async def test_webhook_validates_client_state_deduplicates_and_strips_secret() -> None:
    secret = "state-secret-with-more-than-thirty-two-characters"
    subscription = SimpleNamespace(
        status=GraphSubscriptionStatus.ACTIVE,
        client_state_hash=SharePointWebhookService.client_state_hash(secret),
        last_notification_at=None,
    )
    session = SimpleNamespace(
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )
    service = GraphWebhookProcessingService(
        cast(AsyncSession, session),
        cast(Any, SimpleNamespace(sharepoint_queue_name="sharepoint")),
    )
    repository = _WebhookRepository(subscription)
    service.repository = cast(Any, repository)
    service._dispatch = AsyncMock()  # type: ignore[method-assign]
    notification = {
        "subscriptionId": "remote-subscription",
        "changeType": "updated",
        "resource": "drives/drive/root",
        "resourceData": {"id": "remote-item"},
        "clientState": secret,
    }

    first = await service.accept({"value": [notification]})
    second = await service.accept({"value": [notification]})
    invalid = await service.accept(
        {
            "value": [
                {
                    **notification,
                    "clientState": "invalid-client-state",
                }
            ]
        }
    )

    assert (first.accepted, first.duplicates, first.rejected) == (1, 0, 0)
    assert (second.accepted, second.duplicates, second.rejected) == (0, 1, 0)
    assert (invalid.accepted, invalid.duplicates, invalid.rejected) == (0, 0, 1)
    event = next(iter(repository.events.values()))
    assert "clientState" not in event.metadata_json
    assert secret not in str(event.metadata_json)
    service._dispatch.assert_awaited_once_with(event.id)  # type: ignore[attr-defined]


def test_subscription_schema_requires_https_future_and_secret_repr() -> None:
    payload = GraphSubscriptionCreateRequest(
        sharepoint_connection_id=uuid4(),
        sync_profile_id=uuid4(),
        resource="drives/drive/root",
        notification_url="https://example.test/api/v1/webhook",
        client_state="x" * 40,
        expiration_datetime=datetime.now(UTC) + timedelta(days=1),
    )
    assert "x" * 40 not in repr(payload)
    with pytest.raises(ValidationError):
        GraphSubscriptionCreateRequest(
            sharepoint_connection_id=uuid4(),
            sync_profile_id=uuid4(),
            resource="drives/drive/root",
            notification_url="http://example.test/webhook",
            client_state="x" * 40,
            expiration_datetime=datetime.now(UTC) + timedelta(days=1),
        )


@pytest.mark.asyncio
async def test_subscription_renewal_updates_expiry_without_client_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    subscription = GraphSubscription(
        id=uuid4(),
        sharepoint_connection_id=uuid4(),
        sync_profile_id=uuid4(),
        subscription_id="remote-subscription",
        resource="drives/drive/root",
        change_type="updated",
        notification_url="https://example.test/webhook",
        client_state_hash="a" * 64,
        expiration_datetime=now + timedelta(hours=1),
        status=GraphSubscriptionStatus.EXPIRING,
        renewal_attempts=0,
        created_at=now,
        updated_at=now,
    )
    remote_expiry = now + timedelta(days=2)
    graph = SimpleNamespace(
        patch=AsyncMock(
            return_value={
                "expirationDateTime": remote_expiry.isoformat(),
            }
        ),
        close=AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.sharepoint.subscription_service.create_graph_client",
        lambda _: graph,
    )
    session = SimpleNamespace(commit=AsyncMock())
    service = GraphSubscriptionService.__new__(GraphSubscriptionService)
    service.session = cast(AsyncSession, session)
    service.settings = cast(Any, SimpleNamespace())
    service.repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=subscription)
    )
    service.audit_if_registered = AsyncMock()  # type: ignore[method-assign]

    response = await service.renew(
        subscription.id,
        expiration_datetime=remote_expiry,
    )

    graph.patch.assert_awaited_once()
    graph.close.assert_awaited_once()
    assert response.status is GraphSubscriptionStatus.ACTIVE
    assert response.expiration_datetime == remote_expiry
    assert response.renewal_attempts == 1
    assert "clientState" not in str(graph.patch.await_args)


def test_conflict_resolution_values_are_explicit_and_non_overlapping() -> None:
    assert {
        SyncConflictResolution.KEEP_LOCAL,
        SyncConflictResolution.KEEP_REMOTE,
        SyncConflictResolution.KEEP_BOTH,
        SyncConflictResolution.MERGE_METADATA,
        SyncConflictResolution.IGNORE_REMOTE_CHANGE,
        SyncConflictResolution.IGNORE_LOCAL_CHANGE,
    } == set(SyncConflictResolution)


def test_public_sync_contract_hides_delta_state_and_filters_remote_url() -> None:
    now = datetime.now(UTC)
    response = SharePointSyncJobResponse(
        id=uuid4(),
        sync_profile_id=uuid4(),
        sharepoint_connection_id=uuid4(),
        job_type="MANUAL_INCREMENTAL",
        direction="OUTBOUND",
        status="COMPLETED",
        progress=100,
        requested_at=now,
        attempt_number=1,
        maximum_attempts=3,
        items_discovered=0,
        items_processed=0,
        items_created=0,
        items_updated=0,
        items_skipped=0,
        items_conflicted=0,
        items_failed=0,
        result_summary={
            "deltaTokenCandidateHash": "a" * 64,
            "deltaLink": "https://graph.microsoft.com/private-delta",
            "deltaTokenPersisted": True,
            "deltaPageCount": 2,
        },
        created_at=now,
        updated_at=now,
    ).model_dump(mode="json", by_alias=True)

    assert "deltaTokenBefore" not in response
    assert "deltaTokenAfter" not in response
    assert response["resultSummary"] == {
        "deltaPageCount": 2,
        "deltaStateAdvanced": True,
    }
    assert SharePointFileIntegrationService._safe_remote_web_url(
        "https://tenant.sharepoint.com/sites/docs/file.pdf?downloadToken=secret"
    ) == "https://tenant.sharepoint.com/sites/docs/file.pdf"
    assert (
        SharePointFileIntegrationService._safe_remote_web_url(
            "https://evil.example/download"
        )
        is None
    )
    remote_status = SharePointFileStatusResponse(
        document_file_id=uuid4(),
        storage_provider="SHAREPOINT",
        remote_web_url="https://tenant.sharepoint.com/sites/docs/file.pdf",
    ).model_dump(mode="json", by_alias=True)
    assert remote_status["remoteWebUrl"] == (
        "https://tenant.sharepoint.com/sites/docs/file.pdf"
    )


@pytest.mark.asyncio
async def test_folder_mapping_resolution_is_specific_then_priority(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        department = Department(code="SPT", name="SharePoint Test")
        section = Section(
            department=department,
            code="OPS",
            name="Operations",
        )
        document_type = DocumentType(
            code="SOP",
            name="Procedure",
            category="PROCEDURE",
        )
        connection = SharePointConnection(
            name="Mapping Test",
            tenant_id_reference="tenant",
            site_hostname="tenant.sharepoint.com",
            site_path="/sites/compliance",
            library_name="Documents",
            root_folder_path="DocumentCompliance",
        )
        session.add_all(
            [department, section, document_type, connection]
        )
        await session.flush()
        mappings = [
            SharePointFolderMapping(
                sharepoint_connection_id=connection.id,
                mapping_scope=FolderMappingScope.GLOBAL,
                remote_folder_path="global",
                priority=999,
            ),
            SharePointFolderMapping(
                sharepoint_connection_id=connection.id,
                department_id=department.id,
                mapping_scope=FolderMappingScope.DEPARTMENT,
                remote_folder_path="department",
                priority=999,
            ),
            SharePointFolderMapping(
                sharepoint_connection_id=connection.id,
                document_type_id=document_type.id,
                mapping_scope=FolderMappingScope.DOCUMENT_TYPE,
                remote_folder_path="document-type",
                priority=999,
            ),
            SharePointFolderMapping(
                sharepoint_connection_id=connection.id,
                department_id=department.id,
                document_type_id=document_type.id,
                mapping_scope=(
                    FolderMappingScope.DEPARTMENT_DOCUMENT_TYPE
                ),
                remote_folder_path="department-document-type",
                priority=500,
            ),
            SharePointFolderMapping(
                sharepoint_connection_id=connection.id,
                section_id=section.id,
                document_type_id=document_type.id,
                mapping_scope=FolderMappingScope.SECTION_DOCUMENT_TYPE,
                remote_folder_path="section-document-type-low-priority",
                priority=1,
            ),
            SharePointFolderMapping(
                sharepoint_connection_id=connection.id,
                section_id=section.id,
                document_type_id=document_type.id,
                mapping_scope=FolderMappingScope.SECTION_DOCUMENT_TYPE,
                remote_folder_path="section-document-type-high-priority",
                priority=2,
            ),
        ]
        session.add_all(mappings)
        await session.commit()

        resolved = await SharePointMappingRepository(
            session
        ).resolve_folder(
            connection_id=connection.id,
            department_id=department.id,
            section_id=section.id,
            document_type_id=document_type.id,
        )
        assert resolved is not None
        assert (
            resolved.remote_folder_path
            == "section-document-type-high-priority"
        )

        resolved.is_active = False
        await session.commit()
        fallback = await SharePointMappingRepository(
            session
        ).resolve_folder(
            connection_id=connection.id,
            department_id=department.id,
            section_id=section.id,
            document_type_id=document_type.id,
        )
        assert fallback is not None
        assert fallback.remote_folder_path == (
            "section-document-type-low-priority"
        )


@pytest.mark.asyncio
async def test_profile_local_discovery_is_scoped_and_resolves_exact_revision(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        department = Department(code="LCL", name="Local Scope")
        other_department = Department(code="OTH", name="Other Scope")
        document_type = DocumentType(
            code="WI",
            name="Work Instruction",
            category="OTHER",
        )
        status = DocumentStatus(
            code="DRAFT",
            name="Draft",
            display_order=1,
        )
        connection = SharePointConnection(
            name="Local Discovery",
            tenant_id_reference="tenant",
            site_hostname="tenant.sharepoint.com",
            site_path="/sites/compliance",
            drive_id="drive",
            library_name="Documents",
            root_folder_path="DocumentCompliance",
        )
        session.add_all(
            [
                department,
                other_department,
                document_type,
                status,
                connection,
            ]
        )
        await session.flush()
        profile = SharePointSyncProfile(
            name="Department Local Discovery",
            sharepoint_connection_id=connection.id,
            direction=SyncDirection.OUTBOUND,
            scope_type=FolderMappingScope.DEPARTMENT,
            department_id=department.id,
            conflict_policy=ConflictPolicy.MANUAL,
            is_active=True,
        )
        included_document = Document(
            company_code="MTI",
            department=department,
            document_type=document_type,
            document_number="001",
            base_document_code="MTI-LCL-WI-001",
            title="Included",
        )
        included_revision = DocumentRevision(
            document=included_document,
            revision_code="Rev.000",
            revision_number=0,
            full_document_code="MTI-LCL-WI-001_Rev.000",
            document_status=status,
            is_current=True,
        )
        included_file = DocumentFile(
            document=included_document,
            revision=included_revision,
            original_filename="MTI-LCL-WI-001_Rev.000.pdf",
            sanitized_filename="MTI-LCL-WI-001_Rev.000.pdf",
            file_extension="pdf",
            mime_type="application/pdf",
            detected_mime_type="application/pdf",
            file_size=10,
            sha256_hash="1" * 64,
            storage_key="documents/included.pdf",
            file_status=DocumentFileStatus.AVAILABLE,
            is_primary=True,
            is_current=True,
        )
        excluded_document = Document(
            company_code="MTI",
            department=other_department,
            document_type=document_type,
            document_number="002",
            base_document_code="MTI-OTH-WI-002",
            title="Excluded",
        )
        excluded_revision = DocumentRevision(
            document=excluded_document,
            revision_code="Rev.000",
            revision_number=0,
            full_document_code="MTI-OTH-WI-002_Rev.000",
            document_status=status,
            is_current=True,
        )
        excluded_file = DocumentFile(
            document=excluded_document,
            revision=excluded_revision,
            original_filename="MTI-OTH-WI-002_Rev.000.pdf",
            sanitized_filename="MTI-OTH-WI-002_Rev.000.pdf",
            file_extension="pdf",
            mime_type="application/pdf",
            detected_mime_type="application/pdf",
            file_size=10,
            sha256_hash="2" * 64,
            storage_key="documents/excluded.pdf",
            file_status=DocumentFileStatus.AVAILABLE,
            is_primary=True,
            is_current=True,
        )
        session.add_all(
            [
                profile,
                included_document,
                included_revision,
                included_file,
                excluded_document,
                excluded_revision,
                excluded_file,
            ]
        )
        await session.commit()

        repository = SharePointSyncRepository(session)
        files = await repository.list_profile_document_files(
            profile,
            drive_id="drive",
        )
        matched = await repository.get_profile_revision_by_full_code(
            profile,
            full_document_code="MTI-LCL-WI-001_Rev.000",
        )
        out_of_scope = await repository.get_profile_revision_by_full_code(
            profile,
            full_document_code="MTI-OTH-WI-002_Rev.000",
        )
        job = SharePointSyncJob(
            sync_profile_id=profile.id,
            sharepoint_connection_id=connection.id,
            job_type=SyncJobType.MANUAL_FULL,
            direction=SyncDirection.OUTBOUND,
            status=SharePointSyncJobStatus.COMPARING,
            progress=45,
            maximum_attempts=3,
        )
        await repository.add_job(job)
        (
            queued,
            discovered,
            skipped,
            conflicted,
        ) = await SharePointWorkerService(
            get_settings(),
            session_factory=session_factory,
        )._plan_local_profile_items(
            session,
            repository=repository,
            job=job,
            profile=profile,
            drive_id="drive",
            seen_file_ids=set(),
        )
        await session.commit()
        planned_items = await repository.list_all_items(job.id)

    assert [item.id for item in files] == [included_file.id]
    assert matched is not None and matched.id == included_revision.id
    assert out_of_scope is None
    assert (discovered, skipped, conflicted) == (1, 0, 0)
    assert queued == [planned_items[0].id]
    assert planned_items[0].document_file_id == included_file.id
    assert planned_items[0].operation is SyncItemOperation.CREATE_REMOTE


@pytest.mark.asyncio
async def test_scheduled_sync_creation_is_due_and_idempotent(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 7, 26, 4, 30, tzinfo=UTC)
    async with session_factory() as session:
        connection = SharePointConnection(
            name="Scheduled Connection",
            tenant_id_reference="tenant",
            site_hostname="tenant.sharepoint.com",
            site_path="/sites/compliance",
            drive_id="drive",
            library_name="Documents",
            root_folder_path="DocumentCompliance",
        )
        session.add(connection)
        await session.flush()
        profile = SharePointSyncProfile(
            name="Every Minute",
            sharepoint_connection_id=connection.id,
            direction=SyncDirection.OUTBOUND,
            scope_type=FolderMappingScope.GLOBAL,
            conflict_policy=ConflictPolicy.MANUAL,
            sync_schedule="* * * * *",
            delta_sync_enabled=True,
            is_active=True,
            created_at=now - timedelta(minutes=2),
        )
        session.add_all([connection, profile])
        await session.commit()

    settings = get_settings().model_copy(
        update={"sharepoint_sync_enabled": True}
    )
    service = SharePointScheduledSyncService(
        settings,
        session_factory=session_factory,
    )
    dispatched: list[UUID] = []

    def dispatch(job_id: UUID) -> str:
        dispatched.append(job_id)
        return f"task-{job_id}"

    monkeypatch.setattr(service, "_dispatch", dispatch)
    first = await service.dispatch_due(now=now)
    second = await service.dispatch_due(now=now)

    async with session_factory() as session:
        job = await SharePointSyncRepository(
            session
        ).latest_scheduled_job(profile.id)

    assert first == {
        "created": 1,
        "dispatched": 1,
        "skipped": 0,
        "invalid": 0,
        "failed": 0,
    }
    assert second == {
        "created": 0,
        "dispatched": 0,
        "skipped": 1,
        "invalid": 0,
        "failed": 0,
    }
    assert job is not None
    assert job.job_type is SyncJobType.SCHEDULED_INCREMENTAL
    assert job.result_summary_json["scheduleDispatchState"] == "DISPATCHED"
    assert dispatched == [job.id]


def test_sync_profile_contract_validates_scope_and_cron() -> None:
    common = {
        "name": "Profile",
        "sharepointConnectionId": str(uuid4()),
    }
    with pytest.raises(ValidationError, match="scopeType"):
        SharePointSyncProfileCreateRequest.model_validate(
            {
                **common,
                "scopeType": "SECTION",
            }
        )
    with pytest.raises(ValidationError, match="five-field cron"):
        SharePointSyncProfileCreateRequest.model_validate(
            {
                **common,
                "syncSchedule": "every hour",
            }
        )
    manual = SharePointSyncProfileCreateRequest.model_validate(
        {
            **common,
            "syncSchedule": "Manual",
        }
    )
    assert manual.sync_schedule is None
