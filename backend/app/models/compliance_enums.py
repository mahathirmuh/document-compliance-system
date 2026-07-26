"""Stable Phase 8 compliance values shared by models, schemas, and services."""

from enum import StrEnum


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    """Persist enum values instead of Python member names."""
    return [member.value for member in enum_class]


class SectionAliasLanguageCode(StrEnum):
    """Languages supported by canonical-section aliases."""

    INDONESIAN = "id"
    ENGLISH = "en"
    CHINESE = "zh"
    ANY = "any"


class SectionAliasMatchType(StrEnum):
    """Ordered section-heading matching strategies."""

    EXACT = "EXACT"
    PREFIX = "PREFIX"
    CONTAINS = "CONTAINS"
    REGEX = "REGEX"
    FUZZY = "FUZZY"


class ComplianceJobType(StrEnum):
    """Reason a compliance validation job was requested."""

    INITIAL_VALIDATION = "INITIAL_VALIDATION"
    REVALIDATION = "REVALIDATION"
    MANUAL_VALIDATION = "MANUAL_VALIDATION"


class ComplianceJobStatus(StrEnum):
    """Durable compliance-job progress states."""

    QUEUED = "QUEUED"
    LOADING_CONTEXT = "LOADING_CONTEXT"
    DETECTING_SECTIONS = "DETECTING_SECTIONS"
    GROUPING_CONTENT = "GROUPING_CONTENT"
    VALIDATING_LANGUAGES = "VALIDATING_LANGUAGES"
    VALIDATING_SECTIONS = "VALIDATING_SECTIONS"
    VALIDATING_ORDER = "VALIDATING_ORDER"
    VALIDATING_TABLES = "VALIDATING_TABLES"
    GENERATING_FINDINGS = "GENERATING_FINDINGS"
    CALCULATING_SCORE = "CALCULATING_SCORE"
    PERSISTING = "PERSISTING"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"


ACTIVE_COMPLIANCE_JOB_STATUSES = frozenset(
    {
        ComplianceJobStatus.QUEUED,
        ComplianceJobStatus.LOADING_CONTEXT,
        ComplianceJobStatus.DETECTING_SECTIONS,
        ComplianceJobStatus.GROUPING_CONTENT,
        ComplianceJobStatus.VALIDATING_LANGUAGES,
        ComplianceJobStatus.VALIDATING_SECTIONS,
        ComplianceJobStatus.VALIDATING_ORDER,
        ComplianceJobStatus.VALIDATING_TABLES,
        ComplianceJobStatus.GENERATING_FINDINGS,
        ComplianceJobStatus.CALCULATING_SCORE,
        ComplianceJobStatus.PERSISTING,
        ComplianceJobStatus.CANCEL_REQUESTED,
    }
)

TERMINAL_COMPLIANCE_JOB_STATUSES = frozenset(
    {
        ComplianceJobStatus.COMPLETED,
        ComplianceJobStatus.PARTIALLY_COMPLETED,
        ComplianceJobStatus.FAILED,
        ComplianceJobStatus.CANCELLED,
    }
)


class ComplianceRunStatus(StrEnum):
    """Persistence outcome for an immutable compliance run."""

    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"


class ComplianceStatus(StrEnum):
    """Business-level compliance classification."""

    COMPLIANT = "COMPLIANT"
    PARTIALLY_COMPLIANT = "PARTIALLY_COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    NOT_EVALUATED = "NOT_EVALUATED"


class SectionLanguagePresenceStatus(StrEnum):
    """Language-evidence result within one detected section."""

    PRESENT = "PRESENT"
    NOT_PRESENT = "NOT_PRESENT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    MIXED_ONLY = "MIXED_ONLY"


class TranslationGroupType(StrEnum):
    """Structural grouping method; no semantic equivalence is implied."""

    HEADING_GROUP = "HEADING_GROUP"
    PARAGRAPH_GROUP = "PARAGRAPH_GROUP"
    TABLE_ROW_GROUP = "TABLE_ROW_GROUP"
    TABLE_CELL_GROUP = "TABLE_CELL_GROUP"
    XLSX_ROW_GROUP = "XLSX_ROW_GROUP"
    PDF_POSITIONAL_GROUP = "PDF_POSITIONAL_GROUP"
    MANUAL_GROUP = "MANUAL_GROUP"


class FindingType(StrEnum):
    """Controlled classification of compliance findings."""

    DOCUMENT_CODE = "DOCUMENT_CODE"
    LANGUAGE_PRESENCE = "LANGUAGE_PRESENCE"
    LANGUAGE_COVERAGE = "LANGUAGE_COVERAGE"
    SECTION_MISSING = "SECTION_MISSING"
    SECTION_LANGUAGE_MISSING = "SECTION_LANGUAGE_MISSING"
    SECTION_ORDER = "SECTION_ORDER"
    LANGUAGE_ORDER = "LANGUAGE_ORDER"
    TRANSLATION_GROUP_INCOMPLETE = "TRANSLATION_GROUP_INCOMPLETE"
    TABLE_LANGUAGE_MISSING = "TABLE_LANGUAGE_MISSING"
    CELL_LANGUAGE_MISSING = "CELL_LANGUAGE_MISSING"
    UNKNOWN_LANGUAGE_EXCESS = "UNKNOWN_LANGUAGE_EXCESS"
    MIXED_LANGUAGE_EXCESS = "MIXED_LANGUAGE_EXCESS"
    OCR_CONFIDENCE = "OCR_CONFIDENCE"
    EXTRACTION_QUALITY = "EXTRACTION_QUALITY"
    STRUCTURE = "STRUCTURE"
    MANUAL = "MANUAL"


class FindingCode(StrEnum):
    """Stable machine-readable finding codes from the Phase 8 contract."""

    INVALID_DOCUMENT_CODE = "INVALID_DOCUMENT_CODE"
    MISSING_INDONESIAN = "MISSING_INDONESIAN"
    MISSING_ENGLISH = "MISSING_ENGLISH"
    MISSING_CHINESE = "MISSING_CHINESE"
    LOW_INDONESIAN_COVERAGE = "LOW_INDONESIAN_COVERAGE"
    LOW_ENGLISH_COVERAGE = "LOW_ENGLISH_COVERAGE"
    LOW_CHINESE_COVERAGE = "LOW_CHINESE_COVERAGE"
    MISSING_REQUIRED_SECTION = "MISSING_REQUIRED_SECTION"
    MISSING_SECTION_INDONESIAN = "MISSING_SECTION_INDONESIAN"
    MISSING_SECTION_ENGLISH = "MISSING_SECTION_ENGLISH"
    MISSING_SECTION_CHINESE = "MISSING_SECTION_CHINESE"
    SECTION_ORDER_INVALID = "SECTION_ORDER_INVALID"
    LANGUAGE_ORDER_INVALID = "LANGUAGE_ORDER_INVALID"
    INCOMPLETE_TRANSLATION_GROUP = "INCOMPLETE_TRANSLATION_GROUP"
    MISSING_TRANSLATION_GROUP_INDONESIAN = (
        "MISSING_TRANSLATION_GROUP_INDONESIAN"
    )
    MISSING_TRANSLATION_GROUP_ENGLISH = "MISSING_TRANSLATION_GROUP_ENGLISH"
    MISSING_TRANSLATION_GROUP_CHINESE = "MISSING_TRANSLATION_GROUP_CHINESE"
    TABLE_TRANSLATION_INCOMPLETE = "TABLE_TRANSLATION_INCOMPLETE"
    TABLE_CELL_LANGUAGE_MISSING = "TABLE_CELL_LANGUAGE_MISSING"
    XLSX_ROW_TRANSLATION_INCOMPLETE = "XLSX_ROW_TRANSLATION_INCOMPLETE"
    UNKNOWN_TEXT_EXCEEDS_THRESHOLD = "UNKNOWN_TEXT_EXCEEDS_THRESHOLD"
    MIXED_TEXT_EXCEEDS_THRESHOLD = "MIXED_TEXT_EXCEEDS_THRESHOLD"
    OCR_CONFIDENCE_TOO_LOW = "OCR_CONFIDENCE_TOO_LOW"
    EXTRACTION_PARTIALLY_COMPLETED = "EXTRACTION_PARTIALLY_COMPLETED"
    OCR_REQUIRED_NOT_COMPLETED = "OCR_REQUIRED_NOT_COMPLETED"
    MANUAL_FINDING = "MANUAL_FINDING"


class FindingSeverity(StrEnum):
    """Finding impact levels."""

    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    INFORMATION = "INFORMATION"


class FindingStatus(StrEnum):
    """Auditable finding workflow states."""

    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    ACCEPTED_RISK = "ACCEPTED_RISK"
    REOPENED = "REOPENED"


FINDING_STATUS_TRANSITIONS: dict[FindingStatus, frozenset[FindingStatus]] = {
    FindingStatus.OPEN: frozenset(
        {
            FindingStatus.IN_REVIEW,
            FindingStatus.RESOLVED,
            FindingStatus.FALSE_POSITIVE,
            FindingStatus.ACCEPTED_RISK,
        }
    ),
    FindingStatus.IN_REVIEW: frozenset(
        {
            FindingStatus.RESOLVED,
            FindingStatus.FALSE_POSITIVE,
            FindingStatus.ACCEPTED_RISK,
            FindingStatus.OPEN,
        }
    ),
    FindingStatus.RESOLVED: frozenset({FindingStatus.REOPENED}),
    FindingStatus.CLOSED: frozenset({FindingStatus.REOPENED}),
    FindingStatus.FALSE_POSITIVE: frozenset({FindingStatus.REOPENED}),
    FindingStatus.ACCEPTED_RISK: frozenset({FindingStatus.REOPENED}),
    FindingStatus.REOPENED: frozenset(
        {
            FindingStatus.IN_REVIEW,
            FindingStatus.RESOLVED,
            FindingStatus.FALSE_POSITIVE,
            FindingStatus.ACCEPTED_RISK,
        }
    ),
}
