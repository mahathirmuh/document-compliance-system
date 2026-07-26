"""Phase 8 compliance overview and report response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.models.compliance_enums import ComplianceStatus
from app.schemas.base import ApiSchema
from app.schemas.common import PaginationData
from app.schemas.finding import FindingListResponse


class ComplianceBreakdownItem(ApiSchema):
    label: str
    total: int = Field(ge=0)
    compliant: int = Field(ge=0)
    partially_compliant: int = Field(ge=0)
    non_compliant: int = Field(ge=0)
    needs_review: int = Field(ge=0)
    not_evaluated: int = Field(ge=0)


class ComplianceTrendItem(ApiSchema):
    period: str
    score: float = Field(ge=0, le=100)
    validated: int = Field(ge=0)


class ComplianceLanguageCount(ApiSchema):
    language_code: str
    count: int = Field(ge=0)


class ComplianceSectionCount(ApiSchema):
    canonical_code: str
    count: int = Field(ge=0)


class ComplianceOverviewResponse(ApiSchema):
    total_validated_documents: int = Field(ge=0)
    compliant: int = Field(ge=0)
    partially_compliant: int = Field(ge=0)
    non_compliant: int = Field(ge=0)
    needs_review: int = Field(ge=0)
    not_evaluated: int = Field(ge=0)
    open_critical_findings: int = Field(ge=0)
    open_major_findings: int = Field(ge=0)
    by_department: list[ComplianceBreakdownItem]
    by_document_type: list[ComplianceBreakdownItem]
    trend: list[ComplianceTrendItem]
    findings_by_severity: dict[str, int]
    missing_languages: list[ComplianceLanguageCount]
    missing_sections: list[ComplianceSectionCount]


class ComplianceReportItem(ApiSchema):
    run_id: UUID
    document_id: UUID
    document_file_id: UUID
    document_code: str
    title: str
    department: str
    section: str | None
    document_type: str
    revision: str
    validation_rule: str
    language_presence: dict[str, str]
    section_completeness: float = Field(ge=0, le=100)
    language_order_valid: bool | None
    score: float | None = Field(default=None, ge=0, le=100)
    compliance_status: ComplianceStatus
    critical_findings: int = Field(ge=0)
    major_findings: int = Field(ge=0)
    last_validated: datetime


class ComplianceReportResponse(PaginationData[ComplianceReportItem]):
    pass


class FindingCountItem(ApiSchema):
    label: str
    count: int = Field(ge=0)


class FindingTrendItem(ApiSchema):
    period: str
    count: int = Field(ge=0)


class FindingsReportSummary(ApiSchema):
    total_findings: int = Field(ge=0)
    open: int = Field(ge=0)
    in_review: int = Field(ge=0)
    resolved: int = Field(ge=0)
    critical: int = Field(ge=0)
    major: int = Field(ge=0)
    minor: int = Field(ge=0)
    information: int = Field(ge=0)
    false_positive: int = Field(ge=0)
    accepted_risk: int = Field(ge=0)
    by_department: list[FindingCountItem]
    by_type: list[FindingCountItem]
    by_severity: list[FindingCountItem]
    trend: list[FindingTrendItem]


class FindingsReportResponse(ApiSchema):
    summary: FindingsReportSummary
    findings: FindingListResponse
