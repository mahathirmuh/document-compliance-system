"""Phase 3/Phase 8 validation-rule mirror compatibility regressions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.authorization import UserRole
from app.models.validation_rule import ValidationRule
from app.schemas.validation_rule import ValidationRuleValues
from app.services.auth.token_service import TokenService

TestSessionFactory = async_sessionmaker[AsyncSession]
UserFactory = Callable[..., Any]


def _stored_values() -> dict[str, object]:
    return {
        "name": "Compatibility rule",
        "code": "COMPAT",
        "required_indonesian": True,
        "required_english": True,
        "required_chinese": True,
        "required_languages": ["id", "en", "zh"],
        "minimum_indonesian_coverage": 95,
        "minimum_english_coverage": 95,
        "minimum_chinese_coverage": 95,
        "minimum_language_block_coverage": {
            "id": 95,
            "en": 95,
            "zh": 95,
        },
        "minimum_language_character_coverage": {
            "id": 95,
            "en": 95,
            "zh": 95,
        },
        "minimum_compliance_score": 95,
        "compliant_score": 95,
        "partial_compliance_score": 70,
        "partially_compliant_score": 70,
    }


def _validate_update(
    changes: dict[str, object],
) -> ValidationRuleValues:
    return ValidationRuleValues.model_validate(
        {**_stored_values(), **changes},
        context={
            "validation_rule_explicit_fields": frozenset(changes),
        },
    )


def test_legacy_update_fields_are_authoritative_for_phase8_mirrors() -> None:
    values = _validate_update(
        {
            "required_chinese": False,
            "minimum_chinese_coverage": 40,
            "minimum_compliance_score": 90,
        }
    )

    assert values.required_languages == ["id", "en"]
    assert values.minimum_language_block_coverage == {
        "id": 95,
        "en": 95,
        "zh": 40,
    }
    assert values.minimum_language_character_coverage == {
        "id": 95,
        "en": 95,
        "zh": 40,
    }
    assert values.compliant_score == 90


def test_advanced_update_fields_sync_phase3_mirrors() -> None:
    values = _validate_update(
        {
            "required_languages": ["en", "zh"],
            "minimum_language_block_coverage": {
                "id": 11,
                "en": 22,
                "zh": 33,
            },
            "minimum_language_character_coverage": {
                "id": 12,
                "en": 23,
                "zh": 34,
            },
            "compliant_score": 92,
            "partially_compliant_score": 71,
        }
    )

    assert (
        values.required_indonesian,
        values.required_english,
        values.required_chinese,
    ) == (False, True, True)
    # Block coverage is the deterministic legacy mirror if both advanced
    # coverage dimensions are supplied.
    assert (
        values.minimum_indonesian_coverage,
        values.minimum_english_coverage,
        values.minimum_chinese_coverage,
    ) == (11, 22, 33)
    assert values.minimum_compliance_score == 92
    assert values.partial_compliance_score == 71


def test_character_only_advanced_update_syncs_legacy_coverage() -> None:
    values = _validate_update(
        {
            "minimum_language_character_coverage": {
                "id": 14,
                "en": 24,
                "zh": 34,
            }
        }
    )

    assert (
        values.minimum_indonesian_coverage,
        values.minimum_english_coverage,
        values.minimum_chinese_coverage,
    ) == (14, 24, 34)
    assert values.minimum_language_block_coverage == {
        "id": 95,
        "en": 95,
        "zh": 95,
    }


def test_unrelated_update_preserves_both_sides_without_resynchronizing() -> None:
    stored = _stored_values()
    stored.update(
        {
            "required_chinese": True,
            "required_languages": ["id", "en"],
            "minimum_chinese_coverage": 77,
            "minimum_language_block_coverage": {
                "id": 95,
                "en": 95,
                "zh": 33,
            },
            "minimum_language_character_coverage": {
                "id": 95,
                "en": 95,
                "zh": 34,
            },
            "minimum_compliance_score": 88,
            "compliant_score": 92,
            "description": "Updated only",
        }
    )

    values = ValidationRuleValues.model_validate(
        stored,
        context={
            "validation_rule_explicit_fields": {"description"},
        },
    )

    assert values.required_chinese is True
    assert values.required_languages == ["id", "en"]
    assert values.minimum_chinese_coverage == 77
    assert values.minimum_language_block_coverage["zh"] == 33
    assert values.minimum_language_character_coverage["zh"] == 34
    assert values.minimum_compliance_score == 88
    assert values.compliant_score == 92


async def _admin_headers(
    create_user: UserFactory,
    token_service: TokenService,
) -> dict[str, str]:
    user = await create_user(
        email="rule-compat-admin@example.com",
        role=UserRole.SUPER_ADMIN,
        is_superuser=True,
    )
    return {
        "Authorization": f"Bearer {token_service.create_access_token(user)}"
    }


def _frontend_payload(*, code: str) -> dict[str, object]:
    return {
        "code": code,
        "name": "Frontend compatibility rule",
        "description": None,
        "documentTypeId": None,
        "requiredIndonesian": True,
        "requiredEnglish": True,
        "requiredChinese": True,
        "minimumIndonesianCoverage": 95,
        "minimumEnglishCoverage": 95,
        "minimumChineseCoverage": 95,
        "validateLanguageOrder": True,
        "languageOrder": ["id", "en", "zh"],
        "validateSections": True,
        "requiredSections": ["TITLE", "PURPOSE"],
        "validateTables": False,
        "minimumComplianceScore": 95,
        "partialComplianceScore": 70,
        "isDefault": False,
        "isActive": True,
    }


@pytest.mark.asyncio
async def test_frontend_shape_and_advanced_api_updates_stay_in_sync(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
) -> None:
    headers = await _admin_headers(create_user, token_service)
    frontend_payload = _frontend_payload(code="FRONT-COMPAT")
    created = await api_client.post(
        "/api/v1/master-data/validation-rules",
        headers=headers,
        json=frontend_payload,
    )
    assert created.status_code == 201, created.text
    rule_id = created.json()["data"]["id"]

    legacy_updated = await api_client.put(
        f"/api/v1/master-data/validation-rules/{rule_id}",
        headers=headers,
        json={
            **frontend_payload,
            "requiredChinese": False,
            "minimumChineseCoverage": 40,
            "minimumComplianceScore": 90,
        },
    )
    assert legacy_updated.status_code == 200, legacy_updated.text
    legacy = legacy_updated.json()["data"]
    assert legacy["requiredChinese"] is False
    assert legacy["requiredLanguages"] == ["id", "en"]
    assert legacy["minimumChineseCoverage"] == 40
    assert legacy["minimumLanguageBlockCoverage"]["zh"] == 40
    assert legacy["minimumLanguageCharacterCoverage"]["zh"] == 40
    assert legacy["minimumComplianceScore"] == 90
    assert legacy["compliantScore"] == 90

    advanced_updated = await api_client.put(
        f"/api/v1/master-data/validation-rules/{rule_id}",
        headers=headers,
        json={
            "requiredLanguages": ["en", "zh"],
            "minimumLanguageBlockCoverage": {
                "id": 11,
                "en": 22,
                "zh": 33,
            },
            "minimumLanguageCharacterCoverage": {
                "id": 12,
                "en": 23,
                "zh": 34,
            },
            "compliantScore": 92,
            "partiallyCompliantScore": 71,
        },
    )
    assert advanced_updated.status_code == 200, advanced_updated.text
    advanced = advanced_updated.json()["data"]
    assert (
        advanced["requiredIndonesian"],
        advanced["requiredEnglish"],
        advanced["requiredChinese"],
    ) == (False, True, True)
    assert advanced["requiredLanguages"] == ["en", "zh"]
    assert (
        advanced["minimumIndonesianCoverage"],
        advanced["minimumEnglishCoverage"],
        advanced["minimumChineseCoverage"],
    ) == (11, 22, 33)
    assert advanced["minimumLanguageBlockCoverage"] == {
        "id": 11,
        "en": 22,
        "zh": 33,
    }
    assert advanced["minimumLanguageCharacterCoverage"] == {
        "id": 12,
        "en": 23,
        "zh": 34,
    }
    assert advanced["minimumComplianceScore"] == 92
    assert advanced["partialComplianceScore"] == 71


@pytest.mark.asyncio
async def test_unrelated_api_update_does_not_rewrite_stored_mirrors(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
    session_factory: TestSessionFactory,
) -> None:
    headers = await _admin_headers(create_user, token_service)
    created = await api_client.post(
        "/api/v1/master-data/validation-rules",
        headers=headers,
        json=_frontend_payload(code="UNRELATED"),
    )
    assert created.status_code == 201, created.text
    rule_id = UUID(created.json()["data"]["id"])

    async with session_factory() as session:
        entity = await session.get(ValidationRule, rule_id)
        assert entity is not None
        entity.required_chinese = True
        entity.required_languages_json = ["id", "en"]
        entity.minimum_chinese_coverage = 77
        entity.minimum_language_block_coverage_json = {
            "id": 95,
            "en": 95,
            "zh": 33,
        }
        entity.minimum_language_character_coverage_json = {
            "id": 95,
            "en": 95,
            "zh": 34,
        }
        entity.minimum_compliance_score = 88
        entity.compliant_score = 92
        await session.commit()

    updated = await api_client.put(
        f"/api/v1/master-data/validation-rules/{rule_id}",
        headers=headers,
        json={"description": "Only this field changed."},
    )
    assert updated.status_code == 200, updated.text
    returned = updated.json()["data"]
    assert returned["requiredChinese"] is True
    assert returned["requiredLanguages"] == ["id", "en"]
    assert returned["minimumChineseCoverage"] == 77
    assert returned["minimumLanguageBlockCoverage"]["zh"] == 33
    assert returned["minimumLanguageCharacterCoverage"]["zh"] == 34
    assert returned["minimumComplianceScore"] == 88
    assert returned["compliantScore"] == 92

    async with session_factory() as session:
        entity = await session.get(ValidationRule, rule_id)
        assert entity is not None
        assert entity.description == "Only this field changed."
        assert entity.required_chinese is True
        assert entity.required_languages_json == ["id", "en"]
        assert entity.minimum_chinese_coverage == 77
        assert entity.minimum_language_block_coverage_json["zh"] == 33
        assert entity.minimum_language_character_coverage_json["zh"] == 34
        assert entity.minimum_compliance_score == 88
        assert float(entity.compliant_score) == 92
