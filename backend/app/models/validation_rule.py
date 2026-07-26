"""Multilingual validation-rule master-data persistence model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.document_revision import DocumentRevision
    from app.models.document_type import DocumentType
    from app.models.section_alias_profile import SectionAliasProfile
    from app.models.user import User


DEFAULT_LANGUAGE_ORDER = ["id", "en", "zh"]
DEFAULT_REQUIRED_LANGUAGES = ["id", "en", "zh"]
DEFAULT_REQUIRED_SECTIONS = [
    "TITLE",
    "PURPOSE",
    "SCOPE",
    "RESPONSIBILITY",
    "PROCEDURE",
    "RECORDS",
    "REFERENCE",
]
ALLOWED_SECTION_CODES = frozenset(
    {
        "TITLE",
        "PURPOSE",
        "SCOPE",
        "DEFINITION",
        "RESPONSIBILITY",
        "PROCEDURE",
        "RECORDS",
        "REFERENCE",
        "ATTACHMENT",
        "REVISION_HISTORY",
        "APPROVAL",
        "DISTRIBUTION",
    }
)
DEFAULT_LANGUAGE_BLOCK_COVERAGE = {"id": 95, "en": 95, "zh": 95}
DEFAULT_LANGUAGE_CHARACTER_COVERAGE = {"id": 95, "en": 95, "zh": 95}


class ValidationRule(Base):
    """Configuration for future document-language validation."""

    __tablename__ = "validation_rules"
    __table_args__ = (
        UniqueConstraint("code", name="uq_validation_rules_code"),
        CheckConstraint(
            "minimum_indonesian_coverage BETWEEN 0 AND 100",
            name="validation_rules_indonesian_coverage",
        ),
        CheckConstraint(
            "minimum_english_coverage BETWEEN 0 AND 100",
            name="validation_rules_english_coverage",
        ),
        CheckConstraint(
            "minimum_chinese_coverage BETWEEN 0 AND 100",
            name="validation_rules_chinese_coverage",
        ),
        CheckConstraint(
            "minimum_compliance_score BETWEEN 0 AND 100",
            name="validation_rules_minimum_score",
        ),
        CheckConstraint(
            "partial_compliance_score BETWEEN 0 AND 100",
            name="validation_rules_partial_score",
        ),
        CheckConstraint(
            "partial_compliance_score <= minimum_compliance_score",
            name="validation_rules_score_order",
        ),
        CheckConstraint(
            "required_indonesian OR required_english OR required_chinese",
            name="validation_rules_language_required",
        ),
        CheckConstraint(
            "maximum_unknown_block_percentage BETWEEN 0 AND 100",
            name="validation_rules_unknown_percentage",
        ),
        CheckConstraint(
            "maximum_mixed_block_percentage BETWEEN 0 AND 100",
            name="validation_rules_mixed_percentage",
        ),
        CheckConstraint(
            "document_code_weight >= 0 "
            "AND language_presence_weight >= 0 "
            "AND language_coverage_weight >= 0 "
            "AND section_completeness_weight >= 0 "
            "AND language_order_weight >= 0 "
            "AND translation_group_weight >= 0 "
            "AND table_completeness_weight >= 0",
            name="validation_rules_weights_nonnegative",
        ),
        CheckConstraint(
            "document_code_weight + language_presence_weight "
            "+ language_coverage_weight + section_completeness_weight "
            "+ language_order_weight + translation_group_weight "
            "+ table_completeness_weight = 100",
            name="validation_rules_weight_total",
        ),
        CheckConstraint(
            "critical_finding_score_cap BETWEEN 0 AND 100 "
            "AND major_finding_penalty >= 0 "
            "AND minor_finding_penalty >= 0",
            name="validation_rules_penalty_range",
        ),
        CheckConstraint(
            "compliant_score BETWEEN 0 AND 100 "
            "AND partially_compliant_score BETWEEN 0 AND 100 "
            "AND needs_review_score BETWEEN 0 AND 100",
            name="validation_rules_phase8_score_range",
        ),
        CheckConstraint(
            "needs_review_score <= partially_compliant_score "
            "AND partially_compliant_score <= compliant_score",
            name="validation_rules_phase8_score_order",
        ),
        Index("ix_validation_rules_code", "code"),
        Index("ix_validation_rules_name", "name"),
        Index("ix_validation_rules_document_type_id", "document_type_id"),
        Index(
            "ix_validation_rules_section_alias_profile_id",
            "section_alias_profile_id",
        ),
        Index("ix_validation_rules_is_active", "is_active"),
        Index(
            "uq_validation_rules_global_default",
            "is_default",
            unique=True,
            postgresql_where=text(
                "is_default IS TRUE AND document_type_id IS NULL "
                "AND deleted_at IS NULL"
            ),
            sqlite_where=text(
                "is_default = 1 AND document_type_id IS NULL "
                "AND deleted_at IS NULL"
            ),
        ),
        Index(
            "uq_validation_rules_document_type_default",
            "document_type_id",
            unique=True,
            postgresql_where=text(
                "is_default IS TRUE AND document_type_id IS NOT NULL "
                "AND deleted_at IS NULL"
            ),
            sqlite_where=text(
                "is_default = 1 AND document_type_id IS NOT NULL "
                "AND deleted_at IS NULL"
            ),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_type_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_types.id", ondelete="RESTRICT"),
        nullable=True,
    )
    required_indonesian: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    required_english: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    required_chinese: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    validate_document_code: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    validate_language_presence: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    validate_language_coverage: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    validate_container_completeness: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    minimum_indonesian_coverage: Mapped[int] = mapped_column(
        Integer, nullable=False, default=95, server_default="95"
    )
    minimum_english_coverage: Mapped[int] = mapped_column(
        Integer, nullable=False, default=95, server_default="95"
    )
    minimum_chinese_coverage: Mapped[int] = mapped_column(
        Integer, nullable=False, default=95, server_default="95"
    )
    validate_language_order: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    language_order_json: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=lambda: list(DEFAULT_LANGUAGE_ORDER),
    )
    validate_sections: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    validate_translation_groups: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    required_sections_json: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=lambda: list(DEFAULT_REQUIRED_SECTIONS),
    )
    validate_tables: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    validate_cells: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    required_languages_json: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=lambda: list(DEFAULT_REQUIRED_LANGUAGES),
    )
    section_alias_profile_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("section_alias_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    minimum_language_block_coverage_json: Mapped[dict[str, float]] = (
        mapped_column(
            JSON().with_variant(JSONB, "postgresql"),
            nullable=False,
            default=lambda: dict(DEFAULT_LANGUAGE_BLOCK_COVERAGE),
        )
    )
    minimum_language_character_coverage_json: Mapped[dict[str, float]] = (
        mapped_column(
            JSON().with_variant(JSONB, "postgresql"),
            nullable=False,
            default=lambda: dict(DEFAULT_LANGUAGE_CHARACTER_COVERAGE),
        )
    )
    maximum_unknown_block_percentage: Mapped[float] = mapped_column(
        Numeric(6, 2), nullable=False, default=10, server_default="10"
    )
    maximum_mixed_block_percentage: Mapped[float] = mapped_column(
        Numeric(6, 2), nullable=False, default=20, server_default="20"
    )
    document_code_weight: Mapped[float] = mapped_column(
        Numeric(6, 2), nullable=False, default=10, server_default="10"
    )
    language_presence_weight: Mapped[float] = mapped_column(
        Numeric(6, 2), nullable=False, default=25, server_default="25"
    )
    language_coverage_weight: Mapped[float] = mapped_column(
        Numeric(6, 2), nullable=False, default=15, server_default="15"
    )
    section_completeness_weight: Mapped[float] = mapped_column(
        Numeric(6, 2), nullable=False, default=20, server_default="20"
    )
    language_order_weight: Mapped[float] = mapped_column(
        Numeric(6, 2), nullable=False, default=10, server_default="10"
    )
    translation_group_weight: Mapped[float] = mapped_column(
        Numeric(6, 2), nullable=False, default=15, server_default="15"
    )
    table_completeness_weight: Mapped[float] = mapped_column(
        Numeric(6, 2), nullable=False, default=5, server_default="5"
    )
    critical_finding_score_cap: Mapped[float] = mapped_column(
        Numeric(6, 2), nullable=False, default=69, server_default="69"
    )
    major_finding_penalty: Mapped[float] = mapped_column(
        Numeric(6, 2), nullable=False, default=5, server_default="5"
    )
    minor_finding_penalty: Mapped[float] = mapped_column(
        Numeric(6, 2), nullable=False, default=1, server_default="1"
    )
    compliant_score: Mapped[float] = mapped_column(
        Numeric(6, 2), nullable=False, default=95, server_default="95"
    )
    partially_compliant_score: Mapped[float] = mapped_column(
        Numeric(6, 2), nullable=False, default=70, server_default="70"
    )
    needs_review_score: Mapped[float] = mapped_column(
        Numeric(6, 2), nullable=False, default=50, server_default="50"
    )
    fail_on_missing_required_language: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    fail_on_missing_required_section: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    fail_on_critical_finding: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    validation_options_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    minimum_compliance_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=95, server_default="95"
    )
    partial_compliance_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=70, server_default="70"
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    document_type: Mapped[DocumentType | None] = relationship(
        back_populates="validation_rules",
        foreign_keys=[document_type_id],
    )
    section_alias_profile: Mapped[SectionAliasProfile | None] = relationship(
        back_populates="validation_rules",
        foreign_keys=[section_alias_profile_id],
    )
    creator: Mapped[User | None] = relationship(foreign_keys=[created_by])
    updater: Mapped[User | None] = relationship(foreign_keys=[updated_by])
    document_revisions: Mapped[list[DocumentRevision]] = relationship(
        back_populates="validation_rule",
        foreign_keys="DocumentRevision.validation_rule_id",
        passive_deletes=True,
    )

    @validates("code")
    def normalize_code(self, _: str, value: str) -> str:
        return value.strip().upper()

    @validates("name")
    def normalize_name(self, _: str, value: str) -> str:
        return value.strip()

    @validates(
        "language_order_json",
        "required_sections_json",
        "required_languages_json",
    )
    def copy_json_list(self, _: str, value: list[str]) -> list[str]:
        return list(value)

    @validates(
        "minimum_language_block_coverage_json",
        "minimum_language_character_coverage_json",
        "validation_options_json",
    )
    def copy_json_dict(
        self,
        _: str,
        value: dict[str, Any],
    ) -> dict[str, Any]:
        return dict(value)

    def audit_values(self) -> dict[str, Any]:
        """Return JSON-safe values used by master-data audit events."""
        return {
            "id": str(self.id),
            "code": self.code,
            "name": self.name,
            "documentTypeId": (
                str(self.document_type_id)
                if self.document_type_id is not None
                else None
            ),
            "sectionAliasProfileId": (
                str(self.section_alias_profile_id)
                if self.section_alias_profile_id is not None
                else None
            ),
            "isDefault": self.is_default,
            "isActive": self.is_active,
        }
