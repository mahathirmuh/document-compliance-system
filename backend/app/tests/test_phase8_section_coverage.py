"""Required-section coverage thresholds from Phase 8 section 33."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from app.core.authorization import UserRole
from app.schemas.compliance_internal import (
    ComplianceBlockData,
    ComplianceValidationContext,
    DetectedSectionData,
    ValidationRuleSnapshot,
)
from app.schemas.validation_rule import ValidationRuleCreate
from app.services.auth.token_service import TokenService
from app.services.compliance.compliance_context_service import (
    ComplianceContextService,
)
from app.services.compliance.validators.required_section_validator import (
    RequiredSectionValidator,
)


def _rule(
    *, validation_options: dict[str, object] | None = None
) -> ValidationRuleSnapshot:
    return ValidationRuleSnapshot(
        rule_code="SECTION-COVERAGE",
        validate_sections=True,
        required_languages=["id", "en", "zh"],
        required_sections=["PURPOSE"],
        validation_options=validation_options or {},
    )


def _context(rule: ValidationRuleSnapshot) -> ComplianceValidationContext:
    container_id = uuid4()
    blocks = [
        ComplianceBlockData(
            id=uuid4(),
            container_id=container_id,
            container_type="DOCX_BODY",
            container_name="Body",
            container_index=1,
            block_order=index,
            block_type="PARAGRAPH",
            source_reference=f"DOCX:paragraph={index}",
            text=language + ("x" * 18),
            normalised_text=language + ("x" * 18),
            language_code=language,
            language_confidence=0.95,
            character_count=20,
        )
        for index, language in enumerate(("id", "en", "zh"), start=1)
    ]
    section = DetectedSectionData(
        canonical_code="PURPOSE",
        container_id=container_id,
        heading_text="Tujuan / Purpose / \u76ee\u7684",
        heading_language_code="mixed",
        match_type="EXACT",
        match_confidence=0.99,
        section_order=1,
        start_block_order=1,
        end_block_order=3,
        source_reference="DOCX:paragraph=0",
        is_required=True,
        is_complete=True,
    )
    return ComplianceValidationContext(
        source_format="DOCX",
        blocks=blocks,
        detected_sections=[section],
        rule=rule,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("chinese_threshold", "expected_severity"),
    [(40.0, "MINOR"), (100.0, "MAJOR")],
)
async def test_required_section_coverage_is_tri_language_and_severity_aware(
    chinese_threshold: float,
    expected_severity: str,
) -> None:
    thresholds = {
        "PURPOSE": {
            "id": 30,
            "en": 30,
            "zh": chinese_threshold,
        }
    }
    result = await RequiredSectionValidator().validate(
        _context(
            _rule(
                validation_options={
                    "validateSectionCoverage": True,
                    "sectionCoverageEvaluationMode": "BOTH_REQUIRED",
                    "minimumSectionLanguageBlockCoverage": thresholds,
                    "minimumSectionLanguageCharacterCoverage": thresholds,
                }
            )
        )
    )

    assert result.score == 0
    assert result.metrics["completeSections"] == 0
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.finding_code == "MISSING_SECTION_CHINESE"
    assert finding.finding_type == "SECTION_LANGUAGE_MISSING"
    assert finding.severity == expected_severity
    assert finding.language_code == "zh"
    assert finding.actual_value == {
        "presenceStatus": "PRESENT",
        "coverageStatus": "BELOW_THRESHOLD",
        "blockCoverage": 33.3333,
        "characterCoverage": 33.3333,
    }
    section = result.metrics["sections"][0]
    assert section["missingLanguages"] == []
    assert section["coverageBelowThresholdLanguages"] == ["zh"]
    assert section["languageCoverage"]["id"]["coveragePassed"] is True
    assert section["languageCoverage"]["en"]["coveragePassed"] is True
    assert section["languageCoverage"]["zh"]["coveragePassed"] is False


@pytest.mark.asyncio
async def test_required_section_coverage_is_optional_and_legacy_safe() -> None:
    strict_thresholds = {"PURPOSE": {"id": 100, "en": 100, "zh": 100}}
    disabled = await RequiredSectionValidator().validate(
        _context(
            _rule(
                validation_options={
                    "validateSectionCoverage": False,
                    "minimumSectionLanguageBlockCoverage": strict_thresholds,
                    "minimumSectionLanguageCharacterCoverage": (strict_thresholds),
                }
            )
        )
    )
    legacy = await RequiredSectionValidator().validate(_context(_rule()))

    for result in (disabled, legacy):
        assert result.score == result.maximum_score
        assert result.findings == []
        assert result.metrics["completeSections"] == 1
    assert disabled.metrics["sectionCoverageEnabled"] is False
    assert legacy.metrics["sectionCoverageEnabled"] is False


@pytest.mark.asyncio
async def test_section_coverage_either_mode_uses_configured_evidence() -> None:
    context = _context(
        _rule(
            validation_options={
                "validateSectionCoverage": True,
                "sectionCoverageEvaluationMode": "EITHER_REQUIRED",
                "minimumSectionLanguageBlockCoverage": {
                    "PURPOSE": {"id": 30, "en": 30, "zh": 40}
                },
                "minimumSectionLanguageCharacterCoverage": {
                    "PURPOSE": {"id": 30, "en": 30, "zh": 30}
                },
            }
        )
    )
    result = await RequiredSectionValidator().validate(context)

    assert result.score == result.maximum_score
    assert result.findings == []
    assert result.metrics["completeSections"] == 1


def test_section_coverage_options_are_normalized_and_snapshotted() -> None:
    future_option = {"strategy": "future-compatible"}
    source = SimpleNamespace(
        id=uuid4(),
        code="SNAPSHOT",
        version=3,
        validation_options_json={
            "futureOption": future_option,
            "validate_section_coverage": True,
            "section_coverage_evaluation_mode": "character_only",
            "minimum_section_language_character_coverage": {
                "purpose": {"ID": 25, "en": 25.5, "ZH": 25}
            },
        },
    )

    snapshot = ComplianceContextService().snapshot_rule(source)
    options = snapshot.validation_options

    assert options["futureOption"] == future_option
    assert options["validateSectionCoverage"] is True
    assert options["sectionCoverageEvaluationMode"] == "CHARACTER_ONLY"
    assert options["minimumSectionLanguageCharacterCoverage"] == {
        "PURPOSE": {"id": 25.0, "en": 25.5, "zh": 25.0}
    }
    serialized = snapshot.model_dump(mode="json", by_alias=True)
    assert serialized["validationOptions"] == options


@pytest.mark.parametrize(
    "invalid_options",
    [
        {"validateSectionCoverage": "yes"},
        {"sectionCoverageEvaluationMode": "AVERAGE"},
        {"minimumSectionLanguageBlockCoverage": {"PURPOSE": {"zh": 101}}},
        {"minimumSectionLanguageCharacterCoverage": {"PURPOSE": {"fr": 20}}},
        {"sectionCoverageMinimumConfidence": 1.1},
    ],
)
def test_invalid_section_coverage_options_fail_schema_boundary(
    invalid_options: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ValidationRuleCreate(
            name="Invalid section coverage",
            code="INVALID-SC",
            validation_options=invalid_options,
        )


@pytest.mark.asyncio
async def test_invalid_section_coverage_options_fail_api_boundary(
    api_client: AsyncClient,
    create_user: Any,
    token_service: TokenService,
) -> None:
    user = await create_user(
        email="section-coverage-admin@example.com",
        role=UserRole.SUPER_ADMIN,
        is_superuser=True,
    )
    headers = {"Authorization": f"Bearer {token_service.create_access_token(user)}"}

    response = await api_client.post(
        "/api/v1/master-data/validation-rules",
        headers=headers,
        json={
            "name": "Invalid section coverage",
            "code": "INVALID-SC",
            "validationOptions": {
                "validateSectionCoverage": True,
                "minimumSectionLanguageBlockCoverage": {"PURPOSE": {"zh": 101}},
            },
        },
    )

    assert response.status_code == 422
