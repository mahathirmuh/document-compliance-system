"""Abstract contract for every side-effect-free compliance validator."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.compliance_internal import (
    ComplianceValidationContext,
    ValidatorResult,
)


class BaseComplianceValidator(ABC):
    code: str
    name: str
    weight: float = 0.0

    @abstractmethod
    async def validate(
        self,
        context: ComplianceValidationContext,
    ) -> ValidatorResult:
        """Evaluate one concern without committing or mutating context."""

