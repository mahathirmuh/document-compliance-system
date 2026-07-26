"""Auditable system and manual compliance findings."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.compliance_enums import (
    FindingCode,
    FindingSeverity,
    FindingStatus,
    FindingType,
    enum_values,
)

if TYPE_CHECKING:
    from app.models.compliance_run import ComplianceRun
    from app.models.detected_section import DetectedSection
    from app.models.document import Document
    from app.models.document_file import DocumentFile
    from app.models.document_revision import DocumentRevision
    from app.models.extracted_block import ExtractedBlock
    from app.models.finding_occurrence import FindingOccurrence
    from app.models.ocr_block import OCRBlock
    from app.models.translation_group import TranslationGroup
    from app.models.user import User
    from app.models.validation_rule import ValidationRule


class ValidationFinding(Base):
    """One immutable detection record with mutable reviewed workflow state."""

    __tablename__ = "validation_findings"
    __table_args__ = (
        CheckConstraint(
            "page_number IS NULL OR page_number >= 1",
            name="validation_findings_page_positive",
        ),
        CheckConstraint(
            "NOT is_system_generated OR compliance_run_id IS NOT NULL "
            "OR similarity_run_id IS NOT NULL "
            "OR glossary_validation_run_id IS NOT NULL",
            name="validation_findings_system_run_required",
        ),
        Index("ix_validation_findings_compliance_run_id", "compliance_run_id"),
        Index("ix_validation_findings_similarity_run_id", "similarity_run_id"),
        Index(
            "ix_validation_findings_glossary_validation_run_id",
            "glossary_validation_run_id",
        ),
        Index("ix_validation_findings_document_id", "document_id"),
        Index(
            "ix_validation_findings_document_revision_id",
            "document_revision_id",
        ),
        Index("ix_validation_findings_document_file_id", "document_file_id"),
        Index(
            "ix_validation_findings_validation_rule_id",
            "validation_rule_id",
        ),
        Index("ix_validation_findings_finding_code", "finding_code"),
        Index("ix_validation_findings_finding_type", "finding_type"),
        Index("ix_validation_findings_severity", "severity"),
        Index("ix_validation_findings_status", "status"),
        Index("ix_validation_findings_detected_section_id", "detected_section_id"),
        Index(
            "ix_validation_findings_translation_group_id",
            "translation_group_id",
        ),
        Index("ix_validation_findings_assigned_to", "assigned_to"),
        Index("ix_validation_findings_language_code", "language_code"),
        Index("ix_validation_findings_is_system_generated", "is_system_generated"),
        Index("ix_validation_findings_is_repeat", "is_repeat"),
        Index("ix_validation_findings_previous_finding_id", "previous_finding_id"),
        Index("ix_validation_findings_created_at", "created_at"),
        Index(
            "ix_validation_findings_document_status",
            "document_id",
            "status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    compliance_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("compliance_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    similarity_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("similarity_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    glossary_validation_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("glossary_validation_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    document_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    document_revision_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_revisions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    document_file_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_files.id", ondelete="RESTRICT"),
        nullable=False,
    )
    validation_rule_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("validation_rules.id", ondelete="SET NULL"),
        nullable=True,
    )
    finding_code: Mapped[FindingCode] = mapped_column(
        Enum(
            FindingCode,
            name="finding_code",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    finding_type: Mapped[FindingType] = mapped_column(
        Enum(
            FindingType,
            name="finding_type",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    severity: Mapped[FindingSeverity] = mapped_column(
        Enum(
            FindingSeverity,
            name="finding_severity",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    status: Mapped[FindingStatus] = mapped_column(
        Enum(
            FindingStatus,
            name="finding_status",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=FindingStatus.OPEN,
        server_default=FindingStatus.OPEN.value,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    container_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extracted_containers.id", ondelete="SET NULL"),
        nullable=True,
    )
    detected_section_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("detected_sections.id", ondelete="SET NULL"),
        nullable=True,
    )
    translation_group_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("translation_groups.id", ondelete="SET NULL"),
        nullable=True,
    )
    extracted_block_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extracted_blocks.id", ondelete="SET NULL"),
        nullable=True,
    )
    ocr_block_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ocr_blocks.id", ondelete="SET NULL"),
        nullable=True,
    )
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    worksheet_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    cell_coordinate: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
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
    language_code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    expected_value_json: Mapped[dict[str, Any] | list[Any] | None] = (
        mapped_column(
            JSON().with_variant(JSONB, "postgresql"),
            nullable=True,
        )
    )
    actual_value_json: Mapped[dict[str, Any] | list[Any] | None] = (
        mapped_column(
            JSON().with_variant(JSONB, "postgresql"),
            nullable=True,
        )
    )
    metrics_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    is_system_generated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    is_repeat: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    previous_finding_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("validation_findings.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_to: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolution_comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    false_positive_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    false_positive_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    false_positive_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    accepted_risk_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    accepted_risk_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    accepted_risk_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    accepted_risk_expiry_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    reopened_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reopened_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    reopen_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    compliance_run: Mapped[ComplianceRun | None] = relationship(
        back_populates="findings",
        foreign_keys=[compliance_run_id],
    )
    document: Mapped[Document] = relationship(foreign_keys=[document_id])
    revision: Mapped[DocumentRevision] = relationship(
        foreign_keys=[document_revision_id]
    )
    document_file: Mapped[DocumentFile] = relationship(
        back_populates="validation_findings",
        foreign_keys=[document_file_id],
    )
    validation_rule: Mapped[ValidationRule | None] = relationship(
        foreign_keys=[validation_rule_id]
    )
    detected_section: Mapped[DetectedSection | None] = relationship(
        back_populates="findings",
        foreign_keys=[detected_section_id],
    )
    translation_group: Mapped[TranslationGroup | None] = relationship(
        back_populates="findings",
        foreign_keys=[translation_group_id],
    )
    extracted_block: Mapped[ExtractedBlock | None] = relationship(
        foreign_keys=[extracted_block_id]
    )
    ocr_block: Mapped[OCRBlock | None] = relationship(
        foreign_keys=[ocr_block_id]
    )
    previous_finding: Mapped[ValidationFinding | None] = relationship(
        remote_side=[id],
        foreign_keys=[previous_finding_id],
        back_populates="repeat_findings",
    )
    repeat_findings: Mapped[list[ValidationFinding]] = relationship(
        back_populates="previous_finding",
        foreign_keys=[previous_finding_id],
    )
    creator: Mapped[User | None] = relationship(foreign_keys=[created_by])
    assignee: Mapped[User | None] = relationship(foreign_keys=[assigned_to])
    reviewer: Mapped[User | None] = relationship(foreign_keys=[reviewed_by])
    resolver: Mapped[User | None] = relationship(foreign_keys=[resolved_by])
    false_positive_actor: Mapped[User | None] = relationship(
        foreign_keys=[false_positive_by]
    )
    accepted_risk_actor: Mapped[User | None] = relationship(
        foreign_keys=[accepted_risk_by]
    )
    reopener: Mapped[User | None] = relationship(foreign_keys=[reopened_by])
    occurrences: Mapped[list[FindingOccurrence]] = relationship(
        back_populates="finding",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="FindingOccurrence.detected_at",
    )
