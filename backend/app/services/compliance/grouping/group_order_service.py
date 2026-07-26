"""Language completeness and relative-order rules shared by groupers."""

from __future__ import annotations

from collections.abc import Sequence

from app.services.compliance.constants import NON_TARGET_LANGUAGES


class GroupOrderService:
    """Evaluate order without treating unknown or mixed as target languages."""

    @staticmethod
    def normalize_languages(
        languages: Sequence[str],
        *,
        ignore_unknown: bool = True,
        ignore_mixed: bool = True,
        collapse_consecutive: bool = False,
    ) -> tuple[str, ...]:
        normalized: list[str] = []
        for raw_language in languages:
            language = str(raw_language).casefold()
            if ignore_unknown and language in {"unknown", "other", ""}:
                continue
            if ignore_mixed and language == "mixed":
                continue
            if language in NON_TARGET_LANGUAGES and (
                ignore_unknown or ignore_mixed
            ):
                continue
            if (
                collapse_consecutive
                and normalized
                and normalized[-1] == language
            ):
                continue
            normalized.append(language)
        return tuple(normalized)

    def is_complete(
        self,
        actual: Sequence[str],
        expected: Sequence[str],
    ) -> bool:
        actual_set = set(self.normalize_languages(actual))
        return all(language.casefold() in actual_set for language in expected)

    def is_valid(
        self,
        actual: Sequence[str],
        expected: Sequence[str],
        *,
        allow_missing: bool = False,
        ignore_unknown: bool = True,
        ignore_mixed: bool = True,
    ) -> bool:
        normalized_expected = tuple(
            str(language).casefold() for language in expected
        )
        normalized_actual = self.normalize_languages(
            actual,
            ignore_unknown=ignore_unknown,
            ignore_mixed=ignore_mixed,
            collapse_consecutive=True,
        )
        if not normalized_expected:
            return True
        if not allow_missing and set(normalized_actual) != set(
            normalized_expected,
        ):
            return False
        if any(
            language not in normalized_expected
            for language in normalized_actual
        ):
            return False
        expected_positions = {
            language: index
            for index, language in enumerate(normalized_expected)
        }
        positions = [
            expected_positions[language] for language in normalized_actual
        ]
        return positions == sorted(positions) and len(positions) == len(
            set(positions),
        )

    def missing_languages(
        self,
        actual: Sequence[str],
        expected: Sequence[str],
    ) -> tuple[str, ...]:
        actual_set = set(self.normalize_languages(actual))
        return tuple(
            str(language).casefold()
            for language in expected
            if str(language).casefold() not in actual_set
        )

