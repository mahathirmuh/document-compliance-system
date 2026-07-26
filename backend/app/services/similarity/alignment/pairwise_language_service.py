"""Resolve language members and required/optional pair comparisons."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.schemas.similarity_internal import (
    SimilarityGroupData,
    SimilarityMemberData,
    SimilarityOptions,
)

_SUPPORTED_LANGUAGES = ("id", "en", "zh")
_DEFAULT_PAIRS = (("id", "en"), ("id", "zh"), ("en", "zh"))


@dataclass(frozen=True, slots=True)
class ResolvedLanguageMember:
    language_code: str
    text: str
    member_id: UUID | None
    confidence: float
    source_reference: str
    ocr_confidence: float | None


@dataclass(frozen=True, slots=True)
class PairCandidate:
    source_language: str
    target_language: str
    source: ResolvedLanguageMember | None
    target: ResolvedLanguageMember | None
    required: bool
    missing_primary_language: bool


class PairwiseLanguageService:
    def pairs_for_group(
        self,
        group: SimilarityGroupData,
        options: SimilarityOptions,
    ) -> list[PairCandidate]:
        members = self.resolve_members(group.members)
        configured_required = self._normalize_pairs(options.required_pairs)
        configured_optional = self._normalize_pairs(options.optional_pairs)
        required_pairs = configured_required or list(_DEFAULT_PAIRS)
        pairs = [*required_pairs]
        for pair in configured_optional:
            if pair not in pairs:
                pairs.append(pair)
        primary = (
            options.primary_language.casefold()
            if options.primary_language
            else None
        )
        return [
            PairCandidate(
                source_language=source,
                target_language=target,
                source=members.get(source),
                target=members.get(target),
                required=(source, target) in required_pairs,
                missing_primary_language=bool(
                    primary
                    and primary in (source, target)
                    and primary not in members
                ),
            )
            for source, target in pairs
        ]

    def resolve_members(
        self,
        members: list[SimilarityMemberData],
    ) -> dict[str, ResolvedLanguageMember]:
        by_language: dict[str, list[SimilarityMemberData]] = {}
        for member in sorted(
            members, key=lambda item: (item.block_order, str(item.id or ""))
        ):
            language = member.language_code.casefold()
            if language in _SUPPORTED_LANGUAGES and member.text.strip():
                by_language.setdefault(language, []).append(member)
        return {
            language: ResolvedLanguageMember(
                language_code=language,
                text="\n".join(item.text.strip() for item in items),
                member_id=items[0].id,
                confidence=(
                    sum(item.confidence for item in items) / len(items)
                ),
                source_reference=(
                    items[0].source_reference
                    if items[0].source_reference
                    else ""
                ),
                ocr_confidence=self._average_ocr_confidence(items),
            )
            for language, items in by_language.items()
        }

    @staticmethod
    def _normalize_pairs(
        values: list[tuple[str, str]],
    ) -> list[tuple[str, str]]:
        output: list[tuple[str, str]] = []
        for source, target in values:
            pair = (source.casefold(), target.casefold())
            if (
                pair[0] in _SUPPORTED_LANGUAGES
                and pair[1] in _SUPPORTED_LANGUAGES
                and pair[0] != pair[1]
                and pair not in output
            ):
                output.append(pair)
        return output

    @staticmethod
    def _average_ocr_confidence(
        items: list[SimilarityMemberData],
    ) -> float | None:
        values = [
            float(value)
            for item in items
            if (value := item.metadata.get("ocrConfidence")) is not None
        ]
        return sum(values) / len(values) if values else None
