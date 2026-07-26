"""Stable Phase 9 glossary values shared by models and services."""

from enum import StrEnum


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    """Persist enum values instead of Python enum member names."""

    return [member.value for member in enum_class]


class GlossaryScopeType(StrEnum):
    """Supported profile scopes in descending specificity."""

    GLOBAL = "GLOBAL"
    DEPARTMENT = "DEPARTMENT"
    DOCUMENT_TYPE = "DOCUMENT_TYPE"
    DEPARTMENT_DOCUMENT_TYPE = "DEPARTMENT_DOCUMENT_TYPE"


GLOSSARY_SCOPE_PRIORITY = {
    GlossaryScopeType.GLOBAL: 1,
    GlossaryScopeType.DEPARTMENT: 2,
    GlossaryScopeType.DOCUMENT_TYPE: 3,
    GlossaryScopeType.DEPARTMENT_DOCUMENT_TYPE: 4,
}


class GlossaryTermType(StrEnum):
    """Business intent of a glossary concept."""

    PREFERRED = "PREFERRED"
    REQUIRED = "REQUIRED"
    FORBIDDEN = "FORBIDDEN"
    REFERENCE = "REFERENCE"
    ABBREVIATION = "ABBREVIATION"


class GlossaryTermSeverity(StrEnum):
    """Finding severity selected for a glossary term."""

    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    INFORMATION = "INFORMATION"


class GlossaryLanguageCode(StrEnum):
    """Phase 9 glossary languages."""

    INDONESIAN = "id"
    ENGLISH = "en"
    CHINESE = "zh"


class GlossaryVariantType(StrEnum):
    """Classification of an alternate term spelling."""

    SYNONYM = "SYNONYM"
    ABBREVIATION = "ABBREVIATION"
    SPELLING = "SPELLING"
    LEGACY = "LEGACY"
    FORBIDDEN_VARIANT = "FORBIDDEN_VARIANT"


class GlossaryExceptionScopeType(StrEnum):
    """Supported exception scopes from broadest to most specific."""

    GLOBAL = "GLOBAL"
    DEPARTMENT = "DEPARTMENT"
    DOCUMENT = "DOCUMENT"
    DOCUMENT_REVISION = "DOCUMENT_REVISION"
    DOCUMENT_FILE = "DOCUMENT_FILE"
    SECTION = "SECTION"


class GlossaryExceptionType(StrEnum):
    """Audited exception behaviors."""

    ALLOW_VARIANT = "ALLOW_VARIANT"
    IGNORE_TERM = "IGNORE_TERM"
    ALLOW_MISSING_TRANSLATION = "ALLOW_MISSING_TRANSLATION"
    ALLOW_FORBIDDEN_TERM = "ALLOW_FORBIDDEN_TERM"


class GlossaryValidationStatus(StrEnum):
    """Durable lifecycle states for a validation run/job."""

    QUEUED = "QUEUED"
    LOADING_CONTEXT = "LOADING_CONTEXT"
    MATCHING_TERMS = "MATCHING_TERMS"
    VALIDATING_TERMS = "VALIDATING_TERMS"
    GENERATING_FINDINGS = "GENERATING_FINDINGS"
    PERSISTING = "PERSISTING"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"


ACTIVE_GLOSSARY_VALIDATION_STATUSES = frozenset(
    {
        GlossaryValidationStatus.QUEUED,
        GlossaryValidationStatus.LOADING_CONTEXT,
        GlossaryValidationStatus.MATCHING_TERMS,
        GlossaryValidationStatus.VALIDATING_TERMS,
        GlossaryValidationStatus.GENERATING_FINDINGS,
        GlossaryValidationStatus.PERSISTING,
        GlossaryValidationStatus.CANCEL_REQUESTED,
    }
)


TERMINAL_GLOSSARY_VALIDATION_STATUSES = frozenset(
    {
        GlossaryValidationStatus.COMPLETED,
        GlossaryValidationStatus.PARTIALLY_COMPLETED,
        GlossaryValidationStatus.FAILED,
        GlossaryValidationStatus.CANCELLED,
    }
)


class GlossaryValidationJobType(StrEnum):
    """Reason for creating a glossary validation lifecycle."""

    INITIAL = "INITIAL"
    REVALIDATION = "REVALIDATION"
    MANUAL = "MANUAL"


class GlossarySourceType(StrEnum):
    """Origin of content inspected by glossary matching."""

    NATIVE_EXTRACTION = "NATIVE_EXTRACTION"
    OCR = "OCR"


class GlossaryMatchType(StrEnum):
    """Matcher that produced one retained occurrence."""

    EXACT = "EXACT"
    WHOLE_WORD = "WHOLE_WORD"
    CASE_SENSITIVE = "CASE_SENSITIVE"
    INFLECTION = "INFLECTION"
    REGEX = "REGEX"
    CHINESE_SUBSTRING = "CHINESE_SUBSTRING"
    VARIANT = "VARIANT"
