"""Create Phase 7 local language-detection persistence.

Revision ID: 20260725_0007
Revises: 20260725_0006
Create Date: 2026-07-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260725_0007"
down_revision: str | Sequence[str] | None = "20260725_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LANGUAGE_AUDIT_ACTIONS = (
    "QUEUE_LANGUAGE_DETECTION",
    "START_LANGUAGE_DETECTION",
    "COMPLETE_LANGUAGE_DETECTION",
    "FAIL_LANGUAGE_DETECTION",
    "CANCEL_LANGUAGE_DETECTION",
    "REDETECT_LANGUAGE",
    "EXPORT_LANGUAGE_RESULT",
    "REVIEW_LANGUAGE_RESULT",
)
LANGUAGE_DETECTION_JOB_TYPES = (
    "INITIAL_DETECTION",
    "RE_DETECTION",
)
LANGUAGE_DETECTION_JOB_STATUSES = (
    "QUEUED",
    "LOADING_CONTENT",
    "DETECTING",
    "AGGREGATING",
    "PERSISTING",
    "COMPLETED",
    "PARTIALLY_COMPLETED",
    "FAILED",
    "CANCEL_REQUESTED",
    "CANCELLED",
)
ACTIVE_LANGUAGE_DETECTION_JOB_STATUSES = (
    "QUEUED",
    "LOADING_CONTENT",
    "DETECTING",
    "AGGREGATING",
    "PERSISTING",
    "CANCEL_REQUESTED",
)
LANGUAGE_DETECTION_RUN_STATUSES = (
    "COMPLETED",
    "PARTIALLY_COMPLETED",
    "FAILED",
)
LANGUAGE_SOURCE_TYPES = ("NATIVE_EXTRACTION", "OCR")
LANGUAGE_CODES = ("id", "en", "zh", "mixed", "unknown", "other")
LANGUAGE_ELIGIBILITY_STATUSES = ("ELIGIBLE", "INELIGIBLE")
LANGUAGE_ELIGIBILITY_REASONS = (
    "EMPTY",
    "TOO_SHORT",
    "NO_LETTERS",
    "CODE_LIKE_TEXT",
    "URL_ONLY",
    "EMAIL_ONLY",
)


def _json_type() -> sa.JSON:
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _create_indexes(
    table_name: str,
    definitions: tuple[tuple[str, list[str]], ...],
) -> None:
    for index_name, columns in definitions:
        op.create_index(index_name, table_name, columns)


def _drop_indexes(table_name: str, index_names: tuple[str, ...]) -> None:
    for index_name in index_names:
        op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    """Add retained language results without changing Phase 1-6 records."""
    for action in LANGUAGE_AUDIT_ACTIONS:
        op.execute(
            sa.text(f"ALTER TYPE audit_action ADD VALUE IF NOT EXISTS '{action}'")
        )

    job_type = sa.Enum(
        *LANGUAGE_DETECTION_JOB_TYPES,
        name="language_detection_job_type",
    )
    job_status = sa.Enum(
        *LANGUAGE_DETECTION_JOB_STATUSES,
        name="language_detection_job_status",
    )
    run_status = sa.Enum(
        *LANGUAGE_DETECTION_RUN_STATUSES,
        name="language_detection_run_status",
    )
    source_type = sa.Enum(
        *LANGUAGE_SOURCE_TYPES,
        name="language_source_type",
    )
    language_code = sa.Enum(*LANGUAGE_CODES, name="language_code")
    primary_language_code = sa.Enum(
        *LANGUAGE_CODES,
        name="language_primary_code",
    )
    eligibility_status = sa.Enum(
        *LANGUAGE_ELIGIBILITY_STATUSES,
        name="language_eligibility_status",
    )
    eligibility_reason = sa.Enum(
        *LANGUAGE_ELIGIBILITY_REASONS,
        name="language_eligibility_reason",
    )

    op.create_table(
        "language_detection_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("document_revision_id", sa.Uuid(), nullable=False),
        sa.Column("document_file_id", sa.Uuid(), nullable=False),
        sa.Column("extraction_run_id", sa.Uuid(), nullable=False),
        sa.Column("ocr_run_id", sa.Uuid(), nullable=True),
        sa.Column(
            "job_type",
            job_type,
            server_default="INITIAL_DETECTION",
            nullable=False,
        ),
        sa.Column(
            "status",
            job_status,
            server_default="QUEUED",
            nullable=False,
        ),
        sa.Column(
            "progress",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("current_stage", sa.String(length=500), nullable=True),
        sa.Column(
            "force",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "source_content_hash",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "attempt_number",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
        sa.Column(
            "maximum_attempts",
            sa.Integer(),
            server_default="3",
            nullable=False,
        ),
        sa.Column("worker_reference", sa.String(length=255), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_details_json", _json_type(), nullable=True),
        sa.Column("result_summary_json", _json_type(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="progress_range",
        ),
        sa.CheckConstraint(
            "attempt_number >= 1",
            name="attempt_number_positive",
        ),
        sa.CheckConstraint(
            "maximum_attempts >= 1",
            name="maximum_attempts_positive",
        ),
        sa.CheckConstraint(
            "attempt_number <= maximum_attempts",
            name="attempt_within_maximum",
        ),
        sa.CheckConstraint(
            "source_content_hash IS NULL OR length(source_content_hash) = 64",
            name="source_content_hash_length",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_language_detection_jobs_document_id_documents",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_revision_id"],
            ["document_revisions.id"],
            name=op.f(
                "fk_language_detection_jobs_document_revision_id_document_revisions"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_file_id"],
            ["document_files.id"],
            name=("fk_language_detection_jobs_document_file_id_document_files"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["extraction_run_id"],
            ["extraction_runs.id"],
            name=("fk_language_detection_jobs_extraction_run_id_extraction_runs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ocr_run_id"],
            ["ocr_runs.id"],
            name="fk_language_detection_jobs_ocr_run_id_ocr_runs",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            name="fk_language_detection_jobs_requested_by_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_language_detection_jobs"),
    )
    _create_indexes(
        "language_detection_jobs",
        (
            ("ix_language_detection_jobs_document_id", ["document_id"]),
            (
                "ix_language_detection_jobs_document_revision_id",
                ["document_revision_id"],
            ),
            (
                "ix_language_detection_jobs_document_file_id",
                ["document_file_id"],
            ),
            (
                "ix_language_detection_jobs_extraction_run_id",
                ["extraction_run_id"],
            ),
            ("ix_language_detection_jobs_ocr_run_id", ["ocr_run_id"]),
            ("ix_language_detection_jobs_status", ["status"]),
            (
                "ix_language_detection_jobs_requested_by",
                ["requested_by"],
            ),
            (
                "ix_language_detection_jobs_requested_at",
                ["requested_at"],
            ),
            (
                "ix_language_detection_jobs_source_content_hash",
                ["source_content_hash"],
            ),
        ),
    )
    active_statuses = ", ".join(
        f"'{status}'" for status in ACTIVE_LANGUAGE_DETECTION_JOB_STATUSES
    )
    op.create_index(
        "uq_language_detection_jobs_one_active_per_file",
        "language_detection_jobs",
        ["document_file_id"],
        unique=True,
        postgresql_where=sa.text(f"status IN ({active_statuses})"),
        sqlite_where=sa.text(f"status IN ({active_statuses})"),
    )

    op.create_table(
        "language_detection_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("document_revision_id", sa.Uuid(), nullable=False),
        sa.Column("document_file_id", sa.Uuid(), nullable=False),
        sa.Column("extraction_run_id", sa.Uuid(), nullable=False),
        sa.Column("ocr_run_id", sa.Uuid(), nullable=True),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("detector_name", sa.String(length=100), nullable=False),
        sa.Column("detector_version", sa.String(length=100), nullable=False),
        sa.Column("status", run_status, nullable=False),
        sa.Column(
            "source_content_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "total_blocks",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "eligible_blocks",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "detected_blocks",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "unknown_blocks",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "mixed_blocks",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "indonesian_blocks",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "english_blocks",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "chinese_blocks",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "other_blocks",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "total_characters",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "indonesian_characters",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "english_characters",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "chinese_characters",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "mixed_characters",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "unknown_characters",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("average_confidence", sa.Numeric(6, 5), nullable=True),
        sa.Column("warnings_json", _json_type(), nullable=False),
        sa.Column("metadata_json", _json_type(), nullable=True),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(source_content_hash) = 64",
            name="source_content_hash_length",
        ),
        sa.CheckConstraint(
            "total_blocks >= 0 AND eligible_blocks >= 0 "
            "AND detected_blocks >= 0 AND unknown_blocks >= 0 "
            "AND mixed_blocks >= 0 AND indonesian_blocks >= 0 "
            "AND english_blocks >= 0 AND chinese_blocks >= 0 "
            "AND other_blocks >= 0",
            name="block_counts_nonnegative",
        ),
        sa.CheckConstraint(
            "eligible_blocks <= total_blocks AND detected_blocks <= eligible_blocks",
            name="block_count_bounds",
        ),
        sa.CheckConstraint(
            "total_characters >= 0 AND indonesian_characters >= 0 "
            "AND english_characters >= 0 AND chinese_characters >= 0 "
            "AND mixed_characters >= 0 AND unknown_characters >= 0",
            name="character_counts_nonnegative",
        ),
        sa.CheckConstraint(
            "average_confidence IS NULL OR "
            "(average_confidence >= 0 AND average_confidence <= 1)",
            name="average_confidence_range",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_language_detection_runs_document_id_documents",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_revision_id"],
            ["document_revisions.id"],
            name=op.f(
                "fk_language_detection_runs_document_revision_id_document_revisions"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_file_id"],
            ["document_files.id"],
            name=("fk_language_detection_runs_document_file_id_document_files"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["extraction_run_id"],
            ["extraction_runs.id"],
            name=("fk_language_detection_runs_extraction_run_id_extraction_runs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ocr_run_id"],
            ["ocr_runs.id"],
            name="fk_language_detection_runs_ocr_run_id_ocr_runs",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["language_detection_jobs.id"],
            name=("fk_language_detection_runs_job_id_language_detection_jobs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            name="fk_language_detection_runs_requested_by_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_language_detection_runs"),
        sa.UniqueConstraint(
            "job_id",
            name="uq_language_detection_runs_job_id",
        ),
    )
    _create_indexes(
        "language_detection_runs",
        (
            ("ix_language_detection_runs_document_id", ["document_id"]),
            (
                "ix_language_detection_runs_document_revision_id",
                ["document_revision_id"],
            ),
            (
                "ix_language_detection_runs_document_file_id",
                ["document_file_id"],
            ),
            (
                "ix_language_detection_runs_extraction_run_id",
                ["extraction_run_id"],
            ),
            ("ix_language_detection_runs_ocr_run_id", ["ocr_run_id"]),
            ("ix_language_detection_runs_status", ["status"]),
            (
                "ix_language_detection_runs_source_content_hash",
                ["source_content_hash"],
            ),
            ("ix_language_detection_runs_created_at", ["created_at"]),
        ),
    )

    op.add_column(
        "document_files",
        sa.Column(
            "latest_language_detection_run_id",
            sa.Uuid(),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        op.f(
            "fk_document_files_latest_language_detection_run_id_language_detection_runs"
        ),
        "document_files",
        "language_detection_runs",
        ["latest_language_detection_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_document_files_latest_language_detection_run_id",
        "document_files",
        ["latest_language_detection_run_id"],
    )

    op.create_table(
        "language_block_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "language_detection_run_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column("extracted_block_id", sa.Uuid(), nullable=True),
        sa.Column("ocr_block_id", sa.Uuid(), nullable=True),
        sa.Column("container_id", sa.Uuid(), nullable=True),
        sa.Column("source_type", source_type, nullable=False),
        sa.Column(
            "source_reference",
            sa.String(length=1000),
            nullable=False,
        ),
        sa.Column("language_code", language_code, nullable=False),
        sa.Column(
            "primary_language_code",
            primary_language_code,
            nullable=False,
        ),
        sa.Column(
            "confidence",
            sa.Numeric(6, 5),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "is_mixed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "detected_languages_json",
            _json_type(),
            nullable=False,
        ),
        sa.Column(
            "script_statistics_json",
            _json_type(),
            nullable=False,
        ),
        sa.Column(
            "eligibility_status",
            eligibility_status,
            nullable=False,
        ),
        sa.Column(
            "eligibility_reason",
            eligibility_reason,
            nullable=True,
        ),
        sa.Column(
            "character_count",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "latin_character_count",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "han_character_count",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "word_count",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("metadata_json", _json_type(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(extracted_block_id IS NOT NULL AND ocr_block_id IS NULL) "
            "OR (extracted_block_id IS NULL AND ocr_block_id IS NOT NULL)",
            name="exactly_one_source_block",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="confidence_range",
        ),
        sa.CheckConstraint(
            "character_count >= 0 AND latin_character_count >= 0 "
            "AND han_character_count >= 0 AND word_count >= 0",
            name="counts_nonnegative",
        ),
        sa.CheckConstraint(
            "(eligibility_status = 'ELIGIBLE' "
            "AND eligibility_reason IS NULL) "
            "OR (eligibility_status = 'INELIGIBLE' "
            "AND eligibility_reason IS NOT NULL)",
            name="eligibility_reason_consistent",
        ),
        sa.ForeignKeyConstraint(
            ["language_detection_run_id"],
            ["language_detection_runs.id"],
            name=op.f(
                "fk_language_block_results_language_detection_run_id_"
                "language_detection_runs"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["extracted_block_id"],
            ["extracted_blocks.id"],
            name=("fk_language_block_results_extracted_block_id_extracted_blocks"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ocr_block_id"],
            ["ocr_blocks.id"],
            name="fk_language_block_results_ocr_block_id_ocr_blocks",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["container_id"],
            ["extracted_containers.id"],
            name=("fk_language_block_results_container_id_extracted_containers"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_language_block_results"),
    )
    _create_indexes(
        "language_block_results",
        (
            (
                "ix_language_block_results_run_id",
                ["language_detection_run_id"],
            ),
            (
                "ix_language_block_results_extracted_block_id",
                ["extracted_block_id"],
            ),
            (
                "ix_language_block_results_ocr_block_id",
                ["ocr_block_id"],
            ),
            (
                "ix_language_block_results_container_id",
                ["container_id"],
            ),
            (
                "ix_language_block_results_source_type",
                ["source_type"],
            ),
            (
                "ix_language_block_results_language_code",
                ["language_code"],
            ),
            ("ix_language_block_results_confidence", ["confidence"]),
            ("ix_language_block_results_is_mixed", ["is_mixed"]),
            (
                "ix_language_block_results_eligibility_status",
                ["eligibility_status"],
            ),
            (
                "ix_language_block_results_run_language",
                ["language_detection_run_id", "language_code"],
            ),
            (
                "ix_language_block_results_run_container",
                ["language_detection_run_id", "container_id"],
            ),
        ),
    )

    op.create_table(
        "language_container_summaries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "language_detection_run_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column("container_id", sa.Uuid(), nullable=True),
        sa.Column(
            "container_type",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "container_name",
            sa.String(length=500),
            nullable=True,
        ),
        sa.Column("container_index", sa.Integer(), nullable=False),
        sa.Column(
            "total_blocks",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "eligible_blocks",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "indonesian_blocks",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "english_blocks",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "chinese_blocks",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "mixed_blocks",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "unknown_blocks",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "other_blocks",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "indonesian_characters",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "english_characters",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "chinese_characters",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "mixed_characters",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "unknown_characters",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "dominant_language",
            sa.String(length=20),
            server_default="unknown",
            nullable=False,
        ),
        sa.Column(
            "language_presence_json",
            _json_type(),
            nullable=False,
        ),
        sa.Column("coverage_json", _json_type(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "container_index >= 0",
            name="container_index_nonnegative",
        ),
        sa.CheckConstraint(
            "total_blocks >= 0 AND eligible_blocks >= 0 "
            "AND indonesian_blocks >= 0 AND english_blocks >= 0 "
            "AND chinese_blocks >= 0 AND mixed_blocks >= 0 "
            "AND unknown_blocks >= 0 AND other_blocks >= 0",
            name="block_counts_nonnegative",
        ),
        sa.CheckConstraint(
            "eligible_blocks <= total_blocks",
            name="eligible_blocks_within_total",
        ),
        sa.CheckConstraint(
            "indonesian_characters >= 0 AND english_characters >= 0 "
            "AND chinese_characters >= 0 AND mixed_characters >= 0 "
            "AND unknown_characters >= 0",
            name="character_counts_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["language_detection_run_id"],
            ["language_detection_runs.id"],
            name=op.f(
                "fk_language_container_summaries_"
                "language_detection_run_id_language_detection_runs"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["container_id"],
            ["extracted_containers.id"],
            name=op.f(
                "fk_language_container_summaries_container_id_extracted_containers"
            ),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_language_container_summaries",
        ),
        sa.UniqueConstraint(
            "language_detection_run_id",
            "container_id",
            name="uq_language_container_summaries_run_container",
        ),
    )
    _create_indexes(
        "language_container_summaries",
        (
            (
                "ix_language_container_summaries_run_id",
                ["language_detection_run_id"],
            ),
            (
                "ix_language_container_summaries_container_id",
                ["container_id"],
            ),
            (
                "ix_language_container_summaries_container_type",
                ["container_type"],
            ),
            (
                "ix_language_container_summaries_container_index",
                ["container_index"],
            ),
            (
                "ix_language_container_summaries_dominant_language",
                ["dominant_language"],
            ),
        ),
    )


def downgrade() -> None:
    """Remove Phase 7 language persistence while retaining older data."""
    op.drop_index(
        "ix_document_files_latest_language_detection_run_id",
        table_name="document_files",
    )
    op.drop_constraint(
        op.f(
            "fk_document_files_latest_language_detection_run_id_language_detection_runs"
        ),
        "document_files",
        type_="foreignkey",
    )
    op.drop_column(
        "document_files",
        "latest_language_detection_run_id",
    )

    _drop_indexes(
        "language_container_summaries",
        (
            "ix_language_container_summaries_dominant_language",
            "ix_language_container_summaries_container_index",
            "ix_language_container_summaries_container_type",
            "ix_language_container_summaries_container_id",
            "ix_language_container_summaries_run_id",
        ),
    )
    op.drop_table("language_container_summaries")

    _drop_indexes(
        "language_block_results",
        (
            "ix_language_block_results_run_container",
            "ix_language_block_results_run_language",
            "ix_language_block_results_eligibility_status",
            "ix_language_block_results_is_mixed",
            "ix_language_block_results_confidence",
            "ix_language_block_results_language_code",
            "ix_language_block_results_source_type",
            "ix_language_block_results_container_id",
            "ix_language_block_results_ocr_block_id",
            "ix_language_block_results_extracted_block_id",
            "ix_language_block_results_run_id",
        ),
    )
    op.drop_table("language_block_results")

    _drop_indexes(
        "language_detection_runs",
        (
            "ix_language_detection_runs_created_at",
            "ix_language_detection_runs_source_content_hash",
            "ix_language_detection_runs_status",
            "ix_language_detection_runs_ocr_run_id",
            "ix_language_detection_runs_extraction_run_id",
            "ix_language_detection_runs_document_file_id",
            "ix_language_detection_runs_document_revision_id",
            "ix_language_detection_runs_document_id",
        ),
    )
    op.drop_table("language_detection_runs")

    op.drop_index(
        "uq_language_detection_jobs_one_active_per_file",
        table_name="language_detection_jobs",
    )
    _drop_indexes(
        "language_detection_jobs",
        (
            "ix_language_detection_jobs_source_content_hash",
            "ix_language_detection_jobs_requested_at",
            "ix_language_detection_jobs_requested_by",
            "ix_language_detection_jobs_status",
            "ix_language_detection_jobs_ocr_run_id",
            "ix_language_detection_jobs_extraction_run_id",
            "ix_language_detection_jobs_document_file_id",
            "ix_language_detection_jobs_document_revision_id",
            "ix_language_detection_jobs_document_id",
        ),
    )
    op.drop_table("language_detection_jobs")

    bind = op.get_bind()
    for name, values in (
        ("language_eligibility_reason", LANGUAGE_ELIGIBILITY_REASONS),
        ("language_eligibility_status", LANGUAGE_ELIGIBILITY_STATUSES),
        ("language_primary_code", LANGUAGE_CODES),
        ("language_code", LANGUAGE_CODES),
        ("language_source_type", LANGUAGE_SOURCE_TYPES),
        (
            "language_detection_run_status",
            LANGUAGE_DETECTION_RUN_STATUSES,
        ),
        (
            "language_detection_job_status",
            LANGUAGE_DETECTION_JOB_STATUSES,
        ),
        ("language_detection_job_type", LANGUAGE_DETECTION_JOB_TYPES),
    ):
        sa.Enum(*values, name=name).drop(bind, checkfirst=True)

    # PostgreSQL audit enum labels intentionally remain append-only.
