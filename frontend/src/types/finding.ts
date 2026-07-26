import type {
  ComplianceDocumentSummary,
  ComplianceRevisionSummary,
  RequiredLanguageCode,
} from './compliance';
import type { DocumentUserSummary } from './document';
import type { PaginatedData, SortOrder } from './masterData';

export const findingSeverities = ['CRITICAL', 'MAJOR', 'MINOR', 'INFORMATION'] as const;

export type FindingSeverity = (typeof findingSeverities)[number];

export const findingStatuses = [
  'OPEN',
  'IN_REVIEW',
  'RESOLVED',
  'CLOSED',
  'FALSE_POSITIVE',
  'ACCEPTED_RISK',
  'REOPENED',
] as const;

export type FindingStatus = (typeof findingStatuses)[number];

export const findingTypes = [
  'DOCUMENT_CODE',
  'LANGUAGE_PRESENCE',
  'LANGUAGE_COVERAGE',
  'SECTION_MISSING',
  'SECTION_LANGUAGE_MISSING',
  'SECTION_ORDER',
  'LANGUAGE_ORDER',
  'TRANSLATION_GROUP_INCOMPLETE',
  'TABLE_LANGUAGE_MISSING',
  'CELL_LANGUAGE_MISSING',
  'UNKNOWN_LANGUAGE_EXCESS',
  'MIXED_LANGUAGE_EXCESS',
  'OCR_CONFIDENCE',
  'EXTRACTION_QUALITY',
  'STRUCTURE',
  'MANUAL',
] as const;

export type FindingType = (typeof findingTypes)[number];

export interface FindingReference {
  id: string;
  code: string;
  name: string;
}

export interface FindingHistoryEntry {
  id: string;
  action: string;
  previousStatus: FindingStatus | null;
  newStatus: FindingStatus;
  comment: string | null;
  reason: string | null;
  actor: DocumentUserSummary | null;
  createdAt: string;
}

export interface Finding {
  id: string;
  complianceRunId: string | null;
  documentId: string;
  documentRevisionId: string;
  documentFileId: string;
  validationRuleId: string | null;
  document: ComplianceDocumentSummary | null;
  revision: ComplianceRevisionSummary | null;
  validationRule: FindingReference | null;
  findingCode: string;
  findingType: FindingType;
  severity: FindingSeverity;
  status: FindingStatus;
  title: string;
  description: string;
  recommendation: string | null;
  containerId: string | null;
  detectedSectionId: string | null;
  sectionCode: string | null;
  translationGroupId: string | null;
  extractedBlockId: string | null;
  ocrBlockId: string | null;
  pageNumber: number | null;
  worksheetName: string | null;
  cellCoordinate: string | null;
  sourceReference: string | null;
  location: Record<string, unknown> | null;
  languageCode: RequiredLanguageCode | null;
  expectedValue: unknown;
  actualValue: unknown;
  metrics: Record<string, unknown> | null;
  isSystemGenerated: boolean;
  isRepeat: boolean;
  previousFindingId: string | null;
  assignedTo: DocumentUserSummary | null;
  reviewedBy: DocumentUserSummary | null;
  reviewedAt: string | null;
  reviewComment: string | null;
  resolvedBy: DocumentUserSummary | null;
  resolvedAt: string | null;
  resolutionComment: string | null;
  falsePositiveBy: DocumentUserSummary | null;
  falsePositiveAt: string | null;
  falsePositiveReason: string | null;
  acceptedRiskBy?: DocumentUserSummary | null;
  acceptedRiskAt?: string | null;
  acceptedRiskReason?: string | null;
  acceptedRiskExpiryDate?: string | null;
  reopenedBy: DocumentUserSummary | null;
  reopenedAt: string | null;
  reopenReason: string | null;
  history: FindingHistoryEntry[];
  createdAt: string;
  updatedAt: string;
}

export type FindingListItem = Omit<
  Finding,
  | 'expectedValue'
  | 'actualValue'
  | 'metrics'
  | 'history'
  | 'reviewComment'
  | 'resolutionComment'
  | 'falsePositiveReason'
  | 'reopenReason'
>;

export interface FindingListParams {
  search?: string;
  departmentId?: string;
  documentId?: string;
  revisionId?: string;
  complianceRunId?: string;
  detectedSectionId?: string;
  findingCode?: string;
  findingType?: FindingType;
  severity?: FindingSeverity;
  status?: FindingStatus;
  languageCode?: RequiredLanguageCode;
  section?: string;
  assignedTo?: string;
  createdBySystem?: boolean;
  createdFrom?: string;
  createdTo?: string;
  page: number;
  pageSize: number;
  sortBy?: string;
  sortOrder?: SortOrder;
}

export type FindingList = PaginatedData<FindingListItem>;

export interface ManualFindingRequest {
  documentId: string;
  documentRevisionId: string;
  documentFileId: string;
  severity: FindingSeverity;
  title: string;
  description: string;
  recommendation?: string | null;
  sourceReference?: string | null;
  pageNumber?: number | null;
  worksheetName?: string | null;
  cellCoordinate?: string | null;
}

export interface FindingUpdateRequest {
  severity?: FindingSeverity;
  title?: string;
  description?: string;
  recommendation?: string | null;
}

export interface FindingReviewRequest {
  comment: string;
}

export interface FindingResolveRequest {
  comment: string;
}

export interface FindingReturnToOpenRequest {
  comment: string;
}

export interface FindingFalsePositiveRequest {
  reason: string;
}

export interface FindingAcceptRiskRequest {
  reason: string;
  expiryDate: string;
}

export interface FindingReopenRequest {
  reason: string;
}

export interface FindingAssignRequest {
  assignedTo: string;
}

export type FindingBulkActionRequest =
  | {
      action: 'ASSIGN';
      findingIds: string[];
      assignedTo: string;
    }
  | {
      action: 'REVIEW';
      findingIds: string[];
      comment: string;
    };

export interface FindingBulkActionResult {
  action: FindingBulkActionRequest['action'];
  processedCount: number;
  findingIds: string[];
}

export interface FindingDownload {
  blob: Blob;
  fileName: string | null;
}

export type FindingExportFormat = 'json' | 'xlsx';

export interface FindingsReportSummary {
  totalFindings: number;
  open: number;
  inReview: number;
  resolved: number;
  critical: number;
  major: number;
  minor: number;
  information: number;
  falsePositive: number;
  acceptedRisk: number;
  byDepartment: Array<{ label: string; count: number }>;
  byType: Array<{ label: string; count: number }>;
  bySeverity: Array<{ label: FindingSeverity; count: number }>;
  trend: Array<{ period: string; count: number }>;
}

export interface FindingsReport {
  summary: FindingsReportSummary;
  findings: FindingList;
}

export const findingActionTransitions: Readonly<
  Record<
    FindingStatus,
    readonly (
      | 'review'
      | 'return-to-open'
      | 'resolve'
      | 'false-positive'
      | 'accept-risk'
      | 'reopen'
      | 'assign'
    )[]
  >
> = {
  OPEN: ['review', 'resolve', 'false-positive', 'accept-risk', 'assign'],
  IN_REVIEW: ['return-to-open', 'resolve', 'false-positive', 'accept-risk', 'assign'],
  RESOLVED: ['reopen', 'assign'],
  CLOSED: ['assign'],
  FALSE_POSITIVE: ['reopen', 'assign'],
  ACCEPTED_RISK: ['reopen', 'assign'],
  REOPENED: ['review', 'resolve', 'false-positive', 'accept-risk', 'assign'],
};
