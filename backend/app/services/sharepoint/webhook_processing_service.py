"""Fast webhook validation, deduplication, persistence, and queue dispatch."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.integrations.microsoft_graph.sharepoint.sharepoint_webhook_service import (
    SharePointWebhookService,
)
from app.models.graph_webhook_event import GraphWebhookEvent
from app.models.sharepoint_enums import (
    GraphSubscriptionStatus,
    GraphWebhookProcessingStatus,
    SharePointSyncJobStatus,
    SyncJobType,
)
from app.models.sharepoint_sync_job import SharePointSyncJob
from app.repositories.graph_subscription_repository import (
    GraphSubscriptionRepository,
)
from app.repositories.sharepoint_sync_repository import (
    SharePointSyncRepository,
)
from app.schemas.sharepoint_webhook import GraphWebhookAcceptedResponse
from app.utils.datetime import utc_now


class GraphWebhookProcessingService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
    ) -> None:
        self.session = session
        self.settings = settings
        self.repository = GraphSubscriptionRepository(session)
        self.sync = SharePointSyncRepository(session)
        self.webhooks = SharePointWebhookService()

    async def accept(
        self,
        payload: dict[str, Any],
    ) -> GraphWebhookAcceptedResponse:
        accepted = duplicates = rejected = 0
        queued_event_ids: list[UUID] = []
        for notification in self.webhooks.extract_notifications(payload):
            remote_subscription_id = notification.get("subscriptionId")
            if not isinstance(remote_subscription_id, str):
                rejected += 1
                continue
            subscription = await self.repository.get_by_remote_id(
                remote_subscription_id,
                for_update=True,
            )
            if (
                subscription is None
                or subscription.status
                not in {
                    GraphSubscriptionStatus.ACTIVE,
                    GraphSubscriptionStatus.EXPIRING,
                }
                or not self.webhooks.validate_client_state(
                    notification.get("clientState"),
                    subscription.client_state_hash,
                )
            ):
                rejected += 1
                continue
            notification_without_state = {
                key: value
                for key, value in notification.items()
                if key != "clientState"
            }
            payload_hash = self.webhooks.payload_hash(
                notification_without_state
            )
            if (
                await self.repository.get_event_by_payload(
                    subscription_id=remote_subscription_id,
                    payload_hash=payload_hash,
                )
                is not None
            ):
                duplicates += 1
                continue
            event = GraphWebhookEvent(
                subscription_id=remote_subscription_id,
                resource=str(notification.get("resource") or ""),
                change_type=str(notification.get("changeType") or "updated"),
                tenant_id=(
                    str(notification.get("tenantId"))
                    if notification.get("tenantId") is not None
                    else None
                ),
                client_state_valid=True,
                payload_hash=payload_hash,
                processing_status=GraphWebhookProcessingStatus.QUEUED,
                metadata_json=self.webhooks.safe_metadata(notification),
            )
            try:
                await self.repository.add_event(event)
                subscription.last_notification_at = utc_now()
                await self.session.commit()
            except IntegrityError:
                await self.session.rollback()
                duplicates += 1
                continue
            queued_event_ids.append(event.id)
            accepted += 1
        for event_id in queued_event_ids:
            await self._dispatch(event_id)
        return GraphWebhookAcceptedResponse(
            accepted=accepted,
            duplicates=duplicates,
            rejected=rejected,
        )

    async def process_event(self, event_id: UUID) -> None:
        event = await self.repository.get_event(event_id, for_update=True)
        if event is None or event.processing_status in {
            GraphWebhookProcessingStatus.PROCESSED,
            GraphWebhookProcessingStatus.IGNORED,
            GraphWebhookProcessingStatus.DUPLICATE,
        }:
            return
        subscription = await self.repository.get_by_remote_id(
            event.subscription_id
        )
        if subscription is None or subscription.status not in {
            GraphSubscriptionStatus.ACTIVE,
            GraphSubscriptionStatus.EXPIRING,
        }:
            event.processing_status = GraphWebhookProcessingStatus.IGNORED
            event.processed_at = utc_now()
            await self.session.commit()
            return
        active = await self.sync.active_job(subscription.sync_profile_id)
        if active is not None:
            event.processing_status = GraphWebhookProcessingStatus.PROCESSED
            event.processed_at = utc_now()
            event.sync_job_id = active.id
            await self.session.commit()
            return
        profile = await self.sync.get_profile(subscription.sync_profile_id)
        if profile is None or not profile.is_active:
            event.processing_status = GraphWebhookProcessingStatus.IGNORED
            event.processed_at = utc_now()
            await self.session.commit()
            return
        job = SharePointSyncJob(
            sync_profile_id=profile.id,
            sharepoint_connection_id=profile.sharepoint_connection_id,
            job_type=SyncJobType.WEBHOOK_INCREMENTAL,
            direction=profile.direction,
            status=SharePointSyncJobStatus.QUEUED,
            progress=0,
            current_stage="Queued from validated Graph webhook",
            scope_json={"webhookEventId": str(event.id)},
            maximum_attempts=max(
                1,
                int(getattr(self.settings, "sharepoint_max_retries", 3))
                + 1,
            ),
        )
        await self.sync.add_job(job)
        event.sync_job_id = job.id
        event.processing_status = GraphWebhookProcessingStatus.PROCESSED
        event.processed_at = utc_now()
        await self.session.commit()
        from app.workers.sharepoint_tasks import process_sharepoint_sync_job

        process_sharepoint_sync_job.apply_async(
            args=[str(job.id)],
            queue=str(
                getattr(
                    self.settings,
                    "sharepoint_queue_name",
                    "sharepoint",
                )
            ),
            task_id=str(uuid4()),
        )

    async def _dispatch(self, event_id: UUID) -> None:
        from app.workers.sharepoint_tasks import process_graph_webhook_event

        process_graph_webhook_event.apply_async(
            args=[str(event_id)],
            queue=str(
                getattr(
                    self.settings,
                    "sharepoint_queue_name",
                    "sharepoint",
                )
            ),
            task_id=str(uuid4()),
        )
