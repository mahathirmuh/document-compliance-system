"""Minimal, deduplicated Graph webhook event journal."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.sharepoint_enums import (
    GraphWebhookProcessingStatus,
    enum_values,
)


class GraphWebhookEvent(Base):
    __tablename__ = "graph_webhook_events"
    __table_args__ = (
        UniqueConstraint(
            "subscription_id",
            "payload_hash",
            name="uq_graph_webhook_event_payload",
        ),
        Index("ix_graph_webhook_events_status", "processing_status"),
        Index("ix_graph_webhook_events_received", "received_at"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    subscription_id: Mapped[str] = mapped_column(
        String(1000), nullable=False
    )
    resource: Mapped[str] = mapped_column(String(2000), nullable=False)
    change_type: Mapped[str] = mapped_column(String(100), nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(255))
    client_state_valid: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processing_status: Mapped[GraphWebhookProcessingStatus] = mapped_column(
        Enum(
            GraphWebhookProcessingStatus,
            name="graph_webhook_processing_status",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=GraphWebhookProcessingStatus.RECEIVED,
        server_default=GraphWebhookProcessingStatus.RECEIVED.value,
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    sync_job_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sharepoint_sync_jobs.id", ondelete="SET NULL"),
    )
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
