"""Graph subscription create, renewal, disable, and cleanup."""

from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.database.session import AsyncSessionFactory
from app.integrations.microsoft_graph.graph_client import GraphClient
from app.integrations.microsoft_graph.sharepoint.sharepoint_webhook_service import (
    SharePointWebhookService,
)
from app.models.graph_subscription import GraphSubscription
from app.models.sharepoint_enums import GraphSubscriptionStatus
from app.models.user import User
from app.repositories.graph_subscription_repository import (
    GraphSubscriptionRepository,
)
from app.repositories.sharepoint_connection_repository import (
    SharePointConnectionRepository,
)
from app.repositories.sharepoint_sync_repository import (
    SharePointSyncRepository,
)
from app.schemas.sharepoint_webhook import (
    GraphSubscriptionCreateRequest,
    GraphSubscriptionListResponse,
    GraphSubscriptionResponse,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.sharepoint._common import (
    SharePointServiceBase,
    sharepoint_error,
    total_pages,
)
from app.services.sharepoint.graph_factory import create_graph_client
from app.utils.datetime import utc_now


class GraphSubscriptionService(SharePointServiceBase):
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.settings = settings
        self.repository = GraphSubscriptionRepository(session)

    async def list(
        self,
        *,
        statuses: list[GraphSubscriptionStatus] | None,
        page: int,
        page_size: int,
    ) -> GraphSubscriptionListResponse:
        items, total = await self.repository.list_page(
            statuses=statuses,
            page=page,
            page_size=page_size,
        )
        return GraphSubscriptionListResponse(
            items=[
                GraphSubscriptionResponse.model_validate(item)
                for item in items
            ],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=total_pages(total, page_size),
        )

    async def create(
        self,
        payload: GraphSubscriptionCreateRequest,
    ) -> GraphSubscriptionResponse:
        profile = await SharePointSyncRepository(self.session).get_profile(
            payload.sync_profile_id
        )
        connection = await SharePointConnectionRepository(
            self.session
        ).get_by_id(payload.sharepoint_connection_id)
        if (
            profile is None
            or connection is None
            or profile.sharepoint_connection_id != connection.id
        ):
            raise sharepoint_error(
                "The SharePoint subscription scope is invalid.",
                code="SHAREPOINT_CONNECTION_NOT_FOUND",
                status_code=HTTPStatus.NOT_FOUND,
            )
        if profile.department_id is not None:
            self.policy.ensure_department(profile.department_id)
        if not profile.is_active or not profile.webhook_enabled:
            raise sharepoint_error(
                "The selected sync profile does not enable webhooks.",
                code="SHAREPOINT_SYNC_FAILED",
                status_code=HTTPStatus.CONFLICT,
            )
        expected_resource_prefix = (
            f"drives/{connection.drive_id}/"
            if connection.drive_id
            else ""
        )
        normalized_resource = payload.resource.lstrip("/")
        if (
            not expected_resource_prefix
            or not normalized_resource.startswith(expected_resource_prefix)
        ):
            raise sharepoint_error(
                "The subscription resource is outside the configured drive.",
                code="GRAPH_AUTHORIZATION_FAILED",
                status_code=HTTPStatus.FORBIDDEN,
            )
        configured_url = getattr(
            self.settings,
            "sharepoint_webhook_notification_url",
            None,
        )
        if (
            configured_url
            and payload.notification_url.rstrip("/")
            != str(configured_url).rstrip("/")
        ):
            raise sharepoint_error(
                "The notification URL does not match server configuration.",
                code="SHAREPOINT_CONNECTION_FAILED",
            )
        graph = create_graph_client(self.settings)
        try:
            remote = await graph.post(
                "/subscriptions",
                payload={
                    "changeType": payload.change_type,
                    "notificationUrl": payload.notification_url,
                    "lifecycleNotificationUrl": (
                        payload.lifecycle_notification_url
                    ),
                    "resource": payload.resource,
                    "expirationDateTime": (
                        payload.expiration_datetime.isoformat()
                    ),
                    "clientState": payload.client_state.get_secret_value(),
                },
                expected_statuses={200, 201},
            )
        finally:
            await graph.close()
        remote_id = remote.get("id")
        if not isinstance(remote_id, str) or not remote_id:
            raise sharepoint_error(
                "Graph did not return a subscription identifier.",
                code="SHAREPOINT_CONNECTION_FAILED",
            )
        subscription = GraphSubscription(
            sharepoint_connection_id=payload.sharepoint_connection_id,
            sync_profile_id=payload.sync_profile_id,
            subscription_id=remote_id,
            resource=payload.resource,
            change_type=payload.change_type,
            notification_url=payload.notification_url,
            lifecycle_notification_url=payload.lifecycle_notification_url,
            client_state_hash=(
                SharePointWebhookService.client_state_hash(
                    payload.client_state.get_secret_value()
                )
            ),
            expiration_datetime=payload.expiration_datetime,
            status=GraphSubscriptionStatus.ACTIVE,
        )
        await self.repository.add(subscription)
        await self.audit_if_registered(
            "CREATE_GRAPH_SUBSCRIPTION",
            entity_type="GraphSubscription",
            entity_id=subscription.id,
            description="Microsoft Graph subscription created.",
            values={
                "connectionId": str(subscription.sharepoint_connection_id),
                "profileId": str(subscription.sync_profile_id),
                "resource": subscription.resource,
            },
        )
        await self.session.commit()
        return GraphSubscriptionResponse.model_validate(subscription)

    async def renew(
        self,
        subscription_id: UUID,
        *,
        expiration_datetime,
    ) -> GraphSubscriptionResponse:
        subscription = await self._get(subscription_id, for_update=True)
        graph = create_graph_client(self.settings)
        try:
            remote = await graph.patch(
                f"/subscriptions/{subscription.subscription_id}",
                payload={
                    "expirationDateTime": expiration_datetime.isoformat()
                },
            )
        finally:
            await graph.close()
        remote_expiry = remote.get("expirationDateTime")
        subscription.expiration_datetime = expiration_datetime
        if isinstance(remote_expiry, str):
            from datetime import datetime

            subscription.expiration_datetime = datetime.fromisoformat(
                remote_expiry.replace("Z", "+00:00")
            )
        subscription.status = GraphSubscriptionStatus.ACTIVE
        subscription.last_renewed_at = utc_now()
        subscription.renewal_attempts += 1
        subscription.error_code = None
        subscription.error_message = None
        await self.audit_if_registered(
            "RENEW_GRAPH_SUBSCRIPTION",
            entity_type="GraphSubscription",
            entity_id=subscription.id,
            description="Microsoft Graph subscription renewed.",
        )
        await self.session.commit()
        return GraphSubscriptionResponse.model_validate(subscription)

    async def renew_expiring(self) -> dict[str, int]:
        deadline = utc_now() + timedelta(
            hours=int(
                getattr(
                    self.settings,
                    "sharepoint_webhook_renewal_hours",
                    24,
                )
            )
        )
        subscriptions = await self.repository.expiring_before(deadline)
        renewed = failed = 0
        for subscription in subscriptions:
            try:
                await self.renew(
                    subscription.id,
                    expiration_datetime=deadline + timedelta(days=2),
                )
                renewed += 1
            except Exception:  # noqa: BLE001 - isolate per-subscription failure
                await self.session.rollback()
                current = await self.repository.get_by_id(
                    subscription.id,
                    for_update=True,
                )
                if current is not None:
                    current.status = GraphSubscriptionStatus.RENEWAL_FAILED
                    current.renewal_attempts += 1
                    current.error_code = "GRAPH_SUBSCRIPTION_RENEWAL_FAILED"
                    current.error_message = (
                        "Microsoft Graph subscription renewal failed."
                    )
                    await self.session.commit()
                failed += 1
        return {"renewed": renewed, "failed": failed}

    async def disable(
        self,
        subscription_id: UUID,
        *,
        reason: str,
    ) -> GraphSubscriptionResponse:
        subscription = await self._get(subscription_id, for_update=True)
        subscription.status = GraphSubscriptionStatus.DISABLED
        subscription.error_message = reason.strip()
        await self.session.commit()
        return GraphSubscriptionResponse.model_validate(subscription)

    async def delete_remote(self, subscription_id: UUID) -> None:
        subscription = await self._get(subscription_id, for_update=True)
        graph = create_graph_client(self.settings)
        try:
            await graph.delete(
                f"/subscriptions/{subscription.subscription_id}"
            )
        finally:
            await graph.close()
        subscription.status = GraphSubscriptionStatus.DELETED
        await self.audit_if_registered(
            "DELETE_GRAPH_SUBSCRIPTION",
            entity_type="GraphSubscription",
            entity_id=subscription.id,
            description="Microsoft Graph subscription deleted.",
        )
        await self.session.commit()

    async def _get(
        self,
        subscription_id: UUID,
        *,
        for_update: bool = False,
    ) -> GraphSubscription:
        subscription = await self.repository.get_by_id(
            subscription_id,
            for_update=for_update,
        )
        if subscription is None:
            raise sharepoint_error(
                "Microsoft Graph subscription was not found.",
                code="SHAREPOINT_CONNECTION_NOT_FOUND",
                status_code=HTTPStatus.NOT_FOUND,
            )
        return subscription


class GraphSubscriptionRenewalWorkerService:
    """System actor used by Celery Beat; never requires a fabricated user."""

    def __init__(
        self,
        settings: Settings,
        *,
        session_factory=AsyncSessionFactory,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory

    async def renew_expiring(self) -> dict[str, int]:
        deadline = utc_now() + timedelta(
            hours=int(
                getattr(
                    self.settings,
                    "sharepoint_webhook_renewal_hours",
                    24,
                )
            )
        )
        async with self.session_factory() as session:
            repository = GraphSubscriptionRepository(session)
            identifiers = [
                subscription.id
                for subscription in await repository.expiring_before(deadline)
            ]
        renewed = failed = 0
        for identifier in identifiers:
            graph: GraphClient | None = None
            try:
                async with self.session_factory() as session:
                    repository = GraphSubscriptionRepository(session)
                    subscription = await repository.get_by_id(
                        identifier,
                        for_update=True,
                    )
                    if subscription is None:
                        continue
                    new_expiry = deadline + timedelta(days=2)
                    remote_id = subscription.subscription_id
                    await session.commit()
                graph = create_graph_client(self.settings)
                remote = await graph.patch(
                    f"/subscriptions/{remote_id}",
                    payload={
                        "expirationDateTime": new_expiry.isoformat()
                    },
                )
                async with self.session_factory() as session:
                    subscription = await GraphSubscriptionRepository(
                        session
                    ).get_by_id(identifier, for_update=True)
                    if subscription is None:
                        continue
                    remote_expiry = remote.get("expirationDateTime")
                    if isinstance(remote_expiry, str):
                        from datetime import datetime

                        new_expiry = datetime.fromisoformat(
                            remote_expiry.replace("Z", "+00:00")
                        )
                    subscription.expiration_datetime = new_expiry
                    subscription.status = GraphSubscriptionStatus.ACTIVE
                    subscription.last_renewed_at = utc_now()
                    subscription.renewal_attempts += 1
                    subscription.error_code = None
                    subscription.error_message = None
                    await session.commit()
                renewed += 1
            except Exception:  # noqa: BLE001 - isolate per-subscription failure
                async with self.session_factory() as session:
                    subscription = await GraphSubscriptionRepository(
                        session
                    ).get_by_id(identifier, for_update=True)
                    if subscription is not None:
                        subscription.status = (
                            GraphSubscriptionStatus.RENEWAL_FAILED
                        )
                        subscription.renewal_attempts += 1
                        subscription.error_code = (
                            "GRAPH_SUBSCRIPTION_RENEWAL_FAILED"
                        )
                        subscription.error_message = (
                            "Microsoft Graph subscription renewal failed."
                        )
                        await session.commit()
                failed += 1
            finally:
                if graph is not None:
                    await graph.close()
        return {"renewed": renewed, "failed": failed}
