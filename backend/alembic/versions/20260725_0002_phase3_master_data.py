"""Create Phase 3 master-data persistence.

Revision ID: 20260725_0002
Revises: 20260725_0001
Create Date: 2026-07-25
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260725_0002"
down_revision: str | Sequence[str] | None = "20260725_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PHASE3_AUDIT_ACTIONS = (
    "CREATE_DEPARTMENT",
    "UPDATE_DEPARTMENT",
    "ACTIVATE_DEPARTMENT",
    "DEACTIVATE_DEPARTMENT",
    "CREATE_SECTION",
    "UPDATE_SECTION",
    "ACTIVATE_SECTION",
    "DEACTIVATE_SECTION",
    "CREATE_DOCUMENT_TYPE",
    "UPDATE_DOCUMENT_TYPE",
    "ACTIVATE_DOCUMENT_TYPE",
    "DEACTIVATE_DOCUMENT_TYPE",
    "CREATE_DOCUMENT_STATUS",
    "UPDATE_DOCUMENT_STATUS",
    "ACTIVATE_DOCUMENT_STATUS",
    "DEACTIVATE_DOCUMENT_STATUS",
    "CREATE_VALIDATION_RULE",
    "UPDATE_VALIDATION_RULE",
    "ACTIVATE_VALIDATION_RULE",
    "DEACTIVATE_VALIDATION_RULE",
    "SET_DEFAULT_VALIDATION_RULE",
    "IMPORT_MASTER_DATA",
    "EXPORT_MASTER_DATA",
)


def _audit_columns() -> list[sa.Column[object]]:
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
    """Add master data without modifying existing authentication records."""
    for action in PHASE3_AUDIT_ACTIONS:
        op.execute(
            sa.text(
                f"ALTER TYPE audit_action ADD VALUE IF NOT EXISTS '{action}'"
            )
        )

    op.create_table(
        "departments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        *_audit_columns(),
        *_actor_foreign_keys("departments"),
        sa.PrimaryKeyConstraint("id", name="pk_departments"),
        sa.UniqueConstraint("code", name="uq_departments_code"),
    )
    op.create_index("ix_departments_code", "departments", ["code"])
    op.create_index("ix_departments_name", "departments", ["name"])
    op.create_index(
        "ix_departments_is_active",
        "departments",
        ["is_active"],
    )

    # Phase 2 reserved this nullable UUID before departments existed. Any
    # non-null legacy value is necessarily dangling, so normalize it before
    # enforcing referential integrity instead of letting the upgrade fail.
    op.execute(
        sa.text(
            "UPDATE users SET department_id = NULL "
            "WHERE department_id IS NOT NULL"
        )
    )
    op.create_foreign_key(
        "fk_users_department_id_departments",
        "users",
        "departments",
        ["department_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "sections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            name="fk_sections_department_id_departments",
            ondelete="RESTRICT",
        ),
        *_actor_foreign_keys("sections"),
        sa.PrimaryKeyConstraint("id", name="pk_sections"),
        sa.UniqueConstraint(
            "department_id",
            "code",
            name="uq_sections_department_id_code",
        ),
    )
    op.create_index(
        "ix_sections_department_id",
        "sections",
        ["department_id"],
    )
    op.create_index("ix_sections_code", "sections", ["code"])
    op.create_index("ix_sections_name", "sections", ["name"])
    op.create_index("ix_sections_is_active", "sections", ["is_active"])

    # The default-rule column is added after validation_rules to avoid the
    # DocumentType <-> ValidationRule circular foreign-key dependency.
    op.create_table(
        "document_types",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "requires_section",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        *_audit_columns(),
        *_actor_foreign_keys("document_types"),
        sa.CheckConstraint(
            "category IS NULL OR category IN "
            "('PROCEDURE','POLICY','GUIDELINE','FORM','MANUAL','PLAN','OTHER')",
            name="ck_document_types_document_types_category",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_types"),
        sa.UniqueConstraint("code", name="uq_document_types_code"),
    )
    op.create_index(
        "ix_document_types_code",
        "document_types",
        ["code"],
    )
    op.create_index(
        "ix_document_types_name",
        "document_types",
        ["name"],
    )
    op.create_index(
        "ix_document_types_category",
        "document_types",
        ["category"],
    )
    op.create_index(
        "ix_document_types_is_active",
        "document_types",
        ["is_active"],
    )

    op.create_table(
        "document_statuses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "display_order",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "is_initial",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_final",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_obsolete",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        *_audit_columns(),
        *_actor_foreign_keys("document_statuses"),
        sa.CheckConstraint(
            "display_order >= 0",
            name=(
                "ck_document_statuses_"
                "document_statuses_display_order_nonnegative"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_statuses"),
        sa.UniqueConstraint("code", name="uq_document_statuses_code"),
    )
    op.create_index(
        "ix_document_statuses_code",
        "document_statuses",
        ["code"],
    )
    op.create_index(
        "ix_document_statuses_name",
        "document_statuses",
        ["name"],
    )
    op.create_index(
        "ix_document_statuses_display_order",
        "document_statuses",
        ["display_order"],
    )
    op.create_index(
        "ix_document_statuses_is_active",
        "document_statuses",
        ["is_active"],
    )
    op.create_index(
        "uq_document_statuses_single_initial",
        "document_statuses",
        ["is_initial"],
        unique=True,
        postgresql_where=sa.text(
            "is_initial IS TRUE AND deleted_at IS NULL"
        ),
    )

    op.create_table(
        "validation_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("document_type_id", sa.Uuid(), nullable=True),
        sa.Column(
            "required_indonesian",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "required_english",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "required_chinese",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "minimum_indonesian_coverage",
            sa.Integer(),
            server_default=sa.text("95"),
            nullable=False,
        ),
        sa.Column(
            "minimum_english_coverage",
            sa.Integer(),
            server_default=sa.text("95"),
            nullable=False,
        ),
        sa.Column(
            "minimum_chinese_coverage",
            sa.Integer(),
            server_default=sa.text("95"),
            nullable=False,
        ),
        sa.Column(
            "validate_language_order",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "language_order_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "validate_sections",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "required_sections_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "validate_tables",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "minimum_compliance_score",
            sa.Integer(),
            server_default=sa.text("95"),
            nullable=False,
        ),
        sa.Column(
            "partial_compliance_score",
            sa.Integer(),
            server_default=sa.text("70"),
            nullable=False,
        ),
        sa.Column(
            "is_default",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ["document_type_id"],
            ["document_types.id"],
            name="fk_validation_rules_document_type_id_document_types",
            ondelete="RESTRICT",
        ),
        *_actor_foreign_keys("validation_rules"),
        sa.CheckConstraint(
            "minimum_indonesian_coverage BETWEEN 0 AND 100",
            name=(
                "ck_validation_rules_"
                "validation_rules_indonesian_coverage"
            ),
        ),
        sa.CheckConstraint(
            "minimum_english_coverage BETWEEN 0 AND 100",
            name=(
                "ck_validation_rules_"
                "validation_rules_english_coverage"
            ),
        ),
        sa.CheckConstraint(
            "minimum_chinese_coverage BETWEEN 0 AND 100",
            name=(
                "ck_validation_rules_"
                "validation_rules_chinese_coverage"
            ),
        ),
        sa.CheckConstraint(
            "minimum_compliance_score BETWEEN 0 AND 100",
            name=(
                "ck_validation_rules_validation_rules_minimum_score"
            ),
        ),
        sa.CheckConstraint(
            "partial_compliance_score BETWEEN 0 AND 100",
            name="ck_validation_rules_validation_rules_partial_score",
        ),
        sa.CheckConstraint(
            "partial_compliance_score <= minimum_compliance_score",
            name="ck_validation_rules_validation_rules_score_order",
        ),
        sa.CheckConstraint(
            "required_indonesian OR required_english OR required_chinese",
            name="ck_validation_rules_validation_rules_language_required",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_validation_rules"),
        sa.UniqueConstraint("code", name="uq_validation_rules_code"),
    )
    op.create_index(
        "ix_validation_rules_code",
        "validation_rules",
        ["code"],
    )
    op.create_index(
        "ix_validation_rules_name",
        "validation_rules",
        ["name"],
    )
    op.create_index(
        "ix_validation_rules_document_type_id",
        "validation_rules",
        ["document_type_id"],
    )
    op.create_index(
        "ix_validation_rules_is_active",
        "validation_rules",
        ["is_active"],
    )
    op.create_index(
        "uq_validation_rules_global_default",
        "validation_rules",
        ["is_default"],
        unique=True,
        postgresql_where=sa.text(
            "is_default IS TRUE AND document_type_id IS NULL "
            "AND deleted_at IS NULL"
        ),
    )
    op.create_index(
        "uq_validation_rules_document_type_default",
        "validation_rules",
        ["document_type_id"],
        unique=True,
        postgresql_where=sa.text(
            "is_default IS TRUE AND document_type_id IS NOT NULL "
            "AND deleted_at IS NULL"
        ),
    )

    op.add_column(
        "document_types",
        sa.Column("default_validation_rule_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_document_types_default_validation_rule_id_validation_rules",
        "document_types",
        "validation_rules",
        ["default_validation_rule_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Remove Phase 3 tables while preserving all Phase 2 data."""
    op.drop_constraint(
        "fk_document_types_default_validation_rule_id_validation_rules",
        "document_types",
        type_="foreignkey",
    )
    op.drop_column("document_types", "default_validation_rule_id")

    op.drop_index(
        "uq_validation_rules_document_type_default",
        table_name="validation_rules",
    )
    op.drop_index(
        "uq_validation_rules_global_default",
        table_name="validation_rules",
    )
    op.drop_index(
        "ix_validation_rules_is_active",
        table_name="validation_rules",
    )
    op.drop_index(
        "ix_validation_rules_document_type_id",
        table_name="validation_rules",
    )
    op.drop_index(
        "ix_validation_rules_name",
        table_name="validation_rules",
    )
    op.drop_index(
        "ix_validation_rules_code",
        table_name="validation_rules",
    )
    op.drop_table("validation_rules")

    op.drop_index(
        "uq_document_statuses_single_initial",
        table_name="document_statuses",
    )
    op.drop_index(
        "ix_document_statuses_is_active",
        table_name="document_statuses",
    )
    op.drop_index(
        "ix_document_statuses_display_order",
        table_name="document_statuses",
    )
    op.drop_index(
        "ix_document_statuses_name",
        table_name="document_statuses",
    )
    op.drop_index(
        "ix_document_statuses_code",
        table_name="document_statuses",
    )
    op.drop_table("document_statuses")

    op.drop_index(
        "ix_document_types_is_active",
        table_name="document_types",
    )
    op.drop_index(
        "ix_document_types_category",
        table_name="document_types",
    )
    op.drop_index(
        "ix_document_types_name",
        table_name="document_types",
    )
    op.drop_index(
        "ix_document_types_code",
        table_name="document_types",
    )
    op.drop_table("document_types")

    op.drop_index("ix_sections_is_active", table_name="sections")
    op.drop_index("ix_sections_name", table_name="sections")
    op.drop_index("ix_sections_code", table_name="sections")
    op.drop_index("ix_sections_department_id", table_name="sections")
    op.drop_table("sections")

    op.drop_constraint(
        "fk_users_department_id_departments",
        "users",
        type_="foreignkey",
    )
    op.drop_index("ix_departments_is_active", table_name="departments")
    op.drop_index("ix_departments_name", table_name="departments")
    op.drop_index("ix_departments_code", table_name="departments")
    op.drop_table("departments")

    # PostgreSQL cannot remove individual enum values safely. Keeping the
    # additional labels is backward-compatible with Phase 2 and preserves
    # append-only audit records if a database is later upgraded again.
