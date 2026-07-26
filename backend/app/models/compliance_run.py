"""Immutable Phase 8 compliance-validation results."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database.base import Base
from app.models.compliance_enums import (
    ComplianceRunStatus,
    ComplianceStatus,
    enum_values,
)

if TYPE_CHECKING:
    from app.models.compliance_job import ComplianceJob
    from app.models.detected_section import DetectedSection
    from app.models.document import Document
    from app.models.document_file import DocumentFile
    from app.models.document_revision import DocumentRevision
    from app.models.extraction_run import ExtractionRun
    from app.models.finding_occurrence import FindingOccurrence
    from app.models.language_detection_run import LanguageDetectionRun
    from app.models.ocr_run import OCRRun
    from app.models.translation_group import TranslationGroup
    from app.models.user import User
    from app.models.validation_finding import ValidationFinding
    from app.models.validation_rule import ValidationRule


class ComplianceRun(Base):
    """One retained result with an immutable validation-rule snapshot."""

    __tablename__ = "compliance_runs"
    __table_args__ = (
        UniqueConstraint(
            "compliance_job_id",
            name="uq_compliance_runs_compliance_job_id",
        ),
        CheckConstraint(
            "length(source_content_hash) = 64",
            name="compliance_runs_source_hash_length",
        ),
        CheckConstraint(
            "compliance_score >= 0 AND compliance_score <= 100 "
            "AND maximum_score >= 0 AND maximum_score <= 100",
            name="compliance_runs_score_range",
        ),
        CheckConstraint(
            "document_code_score >= 0 "
            "AND language_presence_score >= 0 "
            "AND language_coverage_score >= 0 "
            "AND section_completeness_score >= 0 "
            "AND language_order_score >= 0 "
            "AND translation_group_score >= 0 "
            "AND table_completeness_score >= 0",
            name="compliance_runs_component_scores_nonnegative",
        ),
        CheckConstraint(
            "total_findings >= 0 AND critical_findings >= 0 "
            "AND major_findings >= 0 AND minor_findings >= 0 "
            "AND information_findings >= 0 AND open_findings >= 0 "
            "AND open_findings <= total_findings",
            name="compliance_runs_finding_counts",
        ),
        Index("ix_compliance_runs_document_id", "document_id"),
        Index(
            "ix_compliance_runs_document_revision_id",
            "document_revision_id",
        ),
        Index("ix_compliance_runs_document_file_id", "document_file_id"),
        Index("ix_compliance_runs_extraction_run_id", "extraction_run_id"),
        Index("ix_compliance_runs_ocr_run_id", "ocr_run_id"),
        Index(
            "ix_compliance_runs_language_detection_run_id",
            "language_detection_run_id",
        ),
        Index("ix_compliance_runs_validation_rule_id", "validation_rule_id"),
        Index("ix_compliance_runs_status", "status"),
        Index("ix_compliance_runs_compliance_status", "compliance_status"),
        Index("ix_compliance_runs_compliance_score", "compliance_score"),
        Index("ix_compliance_runs_source_content_hash", "source_content_hash"),
        Index("ix_compliance_runs_created_at", "created_at"),
        Index(
            "ix_compliance_runs_file_created",
            "document_file_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    compliance_job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("compliance_jobs.id", ondelete="RESTRICT"),
        nullable=False,
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
    extraction_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("extraction_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    ocr_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ocr_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    language_detection_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("language_detection_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    validation_rule_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("validation_rules.id", ondelete="RESTRICT"),
        nullable=False,
    )
    rule_snapshot_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
    )
    source_content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    status: Mapped[ComplianceRunStatus] = mapped_column(
        Enum(
            ComplianceRunStatus,
            name="compliance_run_status",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    compliance_status: Mapped[ComplianceStatus] = mapped_column(
        Enum(
            ComplianceStatus,
            name="compliance_status",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=ComplianceStatus.NOT_EVALUATED,
        server_default=ComplianceStatus.NOT_EVALUATED.value,
    )
    compliance_score: Mapped[Decimal] = mapped_column(
        Numeric(7, 2),
        nullable=False,
        default=0,
        server_default="0",
    )
    maximum_score: Mapped[Decimal] = mapped_column(
        Numeric(7, 2),
        nullable=False,
        default=100,
        server_default="100",
    )
    document_code_score: Mapped[Decimal] = mapped_column(
        Numeric(7, 2), nullable=False, default=0, server_default="0"
    )
    language_presence_score: Mapped[Decimal] = mapped_column(
        Numeric(7, 2), nullable=False, default=0, server_default="0"
    )
    language_coverage_score: Mapped[Decimal] = mapped_column(
        Numeric(7, 2), nullable=False, default=0, server_default="0"
    )
    section_completeness_score: Mapped[Decimal] = mapped_column(
        Numeric(7, 2), nullable=False, default=0, server_default="0"
    )
    language_order_score: Mapped[Decimal] = mapped_column(
        Numeric(7, 2), nullable=False, default=0, server_default="0"
    )
    translation_group_score: Mapped[Decimal] = mapped_column(
        Numeric(7, 2), nullable=False, default=0, server_default="0"
    )
    table_completeness_score: Mapped[Decimal] = mapped_column(
        Numeric(7, 2), nullable=False, default=0, server_default="0"
    )
    total_findings: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    critical_findings: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    major_findings: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    minor_findings: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    information_findings: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    open_findings: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    required_languages_json: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    detected_languages_json: Mapped[list[str] | dict[str, Any]] = (
        mapped_column(
            JSON().with_variant(JSONB, "postgresql"),
            nullable=False,
            default=list,
        )
    )
    missing_languages_json: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    required_sections_json: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    detected_sections_json: Mapped[list[str] | dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    missing_sections_json: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    warnings_json: Mapped[list[str] | list[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    metrics_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    requested_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    compliance_job: Mapped[ComplianceJob] = relationship(
        back_populates="compliance_run",
        foreign_keys=[compliance_job_id],
    )
    document: Mapped[Document] = relationship(foreign_keys=[document_id])
    revision: Mapped[DocumentRevision] = relationship(
        foreign_keys=[document_revision_id]
    )
    document_file: Mapped[DocumentFile] = relationship(
        back_populates="compliance_runs",
        foreign_keys=[document_file_id],
    )
    extraction_run: Mapped[ExtractionRun] = relationship(
        foreign_keys=[extraction_run_id]
    )
    ocr_run: Mapped[OCRRun | None] = relationship(foreign_keys=[ocr_run_id])
    language_detection_run: Mapped[LanguageDetectionRun] = relationship(
        foreign_keys=[language_detection_run_id]
    )
    validation_rule: Mapped[ValidationRule] = relationship(
        foreign_keys=[validation_rule_id]
    )
    requester: Mapped[User | None] = relationship(
        foreign_keys=[requested_by]
    )
    detected_sections: Mapped[list[DetectedSection]] = relationship(
        back_populates="compliance_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DetectedSection.section_order",
    )
    translation_groups: Mapped[list[TranslationGroup]] = relationship(
        back_populates="compliance_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TranslationGroup.group_index",
    )
    findings: Mapped[list[ValidationFinding]] = relationship(
        back_populates="compliance_run",
        passive_deletes=True,
    )
    finding_occurrences: Mapped[list[FindingOccurrence]] = relationship(
        back_populates="compliance_run",
        passive_deletes=True,
    )

    @validates("source_content_hash")
    def normalize_source_hash(self, _: str, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef"
            for character in normalized
        ):
            raise ValueError(
                "source_content_hash must be 64 lowercase hex digits."
            )
        return normalized
