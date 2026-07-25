"""Create Phase 5 physical-document file persistence.

Revision ID: 20260725_0004
Revises: 20260725_0003
Create Date: 2026-07-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260725_0004"
down_revision: str | Sequence[str] | None = "20260725_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PHASE5_AUDIT_ACTIONS = (
    "UPLOAD_FILE_PREVIEW",
    "CONFIRM_FILE_UPLOAD",
    "CANCEL_FILE_UPLOAD",
    "BATCH_UPLOAD_PREVIEW",
    "CONFIRM_BATCH_UPLOAD",
    "ATTACH_FILE_TO_REVISION",
    "CREATE_DOCUMENT_FROM_UPLOAD",
    "CREATE_REVISION_FROM_UPLOAD",
    "REPLACE_DOCUMENT_FILE",
    "DELETE_DOCUMENT_FILE",
    "RESTORE_DOCUMENT_FILE",
    "DOWNLOAD_DOCUMENT_FILE",
    "QUARANTINE_DOCUMENT_FILE",
    "DUPLICATE_FILE_DETECTED",
    "CLEANUP_EXPIRED_UPLOAD_SESSION",
)

DOCUMENT_FILE_STATUSES = (
    "UPLOADING",
    "AVAILABLE",
    "QUARANTINED",
    "REPLACED",
    "DELETED",
    "FAILED",
)
UPLOAD_SESSION_TYPES = ("SINGLE", "BATCH", "REPLACE")
UPLOAD_SESSION_STATUSES = (
    "CREATED",
    "UPLOADING",
    "READY_FOR_CONFIRMATION",
    "COMMITTED",
    "PARTIALLY_COMMITTED",
    "CANCELLED",
    "EXPIRED",
    "FAILED",
)
UPLOAD_IDENTIFICATION_STATUSES = (
    "IDENTIFIED",
    "PARTIALLY_IDENTIFIED",
    "NOT_IDENTIFIED",
    "DUPLICATE_FILE",
    "INVALID",
)
UPLOAD_PROPOSED_ACTIONS = (
    "ATTACH_TO_EXISTING_REVISION",
    "CREATE_DOCUMENT_AND_REVISION",
    "ADD_NEW_REVISION",
    "REPLACE_CURRENT_FILE",
    "MANUAL_REVIEW",
    "SKIP",
)
UPLOAD_SESSION_ITEM_STATUSES = (
    "PENDING",
    "READY",
    "COMMITTED",
    "SKIPPED",
    "FAILED",
    "CANCELLED",
)


def _json_type() -> sa.JSON:
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    """Add private file metadata without modifying Phase 4 records."""
    for action in PHASE5_AUDIT_ACTIONS:
        op.execute(
            sa.text(
                f"ALTER TYPE audit_action ADD VALUE IF NOT EXISTS '{action}'"
            )
        )

    document_file_status = sa.Enum(
        *DOCUMENT_FILE_STATUSES,
        name="document_file_status",
    )
    upload_session_type = sa.Enum(
        *UPLOAD_SESSION_TYPES,
        name="upload_session_type",
    )
    upload_session_status = sa.Enum(
        *UPLOAD_SESSION_STATUSES,
        name="upload_session_status",
    )
    identification_status = sa.Enum(
        *UPLOAD_IDENTIFICATION_STATUSES,
        name="upload_identification_status",
    )
    proposed_action = sa.Enum(
        *UPLOAD_PROPOSED_ACTIONS,
        name="upload_proposed_action",
    )
    item_status = sa.Enum(
        *UPLOAD_SESSION_ITEM_STATUSES,
        name="upload_session_item_status",
    )

    op.create_table(
        "document_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("document_revision_id", sa.Uuid(), nullable=False),
        sa.Column(
            "original_filename",
            sa.String(length=1024),
            nullable=False,
        ),
        sa.Column(
            "sanitized_filename",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "file_extension",
            sa.String(length=10),
            nullable=False,
        ),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column(
            "detected_mime_type",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column(
            "sha256_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "storage_provider",
            sa.String(length=50),
            server_default="local",
            nullable=False,
        ),
        sa.Column(
            "storage_key",
            sa.String(length=1000),
            nullable=False,
        ),
        sa.Column(
            "storage_bucket",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "file_status",
            document_file_status,
            server_default="UPLOADING",
            nullable=False,
        ),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "is_current",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("uploaded_by", sa.Uuid(), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "replaced_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("replaced_by_file_id", sa.Uuid(), nullable=True),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.Column("deletion_reason", sa.Text(), nullable=True),
        sa.Column("metadata_json", _json_type(), nullable=True),
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
            "file_size >= 0",
            name="file_size_nonnegative",
        ),
        sa.CheckConstraint(
            "length(sha256_hash) = 64",
            name="sha256_length",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_document_files_document_id_documents",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_revision_id"],
            ["document_revisions.id"],
            name=(
                "fk_document_files_document_revision_id_"
                "document_revisions"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["users.id"],
            name="fk_document_files_uploaded_by_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["replaced_by_file_id"],
            ["document_files.id"],
            name=(
                "fk_document_files_replaced_by_file_id_document_files"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"],
            ["users.id"],
            name="fk_document_files_deleted_by_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_files"),
        sa.UniqueConstraint(
            "storage_key",
            name="uq_document_files_storage_key",
        ),
    )
    op.create_index(
        "ix_document_files_document_id",
        "document_files",
        ["document_id"],
    )
    op.create_index(
        "ix_document_files_document_revision_id",
        "document_files",
        ["document_revision_id"],
    )
    op.create_index(
        "ix_document_files_sha256_hash",
        "document_files",
        ["sha256_hash"],
    )
    op.create_index(
        "ix_document_files_file_status",
        "document_files",
        ["file_status"],
    )
    op.create_index(
        "ix_document_files_is_current",
        "document_files",
        ["is_current"],
    )
    op.create_index(
        "ix_document_files_uploaded_at",
        "document_files",
        ["uploaded_at"],
    )
    op.create_index(
        "uq_document_files_one_current_primary",
        "document_files",
        ["document_revision_id"],
        unique=True,
        postgresql_where=sa.text(
            "is_current IS TRUE AND is_primary IS TRUE "
            "AND deleted_at IS NULL"
        ),
    )

    op.create_table(
        "upload_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("session_type", upload_session_type, nullable=False),
        sa.Column(
            "status",
            upload_session_status,
            server_default="CREATED",
            nullable=False,
        ),
        sa.Column(
            "total_files",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "total_size",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "committed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "cancelled_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("metadata_json", _json_type(), nullable=True),
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
            "total_files >= 0",
            name="total_files_nonnegative",
        ),
        sa.CheckConstraint(
            "total_size >= 0",
            name="total_size_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_upload_sessions_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_upload_sessions"),
    )
    op.create_index(
        "ix_upload_sessions_user_id",
        "upload_sessions",
        ["user_id"],
    )
    op.create_index(
        "ix_upload_sessions_status",
        "upload_sessions",
        ["status"],
    )
    op.create_index(
        "ix_upload_sessions_expires_at",
        "upload_sessions",
        ["expires_at"],
    )
    op.create_index(
        "ix_upload_sessions_created_at",
        "upload_sessions",
        ["created_at"],
    )

    op.create_table(
        "upload_session_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("upload_session_id", sa.Uuid(), nullable=False),
        sa.Column(
            "temporary_storage_key",
            sa.String(length=1000),
            nullable=False,
        ),
        sa.Column(
            "original_filename",
            sa.String(length=1024),
            nullable=False,
        ),
        sa.Column(
            "sanitized_filename",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column("file_extension", sa.String(length=10), nullable=True),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column(
            "detected_mime_type",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column(
            "sha256_hash",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "identification_status",
            identification_status,
            server_default="NOT_IDENTIFIED",
            nullable=False,
        ),
        sa.Column("matched_document_id", sa.Uuid(), nullable=True),
        sa.Column("matched_revision_id", sa.Uuid(), nullable=True),
        sa.Column(
            "proposed_action",
            proposed_action,
            server_default="SKIP",
            nullable=False,
        ),
        sa.Column("parsed_metadata_json", _json_type(), nullable=True),
        sa.Column("warnings_json", _json_type(), nullable=False),
        sa.Column("errors_json", _json_type(), nullable=False),
        sa.Column("quarantine_reason", sa.String(length=1000), nullable=True),
        sa.Column(
            "temporary_cleanup_pending",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "status",
            item_status,
            server_default="PENDING",
            nullable=False,
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
            "file_size IS NULL OR file_size >= 0",
            name="file_size_nonnegative",
        ),
        sa.CheckConstraint(
            "sha256_hash IS NULL OR length(sha256_hash) = 64",
            name="sha256_length",
        ),
        sa.ForeignKeyConstraint(
            ["upload_session_id"],
            ["upload_sessions.id"],
            name=(
                "fk_upload_session_items_upload_session_id_"
                "upload_sessions"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["matched_document_id"],
            ["documents.id"],
            name=(
                "fk_upload_session_items_matched_document_id_documents"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["matched_revision_id"],
            ["document_revisions.id"],
            name=(
                "fk_upload_session_items_matched_revision_id_"
                "document_revisions"
            ),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_upload_session_items"),
        sa.UniqueConstraint(
            "temporary_storage_key",
            name="uq_upload_session_items_temporary_storage_key",
        ),
    )
    op.create_index(
        "ix_upload_session_items_upload_session_id",
        "upload_session_items",
        ["upload_session_id"],
    )
    op.create_index(
        "ix_upload_session_items_identification_status",
        "upload_session_items",
        ["identification_status"],
    )
    op.create_index(
        "ix_upload_session_items_status",
        "upload_session_items",
        ["status"],
    )
    op.create_index(
        "ix_upload_session_items_matched_document_id",
        "upload_session_items",
        ["matched_document_id"],
    )
    op.create_index(
        "ix_upload_session_items_matched_revision_id",
        "upload_session_items",
        ["matched_revision_id"],
    )
    op.create_index(
        "ix_upload_session_items_sha256_hash",
        "upload_session_items",
        ["sha256_hash"],
    )


def downgrade() -> None:
    """Remove Phase 5 file persistence while retaining Phase 1-4 data."""
    op.drop_index(
        "ix_upload_session_items_sha256_hash",
        table_name="upload_session_items",
    )
    op.drop_index(
        "ix_upload_session_items_matched_revision_id",
        table_name="upload_session_items",
    )
    op.drop_index(
        "ix_upload_session_items_matched_document_id",
        table_name="upload_session_items",
    )
    op.drop_index(
        "ix_upload_session_items_status",
        table_name="upload_session_items",
    )
    op.drop_index(
        "ix_upload_session_items_identification_status",
        table_name="upload_session_items",
    )
    op.drop_index(
        "ix_upload_session_items_upload_session_id",
        table_name="upload_session_items",
    )
    op.drop_table("upload_session_items")

    op.drop_index(
        "ix_upload_sessions_created_at",
        table_name="upload_sessions",
    )
    op.drop_index(
        "ix_upload_sessions_expires_at",
        table_name="upload_sessions",
    )
    op.drop_index(
        "ix_upload_sessions_status",
        table_name="upload_sessions",
    )
    op.drop_index(
        "ix_upload_sessions_user_id",
        table_name="upload_sessions",
    )
    op.drop_table("upload_sessions")

    op.drop_index(
        "uq_document_files_one_current_primary",
        table_name="document_files",
    )
    op.drop_index(
        "ix_document_files_uploaded_at",
        table_name="document_files",
    )
    op.drop_index(
        "ix_document_files_is_current",
        table_name="document_files",
    )
    op.drop_index(
        "ix_document_files_file_status",
        table_name="document_files",
    )
    op.drop_index(
        "ix_document_files_sha256_hash",
        table_name="document_files",
    )
    op.drop_index(
        "ix_document_files_document_revision_id",
        table_name="document_files",
    )
    op.drop_index(
        "ix_document_files_document_id",
        table_name="document_files",
    )
    op.drop_table("document_files")

    bind = op.get_bind()
    for name, values in (
        ("upload_session_item_status", UPLOAD_SESSION_ITEM_STATUSES),
        ("upload_proposed_action", UPLOAD_PROPOSED_ACTIONS),
        (
            "upload_identification_status",
            UPLOAD_IDENTIFICATION_STATUSES,
        ),
        ("upload_session_status", UPLOAD_SESSION_STATUSES),
        ("upload_session_type", UPLOAD_SESSION_TYPES),
        ("document_file_status", DOCUMENT_FILE_STATUSES),
    ):
        sa.Enum(*values, name=name).drop(bind, checkfirst=True)

    # PostgreSQL audit enum labels are intentionally append-only, matching
    # the Phase 3 and Phase 4 downgrade policy.
