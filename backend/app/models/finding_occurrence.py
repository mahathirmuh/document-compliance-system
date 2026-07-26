"""Occurrences linking a logical finding to retained compliance runs."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.compliance_run import ComplianceRun
    from app.models.validation_finding import ValidationFinding


class FindingOccurrence(Base):
    """One observation of a logical finding during a compliance run."""

    __tablename__ = "finding_occurrences"
    __table_args__ = (
        UniqueConstraint(
            "finding_id",
            "compliance_run_id",
            "source_reference",
            name="uq_finding_occurrences_finding_run_source",
        ),
        Index("ix_finding_occurrences_finding_id", "finding_id"),
        Index(
            "ix_finding_occurrences_compliance_run_id",
            "compliance_run_id",
        ),
        Index("ix_finding_occurrences_detected_at", "detected_at"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    finding_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("validation_findings.id", ondelete="CASCADE"),
        nullable=False,
    )
    compliance_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("compliance_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    source_reference: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )
    location_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    metrics_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    finding: Mapped[ValidationFinding] = relationship(
        back_populates="occurrences",
        foreign_keys=[finding_id],
    )
    compliance_run: Mapped[ComplianceRun] = relationship(
        back_populates="finding_occurrences",
        foreign_keys=[compliance_run_id],
    )
