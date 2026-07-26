"""Phase 9 local glossary management and validation services."""

from app.services.glossary.glossary_matching_service import (
    GlossaryMatchingService,
)
from app.services.glossary.glossary_validation_service import (
    GlossaryValidationService,
)

__all__ = ["GlossaryMatchingService", "GlossaryValidationService"]
