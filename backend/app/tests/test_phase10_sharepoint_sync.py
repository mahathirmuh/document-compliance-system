"""SharePoint planning, metadata, delta-state, and webhook regressions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.microsoft_graph_webhook import (
    microsoft_graph_webhook,
)
from app.integrations.microsoft_graph.sharepoint.sharepoint_webhook_service import (
    SharePointWebhookService,
)
from app.models.graph_webhook_event import GraphWebhookEvent
from app.models.sharepoint_enums import (
    ConflictPolicy,
    GraphSubscriptionStatus,
    MetadataDataType,
    SharePointSyncJobStatus,
    SyncConflictResolution,
    SyncConflictType,
    SyncDirection,
    SyncItemOperation,
)
from app.models.sharepoint_sync_job import SharePointSyncJob
from app.schemas.sharepoint_sync import SharePointSyncJobResponse
from app.schemas.sharepoint_webhook import GraphSubscriptionCreateRequest
from app.services.secrets.encryption_service import AesGcmEncryptionService
from app.services.sharepoint.delta_state_service import (
    SharePointDeltaStateService,
)
from app.services.sharepoint.file_integration_service import (
    SharePointFileIntegrationService,
)
from app.services.sharepoint.metadata_transformer import (
    SharePointMetadataTransformer,
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
    transformer = SharePointMetadataTransformer()

    assert transformer.transform(
        "false",
        data_type=MetadataDataType.BOOLEAN,
    ) is False
    assert transformer.transform(
        "  hrm ",
        data_type=MetadataDataType.STRING,
        transformer_code="UPPERCASE",
    ) == "HRM"
    assert transformer.transform(
        {"revision": 2, "valid": True},
        data_type=MetadataDataType.JSON_STRING,
    ) == '{"revision":2,"valid":true}'
    assert transformer.transform(
        "2026-07-26",
        data_type=MetadataDataType.DATE,
    ) == "2026-07-26"
    with pytest.raises(ValueError, match="Unregistered"):
        transformer.transform(
            "value",
            data_type=MetadataDataType.STRING,
            transformer_code="__import__('os')",
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
