"""Create Phase 6 document-content extraction persistence.

Revision ID: 20260725_0005
Revises: 20260725_0004
Create Date: 2026-07-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260725_0005"
down_revision: str | Sequence[str] | None = "20260725_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PHASE6_AUDIT_ACTIONS = (
    "QUEUE_DOCUMENT_EXTRACTION",
    "START_DOCUMENT_EXTRACTION",
    "COMPLETE_DOCUMENT_EXTRACTION",
    "PARTIAL_DOCUMENT_EXTRACTION",
    "DOCUMENT_REQUIRES_OCR",
    "FAIL_DOCUMENT_EXTRACTION",
    "CANCEL_DOCUMENT_EXTRACTION",
    "REEXTRACT_DOCUMENT",
    "VIEW_EXTRACTED_CONTENT",
    "SEARCH_EXTRACTED_CONTENT",
    "EXPORT_EXTRACTED_CONTENT",
)

EXTRACTION_JOB_TYPES = (
    "INITIAL_EXTRACTION",
    "RE_EXTRACTION",
    "MANUAL_EXTRACTION",
)
EXTRACTION_JOB_STATUSES = (
    "QUEUED",
    "INSPECTING",
    "EXTRACTING",
    "NORMALISING",
    "PERSISTING",
    "COMPLETED",
    "PARTIALLY_COMPLETED",
    "OCR_REQUIRED",
    "FAILED",
    "CANCEL_REQUESTED",
    "CANCELLED",
)
ACTIVE_EXTRACTION_JOB_STATUSES = (
    "QUEUED",
    "INSPECTING",
    "EXTRACTING",
    "NORMALISING",
    "PERSISTING",
    "CANCEL_REQUESTED",
)
EXTRACTION_RUN_STATUSES = (
    "COMPLETED",
    "PARTIALLY_COMPLETED",
    "OCR_REQUIRED",
)
EXTRACTOR_TYPES = ("PDF", "DOCX", "XLSX")
EXTRACTED_CONTAINER_TYPES = (
    "PDF_PAGE",
    "DOCX_BODY",
    "DOCX_HEADER",
    "DOCX_FOOTER",
    "XLSX_WORKSHEET",
)
EXTRACTED_BLOCK_TYPES = (
    "TEXT",
    "PARAGRAPH",
    "HEADING",
    "TABLE",
    "TABLE_ROW",
    "TABLE_CELL",
    "HEADER",
    "FOOTER",
    "WORKSHEET_TITLE",
    "CELL",
    "MERGED_CELL",
    "FORMULA",
    "PAGE_NUMBER",
    "UNKNOWN",
)


def _json_type() -> sa.JSON:
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    """Add extraction history without mutating Phase 1-5 records."""
    for action in PHASE6_AUDIT_ACTIONS:
        op.execute(
            sa.text(
                f"ALTER TYPE audit_action ADD VALUE IF NOT EXISTS '{action}'"
            )
        )

    extraction_job_type = sa.Enum(
        *EXTRACTION_JOB_TYPES,
        name="extraction_job_type",
    )
    extraction_job_status = sa.Enum(
        *EXTRACTION_JOB_STATUSES,
        name="extraction_job_status",
    )
    extractor_type = sa.Enum(
        *EXTRACTOR_TYPES,
        name="extraction_extractor_type",
    )
    extraction_run_status = sa.Enum(
        *EXTRACTION_RUN_STATUSES,
        name="extraction_run_status",
    )
    extracted_container_type = sa.Enum(
        *EXTRACTED_CONTAINER_TYPES,
        name="extracted_container_type",
    )
    extracted_block_type = sa.Enum(
        *EXTRACTED_BLOCK_TYPES,
        name="extracted_block_type",
    )

    op.create_table(
        "extraction_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("document_revision_id", sa.Uuid(), nullable=False),
        sa.Column("document_file_id", sa.Uuid(), nullable=False),
        sa.Column(
            "job_type",
            extraction_job_type,
            server_default="INITIAL_EXTRACTION",
            nullable=False,
        ),
        sa.Column(
            "status",
            extraction_job_status,
            server_default="QUEUED",
            nullable=False,
        ),
        sa.Column(
            "progress",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "current_stage",
            sa.String(length=500),
            nullable=True,
        ),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "failed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "cancelled_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
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
        sa.Column(
            "error_code",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_details_json", _json_type(), nullable=True),
        sa.Column("result_summary_json", _json_type(), nullable=True),
        sa.Column(
            "worker_reference",
            sa.String(length=255),
            nullable=True,
        ),
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
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_extraction_jobs_document_id_documents",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_revision_id"],
            ["document_revisions.id"],
            name=(
                "fk_extraction_jobs_document_revision_id_"
                "document_revisions"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_file_id"],
            ["document_files.id"],
            name=(
                "fk_extraction_jobs_document_file_id_document_files"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            name="fk_extraction_jobs_requested_by_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_extraction_jobs"),
    )
    for index_name, columns in (
        ("ix_extraction_jobs_document_id", ["document_id"]),
        (
            "ix_extraction_jobs_document_revision_id",
            ["document_revision_id"],
        ),
        (
            "ix_extraction_jobs_document_file_id",
            ["document_file_id"],
        ),
        ("ix_extraction_jobs_status", ["status"]),
        ("ix_extraction_jobs_requested_by", ["requested_by"]),
        ("ix_extraction_jobs_requested_at", ["requested_at"]),
        ("ix_extraction_jobs_created_at", ["created_at"]),
    ):
        op.create_index(index_name, "extraction_jobs", columns)
    active_statuses = ", ".join(
        f"'{status}'" for status in ACTIVE_EXTRACTION_JOB_STATUSES
    )
    op.create_index(
        "uq_extraction_jobs_one_active_per_file",
        "extraction_jobs",
        ["document_file_id"],
        unique=True,
        postgresql_where=sa.text(f"status IN ({active_statuses})"),
        sqlite_where=sa.text(f"status IN ({active_statuses})"),
    )

    op.create_table(
        "extraction_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("extraction_job_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("document_revision_id", sa.Uuid(), nullable=False),
        sa.Column("document_file_id", sa.Uuid(), nullable=False),
        sa.Column("extractor_type", extractor_type, nullable=False),
        sa.Column(
            "extractor_version",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column("status", extraction_run_status, nullable=False),
        sa.Column(
            "source_sha256_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("source_file_size", sa.BigInteger(), nullable=False),
        sa.Column(
            "content_hash",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "total_pages",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "total_sheets",
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
            "total_paragraphs",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "total_tables",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "total_cells",
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
            "total_words",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "has_selectable_text",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "requires_ocr",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("warnings_json", _json_type(), nullable=False),
        sa.Column("metadata_json", _json_type(), nullable=True),
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
            "source_file_size >= 0",
            name="source_file_size_nonnegative",
        ),
        sa.CheckConstraint(
            "length(source_sha256_hash) = 64",
            name="source_sha256_length",
        ),
        sa.CheckConstraint(
            "content_hash IS NULL OR length(content_hash) = 64",
            name="content_hash_length",
        ),
        sa.CheckConstraint(
            "total_pages >= 0 AND total_sheets >= 0 "
            "AND total_blocks >= 0 AND total_paragraphs >= 0 "
            "AND total_tables >= 0 AND total_cells >= 0 "
            "AND total_characters >= 0 AND total_words >= 0",
            name="summary_counts_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["extraction_job_id"],
            ["extraction_jobs.id"],
            name=(
                "fk_extraction_runs_extraction_job_id_extraction_jobs"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_extraction_runs_document_id_documents",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_revision_id"],
            ["document_revisions.id"],
            name=(
                "fk_extraction_runs_document_revision_id_"
                "document_revisions"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_file_id"],
            ["document_files.id"],
            name=(
                "fk_extraction_runs_document_file_id_document_files"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_extraction_runs"),
        sa.UniqueConstraint(
            "extraction_job_id",
            name="uq_extraction_runs_extraction_job_id",
        ),
    )
    for index_name, columns in (
        ("ix_extraction_runs_document_id", ["document_id"]),
        (
            "ix_extraction_runs_document_revision_id",
            ["document_revision_id"],
        ),
        (
            "ix_extraction_runs_document_file_id",
            ["document_file_id"],
        ),
        ("ix_extraction_runs_status", ["status"]),
        (
            "ix_extraction_runs_source_sha256_hash",
            ["source_sha256_hash"],
        ),
        ("ix_extraction_runs_content_hash", ["content_hash"]),
        ("ix_extraction_runs_created_at", ["created_at"]),
    ):
        op.create_index(index_name, "extraction_runs", columns)

    op.add_column(
        "document_files",
        sa.Column(
            "latest_extraction_run_id",
            sa.Uuid(),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_document_files_latest_extraction_run_id_extraction_runs",
        "document_files",
        "extraction_runs",
        ["latest_extraction_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_document_files_latest_extraction_run_id",
        "document_files",
        ["latest_extraction_run_id"],
    )

    op.create_table(
        "extracted_containers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("extraction_run_id", sa.Uuid(), nullable=False),
        sa.Column(
            "container_type",
            extracted_container_type,
            nullable=False,
        ),
        sa.Column("container_index", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=True),
        sa.Column("title", sa.String(length=1000), nullable=True),
        sa.Column(
            "raw_text",
            sa.Text(),
            server_default="",
            nullable=False,
        ),
        sa.Column(
            "normalised_text",
            sa.Text(),
            server_default="",
            nullable=False,
        ),
        sa.Column(
            "character_count",
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
            "container_index >= 0",
            name="container_index_nonnegative",
        ),
        sa.CheckConstraint(
            "character_count >= 0 AND word_count >= 0",
            name="counts_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["extraction_run_id"],
            ["extraction_runs.id"],
            name=(
                "fk_extracted_containers_extraction_run_id_"
                "extraction_runs"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_extracted_containers"),
    )
    for index_name, columns in (
        (
            "ix_extracted_containers_extraction_run_id",
            ["extraction_run_id"],
        ),
        (
            "ix_extracted_containers_container_type",
            ["container_type"],
        ),
        (
            "ix_extracted_containers_container_index",
            ["container_index"],
        ),
        ("ix_extracted_containers_name", ["name"]),
        (
            "ix_extracted_containers_run_order",
            ["extraction_run_id", "container_index"],
        ),
    ):
        op.create_index(index_name, "extracted_containers", columns)
    op.create_index(
        "ix_extracted_containers_name_search",
        "extracted_containers",
        [sa.text("to_tsvector('simple', name)")],
        postgresql_using="gin",
    )

    op.create_table(
        "extracted_blocks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("extraction_run_id", sa.Uuid(), nullable=False),
        sa.Column("container_id", sa.Uuid(), nullable=False),
        sa.Column("parent_block_id", sa.Uuid(), nullable=True),
        sa.Column("block_type", extracted_block_type, nullable=False),
        sa.Column("block_order", sa.BigInteger(), nullable=False),
        sa.Column(
            "source_reference",
            sa.String(length=1000),
            nullable=False,
        ),
        sa.Column(
            "text",
            sa.Text(),
            server_default="",
            nullable=False,
        ),
        sa.Column(
            "normalised_text",
            sa.Text(),
            server_default="",
            nullable=False,
        ),
        sa.Column(
            "style_name",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column("heading_level", sa.Integer(), nullable=True),
        sa.Column("location_json", _json_type(), nullable=True),
        sa.Column("metadata_json", _json_type(), nullable=True),
        sa.Column(
            "character_count",
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
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "block_order >= 0",
            name="block_order_nonnegative",
        ),
        sa.CheckConstraint(
            "heading_level IS NULL OR "
            "(heading_level >= 1 AND heading_level <= 9)",
            name="heading_level_range",
        ),
        sa.CheckConstraint(
            "character_count >= 0 AND word_count >= 0",
            name="counts_nonnegative",
        ),
        sa.CheckConstraint(
            "parent_block_id IS NULL OR parent_block_id <> id",
            name="not_self_parent",
        ),
        sa.ForeignKeyConstraint(
            ["extraction_run_id"],
            ["extraction_runs.id"],
            name=(
                "fk_extracted_blocks_extraction_run_id_extraction_runs"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["container_id"],
            ["extracted_containers.id"],
            name=(
                "fk_extracted_blocks_container_id_extracted_containers"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_block_id"],
            ["extracted_blocks.id"],
            name=(
                "fk_extracted_blocks_parent_block_id_extracted_blocks"
            ),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_extracted_blocks"),
    )
    for index_name, columns in (
        (
            "ix_extracted_blocks_extraction_run_id",
            ["extraction_run_id"],
        ),
        ("ix_extracted_blocks_container_id", ["container_id"]),
        ("ix_extracted_blocks_block_type", ["block_type"]),
        ("ix_extracted_blocks_block_order", ["block_order"]),
        ("ix_extracted_blocks_parent_block_id", ["parent_block_id"]),
        (
            "ix_extracted_blocks_source_reference",
            ["source_reference"],
        ),
        (
            "ix_extracted_blocks_run_order",
            ["extraction_run_id", "container_id", "block_order"],
        ),
    ):
        op.create_index(index_name, "extracted_blocks", columns)
    op.create_index(
        "ix_extracted_blocks_normalised_text_search",
        "extracted_blocks",
        [
            sa.text(
                "to_tsvector("
                "'simple', normalised_text || ' ' || source_reference"
                ")"
            )
        ],
        postgresql_using="gin",
    )

    op.create_table(
        "extracted_tables",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("extraction_run_id", sa.Uuid(), nullable=False),
        sa.Column("container_id", sa.Uuid(), nullable=False),
        sa.Column(
            "source_reference",
            sa.String(length=1000),
            nullable=False,
        ),
        sa.Column("table_index", sa.Integer(), nullable=False),
        sa.Column(
            "row_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "column_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "raw_text",
            sa.Text(),
            server_default="",
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
            "table_index >= 0",
            name="table_index_nonnegative",
        ),
        sa.CheckConstraint(
            "row_count >= 0 AND column_count >= 0",
            name="dimensions_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["extraction_run_id"],
            ["extraction_runs.id"],
            name=(
                "fk_extracted_tables_extraction_run_id_extraction_runs"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["container_id"],
            ["extracted_containers.id"],
            name=(
                "fk_extracted_tables_container_id_extracted_containers"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_extracted_tables"),
    )
    for index_name, columns in (
        (
            "ix_extracted_tables_extraction_run_id",
            ["extraction_run_id"],
        ),
        ("ix_extracted_tables_container_id", ["container_id"]),
        ("ix_extracted_tables_table_index", ["table_index"]),
        (
            "ix_extracted_tables_source_reference",
            ["source_reference"],
        ),
        (
            "ix_extracted_tables_run_order",
            ["extraction_run_id", "container_id", "table_index"],
        ),
    ):
        op.create_index(index_name, "extracted_tables", columns)

    op.create_table(
        "extracted_table_cells",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("extracted_table_id", sa.Uuid(), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("column_index", sa.Integer(), nullable=False),
        sa.Column(
            "row_span",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
        sa.Column(
            "column_span",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
        sa.Column(
            "coordinate",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "text",
            sa.Text(),
            server_default="",
            nullable=False,
        ),
        sa.Column(
            "normalised_text",
            sa.Text(),
            server_default="",
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
            "row_index >= 0 AND column_index >= 0",
            name="position_nonnegative",
        ),
        sa.CheckConstraint(
            "row_span >= 1 AND column_span >= 1",
            name="span_positive",
        ),
        sa.ForeignKeyConstraint(
            ["extracted_table_id"],
            ["extracted_tables.id"],
            name=(
                "fk_extracted_table_cells_extracted_table_id_"
                "extracted_tables"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_extracted_table_cells"),
        sa.UniqueConstraint(
            "extracted_table_id",
            "row_index",
            "column_index",
            name="uq_extracted_table_cells_table_position",
        ),
    )
    for index_name, columns in (
        (
            "ix_extracted_table_cells_extracted_table_id",
            ["extracted_table_id"],
        ),
        ("ix_extracted_table_cells_coordinate", ["coordinate"]),
        (
            "ix_extracted_table_cells_table_position",
            ["extracted_table_id", "row_index", "column_index"],
        ),
    ):
        op.create_index(index_name, "extracted_table_cells", columns)


def downgrade() -> None:
    """Remove Phase 6 extraction data while retaining Phase 1-5 data."""
    op.drop_index(
        "ix_document_files_latest_extraction_run_id",
        table_name="document_files",
    )
    op.drop_constraint(
        "fk_document_files_latest_extraction_run_id_extraction_runs",
        "document_files",
        type_="foreignkey",
    )
    op.drop_column("document_files", "latest_extraction_run_id")

    for index_name in (
        "ix_extracted_table_cells_table_position",
        "ix_extracted_table_cells_coordinate",
        "ix_extracted_table_cells_extracted_table_id",
    ):
        op.drop_index(index_name, table_name="extracted_table_cells")
    op.drop_table("extracted_table_cells")

    for index_name in (
        "ix_extracted_tables_run_order",
        "ix_extracted_tables_source_reference",
        "ix_extracted_tables_table_index",
        "ix_extracted_tables_container_id",
        "ix_extracted_tables_extraction_run_id",
    ):
        op.drop_index(index_name, table_name="extracted_tables")
    op.drop_table("extracted_tables")

    for index_name in (
        "ix_extracted_blocks_normalised_text_search",
        "ix_extracted_blocks_run_order",
        "ix_extracted_blocks_source_reference",
        "ix_extracted_blocks_parent_block_id",
        "ix_extracted_blocks_block_order",
        "ix_extracted_blocks_block_type",
        "ix_extracted_blocks_container_id",
        "ix_extracted_blocks_extraction_run_id",
    ):
        op.drop_index(index_name, table_name="extracted_blocks")
    op.drop_table("extracted_blocks")

    for index_name in (
        "ix_extracted_containers_name_search",
        "ix_extracted_containers_run_order",
        "ix_extracted_containers_name",
        "ix_extracted_containers_container_index",
        "ix_extracted_containers_container_type",
        "ix_extracted_containers_extraction_run_id",
    ):
        op.drop_index(index_name, table_name="extracted_containers")
    op.drop_table("extracted_containers")

    for index_name in (
        "ix_extraction_runs_created_at",
        "ix_extraction_runs_content_hash",
        "ix_extraction_runs_source_sha256_hash",
        "ix_extraction_runs_status",
        "ix_extraction_runs_document_file_id",
        "ix_extraction_runs_document_revision_id",
        "ix_extraction_runs_document_id",
    ):
        op.drop_index(index_name, table_name="extraction_runs")
    op.drop_table("extraction_runs")

    op.drop_index(
        "uq_extraction_jobs_one_active_per_file",
        table_name="extraction_jobs",
    )
    for index_name in (
        "ix_extraction_jobs_created_at",
        "ix_extraction_jobs_requested_at",
        "ix_extraction_jobs_requested_by",
        "ix_extraction_jobs_status",
        "ix_extraction_jobs_document_file_id",
        "ix_extraction_jobs_document_revision_id",
        "ix_extraction_jobs_document_id",
    ):
        op.drop_index(index_name, table_name="extraction_jobs")
    op.drop_table("extraction_jobs")

    bind = op.get_bind()
    for name, values in (
        ("extracted_block_type", EXTRACTED_BLOCK_TYPES),
        ("extracted_container_type", EXTRACTED_CONTAINER_TYPES),
        ("extraction_run_status", EXTRACTION_RUN_STATUSES),
        ("extraction_extractor_type", EXTRACTOR_TYPES),
        ("extraction_job_status", EXTRACTION_JOB_STATUSES),
        ("extraction_job_type", EXTRACTION_JOB_TYPES),
    ):
        sa.Enum(*values, name=name).drop(bind, checkfirst=True)

    # PostgreSQL audit enum labels are intentionally append-only, matching
    # the Phase 3-5 downgrade policy.
