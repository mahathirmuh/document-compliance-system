"""Retained aggregate results for Phase 9 similarity analysis."""

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
from app.models.similarity_enums import (
    SimilarityRunStatus,
    enum_values,
)

if TYPE_CHECKING:
    from app.models.compliance_run import ComplianceRun
    from app.models.document import Document
    from app.models.document_file import DocumentFile
    from app.models.document_revision import DocumentRevision
    from app.models.language_detection_run import LanguageDetectionRun
    from app.models.similarity_job import SimilarityJob
    from app.models.similarity_result import TranslationSimilarityResult
    from app.models.similarity_section_summary import (
        SectionSimilaritySummary,
    )
    from app.models.user import User


class SimilarityRun(Base):
    """Immutable document-level similarity result."""

    __tablename__ = "similarity_runs"
    __table_args__ = (
        UniqueConstraint(
            "similarity_job_id", name="uq_similarity_runs_job_id"
        ),
        CheckConstraint(
            "length(source_content_hash) = 64",
            name="similarity_runs_source_hash_length",
        ),
        CheckConstraint(
            "(average_similarity IS NULL OR "
            "(average_similarity >= 0 AND average_similarity <= 1)) AND "
            "(minimum_similarity IS NULL OR "
            "(minimum_similarity >= 0 AND minimum_similarity <= 1)) AND "
            "(maximum_similarity IS NULL OR "
            "(maximum_similarity >= 0 AND maximum_similarity <= 1))",
            name="similarity_runs_score_range",
        ),
        CheckConstraint(
            "translation_group_count >= 0 AND eligible_group_count >= 0 "
            "AND analysed_group_count >= 0 AND skipped_group_count >= 0 "
            "AND failed_group_count >= 0",
            name="similarity_runs_group_counts",
        ),
        Index("ix_similarity_runs_document_id", "document_id"),
        Index(
            "ix_similarity_runs_document_revision_id",
            "document_revision_id",
        ),
        Index("ix_similarity_runs_document_file_id", "document_file_id"),
        Index("ix_similarity_runs_compliance_run_id", "compliance_run_id"),
        Index(
            "ix_similarity_runs_language_detection_run_id",
            "language_detection_run_id",
        ),
        Index("ix_similarity_runs_status", "status"),
        Index("ix_similarity_runs_source_hash", "source_content_hash"),
        Index("ix_similarity_runs_created_at", "created_at"),
        Index(
            "ix_similarity_runs_file_created",
            "document_file_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    similarity_job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("similarity_jobs.id", ondelete="RESTRICT"),
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
    compliance_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("compliance_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    language_detection_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("language_detection_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(500), nullable=False)
    model_version: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    status: Mapped[SimilarityRunStatus] = mapped_column(
        Enum(
            SimilarityRunStatus,
            name="similarity_run_status",
            values_callable=enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    source_content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    translation_group_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    eligible_group_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    analysed_group_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    skipped_group_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    failed_group_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    average_similarity: Mapped[Decimal | None] = mapped_column(
        Numeric(7, 6), nullable=True
    )
    minimum_similarity: Mapped[Decimal | None] = mapped_column(
        Numeric(7, 6), nullable=True
    )
    maximum_similarity: Mapped[Decimal | None] = mapped_column(
        Numeric(7, 6), nullable=True
    )
    id_en_average_similarity: Mapped[Decimal | None] = mapped_column(
        Numeric(7, 6), nullable=True
    )
    id_zh_average_similarity: Mapped[Decimal | None] = mapped_column(
        Numeric(7, 6), nullable=True
    )
    en_zh_average_similarity: Mapped[Decimal | None] = mapped_column(
        Numeric(7, 6), nullable=True
    )
    high_similarity_groups: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    review_similarity_groups: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    low_similarity_groups: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    unavailable_similarity_groups: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    number_mismatch_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    date_mismatch_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    measurement_mismatch_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    reference_mismatch_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    negation_mismatch_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
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
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    requested_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    similarity_job: Mapped[SimilarityJob] = relationship(
        back_populates="similarity_run",
        foreign_keys=[similarity_job_id],
    )
    document: Mapped[Document] = relationship(foreign_keys=[document_id])
    revision: Mapped[DocumentRevision] = relationship(
        foreign_keys=[document_revision_id]
    )
    document_file: Mapped[DocumentFile] = relationship(
        foreign_keys=[document_file_id],
        overlaps="similarity_runs",
    )
    compliance_run: Mapped[ComplianceRun] = relationship(
        foreign_keys=[compliance_run_id]
    )
    language_detection_run: Mapped[LanguageDetectionRun] = relationship(
        foreign_keys=[language_detection_run_id]
    )
    requester: Mapped[User | None] = relationship(
        foreign_keys=[requested_by]
    )
    results: Mapped[list[TranslationSimilarityResult]] = relationship(
        back_populates="similarity_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TranslationSimilarityResult.created_at",
    )
    section_summaries: Mapped[list[SectionSimilaritySummary]] = relationship(
        back_populates="similarity_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SectionSimilaritySummary.canonical_section_code",
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
