import type { GlossaryLanguageCode, GlossarySeverity } from './glossary';
import type { PaginatedData } from './masterData';

export const glossaryValidationJobStatuses = [
  'QUEUED',
  'LOADING_CONTEXT',
  'MATCHING_TERMS',
  'VALIDATING_TERMS',
  'GENERATING_FINDINGS',
  'PERSISTING',
  'COMPLETED',
  'PARTIALLY_COMPLETED',
  'FAILED',
  'CANCEL_REQUESTED',
  'CANCELLED',
] as const;

export type GlossaryValidationJobStatus =
  (typeof glossaryValidationJobStatuses)[number];
export type GlossaryValidationRunStatus =
  'COMPLETED' | 'PARTIALLY_COMPLETED' | 'FAILED';
export type GlossaryValidationJobType = 'INITIAL' | 'REVALIDATION' | 'MANUAL';

export const terminalGlossaryValidationJobStatuses: readonly GlossaryValidationJobStatus[] =
  ['COMPLETED', 'PARTIALLY_COMPLETED', 'FAILED', 'CANCELLED'];

export const isTerminalGlossaryValidationJobStatus = (
  status: GlossaryValidationJobStatus,
): boolean => terminalGlossaryValidationJobStatuses.includes(status);

export interface GlossaryValidationRequest {
  documentFileId: string;
  complianceRunId?: string | null;
  profileIds?: readonly string[];
  force?: boolean;
}

export interface GlossaryValidationQueuedResult {
  jobId: string;
  runId: string;
  status: GlossaryValidationJobStatus;
  progress: number;
  documentFileId: string;
  reusedExistingResult: boolean;
}

export interface GlossaryValidationJobListParams {
  page: number;
  pageSize: number;
  status?: GlossaryValidationJobStatus | readonly GlossaryValidationJobStatus[];
  departmentId?: string;
  search?: string;
}

export interface GlossaryValidationRun {
  id: string;
  jobId: string;
  documentId: string;
  documentRevisionId: string;
  documentFileId: string;
  complianceRunId: string | null;
  languageDetectionRunId: string;
  glossaryProfileIds: readonly string[];
  profileSnapshots: readonly Readonly<Record<string, unknown>>[];
  jobType: GlossaryValidationJobType;
  status: GlossaryValidationJobStatus;
  progress: number;
  currentStage: string | null;
  sourceContentHash: string;
  totalTerms: number;
  matchedTerms: number;
  preferredTermMatches: number;
  forbiddenTermMatches: number;
  missingRequiredTranslations: number;
  inconsistentTerms: number;
  exceptionAppliedCount: number;
  totalFindings: number;
  metrics: Readonly<Record<string, unknown>>;
  warnings: readonly (string | Readonly<Record<string, unknown>>)[];
  errorCode: string | null;
  errorMessage: string | null;
  requestedBy: string | null;
  requestedAt: string;
  startedAt: string | null;
  completedAt: string | null;
  failedAt: string | null;
  cancelRequestedAt: string | null;
  cancelledAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export type GlossaryValidationJob = GlossaryValidationRun;
export type GlossaryValidationJobList = PaginatedData<GlossaryValidationJob>;

export interface GlossaryValidationSummary {
  runId: string;
  status: GlossaryValidationJobStatus;
  totalTerms: number;
  matchedTerms: number;
  preferredTermMatches: number;
  forbiddenTermMatches: number;
  missingRequiredTranslations: number;
  inconsistentTerms: number;
  exceptionAppliedCount: number;
  totalFindings: number;
  matchCount: number;
  languageCounts: Readonly<Record<string, number>>;
  findingCounts: Readonly<Record<string, number>>;
  metrics: Readonly<Record<string, unknown>>;
  warnings: readonly (string | Readonly<Record<string, unknown>>)[];
  termsEvaluated?: number;
  preferredMatches?: number;
  forbiddenMatches?: number;
  missingTranslations?: number;
  exceptionsApplied?: number;
  findings?: number;
}

export interface GlossaryMatch {
  id: string;
  glossaryValidationRunId: string;
  glossaryTermId: string;
  glossaryTranslationId: string | null;
  glossaryVariantId: string | null;
  termCode?: string;
  conceptName?: string;
  languageCode: GlossaryLanguageCode;
  sourceType: string;
  extractedBlockId: string | null;
  ocrBlockId: string | null;
  containerId: string | null;
  detectedSectionId: string | null;
  sectionName?: string | null;
  sourceReference: string;
  matchedText: string;
  normalisedMatchedText: string;
  contextSnippet?: string | null;
  startOffset: number;
  endOffset: number;
  matchType: string;
  isPreferred: boolean;
  isForbidden: boolean;
  exceptionId: string | null;
  metadata: Readonly<Record<string, unknown>>;
  findingId?: string | null;
  findingCode?: string | null;
  findingSeverity?: GlossarySeverity | null;
  createdAt: string;
}

export interface GlossaryMatchListParams {
  page: number;
  pageSize: number;
  search?: string;
  languageCode?: GlossaryLanguageCode;
  termId?: string;
  isPreferred?: boolean;
  isForbidden?: boolean;
  hasException?: boolean;
  findingCode?: string;
}

export type GlossaryMatchList = PaginatedData<GlossaryMatch>;

export interface GlossaryValidationFinding {
  id: string;
  findingCode: string;
  severity: GlossarySeverity;
  status: string;
  title: string;
  description: string;
  recommendation: string;
  glossaryTermId: string;
  languageCode?: GlossaryLanguageCode | null;
  sourceReference?: string | null;
  extractedBlockId: string | null;
  ocrBlockId: string | null;
  translationGroupId: string | null;
  exceptionId: string | null;
  metrics: Readonly<Record<string, unknown>>;
  isRepeat: boolean;
  previousFindingId: string | null;
  createdAt: string;
}

export type GlossaryValidationFindingList = PaginatedData<GlossaryValidationFinding>;

export interface GlossaryHistoryParams {
  page: number;
  pageSize: number;
}

export type GlossaryValidationHistory = PaginatedData<GlossaryValidationRun>;
