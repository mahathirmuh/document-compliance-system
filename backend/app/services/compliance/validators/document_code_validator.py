"""Validate the retained document code without querying persistence."""

from __future__ import annotations

import re

from app.schemas.compliance_internal import (
    ComplianceValidationContext,
    ValidatorResult,
)
from app.services.compliance._compat import string_value
from app.services.compliance.constants import FindingCode, FindingSeverity
from app.services.compliance.findings.finding_factory import FindingFactory
from app.services.compliance.validators._helpers import (
    context_option,
    result,
    skipped_result,
    validator_enabled,
    validator_weight,
)
from app.services.compliance.validators.base_validator import (
    BaseComplianceValidator,
)


class DocumentCodeValidator(BaseComplianceValidator):
    code = "DOCUMENT_CODE"
    name = "Document code"
    weight = 10.0

    def __init__(self, finding_factory: FindingFactory | None = None) -> None:
        self.findings = finding_factory or FindingFactory()

    async def validate(
        self,
        context: ComplianceValidationContext,
    ) -> ValidatorResult:
        if not validator_enabled(context, self.code):
            return skipped_result(context, self.code)
        maximum = validator_weight(context, self.code)
        actual = string_value(context.document_code).strip()
        expected = string_value(context.expected_document_code).strip()
        pattern = string_value(
            context_option(context, "document_code_pattern", ""),
        )
        valid = bool(actual)
        reason = ""
        if expected and actual != expected:
            valid = False
            reason = "Document code does not match the expected code."
        if pattern:
            try:
                pattern_matches = re.fullmatch(pattern, actual) is not None
            except re.error:
                pattern_matches = False
                reason = "The configured document-code pattern is invalid."
            if not pattern_matches:
                valid = False
                reason = reason or (
                    "Document code does not match the configured pattern."
                )
        findings = []
        if not valid:
            findings.append(
                self.findings.create(
                    FindingCode.INVALID_DOCUMENT_CODE,
                    description=reason or "Document code is missing.",
                    severity=FindingSeverity.MAJOR,
                    expected_value={
                        "documentCode": expected or None,
                        "pattern": pattern or None,
                    },
                    actual_value={"documentCode": actual or None},
                ),
            )
        return result(
            self.code,
            maximum_score=maximum,
            score=maximum if valid else 0.0,
            findings=findings,
            metrics={
                "valid": valid,
                "expected": expected or None,
                "actual": actual or None,
                "patternConfigured": bool(pattern),
            },
        )

