"""Create the Phase 8 compliance data foundation.

Revision ID: 20260726_0008
Revises: 20260725_0007
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260726_0008"
down_revision: str | Sequence[str] | None = "20260725_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PHASE8_AUDIT_ACTIONS = (
    "QUEUE_COMPLIANCE_VALIDATION",
    "START_COMPLIANCE_VALIDATION",
    "COMPLETE_COMPLIANCE_VALIDATION",
    "PARTIAL_COMPLIANCE_VALIDATION",
    "FAIL_COMPLIANCE_VALIDATION",
    "CANCEL_COMPLIANCE_VALIDATION",
    "REVALIDATE_COMPLIANCE",
    "EXPORT_COMPLIANCE_RESULT",
    "CREATE_FINDING",
    "CREATE_MANUAL_FINDING",
    "UPDATE_FINDING",
    "REVIEW_FINDING",
    "RESOLVE_FINDING",
    "REOPEN_FINDING",
    "MARK_FINDING_FALSE_POSITIVE",
    "ACCEPT_FINDING_RISK",
    "ASSIGN_FINDING",
    "EXPORT_FINDINGS",
    "CREATE_SECTION_DEFINITION",
    "UPDATE_SECTION_DEFINITION",
    "CREATE_SECTION_ALIAS",
    "UPDATE_SECTION_ALIAS",
    "IMPORT_SECTION_ALIASES",
    "EXPORT_SECTION_ALIASES",
)
SECTION_ALIAS_LANGUAGE_CODES = ("id", "en", "zh", "any")
SECTION_ALIAS_MATCH_TYPES = ("EXACT", "PREFIX", "CONTAINS", "REGEX", "FUZZY")
COMPLIANCE_JOB_TYPES = (
    "INITIAL_VALIDATION",
    "REVALIDATION",
    "MANUAL_VALIDATION",
)
COMPLIANCE_JOB_STATUSES = (
    "QUEUED",
    "LOADING_CONTEXT",
    "DETECTING_SECTIONS",
    "GROUPING_CONTENT",
    "VALIDATING_LANGUAGES",
    "VALIDATING_SECTIONS",
    "VALIDATING_ORDER",
    "VALIDATING_TABLES",
    "GENERATING_FINDINGS",
    "CALCULATING_SCORE",
    "PERSISTING",
    "COMPLETED",
    "PARTIALLY_COMPLETED",
    "FAILED",
    "CANCEL_REQUESTED",
    "CANCELLED",
)
ACTIVE_COMPLIANCE_JOB_STATUSES = COMPLIANCE_JOB_STATUSES[:11] + (
    "CANCEL_REQUESTED",
)
COMPLIANCE_RUN_STATUSES = ("COMPLETED", "PARTIALLY_COMPLETED", "FAILED")
COMPLIANCE_STATUSES = (
    "COMPLIANT",
    "PARTIALLY_COMPLIANT",
    "NON_COMPLIANT",
    "NEEDS_REVIEW",
    "NOT_EVALUATED",
)
SECTION_LANGUAGE_PRESENCE_STATUSES = (
    "PRESENT",
    "NOT_PRESENT",
    "INSUFFICIENT_EVIDENCE",
    "MIXED_ONLY",
)
TRANSLATION_GROUP_TYPES = (
    "HEADING_GROUP",
    "PARAGRAPH_GROUP",
    "TABLE_ROW_GROUP",
    "TABLE_CELL_GROUP",
    "XLSX_ROW_GROUP",
    "PDF_POSITIONAL_GROUP",
    "MANUAL_GROUP",
)
FINDING_TYPES = (
    "DOCUMENT_CODE",
    "LANGUAGE_PRESENCE",
    "LANGUAGE_COVERAGE",
    "SECTION_MISSING",
    "SECTION_LANGUAGE_MISSING",
    "SECTION_ORDER",
    "LANGUAGE_ORDER",
    "TRANSLATION_GROUP_INCOMPLETE",
    "TABLE_LANGUAGE_MISSING",
    "CELL_LANGUAGE_MISSING",
    "UNKNOWN_LANGUAGE_EXCESS",
    "MIXED_LANGUAGE_EXCESS",
    "OCR_CONFIDENCE",
    "EXTRACTION_QUALITY",
    "STRUCTURE",
    "MANUAL",
)
FINDING_CODES = (
    "INVALID_DOCUMENT_CODE",
    "MISSING_INDONESIAN",
    "MISSING_ENGLISH",
    "MISSING_CHINESE",
    "LOW_INDONESIAN_COVERAGE",
    "LOW_ENGLISH_COVERAGE",
    "LOW_CHINESE_COVERAGE",
    "MISSING_REQUIRED_SECTION",
    "MISSING_SECTION_INDONESIAN",
    "MISSING_SECTION_ENGLISH",
    "MISSING_SECTION_CHINESE",
    "SECTION_ORDER_INVALID",
    "LANGUAGE_ORDER_INVALID",
    "INCOMPLETE_TRANSLATION_GROUP",
    "MISSING_TRANSLATION_GROUP_INDONESIAN",
    "MISSING_TRANSLATION_GROUP_ENGLISH",
    "MISSING_TRANSLATION_GROUP_CHINESE",
    "TABLE_TRANSLATION_INCOMPLETE",
    "TABLE_CELL_LANGUAGE_MISSING",
    "XLSX_ROW_TRANSLATION_INCOMPLETE",
    "UNKNOWN_TEXT_EXCEEDS_THRESHOLD",
    "MIXED_TEXT_EXCEEDS_THRESHOLD",
    "OCR_CONFIDENCE_TOO_LOW",
    "EXTRACTION_PARTIALLY_COMPLETED",
    "OCR_REQUIRED_NOT_COMPLETED",
    "MANUAL_FINDING",
)
FINDING_SEVERITIES = ("CRITICAL", "MAJOR", "MINOR", "INFORMATION")
FINDING_STATUSES = (
    "OPEN",
    "IN_REVIEW",
    "RESOLVED",
    "CLOSED",
    "FALSE_POSITIVE",
    "ACCEPTED_RISK",
    "REOPENED",
)

ENUM_DEFINITIONS = (
    ("section_alias_language_code", SECTION_ALIAS_LANGUAGE_CODES),
    ("section_alias_match_type", SECTION_ALIAS_MATCH_TYPES),
    ("compliance_job_type", COMPLIANCE_JOB_TYPES),
    ("compliance_job_status", COMPLIANCE_JOB_STATUSES),
    ("compliance_run_status", COMPLIANCE_RUN_STATUSES),
    ("compliance_status", COMPLIANCE_STATUSES),
    (
        "section_language_presence_status",
        SECTION_LANGUAGE_PRESENCE_STATUSES,
    ),
    ("translation_group_type", TRANSLATION_GROUP_TYPES),
    ("finding_code", FINDING_CODES),
    ("finding_type", FINDING_TYPES),
    ("finding_severity", FINDING_SEVERITIES),
    ("finding_status", FINDING_STATUSES),
)


def _json_type() -> sa.JSON:
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _enum(name: str, values: tuple[str, ...]) -> postgresql.ENUM:
    return postgresql.ENUM(*values, name=name, create_type=False)


def _create_enum_types() -> None:
    bind = op.get_bind()
    for name, values in ENUM_DEFINITIONS:
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)


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
    ]


def _actor_constraints(table_name: str) -> list[sa.ForeignKeyConstraint]:
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


def _create_indexes(
    table_name: str,
    definitions: tuple[tuple[str, list[str]], ...],
) -> None:
    for index_name, columns in definitions:
        op.create_index(index_name, table_name, columns)


def _drop_indexes(table_name: str, names: tuple[str, ...]) -> None:
    for name in names:
        op.drop_index(name, table_name=table_name)


def _create_section_catalog() -> None:
    op.create_table(
        "section_alias_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
        *_actor_columns(),
        *_actor_constraints("section_alias_profiles"),
        sa.PrimaryKeyConstraint("id", name="pk_section_alias_profiles"),
        sa.UniqueConstraint(
            "code",
            name="uq_section_alias_profiles_code",
        ),
    )
    _create_indexes(
        "section_alias_profiles",
        (
            ("ix_section_alias_profiles_code", ["code"]),
            ("ix_section_alias_profiles_name", ["name"]),
            ("ix_section_alias_profiles_is_active", ["is_active"]),
        ),
    )
    op.create_index(
        "uq_section_alias_profiles_single_default",
        "section_alias_profiles",
        ["is_default"],
        unique=True,
        postgresql_where=sa.text("is_default IS TRUE"),
        sqlite_where=sa.text("is_default = 1"),
    )

    op.create_table(
        "section_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_code", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "display_order",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "is_required_default",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_repeatable",
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
        *_actor_columns(),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["section_alias_profiles.id"],
            name=(
                "fk_section_definitions_profile_id_"
                "section_alias_profiles"
            ),
            ondelete="CASCADE",
        ),
        *_actor_constraints("section_definitions"),
        sa.CheckConstraint(
            "display_order >= 0",
            name=op.f(
                "ck_section_definitions_"
                "section_definitions_display_order_nonnegative"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_section_definitions"),
        sa.UniqueConstraint(
            "profile_id",
            "canonical_code",
            name="uq_section_definitions_profile_code",
        ),
    )
    _create_indexes(
        "section_definitions",
        (
            ("ix_section_definitions_profile_id", ["profile_id"]),
            (
                "ix_section_definitions_canonical_code",
                ["canonical_code"],
            ),
            ("ix_section_definitions_display_order", ["display_order"]),
            ("ix_section_definitions_is_active", ["is_active"]),
        ),
    )

    op.create_table(
        "section_aliases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("section_definition_id", sa.Uuid(), nullable=False),
        sa.Column(
            "language_code",
            _enum(
                "section_alias_language_code",
                SECTION_ALIAS_LANGUAGE_CODES,
            ),
            nullable=False,
        ),
        sa.Column("alias_text", sa.Text(), nullable=False),
        sa.Column("normalised_alias", sa.Text(), nullable=False),
        sa.Column(
            "match_type",
            _enum("section_alias_match_type", SECTION_ALIAS_MATCH_TYPES),
            server_default="EXACT",
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "is_regex",
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
        *_actor_columns(),
        sa.ForeignKeyConstraint(
            ["section_definition_id"],
            ["section_definitions.id"],
            name=(
                "fk_section_aliases_section_definition_id_"
                "section_definitions"
            ),
            ondelete="CASCADE",
        ),
        *_actor_constraints("section_aliases"),
        sa.CheckConstraint(
            "priority >= 0",
            name="ck_section_aliases_section_aliases_priority_nonnegative",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_section_aliases"),
        sa.UniqueConstraint(
            "section_definition_id",
            "language_code",
            "normalised_alias",
            name="uq_section_aliases_definition_language_normalised",
        ),
    )
    _create_indexes(
        "section_aliases",
        (
            (
                "ix_section_aliases_section_definition_id",
                ["section_definition_id"],
            ),
            ("ix_section_aliases_language_code", ["language_code"]),
            ("ix_section_aliases_normalised_alias", ["normalised_alias"]),
            ("ix_section_aliases_match_type", ["match_type"]),
            ("ix_section_aliases_priority", ["priority"]),
            ("ix_section_aliases_is_active", ["is_active"]),
        ),
    )


def _enhance_validation_rules() -> None:
    scalar_columns = (
        sa.Column(
            "validate_document_code",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "validate_language_presence",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "validate_language_coverage",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "validate_container_completeness",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "validate_translation_groups",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "validate_cells",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "maximum_unknown_block_percentage",
            sa.Numeric(6, 2),
            server_default="10",
            nullable=False,
        ),
        sa.Column(
            "maximum_mixed_block_percentage",
            sa.Numeric(6, 2),
            server_default="20",
            nullable=False,
        ),
        sa.Column(
            "document_code_weight",
            sa.Numeric(6, 2),
            server_default="10",
            nullable=False,
        ),
        sa.Column(
            "language_presence_weight",
            sa.Numeric(6, 2),
            server_default="25",
            nullable=False,
        ),
        sa.Column(
            "language_coverage_weight",
            sa.Numeric(6, 2),
            server_default="15",
            nullable=False,
        ),
        sa.Column(
            "section_completeness_weight",
            sa.Numeric(6, 2),
            server_default="20",
            nullable=False,
        ),
        sa.Column(
            "language_order_weight",
            sa.Numeric(6, 2),
            server_default="10",
            nullable=False,
        ),
        sa.Column(
            "translation_group_weight",
            sa.Numeric(6, 2),
            server_default="15",
            nullable=False,
        ),
        sa.Column(
            "table_completeness_weight",
            sa.Numeric(6, 2),
            server_default="5",
            nullable=False,
        ),
        sa.Column(
            "critical_finding_score_cap",
            sa.Numeric(6, 2),
            server_default="69",
            nullable=False,
        ),
        sa.Column(
            "major_finding_penalty",
            sa.Numeric(6, 2),
            server_default="5",
            nullable=False,
        ),
        sa.Column(
            "minor_finding_penalty",
            sa.Numeric(6, 2),
            server_default="1",
            nullable=False,
        ),
        sa.Column(
            "compliant_score",
            sa.Numeric(6, 2),
            server_default="95",
            nullable=False,
        ),
        sa.Column(
            "partially_compliant_score",
            sa.Numeric(6, 2),
            server_default="70",
            nullable=False,
        ),
        sa.Column(
            "needs_review_score",
            sa.Numeric(6, 2),
            server_default="50",
            nullable=False,
        ),
        sa.Column(
            "fail_on_missing_required_language",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "fail_on_missing_required_section",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "fail_on_critical_finding",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    for column in scalar_columns:
        op.add_column("validation_rules", column)
    op.add_column(
        "validation_rules",
        sa.Column("required_languages_json", _json_type(), nullable=True),
    )
    op.add_column(
        "validation_rules",
        sa.Column(
            "minimum_language_block_coverage_json",
            _json_type(),
            nullable=True,
        ),
    )
    op.add_column(
        "validation_rules",
        sa.Column(
            "minimum_language_character_coverage_json",
            _json_type(),
            nullable=True,
        ),
    )
    op.add_column(
        "validation_rules",
        sa.Column("validation_options_json", _json_type(), nullable=True),
    )
    op.add_column(
        "validation_rules",
        sa.Column("section_alias_profile_id", sa.Uuid(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE validation_rules SET "
            "required_languages_json = "
            "(CASE WHEN required_indonesian THEN '[\"id\"]'::jsonb "
            "ELSE '[]'::jsonb END) || "
            "(CASE WHEN required_english THEN '[\"en\"]'::jsonb "
            "ELSE '[]'::jsonb END) || "
            "(CASE WHEN required_chinese THEN '[\"zh\"]'::jsonb "
            "ELSE '[]'::jsonb END), "
            "minimum_language_block_coverage_json = jsonb_build_object("
            "'id', minimum_indonesian_coverage, "
            "'en', minimum_english_coverage, "
            "'zh', minimum_chinese_coverage), "
            "minimum_language_character_coverage_json = jsonb_build_object("
            "'id', minimum_indonesian_coverage, "
            "'en', minimum_english_coverage, "
            "'zh', minimum_chinese_coverage), "
            "validation_options_json = '{}'::jsonb, "
            "compliant_score = minimum_compliance_score, "
            "partially_compliant_score = partial_compliance_score, "
            "needs_review_score = LEAST(partial_compliance_score, 50)"
        )
    )
    for column_name in (
        "required_languages_json",
        "minimum_language_block_coverage_json",
        "minimum_language_character_coverage_json",
        "validation_options_json",
    ):
        op.alter_column(
            "validation_rules",
            column_name,
            existing_type=_json_type(),
            nullable=False,
        )
    op.create_foreign_key(
        op.f(
            "fk_validation_rules_section_alias_profile_id_"
            "section_alias_profiles"
        ),
        "validation_rules",
        "section_alias_profiles",
        ["section_alias_profile_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_validation_rules_section_alias_profile_id",
        "validation_rules",
        ["section_alias_profile_id"],
    )
    for name, condition in (
        (
            "validation_rules_unknown_percentage",
            "maximum_unknown_block_percentage BETWEEN 0 AND 100",
        ),
        (
            "validation_rules_mixed_percentage",
            "maximum_mixed_block_percentage BETWEEN 0 AND 100",
        ),
        (
            "validation_rules_weights_nonnegative",
            (
                "document_code_weight >= 0 "
                "AND language_presence_weight >= 0 "
                "AND language_coverage_weight >= 0 "
                "AND section_completeness_weight >= 0 "
                "AND language_order_weight >= 0 "
                "AND translation_group_weight >= 0 "
                "AND table_completeness_weight >= 0"
            ),
        ),
        (
            "validation_rules_weight_total",
            (
                "document_code_weight + language_presence_weight "
                "+ language_coverage_weight + section_completeness_weight "
                "+ language_order_weight + translation_group_weight "
                "+ table_completeness_weight = 100"
            ),
        ),
        (
            "validation_rules_penalty_range",
            (
                "critical_finding_score_cap BETWEEN 0 AND 100 "
                "AND major_finding_penalty >= 0 "
                "AND minor_finding_penalty >= 0"
            ),
        ),
        (
            "validation_rules_phase8_score_range",
            (
                "compliant_score BETWEEN 0 AND 100 "
                "AND partially_compliant_score BETWEEN 0 AND 100 "
                "AND needs_review_score BETWEEN 0 AND 100"
            ),
        ),
        (
            "validation_rules_phase8_score_order",
            (
                "needs_review_score <= partially_compliant_score "
                "AND partially_compliant_score <= compliant_score"
            ),
        ),
    ):
        op.create_check_constraint(
            op.f(f"ck_validation_rules_{name}"),
            "validation_rules",
            condition,
        )


def _create_compliance_jobs_and_runs() -> None:
    op.create_table(
        "compliance_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("document_revision_id", sa.Uuid(), nullable=False),
        sa.Column("document_file_id", sa.Uuid(), nullable=False),
        sa.Column("extraction_run_id", sa.Uuid(), nullable=False),
        sa.Column("ocr_run_id", sa.Uuid(), nullable=True),
        sa.Column("language_detection_run_id", sa.Uuid(), nullable=False),
        sa.Column("validation_rule_id", sa.Uuid(), nullable=False),
        sa.Column(
            "job_type",
            _enum("compliance_job_type", COMPLIANCE_JOB_TYPES),
            server_default="INITIAL_VALIDATION",
            nullable=False,
        ),
        sa.Column(
            "status",
            _enum("compliance_job_status", COMPLIANCE_JOB_STATUSES),
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
        sa.Column("source_content_hash", sa.String(length=64), nullable=True),
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
            server_default="1",
            nullable=False,
        ),
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
            name="ck_compliance_jobs_compliance_jobs_progress_range",
        ),
        sa.CheckConstraint(
            "attempt_number >= 1 AND maximum_attempts >= 1 "
            "AND attempt_number <= maximum_attempts",
            name="ck_compliance_jobs_compliance_jobs_attempt_range",
        ),
        sa.CheckConstraint(
            "source_content_hash IS NULL "
            "OR length(source_content_hash) = 64",
            name="ck_compliance_jobs_compliance_jobs_source_hash_length",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_compliance_jobs_document_id_documents",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_revision_id"],
            ["document_revisions.id"],
            name=(
                "fk_compliance_jobs_document_revision_id_"
                "document_revisions"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_file_id"],
            ["document_files.id"],
            name="fk_compliance_jobs_document_file_id_document_files",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["extraction_run_id"],
            ["extraction_runs.id"],
            name="fk_compliance_jobs_extraction_run_id_extraction_runs",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ocr_run_id"],
            ["ocr_runs.id"],
            name="fk_compliance_jobs_ocr_run_id_ocr_runs",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["language_detection_run_id"],
            ["language_detection_runs.id"],
            name=op.f(
                "fk_compliance_jobs_language_detection_run_id_"
                "language_detection_runs"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["validation_rule_id"],
            ["validation_rules.id"],
            name=(
                "fk_compliance_jobs_validation_rule_id_validation_rules"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            name="fk_compliance_jobs_requested_by_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_compliance_jobs"),
    )
    _create_indexes(
        "compliance_jobs",
        (
            ("ix_compliance_jobs_document_id", ["document_id"]),
            (
                "ix_compliance_jobs_document_revision_id",
                ["document_revision_id"],
            ),
            ("ix_compliance_jobs_document_file_id", ["document_file_id"]),
            ("ix_compliance_jobs_extraction_run_id", ["extraction_run_id"]),
            ("ix_compliance_jobs_ocr_run_id", ["ocr_run_id"]),
            (
                "ix_compliance_jobs_language_detection_run_id",
                ["language_detection_run_id"],
            ),
            (
                "ix_compliance_jobs_validation_rule_id",
                ["validation_rule_id"],
            ),
            ("ix_compliance_jobs_status", ["status"]),
            ("ix_compliance_jobs_requested_by", ["requested_by"]),
            ("ix_compliance_jobs_requested_at", ["requested_at"]),
            (
                "ix_compliance_jobs_source_content_hash",
                ["source_content_hash"],
            ),
        ),
    )
    active_statuses = ", ".join(
        f"'{status}'" for status in ACTIVE_COMPLIANCE_JOB_STATUSES
    )
    op.create_index(
        "uq_compliance_jobs_active_source",
        "compliance_jobs",
        ["document_file_id", "source_content_hash"],
        unique=True,
        postgresql_where=sa.text(f"status IN ({active_statuses})"),
        sqlite_where=sa.text(f"status IN ({active_statuses})"),
    )

    op.create_table(
        "compliance_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("compliance_job_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("document_revision_id", sa.Uuid(), nullable=False),
        sa.Column("document_file_id", sa.Uuid(), nullable=False),
        sa.Column("extraction_run_id", sa.Uuid(), nullable=False),
        sa.Column("ocr_run_id", sa.Uuid(), nullable=True),
        sa.Column("language_detection_run_id", sa.Uuid(), nullable=False),
        sa.Column("validation_rule_id", sa.Uuid(), nullable=False),
        sa.Column("rule_snapshot_json", _json_type(), nullable=False),
        sa.Column("source_content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            _enum("compliance_run_status", COMPLIANCE_RUN_STATUSES),
            nullable=False,
        ),
        sa.Column(
            "compliance_status",
            _enum("compliance_status", COMPLIANCE_STATUSES),
            server_default="NOT_EVALUATED",
            nullable=False,
        ),
        sa.Column(
            "compliance_score",
            sa.Numeric(7, 2),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "maximum_score",
            sa.Numeric(7, 2),
            server_default="100",
            nullable=False,
        ),
        *[
            sa.Column(
                name,
                sa.Numeric(7, 2),
                server_default="0",
                nullable=False,
            )
            for name in (
                "document_code_score",
                "language_presence_score",
                "language_coverage_score",
                "section_completeness_score",
                "language_order_score",
                "translation_group_score",
                "table_completeness_score",
            )
        ],
        *[
            sa.Column(
                name,
                sa.Integer(),
                server_default="0",
                nullable=False,
            )
            for name in (
                "total_findings",
                "critical_findings",
                "major_findings",
                "minor_findings",
                "information_findings",
                "open_findings",
            )
        ],
        sa.Column("required_languages_json", _json_type(), nullable=False),
        sa.Column("detected_languages_json", _json_type(), nullable=False),
        sa.Column("missing_languages_json", _json_type(), nullable=False),
        sa.Column("required_sections_json", _json_type(), nullable=False),
        sa.Column("detected_sections_json", _json_type(), nullable=False),
        sa.Column("missing_sections_json", _json_type(), nullable=False),
        sa.Column("warnings_json", _json_type(), nullable=False),
        sa.Column("metrics_json", _json_type(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(source_content_hash) = 64",
            name="ck_compliance_runs_compliance_runs_source_hash_length",
        ),
        sa.CheckConstraint(
            "compliance_score >= 0 AND compliance_score <= 100 "
            "AND maximum_score >= 0 AND maximum_score <= 100",
            name="ck_compliance_runs_compliance_runs_score_range",
        ),
        sa.CheckConstraint(
            "document_code_score >= 0 "
            "AND language_presence_score >= 0 "
            "AND language_coverage_score >= 0 "
            "AND section_completeness_score >= 0 "
            "AND language_order_score >= 0 "
            "AND translation_group_score >= 0 "
            "AND table_completeness_score >= 0",
            name=(
                "ck_compliance_runs_"
                "compliance_runs_component_scores_nonnegative"
            ),
        ),
        sa.CheckConstraint(
            "total_findings >= 0 AND critical_findings >= 0 "
            "AND major_findings >= 0 AND minor_findings >= 0 "
            "AND information_findings >= 0 AND open_findings >= 0 "
            "AND open_findings <= total_findings",
            name="ck_compliance_runs_compliance_runs_finding_counts",
        ),
        sa.ForeignKeyConstraint(
            ["compliance_job_id"],
            ["compliance_jobs.id"],
            name="fk_compliance_runs_compliance_job_id_compliance_jobs",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_compliance_runs_document_id_documents",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_revision_id"],
            ["document_revisions.id"],
            name=(
                "fk_compliance_runs_document_revision_id_"
                "document_revisions"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_file_id"],
            ["document_files.id"],
            name="fk_compliance_runs_document_file_id_document_files",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["extraction_run_id"],
            ["extraction_runs.id"],
            name="fk_compliance_runs_extraction_run_id_extraction_runs",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ocr_run_id"],
            ["ocr_runs.id"],
            name="fk_compliance_runs_ocr_run_id_ocr_runs",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["language_detection_run_id"],
            ["language_detection_runs.id"],
            name=op.f(
                "fk_compliance_runs_language_detection_run_id_"
                "language_detection_runs"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["validation_rule_id"],
            ["validation_rules.id"],
            name=(
                "fk_compliance_runs_validation_rule_id_validation_rules"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            name="fk_compliance_runs_requested_by_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_compliance_runs"),
        sa.UniqueConstraint(
            "compliance_job_id",
            name="uq_compliance_runs_compliance_job_id",
        ),
    )
    _create_indexes(
        "compliance_runs",
        (
            ("ix_compliance_runs_document_id", ["document_id"]),
            (
                "ix_compliance_runs_document_revision_id",
                ["document_revision_id"],
            ),
            ("ix_compliance_runs_document_file_id", ["document_file_id"]),
            ("ix_compliance_runs_extraction_run_id", ["extraction_run_id"]),
            ("ix_compliance_runs_ocr_run_id", ["ocr_run_id"]),
            (
                "ix_compliance_runs_language_detection_run_id",
                ["language_detection_run_id"],
            ),
            (
                "ix_compliance_runs_validation_rule_id",
                ["validation_rule_id"],
            ),
            ("ix_compliance_runs_status", ["status"]),
            ("ix_compliance_runs_compliance_status", ["compliance_status"]),
            ("ix_compliance_runs_compliance_score", ["compliance_score"]),
            (
                "ix_compliance_runs_source_content_hash",
                ["source_content_hash"],
            ),
            ("ix_compliance_runs_created_at", ["created_at"]),
            (
                "ix_compliance_runs_file_created",
                ["document_file_id", "created_at"],
            ),
        ),
    )
    op.add_column(
        "document_files",
        sa.Column("latest_compliance_run_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_document_files_latest_compliance_run_id_compliance_runs",
        "document_files",
        "compliance_runs",
        ["latest_compliance_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_document_files_latest_compliance_run_id",
        "document_files",
        ["latest_compliance_run_id"],
    )


def _create_section_and_group_results() -> None:
    op.create_table(
        "detected_sections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("compliance_run_id", sa.Uuid(), nullable=False),
        sa.Column("section_definition_id", sa.Uuid(), nullable=True),
        sa.Column("canonical_code", sa.String(length=64), nullable=False),
        sa.Column("container_id", sa.Uuid(), nullable=True),
        sa.Column("start_block_id", sa.Uuid(), nullable=True),
        sa.Column("end_block_id", sa.Uuid(), nullable=True),
        sa.Column("heading_block_id", sa.Uuid(), nullable=True),
        sa.Column("heading_text", sa.Text(), nullable=False),
        sa.Column(
            "heading_language_code",
            sa.String(length=20),
            nullable=True,
        ),
        sa.Column(
            "match_type",
            _enum("section_alias_match_type", SECTION_ALIAS_MATCH_TYPES),
            nullable=False,
        ),
        sa.Column("match_confidence", sa.Numeric(6, 5), nullable=False),
        sa.Column("section_order", sa.Integer(), nullable=False),
        sa.Column(
            "is_required",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_complete",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("language_presence_json", _json_type(), nullable=False),
        sa.Column("metrics_json", _json_type(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "match_confidence >= 0 AND match_confidence <= 1",
            name=(
                "ck_detected_sections_"
                "detected_sections_confidence_range"
            ),
        ),
        sa.CheckConstraint(
            "section_order >= 0",
            name="ck_detected_sections_detected_sections_order_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["compliance_run_id"],
            ["compliance_runs.id"],
            name=(
                "fk_detected_sections_compliance_run_id_compliance_runs"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["section_definition_id"],
            ["section_definitions.id"],
            name=(
                "fk_detected_sections_section_definition_id_"
                "section_definitions"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["container_id"],
            ["extracted_containers.id"],
            name=(
                "fk_detected_sections_container_id_extracted_containers"
            ),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_detected_sections"),
        sa.UniqueConstraint(
            "compliance_run_id",
            "section_order",
            name="uq_detected_sections_run_order",
        ),
    )
    _create_indexes(
        "detected_sections",
        (
            (
                "ix_detected_sections_compliance_run_id",
                ["compliance_run_id"],
            ),
            (
                "ix_detected_sections_section_definition_id",
                ["section_definition_id"],
            ),
            (
                "ix_detected_sections_canonical_code",
                ["canonical_code"],
            ),
            ("ix_detected_sections_container_id", ["container_id"]),
            (
                "ix_detected_sections_heading_block_id",
                ["heading_block_id"],
            ),
            ("ix_detected_sections_is_required", ["is_required"]),
            ("ix_detected_sections_is_complete", ["is_complete"]),
        ),
    )

    op.create_table(
        "section_language_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("detected_section_id", sa.Uuid(), nullable=False),
        sa.Column("language_code", sa.String(length=20), nullable=False),
        sa.Column(
            "presence_status",
            _enum(
                "section_language_presence_status",
                SECTION_LANGUAGE_PRESENCE_STATUSES,
            ),
            nullable=False,
        ),
        sa.Column(
            "block_count",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "character_count",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "coverage_percentage",
            sa.Numeric(7, 3),
            server_default="0",
            nullable=False,
        ),
        sa.Column("average_confidence", sa.Numeric(6, 5), nullable=True),
        sa.Column("first_block_id", sa.Uuid(), nullable=True),
        sa.Column("last_block_id", sa.Uuid(), nullable=True),
        sa.Column("metrics_json", _json_type(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "block_count >= 0 AND character_count >= 0",
            name=op.f(
                "ck_section_language_results_"
                "section_language_results_counts_nonnegative"
            ),
        ),
        sa.CheckConstraint(
            "coverage_percentage >= 0 AND coverage_percentage <= 100",
            name=op.f(
                "ck_section_language_results_"
                "section_language_results_coverage_range"
            ),
        ),
        sa.CheckConstraint(
            "average_confidence IS NULL OR "
            "(average_confidence >= 0 AND average_confidence <= 1)",
            name=op.f(
                "ck_section_language_results_"
                "section_language_results_confidence_range"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["detected_section_id"],
            ["detected_sections.id"],
            name=op.f(
                "fk_section_language_results_detected_section_id_"
                "detected_sections"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_section_language_results"),
        sa.UniqueConstraint(
            "detected_section_id",
            "language_code",
            name="uq_section_language_results_section_language",
        ),
    )
    _create_indexes(
        "section_language_results",
        (
            (
                "ix_section_language_results_detected_section_id",
                ["detected_section_id"],
            ),
            (
                "ix_section_language_results_language_code",
                ["language_code"],
            ),
            (
                "ix_section_language_results_presence_status",
                ["presence_status"],
            ),
        ),
    )

    op.create_table(
        "translation_groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("compliance_run_id", sa.Uuid(), nullable=False),
        sa.Column("container_id", sa.Uuid(), nullable=True),
        sa.Column("detected_section_id", sa.Uuid(), nullable=True),
        sa.Column("group_index", sa.Integer(), nullable=False),
        sa.Column(
            "group_type",
            _enum("translation_group_type", TRANSLATION_GROUP_TYPES),
            nullable=False,
        ),
        sa.Column("start_block_order", sa.Integer(), nullable=False),
        sa.Column("end_block_order", sa.Integer(), nullable=False),
        sa.Column(
            "source_reference",
            sa.String(length=1000),
            nullable=False,
        ),
        sa.Column("expected_languages_json", _json_type(), nullable=False),
        sa.Column("detected_languages_json", _json_type(), nullable=False),
        sa.Column("language_order_json", _json_type(), nullable=False),
        sa.Column(
            "is_complete",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_order_valid",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("confidence", sa.Numeric(6, 5), nullable=False),
        sa.Column("metrics_json", _json_type(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "group_index >= 0 AND start_block_order >= 0 "
            "AND end_block_order >= start_block_order",
            name=(
                "ck_translation_groups_"
                "translation_groups_order_range"
            ),
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name=(
                "ck_translation_groups_"
                "translation_groups_confidence_range"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["compliance_run_id"],
            ["compliance_runs.id"],
            name=(
                "fk_translation_groups_compliance_run_id_compliance_runs"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["container_id"],
            ["extracted_containers.id"],
            name=(
                "fk_translation_groups_container_id_extracted_containers"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["detected_section_id"],
            ["detected_sections.id"],
            name=(
                "fk_translation_groups_detected_section_id_"
                "detected_sections"
            ),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_translation_groups"),
        sa.UniqueConstraint(
            "compliance_run_id",
            "group_index",
            name="uq_translation_groups_run_index",
        ),
    )
    _create_indexes(
        "translation_groups",
        (
            (
                "ix_translation_groups_compliance_run_id",
                ["compliance_run_id"],
            ),
            ("ix_translation_groups_container_id", ["container_id"]),
            (
                "ix_translation_groups_detected_section_id",
                ["detected_section_id"],
            ),
            ("ix_translation_groups_group_type", ["group_type"]),
            ("ix_translation_groups_is_complete", ["is_complete"]),
            (
                "ix_translation_groups_is_order_valid",
                ["is_order_valid"],
            ),
            ("ix_translation_groups_confidence", ["confidence"]),
        ),
    )

    op.create_table(
        "translation_group_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("translation_group_id", sa.Uuid(), nullable=False),
        sa.Column("language_code", sa.String(length=20), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("extracted_block_id", sa.Uuid(), nullable=True),
        sa.Column("ocr_block_id", sa.Uuid(), nullable=True),
        sa.Column("language_block_result_id", sa.Uuid(), nullable=True),
        sa.Column("block_order", sa.Integer(), nullable=False),
        sa.Column("text_snapshot", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(6, 5), nullable=False),
        sa.Column("position_json", _json_type(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "block_order >= 0",
            name=op.f(
                "ck_translation_group_members_"
                "translation_group_members_order_nonnegative"
            ),
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name=op.f(
                "ck_translation_group_members_"
                "translation_group_members_confidence_range"
            ),
        ),
        sa.CheckConstraint(
            "extracted_block_id IS NOT NULL "
            "OR ocr_block_id IS NOT NULL "
            "OR language_block_result_id IS NOT NULL",
            name=op.f(
                "ck_translation_group_members_"
                "translation_group_members_source_required"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["translation_group_id"],
            ["translation_groups.id"],
            name=op.f(
                "fk_translation_group_members_translation_group_id_"
                "translation_groups"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["extracted_block_id"],
            ["extracted_blocks.id"],
            name=op.f(
                "fk_translation_group_members_extracted_block_id_"
                "extracted_blocks"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ocr_block_id"],
            ["ocr_blocks.id"],
            name=(
                "fk_translation_group_members_ocr_block_id_ocr_blocks"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["language_block_result_id"],
            ["language_block_results.id"],
            name=op.f(
                "fk_translation_group_members_language_block_result_id_"
                "language_block_results"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_translation_group_members"),
        sa.UniqueConstraint(
            "translation_group_id",
            "block_order",
            "language_code",
            name="uq_translation_group_members_group_order_language",
        ),
    )
    _create_indexes(
        "translation_group_members",
        (
            (
                "ix_translation_group_members_translation_group_id",
                ["translation_group_id"],
            ),
            (
                "ix_translation_group_members_extracted_block_id",
                ["extracted_block_id"],
            ),
            (
                "ix_translation_group_members_ocr_block_id",
                ["ocr_block_id"],
            ),
            (
                "ix_translation_group_members_language_block_result_id",
                ["language_block_result_id"],
            ),
            (
                "ix_translation_group_members_language_code",
                ["language_code"],
            ),
            (
                "ix_translation_group_members_block_order",
                ["block_order"],
            ),
        ),
    )


def _create_findings() -> None:
    op.create_table(
        "validation_findings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("compliance_run_id", sa.Uuid(), nullable=True),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("document_revision_id", sa.Uuid(), nullable=False),
        sa.Column("document_file_id", sa.Uuid(), nullable=False),
        sa.Column("validation_rule_id", sa.Uuid(), nullable=True),
        sa.Column(
            "finding_code",
            _enum("finding_code", FINDING_CODES),
            nullable=False,
        ),
        sa.Column(
            "finding_type",
            _enum("finding_type", FINDING_TYPES),
            nullable=False,
        ),
        sa.Column(
            "severity",
            _enum("finding_severity", FINDING_SEVERITIES),
            nullable=False,
        ),
        sa.Column(
            "status",
            _enum("finding_status", FINDING_STATUSES),
            server_default="OPEN",
            nullable=False,
        ),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("container_id", sa.Uuid(), nullable=True),
        sa.Column("detected_section_id", sa.Uuid(), nullable=True),
        sa.Column("translation_group_id", sa.Uuid(), nullable=True),
        sa.Column("extracted_block_id", sa.Uuid(), nullable=True),
        sa.Column("ocr_block_id", sa.Uuid(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("worksheet_name", sa.String(length=255), nullable=True),
        sa.Column("cell_coordinate", sa.String(length=50), nullable=True),
        sa.Column(
            "source_reference",
            sa.String(length=1000),
            nullable=True,
        ),
        sa.Column("location_json", _json_type(), nullable=False),
        sa.Column("language_code", sa.String(length=20), nullable=True),
        sa.Column("expected_value_json", _json_type(), nullable=True),
        sa.Column("actual_value_json", _json_type(), nullable=True),
        sa.Column("metrics_json", _json_type(), nullable=False),
        sa.Column(
            "is_system_generated",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "is_repeat",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("previous_finding_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("assigned_to", sa.Uuid(), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("resolved_by", sa.Uuid(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_comment", sa.Text(), nullable=True),
        sa.Column("false_positive_by", sa.Uuid(), nullable=True),
        sa.Column(
            "false_positive_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("false_positive_reason", sa.Text(), nullable=True),
        sa.Column("accepted_risk_by", sa.Uuid(), nullable=True),
        sa.Column(
            "accepted_risk_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("accepted_risk_reason", sa.Text(), nullable=True),
        sa.Column("accepted_risk_expiry_date", sa.Date(), nullable=True),
        sa.Column("reopened_by", sa.Uuid(), nullable=True),
        sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reopen_reason", sa.Text(), nullable=True),
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
            "page_number IS NULL OR page_number >= 1",
            name=(
                "ck_validation_findings_"
                "validation_findings_page_positive"
            ),
        ),
        sa.CheckConstraint(
            "NOT is_system_generated OR compliance_run_id IS NOT NULL",
            name=(
                "ck_validation_findings_"
                "validation_findings_system_run_required"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["compliance_run_id"],
            ["compliance_runs.id"],
            name=(
                "fk_validation_findings_compliance_run_id_compliance_runs"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_validation_findings_document_id_documents",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_revision_id"],
            ["document_revisions.id"],
            name=(
                "fk_validation_findings_document_revision_id_"
                "document_revisions"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_file_id"],
            ["document_files.id"],
            name=(
                "fk_validation_findings_document_file_id_document_files"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["validation_rule_id"],
            ["validation_rules.id"],
            name=(
                "fk_validation_findings_validation_rule_id_"
                "validation_rules"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["container_id"],
            ["extracted_containers.id"],
            name=(
                "fk_validation_findings_container_id_extracted_containers"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["detected_section_id"],
            ["detected_sections.id"],
            name=(
                "fk_validation_findings_detected_section_id_"
                "detected_sections"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["translation_group_id"],
            ["translation_groups.id"],
            name=(
                "fk_validation_findings_translation_group_id_"
                "translation_groups"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["extracted_block_id"],
            ["extracted_blocks.id"],
            name=(
                "fk_validation_findings_extracted_block_id_"
                "extracted_blocks"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ocr_block_id"],
            ["ocr_blocks.id"],
            name="fk_validation_findings_ocr_block_id_ocr_blocks",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["previous_finding_id"],
            ["validation_findings.id"],
            name=(
                "fk_validation_findings_previous_finding_id_"
                "validation_findings"
            ),
            ondelete="SET NULL",
        ),
        *[
            sa.ForeignKeyConstraint(
                [column],
                ["users.id"],
                name=f"fk_validation_findings_{column}_users",
                ondelete="SET NULL",
            )
            for column in (
                "created_by",
                "assigned_to",
                "reviewed_by",
                "resolved_by",
                "false_positive_by",
                "accepted_risk_by",
                "reopened_by",
            )
        ],
        sa.PrimaryKeyConstraint("id", name="pk_validation_findings"),
    )
    _create_indexes(
        "validation_findings",
        (
            (
                "ix_validation_findings_compliance_run_id",
                ["compliance_run_id"],
            ),
            ("ix_validation_findings_document_id", ["document_id"]),
            (
                "ix_validation_findings_document_revision_id",
                ["document_revision_id"],
            ),
            (
                "ix_validation_findings_document_file_id",
                ["document_file_id"],
            ),
            (
                "ix_validation_findings_validation_rule_id",
                ["validation_rule_id"],
            ),
            ("ix_validation_findings_finding_code", ["finding_code"]),
            ("ix_validation_findings_finding_type", ["finding_type"]),
            ("ix_validation_findings_severity", ["severity"]),
            ("ix_validation_findings_status", ["status"]),
            (
                "ix_validation_findings_detected_section_id",
                ["detected_section_id"],
            ),
            (
                "ix_validation_findings_translation_group_id",
                ["translation_group_id"],
            ),
            ("ix_validation_findings_assigned_to", ["assigned_to"]),
            ("ix_validation_findings_language_code", ["language_code"]),
            (
                "ix_validation_findings_is_system_generated",
                ["is_system_generated"],
            ),
            ("ix_validation_findings_is_repeat", ["is_repeat"]),
            (
                "ix_validation_findings_previous_finding_id",
                ["previous_finding_id"],
            ),
            ("ix_validation_findings_created_at", ["created_at"]),
            (
                "ix_validation_findings_document_status",
                ["document_id", "status"],
            ),
        ),
    )

    op.create_table(
        "finding_occurrences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("finding_id", sa.Uuid(), nullable=False),
        sa.Column("compliance_run_id", sa.Uuid(), nullable=False),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "source_reference",
            sa.String(length=1000),
            nullable=True,
        ),
        sa.Column("location_json", _json_type(), nullable=False),
        sa.Column("metrics_json", _json_type(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["finding_id"],
            ["validation_findings.id"],
            name=(
                "fk_finding_occurrences_finding_id_validation_findings"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["compliance_run_id"],
            ["compliance_runs.id"],
            name=(
                "fk_finding_occurrences_compliance_run_id_compliance_runs"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_finding_occurrences"),
        sa.UniqueConstraint(
            "finding_id",
            "compliance_run_id",
            "source_reference",
            name="uq_finding_occurrences_finding_run_source",
        ),
    )
    _create_indexes(
        "finding_occurrences",
        (
            ("ix_finding_occurrences_finding_id", ["finding_id"]),
            (
                "ix_finding_occurrences_compliance_run_id",
                ["compliance_run_id"],
            ),
            ("ix_finding_occurrences_detected_at", ["detected_at"]),
        ),
    )


def upgrade() -> None:
    """Upgrade a Phase 7 database without changing retained source results."""
    for action in PHASE8_AUDIT_ACTIONS:
        op.execute(
            sa.text(
                f"ALTER TYPE audit_action ADD VALUE IF NOT EXISTS '{action}'"
            )
        )
    _create_enum_types()
    _create_section_catalog()
    _enhance_validation_rules()
    _create_compliance_jobs_and_runs()
    _create_section_and_group_results()
    _create_findings()


def _drop_findings() -> None:
    _drop_indexes(
        "finding_occurrences",
        (
            "ix_finding_occurrences_detected_at",
            "ix_finding_occurrences_compliance_run_id",
            "ix_finding_occurrences_finding_id",
        ),
    )
    op.drop_table("finding_occurrences")
    _drop_indexes(
        "validation_findings",
        (
            "ix_validation_findings_document_status",
            "ix_validation_findings_created_at",
            "ix_validation_findings_previous_finding_id",
            "ix_validation_findings_is_repeat",
            "ix_validation_findings_is_system_generated",
            "ix_validation_findings_language_code",
            "ix_validation_findings_assigned_to",
            "ix_validation_findings_translation_group_id",
            "ix_validation_findings_detected_section_id",
            "ix_validation_findings_status",
            "ix_validation_findings_severity",
            "ix_validation_findings_finding_type",
            "ix_validation_findings_finding_code",
            "ix_validation_findings_validation_rule_id",
            "ix_validation_findings_document_file_id",
            "ix_validation_findings_document_revision_id",
            "ix_validation_findings_document_id",
            "ix_validation_findings_compliance_run_id",
        ),
    )
    op.drop_table("validation_findings")


def _drop_section_and_group_results() -> None:
    _drop_indexes(
        "translation_group_members",
        (
            "ix_translation_group_members_block_order",
            "ix_translation_group_members_language_code",
            "ix_translation_group_members_language_block_result_id",
            "ix_translation_group_members_ocr_block_id",
            "ix_translation_group_members_extracted_block_id",
            "ix_translation_group_members_translation_group_id",
        ),
    )
    op.drop_table("translation_group_members")
    _drop_indexes(
        "translation_groups",
        (
            "ix_translation_groups_confidence",
            "ix_translation_groups_is_order_valid",
            "ix_translation_groups_is_complete",
            "ix_translation_groups_group_type",
            "ix_translation_groups_detected_section_id",
            "ix_translation_groups_container_id",
            "ix_translation_groups_compliance_run_id",
        ),
    )
    op.drop_table("translation_groups")
    _drop_indexes(
        "section_language_results",
        (
            "ix_section_language_results_presence_status",
            "ix_section_language_results_language_code",
            "ix_section_language_results_detected_section_id",
        ),
    )
    op.drop_table("section_language_results")
    _drop_indexes(
        "detected_sections",
        (
            "ix_detected_sections_is_complete",
            "ix_detected_sections_is_required",
            "ix_detected_sections_heading_block_id",
            "ix_detected_sections_container_id",
            "ix_detected_sections_canonical_code",
            "ix_detected_sections_section_definition_id",
            "ix_detected_sections_compliance_run_id",
        ),
    )
    op.drop_table("detected_sections")


def _drop_compliance_jobs_and_runs() -> None:
    op.drop_index(
        "ix_document_files_latest_compliance_run_id",
        table_name="document_files",
    )
    op.drop_constraint(
        "fk_document_files_latest_compliance_run_id_compliance_runs",
        "document_files",
        type_="foreignkey",
    )
    op.drop_column("document_files", "latest_compliance_run_id")
    _drop_indexes(
        "compliance_runs",
        (
            "ix_compliance_runs_file_created",
            "ix_compliance_runs_created_at",
            "ix_compliance_runs_source_content_hash",
            "ix_compliance_runs_compliance_score",
            "ix_compliance_runs_compliance_status",
            "ix_compliance_runs_status",
            "ix_compliance_runs_validation_rule_id",
            "ix_compliance_runs_language_detection_run_id",
            "ix_compliance_runs_ocr_run_id",
            "ix_compliance_runs_extraction_run_id",
            "ix_compliance_runs_document_file_id",
            "ix_compliance_runs_document_revision_id",
            "ix_compliance_runs_document_id",
        ),
    )
    op.drop_table("compliance_runs")
    op.drop_index(
        "uq_compliance_jobs_active_source",
        table_name="compliance_jobs",
    )
    _drop_indexes(
        "compliance_jobs",
        (
            "ix_compliance_jobs_source_content_hash",
            "ix_compliance_jobs_requested_at",
            "ix_compliance_jobs_requested_by",
            "ix_compliance_jobs_status",
            "ix_compliance_jobs_validation_rule_id",
            "ix_compliance_jobs_language_detection_run_id",
            "ix_compliance_jobs_ocr_run_id",
            "ix_compliance_jobs_extraction_run_id",
            "ix_compliance_jobs_document_file_id",
            "ix_compliance_jobs_document_revision_id",
            "ix_compliance_jobs_document_id",
        ),
    )
    op.drop_table("compliance_jobs")


def _downgrade_validation_rules() -> None:
    for name in (
        "validation_rules_phase8_score_order",
        "validation_rules_phase8_score_range",
        "validation_rules_penalty_range",
        "validation_rules_weight_total",
        "validation_rules_weights_nonnegative",
        "validation_rules_mixed_percentage",
        "validation_rules_unknown_percentage",
    ):
        op.drop_constraint(
            op.f(f"ck_validation_rules_{name}"),
            "validation_rules",
            type_="check",
        )
    op.drop_index(
        "ix_validation_rules_section_alias_profile_id",
        table_name="validation_rules",
    )
    op.drop_constraint(
        op.f(
            "fk_validation_rules_section_alias_profile_id_"
            "section_alias_profiles"
        ),
        "validation_rules",
        type_="foreignkey",
    )
    for column_name in (
        "section_alias_profile_id",
        "validation_options_json",
        "fail_on_critical_finding",
        "fail_on_missing_required_section",
        "fail_on_missing_required_language",
        "needs_review_score",
        "partially_compliant_score",
        "compliant_score",
        "minor_finding_penalty",
        "major_finding_penalty",
        "critical_finding_score_cap",
        "table_completeness_weight",
        "translation_group_weight",
        "language_order_weight",
        "section_completeness_weight",
        "language_coverage_weight",
        "language_presence_weight",
        "document_code_weight",
        "maximum_mixed_block_percentage",
        "maximum_unknown_block_percentage",
        "minimum_language_character_coverage_json",
        "minimum_language_block_coverage_json",
        "required_languages_json",
        "validate_cells",
        "validate_translation_groups",
        "validate_container_completeness",
        "validate_language_coverage",
        "validate_language_presence",
        "validate_document_code",
    ):
        op.drop_column("validation_rules", column_name)


def _drop_section_catalog() -> None:
    _drop_indexes(
        "section_aliases",
        (
            "ix_section_aliases_is_active",
            "ix_section_aliases_priority",
            "ix_section_aliases_match_type",
            "ix_section_aliases_normalised_alias",
            "ix_section_aliases_language_code",
            "ix_section_aliases_section_definition_id",
        ),
    )
    op.drop_table("section_aliases")
    _drop_indexes(
        "section_definitions",
        (
            "ix_section_definitions_is_active",
            "ix_section_definitions_display_order",
            "ix_section_definitions_canonical_code",
            "ix_section_definitions_profile_id",
        ),
    )
    op.drop_table("section_definitions")
    op.drop_index(
        "uq_section_alias_profiles_single_default",
        table_name="section_alias_profiles",
    )
    _drop_indexes(
        "section_alias_profiles",
        (
            "ix_section_alias_profiles_is_active",
            "ix_section_alias_profiles_name",
            "ix_section_alias_profiles_code",
        ),
    )
    op.drop_table("section_alias_profiles")


def downgrade() -> None:
    """Remove only Phase 8 data and restore the Phase 7 schema."""
    _drop_findings()
    _drop_section_and_group_results()
    _drop_compliance_jobs_and_runs()
    _downgrade_validation_rules()
    _drop_section_catalog()
    bind = op.get_bind()
    for name, values in reversed(ENUM_DEFINITIONS):
        postgresql.ENUM(*values, name=name).drop(bind, checkfirst=True)
    # PostgreSQL audit enum labels remain append-only by design.
