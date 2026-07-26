"""Microsoft Graph webhook subscriptions without plaintext client state."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.database.base import Base
from app.models.sharepoint_enums import (
    GraphSubscriptionStatus,
    enum_values,
)


class GraphSubscription(Base):
    __tablename__ = "graph_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "subscription_id",
            name="uq_graph_subscriptions_subscription_id",
        ),
        UniqueConstraint(
            "sharepoint_connection_id",
            "sync_profile_id",
            "resource",
            name="uq_graph_subscriptions_resource_scope",
        ),
        CheckConstraint(
            "length(client_state_hash) = 64",
            name="graph_subscriptions_client_state_hash_length",
        ),
        CheckConstraint(
            "renewal_attempts >= 0",
            name="graph_subscriptions_renewal_attempts_nonnegative",
        ),
        Index("ix_graph_subscriptions_status", "status"),
        Index("ix_graph_subscriptions_expiration", "expiration_datetime"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    sharepoint_connection_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sharepoint_connections.id", ondelete="CASCADE"),
        nullable=False,
    )
    sync_profile_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sharepoint_sync_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    subscription_id: Mapped[str] = mapped_column(
        String(1000), nullable=False
    )
    resource: Mapped[str] = mapped_column(String(2000), nullable=False)
    change_type: Mapped[str] = mapped_column(String(100), nullable=False)
    notification_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    lifecycle_notification_url: Mapped[str | None] = mapped_column(String(2000))
    client_state_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expiration_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[GraphSubscriptionStatus] = mapped_column(
        Enum(
            GraphSubscriptionStatus,
            name="graph_subscription_status",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=GraphSubscriptionStatus.ACTIVE,
        server_default=GraphSubscriptionStatus.ACTIVE.value,
    )
    last_renewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_notification_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    renewal_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    @validates("client_state_hash")
    def validate_client_state_hash(self, _: str, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef"
            for character in normalized
        ):
            raise ValueError("Webhook client state must be stored as SHA-256.")
        return normalized
