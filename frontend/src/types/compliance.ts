import type { DocumentUserSummary } from './document';
import type { PaginatedData, SortOrder } from './masterData';

export const complianceStatuses = [
  'COMPLIANT',
  'PARTIALLY_COMPLIANT',
  'NON_COMPLIANT',
  'NEEDS_REVIEW',
  'NOT_EVALUATED',
] as const;

export type ComplianceStatus = (typeof complianceStatuses)[number];

export const complianceJobStatuses = [
  'QUEUED',
  'LOADING_CONTEXT',
  'DETECTING_SECTIONS',
  'GROUPING_CONTENT',
  'VALIDATING_LANGUAGES',
  'VALIDATING_SECTIONS',
  'VALIDATING_ORDER',
  'VALIDATING_TABLES',
  'GENERATING_FINDINGS',
  'CALCULATING_SCORE',
  'PERSISTING',
  'COMPLETED',
  'PARTIALLY_COMPLETED',
  'FAILED',
  'CANCEL_REQUESTED',
  'CANCELLED',
] as const;

export type ComplianceJobStatus = (typeof complianceJobStatuses)[number];

export const terminalComplianceJobStatuses = [
  'COMPLETED',
  'PARTIALLY_COMPLETED',
  'FAILED',
  'CANCELLED',
] as const satisfies readonly ComplianceJobStatus[];

export const activeComplianceJobStatuses = [
  'QUEUED',
  'LOADING_CONTEXT',
  'DETECTING_SECTIONS',
  'GROUPING_CONTENT',
  'VALIDATING_LANGUAGES',
  'VALIDATING_SECTIONS',
  'VALIDATING_ORDER',
  'VALIDATING_TABLES',
  'GENERATING_FINDINGS',
  'CALCULATING_SCORE',
  'PERSISTING',
  'CANCEL_REQUESTED',
] as const satisfies readonly ComplianceJobStatus[];

export type ComplianceJobType =
  'INITIAL_VALIDATION' | 'REVALIDATION' | 'MANUAL_VALIDATION';

export type ComplianceRunStatus = 'COMPLETED' | 'PARTIALLY_COMPLETED' | 'FAILED';
export type RequiredLanguageCode = 'id' | 'en' | 'zh';
export type LanguagePresenceStatus =
  'PRESENT' | 'NOT_PRESENT' | 'INSUFFICIENT_EVIDENCE' | 'MIXED_ONLY';

export interface ComplianceDocumentSummary {
  id: string;
  baseDocumentCode: string;
  title: string;
  departmentId: string;
  departmentName?: string | null;
}

export interface ComplianceRevisionSummary {
  id: string;
  revisionCode: string;
  fullDocumentCode: string;
}

export interface ComplianceFileSummary {
  id: string;
  filename: string;
  fileExtension?: string;
}

export interface ComplianceRuleSummary {
  id: string;
  code: string;
  name: string;
  version?: number;
}

export interface ComplianceStartRequest {
  documentFileId: string;
  extractionRunId?: string | null;
  ocrRunId?: string | null;
  languageDetectionRunId?: string | null;
  validationRuleId?: string | null;
  force?: boolean;
}

export interface ComplianceQueuedResult {
  jobId: string;
  status: ComplianceJobStatus;
  progress: number;
  documentFileId: string;
  runId: string | null;
  reusedExistingResult: boolean;
}

export interface ComplianceJobResultSummary {
  runId: string | null;
  complianceStatus: ComplianceStatus | null;
  complianceScore: number | null;
  totalFindings: number;
  criticalFindings: number;
  majorFindings: number;
  minorFindings: number;
}

export interface ComplianceJob {
  id: string;
  documentId: string;
  documentRevisionId: string;
  documentFileId: string;
  document: ComplianceDocumentSummary | null;
  revision: ComplianceRevisionSummary | null;
  file: ComplianceFileSummary | null;
  validationRule: ComplianceRuleSummary | null;
  jobType: ComplianceJobType;
  status: ComplianceJobStatus;
  progress: number;
  currentStage: string | null;
  requestedBy: DocumentUserSummary | null;
  requestedAt: string;
  startedAt: string | null;
  completedAt: string | null;
  failedAt: string | null;
  cancelledAt: string | null;
  attemptNumber: number;
  maximumAttempts: number;
  errorCode: string | null;
  errorMessage: string | null;
  resultSummary: ComplianceJobResultSummary | null;
}

export interface ComplianceCancelResult {
  id: string;
  status: ComplianceJobStatus;
  progress: number;
  currentStage: string | null;
  cancelledAt: string | null;
}

export interface ComplianceJobListParams {
  search?: string;
  departmentId?: string;
  documentId?: string;
  revisionId?: string;
  documentFileId?: string;
  validationRuleId?: string;
  complianceStatus?: ComplianceStatus;
  status?: ComplianceJobStatus | readonly ComplianceJobStatus[];
  requestedBy?: string;
  requestedFrom?: string;
  requestedTo?: string;
  page: number;
  pageSize: number;
  sortBy?: 'requestedAt' | 'completedAt' | 'status' | 'progress';
  sortOrder?: SortOrder;
}

export type ComplianceJobList = PaginatedData<ComplianceJob>;

export interface ComplianceRun {
  id: string;
  complianceJobId: string;
  documentId: string;
  documentRevisionId: string;
  documentFileId: string;
  extractionRunId: string;
  ocrRunId: string | null;
  languageDetectionRunId: string;
  validationRuleId: string;
  document: ComplianceDocumentSummary | null;
  revision: ComplianceRevisionSummary | null;
  file: ComplianceFileSummary | null;
  validationRule: ComplianceRuleSummary | null;
  ruleSnapshot: Record<string, unknown>;
  sourceContentHash: string;
  status: ComplianceRunStatus;
  complianceStatus: ComplianceStatus;
  complianceScore: number | null;
  maximumScore: number;
  documentCodeScore: number;
  languagePresenceScore: number;
  languageCoverageScore: number;
  sectionCompletenessScore: number;
  languageOrderScore: number;
  translationGroupScore: number;
  tableCompletenessScore: number;
  totalFindings: number;
  criticalFindings: number;
  majorFindings: number;
  minorFindings: number;
  informationFindings: number;
  openFindings: number;
  requiredLanguages: RequiredLanguageCode[];
  detectedLanguages: RequiredLanguageCode[];
  missingLanguages: RequiredLanguageCode[];
  requiredSections: string[];
  detectedSections: string[];
  missingSections: string[];
  warnings: string[];
  metrics: Record<string, unknown>;
  startedAt: string;
  completedAt: string | null;
  requestedBy: DocumentUserSummary | null;
  createdAt: string;
}

export interface LanguageComplianceMetric {
  languageCode: RequiredLanguageCode;
  presence: LanguagePresenceStatus;
  blockCoverage: number;
  characterCoverage: number;
  minimumBlockCoverage: number | null;
  minimumCharacterCoverage: number | null;
  averageConfidence: number | null;
  findingCount: number;
}

export interface TranslationGroupSummary {
  total: number;
  complete: number;
  incomplete: number;
  lowConfidence?: number;
}

export interface ComplianceFindingSummary {
  total: number;
  critical: number;
  major: number;
  minor: number;
  information: number;
  open?: number;
}

export interface ComplianceSummary {
  runId: string;
  status: ComplianceRunStatus;
  complianceStatus: ComplianceStatus;
  complianceScore: number | null;
  requiredLanguages: RequiredLanguageCode[];
  languagePresence: Record<RequiredLanguageCode, LanguagePresenceStatus>;
  languageCoverage: Record<RequiredLanguageCode, number>;
  languageMetrics?: LanguageComplianceMetric[];
  missingLanguages?: RequiredLanguageCode[];
  requiredSections: number;
  detectedSections: number;
  completeSections: number;
  missingSections?: string[];
  translationGroups: TranslationGroupSummary;
  findings: ComplianceFindingSummary;
  warnings: string[];
  prerequisiteErrors?: string[];
}

export interface ScoreComponent {
  earned: number;
  maximum: number;
}

export interface ComplianceScoreBreakdown {
  documentCode: ScoreComponent;
  languagePresence: ScoreComponent;
  languageCoverage: ScoreComponent;
  sectionCompleteness: ScoreComponent;
  languageOrder: ScoreComponent;
  translationGroups: ScoreComponent;
  tableCompleteness: ScoreComponent;
  penalties: {
    major: number;
    minor: number;
    critical?: number;
  };
  scoreCap?: number | null;
  scoreCapReason?: string | null;
  finalScore: number | null;
}

export interface SectionLanguageResult {
  id: string;
  detectedSectionId: string;
  languageCode: RequiredLanguageCode;
  presenceStatus: LanguagePresenceStatus;
  blockCount: number;
  characterCount: number;
  coveragePercentage: number;
  averageConfidence: number | null;
  firstBlockId: string | null;
  lastBlockId: string | null;
  metrics: Record<string, unknown>;
  createdAt: string;
}

export interface DetectedSection {
  id: string;
  complianceRunId: string;
  sectionDefinitionId: string | null;
  canonicalCode: string;
  containerId: string | null;
  startBlockId: string | null;
  endBlockId: string | null;
  headingBlockId: string | null;
  headingText: string;
  headingLanguageCode: RequiredLanguageCode | 'mixed' | 'unknown';
  matchType: string;
  matchConfidence: number;
  sectionOrder: number;
  isRequired: boolean;
  isComplete: boolean;
  languagePresence: Partial<Record<RequiredLanguageCode, LanguagePresenceStatus>>;
  languageResults: SectionLanguageResult[];
  metrics: Record<string, unknown>;
  findingCount: number;
  createdAt: string;
}

export interface ComplianceResultListParams {
  page: number;
  pageSize: number;
}

export type DetectedSectionList = PaginatedData<DetectedSection>;

export type TranslationGroupType =
  | 'HEADING_GROUP'
  | 'PARAGRAPH_GROUP'
  | 'TABLE_ROW_GROUP'
  | 'TABLE_CELL_GROUP'
  | 'XLSX_ROW_GROUP'
  | 'PDF_POSITIONAL_GROUP'
  | 'MANUAL_GROUP';

export interface TranslationGroupMember {
  id: string;
  translationGroupId: string;
  languageCode: RequiredLanguageCode | 'mixed' | 'unknown' | 'other';
  sourceType: string;
  extractedBlockId: string | null;
  ocrBlockId: string | null;
  languageBlockResultId: string | null;
  blockOrder: number;
  textSnapshot: string | null;
  confidence: number;
  position: Record<string, unknown> | null;
  createdAt: string;
}

export interface TranslationGroup {
  id: string;
  complianceRunId: string;
  containerId: string | null;
  detectedSectionId: string | null;
  sectionCode?: string | null;
  groupIndex: number;
  groupType: TranslationGroupType;
  startBlockOrder: number;
  endBlockOrder: number;
  sourceReference: string;
  expectedLanguages: RequiredLanguageCode[];
  detectedLanguages: RequiredLanguageCode[];
  languageOrder: RequiredLanguageCode[];
  actualLanguageOrder?: RequiredLanguageCode[];
  isComplete: boolean;
  isOrderValid: boolean;
  confidence: number;
  metrics: Record<string, unknown>;
  members: TranslationGroupMember[];
  findingCount: number;
  createdAt: string;
}

export interface TranslationGroupListParams extends ComplianceResultListParams {
  isComplete?: boolean;
  isOrderValid?: boolean;
  lowConfidence?: boolean;
  detectedSectionId?: string;
  containerId?: string;
}

export type TranslationGroupList = PaginatedData<TranslationGroup>;

export interface ComplianceHistoryParams {
  page: number;
  pageSize: number;
}

export type ComplianceHistory = PaginatedData<ComplianceRun>;

export interface ComplianceRevalidateRequest {
  reason: string;
  validationRuleId?: string | null;
}

export interface ComplianceComparison {
  currentRunId: string;
  previousRunId: string;
  scoreChange: number;
  previousStatus: ComplianceStatus;
  currentStatus: ComplianceStatus;
  languagesAdded: RequiredLanguageCode[];
  languagesRemoved: RequiredLanguageCode[];
  sectionsAdded: string[];
  sectionsRemoved: string[];
  newFindings: number;
  resolvedCandidates: number;
  repeatedFindings: number;
  translationGroupCompletenessChange: number;
}

export type ComplianceExportFormat = 'json' | 'xlsx';

export interface ComplianceDownload {
  blob: Blob;
  fileName: string | null;
}

export interface ComplianceOverviewParams {
  dateFrom?: string;
  dateTo?: string;
  departmentId?: string;
  sectionId?: string;
  documentTypeId?: string;
  validationRuleId?: string;
  complianceStatus?: ComplianceStatus;
}

export interface ComplianceBreakdownItem {
  label: string;
  total: number;
  compliant: number;
  partiallyCompliant: number;
  nonCompliant: number;
  needsReview: number;
  notEvaluated: number;
}

export interface ComplianceTrendItem {
  period: string;
  score: number;
  validated: number;
}

export interface ComplianceOverview {
  totalValidatedDocuments: number;
  compliant: number;
  partiallyCompliant: number;
  nonCompliant: number;
  needsReview: number;
  notEvaluated: number;
  openCriticalFindings: number;
  openMajorFindings: number;
  byDepartment: ComplianceBreakdownItem[];
  byDocumentType: ComplianceBreakdownItem[];
  trend: ComplianceTrendItem[];
  findingsBySeverity: Record<'critical' | 'major' | 'minor' | 'information', number>;
  missingLanguages: Array<{ languageCode: RequiredLanguageCode; count: number }>;
  missingSections: Array<{ canonicalCode: string; count: number }>;
}

export interface ComplianceReportItem {
  runId: string;
  documentId: string;
  documentFileId: string;
  documentCode: string;
  title: string;
  department: string;
  section: string | null;
  documentType: string;
  revision: string;
  validationRule: string;
  languagePresence: Record<RequiredLanguageCode, LanguagePresenceStatus>;
  sectionCompleteness: number;
  languageOrderValid: boolean | null;
  score: number | null;
  complianceStatus: ComplianceStatus;
  criticalFindings: number;
  majorFindings: number;
  lastValidated: string;
}

export interface ComplianceReportParams extends ComplianceOverviewParams {
  search?: string;
  page: number;
  pageSize: number;
  sortBy?: string;
  sortOrder?: SortOrder;
}

export type ComplianceReport = PaginatedData<ComplianceReportItem>;

export const isTerminalComplianceJobStatus = (status: ComplianceJobStatus): boolean =>
  terminalComplianceJobStatuses.includes(
    status as (typeof terminalComplianceJobStatuses)[number],
  );

export const isActiveComplianceJobStatus = (status: ComplianceJobStatus): boolean =>
  activeComplianceJobStatuses.includes(
    status as (typeof activeComplianceJobStatuses)[number],
  );
