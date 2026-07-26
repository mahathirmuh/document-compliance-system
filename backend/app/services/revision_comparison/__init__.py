"""Phase 9 revision comparison without source-document mutation."""

from app.services.revision_comparison.revision_alignment_service import (
    AlignedRevisionPair,
    CanonicalRevisionItem,
    RevisionAlignmentService,
)
from app.services.revision_comparison.revision_change_detection_service import (
    DetectedRevisionChange,
    RevisionChangeDetectionService,
)

__all__ = [
    "AlignedRevisionPair",
    "CanonicalRevisionItem",
    "DetectedRevisionChange",
    "RevisionAlignmentService",
    "RevisionChangeDetectionService",
]
