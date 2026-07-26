"""Cached worker-presence state used by the system-health dashboard."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.notification_enums import enum_values


class WorkerHeartbeatState(StrEnum):
    ACTIVE = "ACTIVE"
    DRAINING = "DRAINING"
    STOPPED = "STOPPED"


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"
    __table_args__ = (
        UniqueConstraint(
            "worker_name",
            "worker_instance",
            name="uq_worker_heartbeats_name_instance",
        ),
        Index("ix_worker_heartbeats_worker_name", "worker_name"),
        Index("ix_worker_heartbeats_queue_name", "queue_name"),
        Index(
            "ix_worker_heartbeats_last_heartbeat_at",
            "last_heartbeat_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    worker_name: Mapped[str] = mapped_column(String(100), nullable=False)
    worker_instance: Mapped[str] = mapped_column(String(255), nullable=False)
    queue_name: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[WorkerHeartbeatState] = mapped_column(
        Enum(
            WorkerHeartbeatState,
            name="worker_heartbeat_state",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=WorkerHeartbeatState.ACTIVE,
        server_default=WorkerHeartbeatState.ACTIVE.value,
    )
    last_heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
