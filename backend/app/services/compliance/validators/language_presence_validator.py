"""Required-language presence using minimum block/character/confidence evidence."""

from __future__ import annotations

from collections import defaultdict

from app.schemas.compliance_internal import (
    ComplianceValidationContext,
    ValidatorResult,
)
from app.services.compliance._compat import (
    bool_value,
    float_value,
    read,
)
from app.services.compliance.constants import (
    LANGUAGE_NAMES,
    MISSING_LANGUAGE_CODES,
    FindingSeverity,
    ValidatorStatus,
)
from app.services.compliance.findings.finding_factory import FindingFactory
from app.services.compliance.validators._helpers import (
    block_characters,
    context_option,
    eligible_block,
    language_threshold,
    required_languages,
    result,
    skipped_result,
    validator_enabled,
    validator_weight,
)
from app.services.compliance.validators.base_validator import (
    BaseComplianceValidator,
)


class LanguagePresenceValidator(BaseComplianceValidator):
    code = "LANGUAGE_PRESENCE"
    name = "Language presence"
    weight = 25.0

    def __init__(self, finding_factory: FindingFactory | None = None) -> None:
        self.findings = finding_factory or FindingFactory()

    async def validate(
        self,
        context: ComplianceValidationContext,
    ) -> ValidatorResult:
        if not validator_enabled(context, self.code):
            return skipped_result(context, self.code)
        maximum = validator_weight(context, self.code)
        languages = required_languages(context)
        minimum_confidence = float_value(
            context_option(context, "presence_minimum_confidence", 0.65),
            0.65,
        )
        evidence_blocks: dict[str, int] = defaultdict(int)
        evidence_characters: dict[str, int] = defaultdict(int)
        confidence_sums: dict[str, float] = defaultdict(float)
        eligible_count = 0
        eligible_characters = 0
        for block in context.blocks:
            if not eligible_block(block, minimum_confidence=minimum_confidence):
                continue
            eligible_count += 1
            eligible_characters += block_characters(block)
            language = block.language_code.casefold()
            if language not in languages:
                continue
            evidence_blocks[language] += 1
            evidence_characters[language] += block_characters(block)
            confidence_sums[language] += block.language_confidence

        states: dict[str, str] = {}
        generated = []
        present_count = 0
        fail_missing = bool_value(
            read(
                context.rule,
                "fail_on_missing_required_language",
                True,
            ),
            True,
        )
        for language in languages:
            minimum_blocks = int(
                language_threshold(
                    context,
                    "presence_minimum_blocks",
                    language,
                    2,
                ),
            )
            minimum_characters = int(
                language_threshold(
                    context,
                    "presence_minimum_characters",
                    language,
                    20,
                ),
            )
            present = (
                evidence_blocks[language] >= minimum_blocks
                and evidence_characters[language] >= minimum_characters
            )
            insufficient_document = (
                eligible_count < minimum_blocks
                or eligible_characters < minimum_characters
            )
            if present:
                state = "PRESENT"
                present_count += 1
            elif insufficient_document:
                state = "INSUFFICIENT_EVIDENCE"
            else:
                state = "NOT_PRESENT"
            states[language] = state
            if state != "PRESENT":
                severity = (
                    FindingSeverity.INFORMATION
                    if state == "INSUFFICIENT_EVIDENCE"
                    else (
                        FindingSeverity.CRITICAL
                        if fail_missing
                        else FindingSeverity.MAJOR
                    )
                )
                generated.append(
                    self.findings.create(
                        MISSING_LANGUAGE_CODES.get(
                            language,
                            f"MISSING_{language.upper()}",
                        ),
                        severity=severity,
                        language_code=language,
                        description=(
                            f"{LANGUAGE_NAMES.get(language, language)} "
                            f"presence is {state.lower().replace('_', ' ')}."
                        ),
                        expected_value={
                            "minimumBlocks": minimum_blocks,
                            "minimumCharacters": minimum_characters,
                            "minimumConfidence": minimum_confidence,
                        },
                        actual_value={
                            "blocks": evidence_blocks[language],
                            "characters": evidence_characters[language],
                            "presenceStatus": state,
                        },
                    ),
                )
        earned = (
            present_count / len(languages) * maximum if languages else maximum
        )
        all_insufficient = bool(languages) and all(
            state == "INSUFFICIENT_EVIDENCE" for state in states.values()
        )
        return result(
            self.code,
            maximum_score=maximum,
            score=earned,
            findings=generated,
            status=(
                ValidatorStatus.NEEDS_REVIEW
                if all_insufficient
                else None
            ),
            metrics={
                "requiredLanguages": languages,
                "presence": states,
                "blockCounts": dict(evidence_blocks),
                "characterCounts": dict(evidence_characters),
                "averageConfidence": {
                    language: round(
                        confidence_sums[language]
                        / evidence_blocks[language],
                        6,
                    )
                    if evidence_blocks[language]
                    else None
                    for language in languages
                },
                "eligibleBlocks": eligible_count,
                "eligibleCharacters": eligible_characters,
                "minimumConfidence": minimum_confidence,
            },
        )

