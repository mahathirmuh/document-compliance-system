"""Create Phase 4 document register persistence.

Revision ID: 20260725_0003
Revises: 20260725_0002
Create Date: 2026-07-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260725_0003"
down_revision: str | Sequence[str] | None = "20260725_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PHASE4_AUDIT_ACTIONS = (
    "CREATE_DOCUMENT",
    "UPDATE_DOCUMENT",
    "CHANGE_DOCUMENT_CODE",
    "ARCHIVE_DOCUMENT",
    "RESTORE_DOCUMENT",
    "CREATE_DOCUMENT_REVISION",
    "UPDATE_DOCUMENT_REVISION",
    "SET_CURRENT_REVISION",
    "SUPERSEDE_DOCUMENT_REVISION",
    "IMPORT_DOCUMENT_REGISTER",
    "EXPORT_DOCUMENT_REGISTER",
    "BULK_ARCHIVE_DOCUMENTS",
    "BULK_RESTORE_DOCUMENTS",
    "BULK_UPDATE_DOCUMENT_STATUS",
)


def _actor_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def _actor_foreign_keys(table_name: str) -> list[sa.ForeignKeyConstraint]:
    return [
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=f"fk_{table_name}_created_by_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=f"fk_{table_name}_updated_by_users",
            ondelete="SET NULL",
        ),
    ]


def upgrade() -> None:
    """Add document identities and revisions without changing Phase 1-3 data."""
    for action in PHASE4_AUDIT_ACTIONS:
        op.execute(
            sa.text(
                f"ALTER TYPE audit_action ADD VALUE IF NOT EXISTS '{action}'"
            )
        )

    # current_revision_id is intentionally created without its FK first.
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_code", sa.String(length=20), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("section_id", sa.Uuid(), nullable=True),
        sa.Column("document_type_id", sa.Uuid(), nullable=False),
        sa.Column("document_number", sa.String(length=50), nullable=False),
        sa.Column(
            "base_document_code",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_department_id", sa.Uuid(), nullable=True),
        sa.Column(
            "document_owner_name",
            sa.String(length=150),
            nullable=True,
        ),
        sa.Column("current_revision_id", sa.Uuid(), nullable=True),
        sa.Column(
            "is_archived",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "archived_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("archived_by", sa.Uuid(), nullable=True),
        sa.Column("archive_reason", sa.Text(), nullable=True),
        *_actor_columns(),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            name="fk_documents_department_id_departments",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["section_id"],
            ["sections.id"],
            name="fk_documents_section_id_sections",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_type_id"],
            ["document_types.id"],
            name="fk_documents_document_type_id_document_types",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_department_id"],
            ["departments.id"],
            name="fk_documents_owner_department_id_departments",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["archived_by"],
            ["users.id"],
            name="fk_documents_archived_by_users",
            ondelete="SET NULL",
        ),
        *_actor_foreign_keys("documents"),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
        sa.UniqueConstraint(
            "base_document_code",
            name="uq_documents_base_document_code",
        ),
    )
    op.create_index("ix_documents_company_code", "documents", ["company_code"])
    op.create_index(
        "ix_documents_department_id",
        "documents",
        ["department_id"],
    )
    op.create_index("ix_documents_section_id", "documents", ["section_id"])
    op.create_index(
        "ix_documents_document_type_id",
        "documents",
        ["document_type_id"],
    )
    op.create_index(
        "ix_documents_document_number",
        "documents",
        ["document_number"],
    )
    op.create_index(
        "ix_documents_base_document_code",
        "documents",
        ["base_document_code"],
    )
    op.create_index("ix_documents_title", "documents", ["title"])
    op.create_index(
        "ix_documents_is_archived",
        "documents",
        ["is_archived"],
    )
    op.create_index("ix_documents_created_at", "documents", ["created_at"])

    op.create_table(
        "document_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("revision_code", sa.String(length=30), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=True),
        sa.Column(
            "full_document_code",
            sa.String(length=300),
            nullable=False,
        ),
        sa.Column("document_status_id", sa.Uuid(), nullable=False),
        sa.Column("validation_rule_id", sa.Uuid(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("review_date", sa.Date(), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("sharepoint_url", sa.String(length=2000), nullable=True),
        sa.Column(
            "external_reference",
            sa.String(length=500),
            nullable=True,
        ),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column(
            "is_current",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_superseded",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "superseded_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("superseded_by_revision_id", sa.Uuid(), nullable=True),
        *_actor_columns(),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_document_revisions_document_id_documents",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_status_id"],
            ["document_statuses.id"],
            name=(
                "fk_document_revisions_document_status_id_"
                "document_statuses"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["validation_rule_id"],
            ["validation_rules.id"],
            name=(
                "fk_document_revisions_validation_rule_id_validation_rules"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["superseded_by_revision_id"],
            ["document_revisions.id"],
            name="fk_doc_revisions_superseded_by",
            ondelete="SET NULL",
        ),
        *_actor_foreign_keys("document_revisions"),
        sa.CheckConstraint(
            "revision_number IS NULL OR revision_number >= 0",
            name="revision_number_nonnegative",
        ),
        sa.CheckConstraint(
            "expiry_date IS NULL OR effective_date IS NULL "
            "OR expiry_date >= effective_date",
            name="expiry_after_effective",
        ),
        sa.CheckConstraint(
            "review_date IS NULL OR issue_date IS NULL "
            "OR review_date >= issue_date",
            name="review_after_issue",
        ),
        sa.CheckConstraint(
            "superseded_by_revision_id IS NULL "
            "OR superseded_by_revision_id <> id",
            name="not_self_superseded",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_revisions"),
        sa.UniqueConstraint(
            "document_id",
            "revision_code",
            name="uq_document_revisions_document_id_revision_code",
        ),
        sa.UniqueConstraint(
            "full_document_code",
            name="uq_document_revisions_full_document_code",
        ),
    )
    op.create_index(
        "ix_document_revisions_document_id",
        "document_revisions",
        ["document_id"],
    )
    op.create_index(
        "ix_document_revisions_revision_code",
        "document_revisions",
        ["revision_code"],
    )
    op.create_index(
        "ix_document_revisions_document_status_id",
        "document_revisions",
        ["document_status_id"],
    )
    op.create_index(
        "ix_document_revisions_validation_rule_id",
        "document_revisions",
        ["validation_rule_id"],
    )
    op.create_index(
        "ix_document_revisions_is_current",
        "document_revisions",
        ["is_current"],
    )
    op.create_index(
        "ix_document_revisions_effective_date",
        "document_revisions",
        ["effective_date"],
    )
    op.create_index(
        "ix_document_revisions_created_at",
        "document_revisions",
        ["created_at"],
    )
    op.create_index(
        "uq_document_revisions_one_current",
        "document_revisions",
        ["document_id"],
        unique=True,
        postgresql_where=sa.text(
            "is_current IS TRUE AND deleted_at IS NULL"
        ),
    )

    op.create_foreign_key(
        "fk_documents_current_revision_id_document_revisions",
        "documents",
        "document_revisions",
        ["current_revision_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Remove Phase 4 tables while retaining Phase 1-3 data."""
    op.drop_constraint(
        "fk_documents_current_revision_id_document_revisions",
        "documents",
        type_="foreignkey",
    )
    op.drop_index(
        "uq_document_revisions_one_current",
        table_name="document_revisions",
    )
    op.drop_index(
        "ix_document_revisions_created_at",
        table_name="document_revisions",
    )
    op.drop_index(
        "ix_document_revisions_effective_date",
        table_name="document_revisions",
    )
    op.drop_index(
        "ix_document_revisions_is_current",
        table_name="document_revisions",
    )
    op.drop_index(
        "ix_document_revisions_validation_rule_id",
        table_name="document_revisions",
    )
    op.drop_index(
        "ix_document_revisions_document_status_id",
        table_name="document_revisions",
    )
    op.drop_index(
        "ix_document_revisions_revision_code",
        table_name="document_revisions",
    )
    op.drop_index(
        "ix_document_revisions_document_id",
        table_name="document_revisions",
    )
    op.drop_table("document_revisions")

    op.drop_index("ix_documents_created_at", table_name="documents")
    op.drop_index("ix_documents_is_archived", table_name="documents")
    op.drop_index("ix_documents_title", table_name="documents")
    op.drop_index("ix_documents_base_document_code", table_name="documents")
    op.drop_index("ix_documents_document_number", table_name="documents")
    op.drop_index("ix_documents_document_type_id", table_name="documents")
    op.drop_index("ix_documents_section_id", table_name="documents")
    op.drop_index("ix_documents_department_id", table_name="documents")
    op.drop_index("ix_documents_company_code", table_name="documents")
    op.drop_table("documents")

    # PostgreSQL enum labels remain append-only, as in the Phase 3 downgrade.
