"""Focused coverage for the Phase 8 compliance data foundation."""

from __future__ import annotations

from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import configure_mappers

from app.core.authorization import UserRole
from app.core.config import get_settings
from app.database.base import Base
from app.models.compliance_enums import SectionAliasLanguageCode
from app.models.section_alias import (
    SectionAlias,
    normalise_section_heading,
)
from app.models.section_alias_profile import SectionAliasProfile
from app.models.section_definition import SectionDefinition
from app.models.user import User
from app.schemas.compliance_internal import FindingDraft as StoredFindingDraft
from app.schemas.section_detection import SectionMatchTestRequest
from app.schemas.validation_rule import ValidationRuleCreate
from app.services.auth.auth_service import RequestMetadata
from app.services.compliance.contracts import FindingDraft as EngineFindingDraft
from app.services.compliance.sections.section_alias_service import (
    SectionAliasService as RuntimeSectionAliasService,
)
from app.services.master_data.section_alias_service import (
    SectionAliasService,
    validate_safe_regex,
)
from scripts.seed_section_definitions import seed_section_definitions

TestSessionFactory = async_sessionmaker[AsyncSession]


def test_engine_finding_section_code_maps_to_persistence_contract() -> None:
    engine_finding = EngineFindingDraft(
        finding_code="MISSING_REQUIRED_SECTION",
        finding_type="SECTION",
        severity="MAJOR",
        title="Missing section",
        description="The required section was not found.",
        recommendation="Add the required section.",
        section_code="PURPOSE",
    )

    stored_finding = StoredFindingDraft.model_validate(engine_finding)

    assert stored_finding.detected_section_code == "PURPOSE"


def test_phase8_models_are_mapped_with_required_foreign_keys() -> None:
    configure_mappers()
    expected_tables = {
        "compliance_jobs",
        "compliance_runs",
        "detected_sections",
        "finding_occurrences",
        "section_alias_profiles",
        "section_aliases",
        "section_definitions",
        "section_language_results",
        "translation_group_members",
        "translation_groups",
        "validation_findings",
    }
    assert expected_tables <= set(Base.metadata.tables)

    document_files = Base.metadata.tables["document_files"]
    validation_rules = Base.metadata.tables["validation_rules"]
    assert {
        foreign_key.target_fullname
        for foreign_key in document_files.c.latest_compliance_run_id.foreign_keys
    } == {"compliance_runs.id"}
    assert {
        foreign_key.target_fullname
        for foreign_key in validation_rules.c.section_alias_profile_id.foreign_keys
    } == {"section_alias_profiles.id"}


def test_validation_rule_legacy_fields_populate_phase8_fields() -> None:
    rule = ValidationRuleCreate(
        name="Legacy-compatible rule",
        code="LEGACY8",
        required_indonesian=True,
        required_english=False,
        required_chinese=True,
        minimum_indonesian_coverage=91,
        minimum_english_coverage=82,
        minimum_chinese_coverage=73,
        minimum_compliance_score=90,
        partial_compliance_score=65,
    )

    assert rule.required_languages == ["id", "zh"]
    assert rule.minimum_language_block_coverage == {
        "id": 91,
        "en": 82,
        "zh": 73,
    }
    assert rule.minimum_language_character_coverage == {
        "id": 91,
        "en": 82,
        "zh": 73,
    }
    assert rule.compliant_score == 90
    assert rule.partially_compliant_score == 65


def test_phase8_migration_precedes_the_phase9_single_head() -> None:
    config = Config("alembic.ini")
    scripts = ScriptDirectory.from_config(config)
    phase8_revision = scripts.get_revision("20260726_0008")
    phase9_revision = scripts.get_revision("20260726_0009")

    assert scripts.get_current_head() == "20260726_0009"
    assert phase8_revision is not None
    assert phase8_revision.down_revision == "20260725_0007"
    assert phase9_revision is not None
    assert phase9_revision.down_revision == "20260726_0008"


def test_heading_normalization_and_regex_guardrails() -> None:
    settings = get_settings()

    assert normalise_section_heading("  2. PURPOSE:  ") == "purpose"
    assert (
        normalise_section_heading("III. \u6807\u9898\uff1a")
        == "\u6807\u9898"
    )
    validate_safe_regex(
        r"^\s*\d+\.\s*Purpose\s*:?\s*$",
        settings,
    )

    for unsafe_pattern in (
        r"(a+)+$",
        r"^(a)\1$",
        r"(?=Purpose)Purpose",
        "x" * (settings.section_alias_regex_max_length + 1),
    ):
        with pytest.raises(ValueError):
            validate_safe_regex(unsafe_pattern, settings)


def test_runtime_section_regex_enforces_execution_timeout() -> None:
    service = RuntimeSectionAliasService(regex_timeout_ms=1)
    pattern = service.validate_regex(r"(a|aa)+$")

    assert service.regex_matches(pattern, ("a" * 200) + "!") is False


@pytest.mark.asyncio
async def test_section_seed_is_idempotent_and_multilingual(
    session_factory: TestSessionFactory,
) -> None:
    async with session_factory() as session:
        first = await seed_section_definitions(session)
        second = await seed_section_definitions(session)

        assert first == {
            "profiles": 1,
            "definitions": 12,
            "aliases": 46,
            "rulesLinked": 0,
        }
        assert second == {
            "profiles": 0,
            "definitions": 0,
            "aliases": 0,
            "rulesLinked": 0,
        }
        assert await session.scalar(
            select(func.count()).select_from(SectionAliasProfile)
        ) == 1
        assert await session.scalar(
            select(func.count()).select_from(SectionDefinition)
        ) == 12
        assert await session.scalar(
            select(func.count()).select_from(SectionAlias)
        ) == 46
        assert (
            await session.scalar(
                select(SectionAlias.id).where(
                    SectionAlias.language_code
                    == SectionAliasLanguageCode.CHINESE,
                    SectionAlias.alias_text == "\u6807\u9898",
                )
            )
            is not None
        )


@pytest.mark.asyncio
async def test_seeded_alias_matcher_handles_numbering_and_language_filter(
    session_factory: TestSessionFactory,
) -> None:
    async with session_factory() as session:
        await seed_section_definitions(session)
        user = User(
            id=uuid4(),
            name="Configuration Admin",
            email="section-admin@example.com",
            password_hash="not-used",
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            is_superuser=True,
            failed_login_attempts=0,
        )
        service = SectionAliasService(
            session,
            user,
            RequestMetadata(ip_address=None, user_agent=None),
        )

        english = await service.test_match(
            SectionMatchTestRequest(
                heading="2. PURPOSE:",
                language_code=SectionAliasLanguageCode.ENGLISH,
            )
        )
        chinese = await service.test_match(
            SectionMatchTestRequest(
                heading="\u4e09\u3001\u6807\u9898\uff1a",
                language_code=SectionAliasLanguageCode.CHINESE,
            )
        )
        wrong_language = await service.test_match(
            SectionMatchTestRequest(
                heading="Tujuan",
                language_code=SectionAliasLanguageCode.ENGLISH,
            )
        )

        assert english.matched is True
        assert english.canonical_code == "PURPOSE"
        assert english.confidence == 1
        assert chinese.matched is True
        assert chinese.canonical_code == "TITLE"
        assert wrong_language.matched is False
