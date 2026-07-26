"""Focused notification architecture and tenant-ownership tests."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.authorization import AuditAction
from app.core.exceptions import ApplicationError
from app.models.audit_log import AuditLog
from app.models.in_app_notification import InAppNotification
from app.models.notification_enums import (
    NotificationChannel,
    NotificationContentType,
    NotificationEventType,
    NotificationRecipientType,
    NotificationScopeType,
    NotificationSeverity,
)
from app.models.notification_preference import NotificationPreference
from app.models.notification_rule import NotificationRule
from app.models.notification_template import NotificationTemplate
from app.schemas.notification import InAppNotificationCreate
from app.services.notification.channels.base_notification_channel import (
    BaseNotificationChannel,
)
from app.services.notification.channels.graph_email_notification_channel import (
    GraphEmailNotificationChannel,
)
from app.services.notification.channels.teams_notification_channel import (
    TeamsNotificationChannel,
)
from app.services.notification.channels.telegram_notification_channel import (
    TelegramNotificationChannel,
)
from app.services.notification.contracts import (
    DeliveryResult,
    NotificationEvent,
    NotificationMessage,
    ResolvedRecipient,
)
from app.services.notification.notification_dispatch_service import (
    NotificationDispatchService,
)
from app.services.notification.notification_preference_service import (
    NotificationPreferenceService,
)
from app.services.notification.notification_service import (
    NotificationOrchestrationService,
    NotificationService,
)
from app.services.notification.notification_template_service import (
    NotificationTemplateRenderError,
    render_controlled_template,
)


class FakeGraphMailClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def send_mail(
        self,
        *,
        sender_user_id: str,
        message: dict[str, Any],
        client_request_id: str | None,
    ) -> str:
        self.calls.append(
            {
                "sender": sender_user_id,
                "message": message,
                "requestId": client_request_id,
            }
        )
        return "graph-message-id"


class FakeNotificationPublisher:
    def __init__(self) -> None:
        self.items: list[tuple[dict[str, Any], bool]] = []

    async def publish(
        self,
        payload: dict[str, Any],
        *,
        digest: bool,
    ) -> str:
        self.items.append((payload, digest))
        return "queued-id"


class FakeTeamsClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def post_json(
        self,
        *,
        url: str,
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> str:
        self.calls.append(
            {
                "url": url,
                "payload": payload,
                "timeout": timeout_seconds,
            }
        )
        return "teams-message-id"


class FakeTelegramClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    async def send_message(self, *, chat_id: str, text: str) -> str:
        self.calls.append({"chatId": chat_id, "text": text})
        return "telegram-message-id"


class FailingTelegramChannel(BaseNotificationChannel):
    channel = NotificationChannel.TELEGRAM

    async def send(
        self,
        message: NotificationMessage,
        *,
        request_id: str | None = None,
    ) -> DeliveryResult:
        return DeliveryResult(
            succeeded=False,
            error_code="NOTIFICATION_TELEGRAM_SEND_FAILED",
            error_message="Provider unavailable.",
            retryable=True,
        )


def _email_message(reference: str = "recipient@example.com") -> NotificationMessage:
    return NotificationMessage(
        event_type=NotificationEventType.REPORT_GENERATED,
        channel=NotificationChannel.EMAIL_GRAPH,
        recipient=ResolvedRecipient(
            recipient_type=NotificationRecipientType.SPECIFIC_EMAILS,
            reference=reference,
        ),
        subject="Report ready\r\nBcc: attacker@example.com",
        body="<p>Ready</p>",
        content_type=NotificationContentType.HTML,
        severity=NotificationSeverity.INFORMATION,
    )


def _plain_message(
    *,
    channel: NotificationChannel,
    recipient_type: NotificationRecipientType,
    reference: str,
    subject: str = "System notice",
    body: str = "The background task completed.",
) -> NotificationMessage:
    return NotificationMessage(
        event_type=NotificationEventType.SYSTEM_WORKER_UNAVAILABLE,
        channel=channel,
        recipient=ResolvedRecipient(
            recipient_type=recipient_type,
            reference=reference,
        ),
        subject=subject,
        body=body,
        content_type=NotificationContentType.PLAIN_TEXT,
        severity=NotificationSeverity.WARNING,
    )


def test_controlled_template_escapes_html_and_rejects_code_syntax() -> None:
    rendered = render_controlled_template(
        "<p>Hello {{ user.name }}</p>",
        {"user": {"name": "<script>alert(1)</script>"}},
        escape_html=True,
    )
    assert rendered == ("<p>Hello &lt;script&gt;alert(1)&lt;/script&gt;</p>")

    with pytest.raises(NotificationTemplateRenderError):
        render_controlled_template(
            "{% for item in items %}{{ item }}{% endfor %}",
            {"items": ["unsafe"]},
            escape_html=False,
        )
    with pytest.raises(NotificationTemplateRenderError):
        render_controlled_template(
            "{{ missing.value }}",
            {},
            escape_html=False,
        )


@pytest.mark.parametrize(
    "value",
    (
        "https://attacker.example/path",
        "//attacker.example/path",
        r"/safe\..\redirect",
    ),
)
def test_in_app_action_url_rejects_external_routes(value: str) -> None:
    with pytest.raises(ValidationError):
        InAppNotificationCreate(
            user_id=uuid4(),
            event_type=NotificationEventType.DOCUMENT_UPLOADED,
            title="Uploaded",
            message="Document uploaded.",
            action_url=value,
        )


@pytest.mark.asyncio
async def test_graph_adapter_uses_fixed_sender_and_sanitizes_subject() -> None:
    client = FakeGraphMailClient()
    channel = GraphEmailNotificationChannel(
        client,
        enabled=True,
        sender_user_id="configured-mailbox-id",
        reply_to="noreply@example.com",
        maximum_recipients=2,
    )
    result = await channel.send(
        _email_message(),
        request_id="request-123",
    )

    assert result.succeeded is True
    assert result.provider_message_id == "graph-message-id"
    assert client.calls[0]["sender"] == "configured-mailbox-id"
    graph_message = client.calls[0]["message"]
    assert "\r" not in graph_message["subject"]
    assert "\n" not in graph_message["subject"]
    assert graph_message["replyTo"][0]["emailAddress"]["address"] == (
        "noreply@example.com"
    )
    assert "token" not in str(graph_message).casefold()


@pytest.mark.asyncio
async def test_graph_adapter_rejects_arbitrary_recipient() -> None:
    client = FakeGraphMailClient()
    channel = GraphEmailNotificationChannel(
        client,
        enabled=True,
        sender_user_id="configured-mailbox-id",
    )
    with pytest.raises(Exception, match="recipient is invalid"):
        await channel.send(_email_message("not-an-email"))
    assert client.calls == []


@pytest.mark.asyncio
async def test_teams_and_telegram_adapters_are_mocked_and_bounded() -> None:
    teams_client = FakeTeamsClient()
    teams = TeamsNotificationChannel(
        teams_client,
        enabled=True,
        mode="incoming_webhook",
        webhook_url="https://hooks.example.test/secret-path",
        timeout_seconds=4,
    )
    teams_result = await teams.send(
        _plain_message(
            channel=NotificationChannel.TEAMS,
            recipient_type=NotificationRecipientType.TEAMS_CHANNEL,
            reference="configured-webhook",
            subject="s" * 700,
            body="b" * 7000,
        )
    )
    assert teams_result.succeeded is True
    card_body = teams_client.calls[0]["payload"]["attachments"][0]["content"]["body"]
    assert len(card_body[0]["text"]) == 500
    assert len(card_body[1]["text"]) == 5000

    telegram_client = FakeTelegramClient()
    telegram = TelegramNotificationChannel(
        telegram_client,
        enabled=True,
        default_chat_id=None,
    )
    telegram_result = await telegram.send(
        _plain_message(
            channel=NotificationChannel.TELEGRAM,
            recipient_type=NotificationRecipientType.TELEGRAM_CHAT,
            reference="trusted-chat",
            subject="s" * 700,
            body="b" * 5000,
        )
    )
    assert telegram_result.succeeded is True
    assert telegram_client.calls[0]["chatId"] == "trusted-chat"
    assert len(telegram_client.calls[0]["text"]) <= 4002


@pytest.mark.asyncio
async def test_disabled_notification_channel_does_not_call_provider() -> None:
    client = FakeTelegramClient()
    result = await TelegramNotificationChannel(
        client,
        enabled=False,
        default_chat_id="configured-chat",
    ).send(
        _plain_message(
            channel=NotificationChannel.TELEGRAM,
            recipient_type=NotificationRecipientType.TELEGRAM_CHAT,
            reference="trusted-chat",
        )
    )
    assert result.succeeded is False
    assert result.error_code == "NOTIFICATION_CHANNEL_DISABLED"
    assert result.retryable is False
    assert client.calls == []


@pytest.mark.asyncio
async def test_failed_dispatch_is_retry_scheduled_and_audited_without_body(
    session_factory,
) -> None:
    message = NotificationMessage(
        event_type=NotificationEventType.SYSTEM_SECURITY_ALERT,
        channel=NotificationChannel.TELEGRAM,
        recipient=ResolvedRecipient(
            recipient_type=NotificationRecipientType.TELEGRAM_CHAT,
            reference="trusted-chat",
        ),
        subject="Security alert",
        body="sensitive body must not enter audit",
        content_type=NotificationContentType.PLAIN_TEXT,
        severity=NotificationSeverity.CRITICAL,
    )
    async with session_factory() as session:
        delivery = await NotificationDispatchService(
            session,
            channels={NotificationChannel.TELEGRAM: FailingTelegramChannel()},
            maximum_attempts=3,
        ).dispatch(message, template_id=None)
        audit = await session.scalar(
            select(AuditLog).where(AuditLog.entity_id == delivery.id)
        )
    assert delivery.status.value == "RETRY_SCHEDULED"
    assert delivery.next_retry_at is not None
    assert audit is not None
    assert audit.action == AuditAction.FAIL_NOTIFICATION
    assert "sensitive body" not in str(audit.new_values_json)


@pytest.mark.asyncio
async def test_retry_exhaustion_records_each_failure_without_payload(
    session_factory,
) -> None:
    message = _plain_message(
        channel=NotificationChannel.TELEGRAM,
        recipient_type=NotificationRecipientType.TELEGRAM_CHAT,
        reference="trusted-chat",
        body="private retry payload",
    )
    async with session_factory() as session:
        service = NotificationDispatchService(
            session,
            channels={NotificationChannel.TELEGRAM: FailingTelegramChannel()},
            maximum_attempts=2,
            retry_base_seconds=1,
        )
        delivery = await service.dispatch(message, template_id=None)
        retried = await service.retry_existing(delivery.id, message)
        audit_count = int(
            await session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.entity_id == delivery.id)
            )
            or 0
        )
        audit_values = list(
            await session.scalars(
                select(AuditLog).where(AuditLog.entity_id == delivery.id)
            )
        )
    assert retried.status.value == "FAILED"
    assert retried.attempt_count == 2
    assert retried.error_code == "NOTIFICATION_RETRY_EXHAUSTED"
    assert audit_count == 2
    assert all(
        "private retry payload" not in str(item.new_values_json)
        for item in audit_values
    )


@pytest.mark.asyncio
async def test_in_app_mutation_is_strictly_user_owned(
    session_factory,
    create_user,
) -> None:
    owner = await create_user(email="owner@example.com")
    other = await create_user(email="other@example.com")
    notification_id = uuid4()
    async with session_factory() as session:
        session.add(
            InAppNotification(
                id=notification_id,
                user_id=owner.id,
                event_type=NotificationEventType.DOCUMENT_UPLOADED,
                title="Uploaded",
                message="A private document was uploaded.",
                severity=NotificationSeverity.INFORMATION,
            )
        )
        await session.commit()

    async with session_factory() as session:
        with pytest.raises(ApplicationError) as caught:
            await NotificationService(
                session,
                user_id=other.id,
            ).mark_read(notification_id)
        assert caught.value.status_code == 404

    async with session_factory() as session:
        result = await NotificationService(
            session,
            user_id=owner.id,
        ).mark_read(notification_id)
        assert result.notification_id == notification_id


@pytest.mark.asyncio
async def test_unread_count_and_read_all_are_user_scoped_and_ignore_expired(
    session_factory,
    create_user,
) -> None:
    owner = await create_user(email="read-all-owner@example.com")
    other = await create_user(email="read-all-other@example.com")
    async with session_factory() as session:
        session.add_all(
            [
                InAppNotification(
                    user_id=owner.id,
                    event_type=NotificationEventType.DOCUMENT_UPLOADED,
                    title="Current",
                    message="Visible unread notification.",
                    severity=NotificationSeverity.INFORMATION,
                ),
                InAppNotification(
                    user_id=owner.id,
                    event_type=NotificationEventType.DOCUMENT_UPLOADED,
                    title="Expired",
                    message="Expired unread notification.",
                    severity=NotificationSeverity.INFORMATION,
                    expires_at=datetime.now(UTC) - timedelta(minutes=1),
                ),
                InAppNotification(
                    user_id=other.id,
                    event_type=NotificationEventType.DOCUMENT_UPLOADED,
                    title="Other",
                    message="Another user's unread notification.",
                    severity=NotificationSeverity.INFORMATION,
                ),
            ]
        )
        await session.commit()

    async with session_factory() as session:
        service = NotificationService(session, user_id=owner.id)
        assert (await service.unread_count()).unread_count == 1
        assert (await service.mark_all_read()).affected_count == 1
        assert (await service.unread_count()).unread_count == 0
        assert (
            await NotificationService(
                session,
                user_id=other.id,
            ).unread_count()
        ).unread_count == 1


@pytest.mark.asyncio
async def test_preference_quiet_hours_and_critical_mandatory_bypass(
    session_factory,
    create_user,
) -> None:
    user = await create_user(email="quiet@example.com")
    async with session_factory() as session:
        session.add(
            NotificationPreference(
                user_id=user.id,
                event_type=NotificationEventType.REPORT_GENERATED,
                in_app_enabled=True,
                email_enabled=True,
                quiet_hours_enabled=True,
                quiet_hours_start=time(22, 0),
                quiet_hours_end=time(6, 0),
                timezone="UTC",
            )
        )
        await session.commit()

    during_quiet_hours = datetime(2026, 1, 1, 23, 0, tzinfo=UTC)
    async with session_factory() as session:
        service = NotificationPreferenceService(session, user_id=user.id)
        preferences = await service.list()
        assert len(preferences) == len(NotificationEventType)
        assert (
            next(
                item
                for item in preferences
                if item.event_type == NotificationEventType.DOCUMENT_UPLOADED
            ).id
            is None
        )
        assert (
            await service.delivery_allowed(
                event_type=NotificationEventType.REPORT_GENERATED,
                channel=NotificationChannel.EMAIL_GRAPH,
                mandatory_rule=False,
                now=during_quiet_hours,
            )
            is False
        )
        assert (
            await service.delivery_allowed(
                event_type=NotificationEventType.SYSTEM_SECURITY_ALERT,
                channel=NotificationChannel.EMAIL_GRAPH,
                mandatory_rule=True,
                now=during_quiet_hours,
            )
            is True
        )
        assert (
            await service.delivery_allowed(
                event_type=NotificationEventType.REPORT_GENERATED,
                channel=NotificationChannel.EMAIL_GRAPH,
                mandatory_rule=True,
                now=during_quiet_hours,
            )
            is False
        )


@pytest.mark.asyncio
async def test_event_orchestrator_resolves_rule_renders_and_queues(
    session_factory,
) -> None:
    template_id = uuid4()
    async with session_factory() as session:
        session.add(
            NotificationTemplate(
                id=template_id,
                code="REPORT_READY",
                name="Report ready",
                event_type=NotificationEventType.REPORT_GENERATED,
                channel=NotificationChannel.EMAIL_GRAPH,
                subject_template="{{ report.name }} ready",
                body_template="<p>{{ report.owner }}</p>",
                content_type=NotificationContentType.HTML,
                language_code="en",
                version=1,
                is_default=True,
                is_active=True,
            )
        )
        session.add(
            NotificationRule(
                name="Report recipients",
                event_type=NotificationEventType.REPORT_GENERATED,
                channel=NotificationChannel.EMAIL_GRAPH,
                scope_type=NotificationScopeType.GLOBAL,
                severity_filter_json=[],
                recipient_type=NotificationRecipientType.SPECIFIC_EMAILS,
                recipient_value_json={"emails": ["recipient@example.com"]},
                template_id=template_id,
                send_immediately=True,
                digest_enabled=False,
                is_active=True,
            )
        )
        await session.commit()

    publisher = FakeNotificationPublisher()
    async with session_factory() as session:
        result = await NotificationOrchestrationService(
            session,
            publisher=publisher,
        ).emit(
            NotificationEvent(
                event_type=NotificationEventType.REPORT_GENERATED,
                variables={
                    "report": {
                        "name": "Monthly",
                        "owner": "<script>unsafe</script>",
                    }
                },
                action_url="/reports/monthly",
            )
        )
    assert result.matched_rule_count == 1
    assert result.queued_delivery_count == 1
    assert result.failed_publish_count == 0
    payload, digest = publisher.items[0]
    assert payload["subject"] == "Monthly ready"
    assert "&lt;script&gt;" in payload["body"]
    assert payload["actionUrl"] == "/reports/monthly"
    assert digest is False
