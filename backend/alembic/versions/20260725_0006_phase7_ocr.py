"""Create Phase 7 local OCR persistence.

Revision ID: 20260725_0006
Revises: 20260725_0005
Create Date: 2026-07-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260725_0006"
down_revision: str | Sequence[str] | None = "20260725_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OCR_AUDIT_ACTIONS = (
    "QUEUE_OCR",
    "START_OCR",
    "COMPLETE_OCR",
    "PARTIAL_OCR",
    "FAIL_OCR",
    "CANCEL_OCR",
    "REOCR_DOCUMENT",
    "EXPORT_OCR_RESULT",
)
OCR_JOB_TYPES = ("INITIAL_OCR", "RE_OCR", "MANUAL_PAGE_OCR")
OCR_JOB_STATUSES = (
    "QUEUED",
    "INSPECTING",
    "RENDERING",
    "PREPROCESSING",
    "RECOGNISING",
    "MERGING",
    "PERSISTING",
    "COMPLETED",
    "PARTIALLY_COMPLETED",
    "FAILED",
    "CANCEL_REQUESTED",
    "CANCELLED",
)
ACTIVE_OCR_JOB_STATUSES = (
    "QUEUED",
    "INSPECTING",
    "RENDERING",
    "PREPROCESSING",
    "RECOGNISING",
    "MERGING",
    "PERSISTING",
    "CANCEL_REQUESTED",
)
OCR_LANGUAGE_PROFILES = ("LATIN", "CHINESE_SIMPLIFIED", "AUTO_MULTILINGUAL")
OCR_PREPROCESSING_PROFILES = ("NONE", "STANDARD", "AGGRESSIVE")
OCR_RUN_STATUSES = (
    "COMPLETED",
    "PARTIALLY_COMPLETED",
    "FAILED",
    "CANCELLED",
)
OCR_PAGE_STATUSES = (
    "COMPLETED",
    "LOW_CONFIDENCE",
    "NO_TEXT_FOUND",
    "FAILED",
    "SKIPPED",
)


def _json_type() -> sa.JSON:
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    """Add retained OCR history without altering Phase 1-6 content."""
    for action in OCR_AUDIT_ACTIONS:
        op.execute(
            sa.text(f"ALTER TYPE audit_action ADD VALUE IF NOT EXISTS '{action}'")
        )

    ocr_job_type = sa.Enum(*OCR_JOB_TYPES, name="ocr_job_type")
    ocr_job_status = sa.Enum(*OCR_JOB_STATUSES, name="ocr_job_status")
    ocr_language_profile = sa.Enum(
        *OCR_LANGUAGE_PROFILES,
        name="ocr_language_profile",
    )
    ocr_preprocessing_profile = sa.Enum(
        *OCR_PREPROCESSING_PROFILES,
        name="ocr_preprocessing_profile",
    )
    ocr_run_status = sa.Enum(*OCR_RUN_STATUSES, name="ocr_run_status")
    ocr_page_status = sa.Enum(*OCR_PAGE_STATUSES, name="ocr_page_status")

    op.create_table(
        "ocr_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("document_revision_id", sa.Uuid(), nullable=False),
        sa.Column("document_file_id", sa.Uuid(), nullable=False),
        sa.Column("extraction_run_id", sa.Uuid(), nullable=False),
        sa.Column(
            "job_type",
            ocr_job_type,
            server_default="INITIAL_OCR",
            nullable=False,
        ),
        sa.Column(
            "status",
            ocr_job_status,
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
            "language_profile",
            ocr_language_profile,
            server_default="AUTO_MULTILINGUAL",
            nullable=False,
        ),
        sa.Column(
            "preprocessing_profile",
            ocr_preprocessing_profile,
            server_default="STANDARD",
            nullable=False,
        ),
        sa.Column(
            "requested_page_numbers_json",
            _json_type(),
            nullable=False,
        ),
        sa.Column(
            "processed_page_numbers_json",
            _json_type(),
            nullable=False,
        ),
        sa.Column(
            "failed_page_numbers_json",
            _json_type(),
            nullable=False,
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
            server_default="2",
            nullable=False,
        ),
        sa.Column(
            "provider",
            sa.String(length=100),
            server_default="paddleocr",
            nullable=False,
        ),
        sa.Column("provider_version", sa.String(length=100), nullable=True),
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
            name="ocr_job_progress_range",
        ),
        sa.CheckConstraint(
            "attempt_number >= 1 AND maximum_attempts >= 1 "
            "AND attempt_number <= maximum_attempts",
            name="ocr_job_attempt_range",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_ocr_jobs_document_id_documents",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_revision_id"],
            ["document_revisions.id"],
            name="fk_ocr_jobs_document_revision_id_document_revisions",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_file_id"],
            ["document_files.id"],
            name="fk_ocr_jobs_document_file_id_document_files",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["extraction_run_id"],
            ["extraction_runs.id"],
            name="fk_ocr_jobs_extraction_run_id_extraction_runs",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            name="fk_ocr_jobs_requested_by_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ocr_jobs"),
    )
    for index_name, columns in (
        ("ix_ocr_jobs_document_id", ["document_id"]),
        ("ix_ocr_jobs_document_revision_id", ["document_revision_id"]),
        ("ix_ocr_jobs_document_file_id", ["document_file_id"]),
        ("ix_ocr_jobs_extraction_run_id", ["extraction_run_id"]),
        ("ix_ocr_jobs_status", ["status"]),
        ("ix_ocr_jobs_requested_by", ["requested_by"]),
        ("ix_ocr_jobs_requested_at", ["requested_at"]),
        ("ix_ocr_jobs_created_at", ["created_at"]),
    ):
        op.create_index(index_name, "ocr_jobs", columns)
    active_statuses = ", ".join(f"'{status}'" for status in ACTIVE_OCR_JOB_STATUSES)
    op.create_index(
        "uq_ocr_jobs_one_active_per_file",
        "ocr_jobs",
        ["document_file_id"],
        unique=True,
        postgresql_where=sa.text(f"status IN ({active_statuses})"),
        sqlite_where=sa.text(f"status IN ({active_statuses})"),
    )

    op.create_table(
        "ocr_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ocr_job_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("document_revision_id", sa.Uuid(), nullable=False),
        sa.Column("document_file_id", sa.Uuid(), nullable=False),
        sa.Column("source_extraction_run_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("provider_version", sa.String(length=100), nullable=True),
        sa.Column(
            "language_profile",
            ocr_language_profile,
            nullable=False,
        ),
        sa.Column("status", ocr_run_status, nullable=False),
        sa.Column(
            "source_sha256_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "page_count_requested",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "page_count_processed",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "page_count_failed",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "total_blocks",
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
        sa.Column("average_confidence", sa.Float(), nullable=True),
        sa.Column("minimum_confidence", sa.Float(), nullable=True),
        sa.Column("maximum_confidence", sa.Float(), nullable=True),
        sa.Column(
            "render_dpi",
            sa.Integer(),
            server_default="300",
            nullable=False,
        ),
        sa.Column(
            "preprocessing_profile",
            ocr_preprocessing_profile,
            nullable=False,
        ),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("warnings_json", _json_type(), nullable=False),
        sa.Column("metadata_json", _json_type(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "page_count_requested >= 0 AND page_count_processed >= 0 "
            "AND page_count_failed >= 0 AND total_blocks >= 0 "
            "AND total_characters >= 0",
            name="ocr_run_counts_nonnegative",
        ),
        sa.CheckConstraint(
            "average_confidence IS NULL OR "
            "(average_confidence >= 0 AND average_confidence <= 1)",
            name="ocr_run_average_confidence_range",
        ),
        sa.CheckConstraint(
            "minimum_confidence IS NULL OR "
            "(minimum_confidence >= 0 AND minimum_confidence <= 1)",
            name="ocr_run_minimum_confidence_range",
        ),
        sa.CheckConstraint(
            "maximum_confidence IS NULL OR "
            "(maximum_confidence >= 0 AND maximum_confidence <= 1)",
            name="ocr_run_maximum_confidence_range",
        ),
        sa.CheckConstraint(
            "render_dpi >= 72",
            name="ocr_run_render_dpi_minimum",
        ),
        sa.CheckConstraint(
            "length(source_sha256_hash) = 64",
            name="ocr_run_source_sha256_length",
        ),
        sa.CheckConstraint(
            "content_hash IS NULL OR length(content_hash) = 64",
            name="ocr_run_content_hash_length",
        ),
        sa.ForeignKeyConstraint(
            ["ocr_job_id"],
            ["ocr_jobs.id"],
            name="fk_ocr_runs_ocr_job_id_ocr_jobs",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_ocr_runs_document_id_documents",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_revision_id"],
            ["document_revisions.id"],
            name="fk_ocr_runs_document_revision_id_document_revisions",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_file_id"],
            ["document_files.id"],
            name="fk_ocr_runs_document_file_id_document_files",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_extraction_run_id"],
            ["extraction_runs.id"],
            name="fk_ocr_runs_source_extraction_run_id_extraction_runs",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ocr_runs"),
        sa.UniqueConstraint("ocr_job_id", name="uq_ocr_runs_ocr_job_id"),
    )
    for index_name, columns in (
        ("ix_ocr_runs_document_id", ["document_id"]),
        ("ix_ocr_runs_document_revision_id", ["document_revision_id"]),
        ("ix_ocr_runs_document_file_id", ["document_file_id"]),
        (
            "ix_ocr_runs_source_extraction_run_id",
            ["source_extraction_run_id"],
        ),
        ("ix_ocr_runs_status", ["status"]),
        ("ix_ocr_runs_source_sha256_hash", ["source_sha256_hash"]),
        ("ix_ocr_runs_content_hash", ["content_hash"]),
        ("ix_ocr_runs_created_at", ["created_at"]),
    ):
        op.create_index(index_name, "ocr_runs", columns)

    op.add_column(
        "document_files",
        sa.Column("latest_ocr_run_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_document_files_latest_ocr_run_id_ocr_runs",
        "document_files",
        "ocr_runs",
        ["latest_ocr_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_document_files_latest_ocr_run_id",
        "document_files",
        ["latest_ocr_run_id"],
    )

    op.create_table(
        "ocr_page_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ocr_run_id", sa.Uuid(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("status", ocr_page_status, nullable=False),
        sa.Column(
            "language_profile",
            ocr_language_profile,
            nullable=False,
        ),
        sa.Column("render_width", sa.Integer(), nullable=False),
        sa.Column("render_height", sa.Integer(), nullable=False),
        sa.Column("render_dpi", sa.Integer(), nullable=False),
        sa.Column(
            "rotation_applied",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("deskew_angle", sa.Float(), nullable=True),
        sa.Column(
            "block_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "character_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("average_confidence", sa.Float(), nullable=True),
        sa.Column("minimum_confidence", sa.Float(), nullable=True),
        sa.Column("maximum_confidence", sa.Float(), nullable=True),
        sa.Column("raw_text", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "normalised_text",
            sa.Text(),
            server_default="",
            nullable=False,
        ),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("warning_codes_json", _json_type(), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", _json_type(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "page_number >= 1",
            name="ocr_page_result_page_positive",
        ),
        sa.CheckConstraint(
            "render_width >= 0 AND render_height >= 0 AND render_dpi >= 72",
            name="ocr_page_result_render_dimensions",
        ),
        sa.CheckConstraint(
            "block_count >= 0 AND character_count >= 0",
            name="ocr_page_result_counts_nonnegative",
        ),
        sa.CheckConstraint(
            "average_confidence IS NULL OR "
            "(average_confidence >= 0 AND average_confidence <= 1)",
            name="ocr_page_result_average_confidence_range",
        ),
        sa.CheckConstraint(
            "minimum_confidence IS NULL OR "
            "(minimum_confidence >= 0 AND minimum_confidence <= 1)",
            name="ocr_page_result_minimum_confidence_range",
        ),
        sa.CheckConstraint(
            "maximum_confidence IS NULL OR "
            "(maximum_confidence >= 0 AND maximum_confidence <= 1)",
            name="ocr_page_result_maximum_confidence_range",
        ),
        sa.CheckConstraint(
            "content_hash IS NULL OR length(content_hash) = 64",
            name="ocr_page_result_content_hash_length",
        ),
        sa.ForeignKeyConstraint(
            ["ocr_run_id"],
            ["ocr_runs.id"],
            name="fk_ocr_page_results_ocr_run_id_ocr_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ocr_page_results"),
        sa.UniqueConstraint(
            "ocr_run_id",
            "page_number",
            name="uq_ocr_page_results_run_page",
        ),
    )
    for index_name, columns in (
        ("ix_ocr_page_results_ocr_run_id", ["ocr_run_id"]),
        ("ix_ocr_page_results_page_number", ["page_number"]),
        ("ix_ocr_page_results_status", ["status"]),
        ("ix_ocr_page_results_created_at", ["created_at"]),
    ):
        op.create_index(index_name, "ocr_page_results", columns)

    op.create_table(
        "ocr_blocks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ocr_run_id", sa.Uuid(), nullable=False),
        sa.Column("ocr_page_result_id", sa.Uuid(), nullable=False),
        sa.Column("block_order", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("normalised_text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("polygon_json", _json_type(), nullable=False),
        sa.Column("bbox_json", _json_type(), nullable=False),
        sa.Column("provider_model", sa.String(length=255), nullable=False),
        sa.Column(
            "recognition_profile",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "orientation",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("metadata_json", _json_type(), nullable=True),
        sa.Column(
            "character_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "block_order >= 0 AND character_count >= 0",
            name="ocr_block_counts_nonnegative",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ocr_block_confidence_range",
        ),
        sa.CheckConstraint(
            "orientation IN (0, 90, 180, 270)",
            name="ocr_block_orientation_value",
        ),
        sa.ForeignKeyConstraint(
            ["ocr_run_id"],
            ["ocr_runs.id"],
            name="fk_ocr_blocks_ocr_run_id_ocr_runs",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ocr_page_result_id"],
            ["ocr_page_results.id"],
            name="fk_ocr_blocks_ocr_page_result_id_ocr_page_results",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ocr_blocks"),
    )
    for index_name, columns in (
        ("ix_ocr_blocks_ocr_run_id", ["ocr_run_id"]),
        ("ix_ocr_blocks_ocr_page_result_id", ["ocr_page_result_id"]),
        ("ix_ocr_blocks_confidence", ["confidence"]),
        ("ix_ocr_blocks_block_order", ["block_order"]),
        (
            "ix_ocr_blocks_page_order",
            ["ocr_page_result_id", "block_order"],
        ),
    ):
        op.create_index(index_name, "ocr_blocks", columns)


def downgrade() -> None:
    """Remove Phase 7 OCR persistence while retaining Phase 1-6 data."""
    op.drop_index(
        "ix_document_files_latest_ocr_run_id",
        table_name="document_files",
    )
    op.drop_constraint(
        "fk_document_files_latest_ocr_run_id_ocr_runs",
        "document_files",
        type_="foreignkey",
    )
    op.drop_column("document_files", "latest_ocr_run_id")

    for index_name in (
        "ix_ocr_blocks_page_order",
        "ix_ocr_blocks_block_order",
        "ix_ocr_blocks_confidence",
        "ix_ocr_blocks_ocr_page_result_id",
        "ix_ocr_blocks_ocr_run_id",
    ):
        op.drop_index(index_name, table_name="ocr_blocks")
    op.drop_table("ocr_blocks")

    for index_name in (
        "ix_ocr_page_results_created_at",
        "ix_ocr_page_results_status",
        "ix_ocr_page_results_page_number",
        "ix_ocr_page_results_ocr_run_id",
    ):
        op.drop_index(index_name, table_name="ocr_page_results")
    op.drop_table("ocr_page_results")

    for index_name in (
        "ix_ocr_runs_created_at",
        "ix_ocr_runs_content_hash",
        "ix_ocr_runs_source_sha256_hash",
        "ix_ocr_runs_status",
        "ix_ocr_runs_source_extraction_run_id",
        "ix_ocr_runs_document_file_id",
        "ix_ocr_runs_document_revision_id",
        "ix_ocr_runs_document_id",
    ):
        op.drop_index(index_name, table_name="ocr_runs")
    op.drop_table("ocr_runs")

    op.drop_index(
        "uq_ocr_jobs_one_active_per_file",
        table_name="ocr_jobs",
    )
    for index_name in (
        "ix_ocr_jobs_created_at",
        "ix_ocr_jobs_requested_at",
        "ix_ocr_jobs_requested_by",
        "ix_ocr_jobs_status",
        "ix_ocr_jobs_extraction_run_id",
        "ix_ocr_jobs_document_file_id",
        "ix_ocr_jobs_document_revision_id",
        "ix_ocr_jobs_document_id",
    ):
        op.drop_index(index_name, table_name="ocr_jobs")
    op.drop_table("ocr_jobs")

    bind = op.get_bind()
    for name, values in (
        ("ocr_page_status", OCR_PAGE_STATUSES),
        ("ocr_run_status", OCR_RUN_STATUSES),
        ("ocr_preprocessing_profile", OCR_PREPROCESSING_PROFILES),
        ("ocr_language_profile", OCR_LANGUAGE_PROFILES),
        ("ocr_job_status", OCR_JOB_STATUSES),
        ("ocr_job_type", OCR_JOB_TYPES),
    ):
        sa.Enum(*values, name=name).drop(bind, checkfirst=True)

    # PostgreSQL audit enum labels intentionally remain append-only.
