"""End-to-end pure section detection from extracted blocks and aliases."""

from __future__ import annotations

from collections.abc import Sequence

from app.schemas.compliance_internal import DetectedSectionData
from app.services.compliance._compat import read, string_value
from app.services.compliance.sections.heading_candidate_service import (
    HeadingCandidateService,
)
from app.services.compliance.sections.section_boundary_service import (
    SectionBoundaryService,
)
from app.services.compliance.sections.section_matcher import SectionMatcher


class SectionDetector:
    """Compose candidate scoring, alias matching, and boundary detection."""

    def __init__(
        self,
        candidate_service: HeadingCandidateService | None = None,
        matcher: SectionMatcher | None = None,
        boundary_service: SectionBoundaryService | None = None,
    ) -> None:
        self.candidate_service = candidate_service or HeadingCandidateService()
        self.matcher = matcher or SectionMatcher()
        self.boundary_service = boundary_service or SectionBoundaryService()

    def detect(
        self,
        blocks: Sequence[object],
        aliases: Sequence[object],
        *,
        required_sections: Sequence[str] = (),
        profile_id: object | None = None,
        allow_repeated_sections: bool = False,
    ) -> list[DetectedSectionData]:
        alias_texts = [
            string_value(read(alias, "alias_text", ""))
            for alias in aliases
        ]
        candidates = self.candidate_service.detect(
            blocks,
            alias_texts=alias_texts,
        )
        matches = self.matcher.match_all(
            candidates,
            aliases,
            profile_id=profile_id,
        )
        return self.boundary_service.build(
            matches,
            blocks,
            required_sections=required_sections,
            allow_repeated_sections=allow_repeated_sections,
        )

    def detect_sections(
        self,
        blocks: Sequence[object],
        aliases: Sequence[object],
        *,
        required_sections: Sequence[str] = (),
        profile_id: object | None = None,
        allow_repeated_sections: bool = False,
    ) -> list[DetectedSectionData]:
        return self.detect(
            blocks,
            aliases,
            required_sections=required_sections,
            profile_id=profile_id,
            allow_repeated_sections=allow_repeated_sections,
        )
