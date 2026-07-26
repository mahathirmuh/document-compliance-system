"""Explicit case-sensitive glossary matcher."""

from app.services.glossary.matching.exact_term_matcher import ExactTermMatcher


class CaseSensitiveMatcher(ExactTermMatcher):
    """Compatibility wrapper for the architecture contract."""

    def find_case_sensitive(self, text: str, term: str):
        return self.find(text, term, case_sensitive=True)
