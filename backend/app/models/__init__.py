"""SQLAlchemy model exports registered with the shared Alembic metadata."""

from app.models.audit_log import AuditLog
from app.models.compliance_enums import (
    ACTIVE_COMPLIANCE_JOB_STATUSES,
    FINDING_STATUS_TRANSITIONS,
    TERMINAL_COMPLIANCE_JOB_STATUSES,
    ComplianceJobStatus,
    ComplianceJobType,
    ComplianceRunStatus,
    ComplianceStatus,
    FindingCode,
    FindingSeverity,
    FindingStatus,
    FindingType,
    SectionAliasLanguageCode,
    SectionAliasMatchType,
    SectionLanguagePresenceStatus,
    TranslationGroupType,
)
from app.models.compliance_job import ComplianceJob
from app.models.compliance_run import ComplianceRun
from app.models.department import Department
from app.models.detected_section import DetectedSection
from app.models.document import Document
from app.models.document_file import DocumentFile, DocumentFileStatus
from app.models.document_revision import DocumentRevision
from app.models.document_status import DocumentStatus
from app.models.document_type import DocumentType
from app.models.extracted_block import ExtractedBlock, ExtractedBlockType
from app.models.extracted_container import (
    ExtractedContainer,
    ExtractedContainerType,
)
from app.models.extracted_table import ExtractedTable
from app.models.extracted_table_cell import ExtractedTableCell
from app.models.extraction_job import (
    ACTIVE_EXTRACTION_JOB_STATUSES,
    ExtractionJob,
    ExtractionJobStatus,
    ExtractionJobType,
)
from app.models.extraction_run import (
    ExtractionRun,
    ExtractionRunStatus,
    ExtractorType,
)
from app.models.finding_occurrence import FindingOccurrence
from app.models.glossary_enums import (
    ACTIVE_GLOSSARY_VALIDATION_STATUSES,
    TERMINAL_GLOSSARY_VALIDATION_STATUSES,
    GlossaryExceptionScopeType,
    GlossaryExceptionType,
    GlossaryLanguageCode,
    GlossaryMatchType,
    GlossaryScopeType,
    GlossarySourceType,
    GlossaryTermSeverity,
    GlossaryTermType,
    GlossaryValidationJobType,
    GlossaryValidationStatus,
    GlossaryVariantType,
)
from app.models.glossary_exception import GlossaryException
from app.models.glossary_match import GlossaryMatch
from app.models.glossary_profile import GlossaryProfile
from app.models.glossary_term import GlossaryTerm
from app.models.glossary_term_variant import GlossaryTermVariant
from app.models.glossary_translation import GlossaryTranslation
from app.models.glossary_validation_run import GlossaryValidationRun
from app.models.language_block_result import (
    LanguageBlockResult,
    LanguageCode,
    LanguageEligibilityReason,
    LanguageEligibilityStatus,
    LanguageSourceType,
)
from app.models.language_container_summary import LanguageContainerSummary
from app.models.language_detection_job import (
    ACTIVE_LANGUAGE_DETECTION_JOB_STATUSES,
    LanguageDetectionJob,
    LanguageDetectionJobStatus,
    LanguageDetectionJobType,
)
from app.models.language_detection_run import (
    LanguageDetectionRun,
    LanguageDetectionRunStatus,
)
from app.models.ocr_block import OCRBlock
from app.models.ocr_job import (
    ACTIVE_OCR_JOB_STATUSES,
    OCRJob,
    OCRJobStatus,
    OCRJobType,
    OCRLanguageProfile,
    OCRPreprocessingProfile,
)
from app.models.ocr_page_result import OCRPageResult, OCRPageStatus
from app.models.ocr_run import OCRRun, OCRRunStatus
from app.models.refresh_token import RefreshToken
from app.models.report_schedule import ReportSchedule, ReportScheduleType
from app.models.report_snapshot import (
    AdvancedReportType,
    ReportFileFormat,
    ReportJobStatus,
    ReportSnapshot,
    ReportSnapshotStatus,
)
from app.models.revision_change import (
    RevisionChange,
    RevisionChangeType,
    RevisionEntityType,
)
from app.models.revision_comparison import (
    RevisionComparison,
    RevisionComparisonClassification,
    RevisionComparisonStatus,
)
from app.models.revision_comparison_job import (
    ACTIVE_REVISION_COMPARISON_JOB_STATUSES,
    TERMINAL_REVISION_COMPARISON_JOB_STATUSES,
    RevisionComparisonJob,
    RevisionComparisonJobStatus,
    RevisionComparisonJobType,
)
from app.models.section import Section
from app.models.section_alias import SectionAlias
from app.models.section_alias_profile import SectionAliasProfile
from app.models.section_definition import SectionDefinition
from app.models.section_language_result import SectionLanguageResult
from app.models.similarity_enums import (
    ACTIVE_SIMILARITY_JOB_STATUSES,
    TERMINAL_SIMILARITY_JOB_STATUSES,
    ConsistencyStatus,
    SimilarityAnalysisStatus,
    SimilarityCategory,
    SimilarityJobStatus,
    SimilarityJobType,
    SimilarityRunStatus,
)
from app.models.similarity_job import SimilarityJob
from app.models.similarity_result import TranslationSimilarityResult
from app.models.similarity_run import SimilarityRun
from app.models.similarity_section_summary import SectionSimilaritySummary
from app.models.translation_group import TranslationGroup
from app.models.translation_group_member import TranslationGroupMember
from app.models.upload_session import (
    UploadSession,
    UploadSessionStatus,
    UploadSessionType,
)
from app.models.upload_session_item import (
    UploadIdentificationStatus,
    UploadProposedAction,
    UploadSessionItem,
    UploadSessionItemStatus,
)
from app.models.user import User
from app.models.validation_finding import ValidationFinding
from app.models.validation_rule import ValidationRule

__all__ = [
    "ACTIVE_COMPLIANCE_JOB_STATUSES",
    "ACTIVE_EXTRACTION_JOB_STATUSES",
    "ACTIVE_GLOSSARY_VALIDATION_STATUSES",
    "ACTIVE_LANGUAGE_DETECTION_JOB_STATUSES",
    "ACTIVE_OCR_JOB_STATUSES",
    "ACTIVE_REVISION_COMPARISON_JOB_STATUSES",
    "ACTIVE_SIMILARITY_JOB_STATUSES",
    "FINDING_STATUS_TRANSITIONS",
    "TERMINAL_COMPLIANCE_JOB_STATUSES",
    "TERMINAL_GLOSSARY_VALIDATION_STATUSES",
    "TERMINAL_REVISION_COMPARISON_JOB_STATUSES",
    "TERMINAL_SIMILARITY_JOB_STATUSES",
    "AdvancedReportType",
    "AuditLog",
    "ComplianceJob",
    "ComplianceJobStatus",
    "ComplianceJobType",
    "ComplianceRun",
    "ComplianceRunStatus",
    "ComplianceStatus",
    "ConsistencyStatus",
    "Department",
    "DetectedSection",
    "Document",
    "DocumentFile",
    "DocumentFileStatus",
    "DocumentRevision",
    "DocumentStatus",
    "DocumentType",
    "ExtractedBlock",
    "ExtractedBlockType",
    "ExtractedContainer",
    "ExtractedContainerType",
    "ExtractedTable",
    "ExtractedTableCell",
    "ExtractionJob",
    "ExtractionJobStatus",
    "ExtractionJobType",
    "ExtractionRun",
    "ExtractionRunStatus",
    "ExtractorType",
    "FindingCode",
    "FindingOccurrence",
    "FindingSeverity",
    "FindingStatus",
    "FindingType",
    "GlossaryException",
    "GlossaryExceptionScopeType",
    "GlossaryExceptionType",
    "GlossaryLanguageCode",
    "GlossaryMatch",
    "GlossaryMatchType",
    "GlossaryProfile",
    "GlossaryScopeType",
    "GlossarySourceType",
    "GlossaryTerm",
    "GlossaryTermSeverity",
    "GlossaryTermType",
    "GlossaryTermVariant",
    "GlossaryTranslation",
    "GlossaryValidationJobType",
    "GlossaryValidationRun",
    "GlossaryValidationStatus",
    "GlossaryVariantType",
    "LanguageBlockResult",
    "LanguageCode",
    "LanguageContainerSummary",
    "LanguageDetectionJob",
    "LanguageDetectionJobStatus",
    "LanguageDetectionJobType",
    "LanguageDetectionRun",
    "LanguageDetectionRunStatus",
    "LanguageEligibilityReason",
    "LanguageEligibilityStatus",
    "LanguageSourceType",
    "OCRBlock",
    "OCRJob",
    "OCRJobStatus",
    "OCRJobType",
    "OCRLanguageProfile",
    "OCRPageResult",
    "OCRPageStatus",
    "OCRPreprocessingProfile",
    "OCRRun",
    "OCRRunStatus",
    "RefreshToken",
    "ReportFileFormat",
    "ReportJobStatus",
    "ReportSchedule",
    "ReportScheduleType",
    "ReportSnapshot",
    "ReportSnapshotStatus",
    "RevisionChange",
    "RevisionChangeType",
    "RevisionComparison",
    "RevisionComparisonClassification",
    "RevisionComparisonJob",
    "RevisionComparisonJobStatus",
    "RevisionComparisonJobType",
    "RevisionComparisonStatus",
    "RevisionEntityType",
    "Section",
    "SectionAlias",
    "SectionAliasLanguageCode",
    "SectionAliasMatchType",
    "SectionAliasProfile",
    "SectionDefinition",
    "SectionLanguagePresenceStatus",
    "SectionLanguageResult",
    "SectionSimilaritySummary",
    "SimilarityAnalysisStatus",
    "SimilarityCategory",
    "SimilarityJob",
    "SimilarityJobStatus",
    "SimilarityJobType",
    "SimilarityRun",
    "SimilarityRunStatus",
    "TranslationGroup",
    "TranslationGroupMember",
    "TranslationGroupType",
    "TranslationSimilarityResult",
    "UploadIdentificationStatus",
    "UploadProposedAction",
    "UploadSession",
    "UploadSessionItem",
    "UploadSessionItemStatus",
    "UploadSessionStatus",
    "UploadSessionType",
    "User",
    "ValidationFinding",
    "ValidationRule",
]
