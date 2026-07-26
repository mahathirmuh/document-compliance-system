import type { DocumentReference, DocumentUserSummary } from './document';
import type { PaginatedData } from './masterData';

export const similarityCategories = [
  'HIGH',
  'ACCEPTABLE',
  'NEEDS_REVIEW',
  'LOW',
  'NOT_EVALUATED',
] as const;

export type SimilarityCategory = (typeof similarityCategories)[number];

export const similarityJobStatuses = [
  'QUEUED',
  'LOADING_CONTEXT',
  'LOADING_MODEL',
  'ALIGNING_GROUPS',
  'ENCODING',
  'CALCULATING_SIMILARITY',
  'CHECKING_CONSISTENCY',
  'AGGREGATING',
  'GENERATING_FINDINGS',
  'PERSISTING',
  'COMPLETED',
  'PARTIALLY_COMPLETED',
  'FAILED',
  'CANCEL_REQUESTED',
  'CANCELLED',
] as const;

export type SimilarityJobStatus = (typeof similarityJobStatuses)[number];
export type SimilarityJobType =
  'INITIAL_SIMILARITY' | 'REANALYSIS' | 'MANUAL_SIMILARITY';
export type SimilarityRunStatus = 'COMPLETED' | 'PARTIALLY_COMPLETED' | 'FAILED';
export type SimilarityResultStatus =
  | 'COMPLETED'
  | 'SKIPPED_TOO_SHORT'
  | 'SKIPPED_UNSUPPORTED'
  | 'FAILED'
  | 'INSUFFICIENT_CONTENT';
export type ConsistencyStatus =
  | 'MATCH'
  | 'MISMATCH'
  | 'AMBIGUOUS'
  | 'NOT_APPLICABLE'
  | 'POTENTIALLY_EQUIVALENT'
  | 'POSSIBLE_NEGATION_MISMATCH';
export type SupportedLanguageCode = 'id' | 'en' | 'zh';
export type SimilarityExportFormat = 'json' | 'xlsx';

export const terminalSimilarityJobStatuses: readonly SimilarityJobStatus[] = [
  'COMPLETED',
  'PARTIALLY_COMPLETED',
  'FAILED',
  'CANCELLED',
];

export const isTerminalSimilarityJobStatus = (status: SimilarityJobStatus): boolean =>
  terminalSimilarityJobStatuses.includes(status);

export const isActiveSimilarityJobStatus = (status: SimilarityJobStatus): boolean =>
  !isTerminalSimilarityJobStatus(status);

export interface SimilarityStartRequest {
  documentFileId: string;
  complianceRunId?: string | null;
  languageDetectionRunId?: string | null;
  force?: boolean;
}

export interface SimilarityRerunRequest {
  reason: string;
}

export interface SimilarityResultSummary {
  runId?: string | null;
  averageSimilarity?: number | null;
  minimumSimilarity?: number | null;
  translationGroups?: number;
  lowGroups?: number;
  numberMismatches?: number;
  dateMismatches?: number;
  measurementMismatches?: number;
  referenceMismatches?: number;
  negationMismatches?: number;
  analysedGroups?: number;
  lowSimilarityGroups?: number;
  findingCount?: number;
}

export interface SimilarityJob {
  id: string;
  documentId: string;
  documentRevisionId: string;
  documentFileId: string;
  complianceRunId: string | null;
  languageDetectionRunId: string | null;
  jobType: SimilarityJobType;
  status: SimilarityJobStatus;
  progress: number;
  currentStage: string | null;
  provider: string;
  providerName?: string | null;
  modelName: string;
  sourceContentHash: string | null;
  attemptNumber: number;
  maximumAttempts: number;
  retryCount?: number;
  requestedBy: DocumentUserSummary | null;
  requestedAt: string;
  startedAt: string | null;
  completedAt: string | null;
  failedAt: string | null;
  cancelledAt: string | null;
  errorCode: string | null;
  errorMessage: string | null;
  errorDetails: Readonly<Record<string, unknown>> | null;
  resultSummary: SimilarityResultSummary | null;
  createdAt: string;
  updatedAt: string;
  document?: {
    id: string;
    baseDocumentCode: string;
    title: string;
    departmentId: string;
  } | null;
  revision?: {
    id: string;
    revisionCode: string;
    fullDocumentCode: string;
  } | null;
  file?: {
    id: string;
    filename: string;
    fileExtension: string;
  } | null;
}

export interface SimilarityJobListParams {
  page: number;
  pageSize: number;
  status?: SimilarityJobStatus | readonly SimilarityJobStatus[];
  departmentId?: string;
  search?: string;
  requestedFrom?: string;
  requestedTo?: string;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
}

export type SimilarityJobList = PaginatedData<SimilarityJob>;

export interface SimilarityQueuedResult {
  id: string;
  jobId?: string;
  status: SimilarityJobStatus;
  progress: number;
  documentFileId: string;
  runId: string | null;
  reusedExistingResult: boolean;
  message?: string;
}

export interface SimilarityCancelResult {
  id: string;
  status: SimilarityJobStatus;
  progress: number;
  currentStage: string | null;
  cancelledAt: string | null;
}

export interface LanguagePairSummary {
  sourceLanguage: SupportedLanguageCode;
  targetLanguage: SupportedLanguageCode;
  averageSimilarity: number | null;
  minimumSimilarity: number | null;
  groupsAnalysed: number;
  high: number;
  acceptable: number;
  needsReview: number;
  low: number;
  notEvaluated: number;
}

export interface SimilarityRun {
  id: string;
  similarityJobId: string | null;
  documentId: string;
  documentRevisionId: string;
  documentFileId: string;
  complianceRunId: string | null;
  languageDetectionRunId: string | null;
  providerName?: string;
  provider: string;
  modelName: string;
  modelVersion: string | null;
  status: SimilarityRunStatus;
  sourceContentHash: string;
  translationGroupCount: number;
  eligibleGroupCount: number;
  analysedGroupCount: number;
  skippedGroupCount: number;
  failedGroupCount: number;
  totalGroups?: number;
  evaluatedGroups?: number;
  skippedGroups?: number;
  failedGroups?: number;
  averageSimilarity: number | null;
  minimumSimilarity: number | null;
  maximumSimilarity: number | null;
  idEnAverageSimilarity: number | null;
  idZhAverageSimilarity: number | null;
  enZhAverageSimilarity: number | null;
  highSimilarityGroups: number;
  reviewSimilarityGroups: number;
  lowSimilarityGroups: number;
  unavailableSimilarityGroups: number;
  highCount?: number;
  acceptableCount?: number;
  needsReviewCount?: number;
  lowCount?: number;
  notEvaluatedCount?: number;
  numberMismatchCount: number;
  dateMismatchCount: number;
  measurementMismatchCount: number;
  referenceMismatchCount: number;
  negationMismatchCount: number;
  languagePairSummaries?: readonly LanguagePairSummary[];
  warnings: readonly (string | Readonly<Record<string, unknown>>)[];
  metrics: Readonly<Record<string, unknown>>;
  requestedBy: DocumentUserSummary | null;
  startedAt: string | null;
  completedAt: string | null;
  createdAt: string;
  document?: {
    id: string;
    baseDocumentCode: string;
    title: string;
    departmentId: string;
  } | null;
  revision?: {
    id: string;
    revisionCode: string;
    fullDocumentCode: string;
  } | null;
  file?: {
    id: string;
    filename: string;
    fileExtension: string;
  } | null;
}

export interface SimilaritySummary {
  runId: string;
  status: SimilarityRunStatus;
  averageSimilarity: number | null;
  minimumSimilarity: number | null;
  maximumSimilarity: number | null;
  translationGroupCount: number;
  eligibleGroupCount: number;
  analysedGroupCount: number;
  skippedGroupCount: number;
  failedGroupCount: number;
  categories: Readonly<Record<string, number>>;
  pairAverages: Readonly<Record<string, number | null>>;
  mismatches: Readonly<Record<string, number>>;
  sectionCount: number;
  groupsAnalysed?: number;
  high?: number;
  acceptable?: number;
  needsReview?: number;
  low?: number;
  notEvaluated?: number;
  numberMismatches?: number;
  dateMismatches?: number;
  measurementMismatches?: number;
  referenceMismatches?: number;
  negationMismatches?: number;
  findingCount: number;
  qualityStatus?: QualityStatus;
  warnings: readonly (string | Readonly<Record<string, unknown>>)[];
  languagePairs?: readonly LanguagePairSummary[];
}

export type QualityStatus =
  'HIGH_QUALITY' | 'ACCEPTABLE' | 'NEEDS_REVIEW' | 'LOW_QUALITY' | 'NOT_EVALUATED';

export interface ConsistencyDetail {
  sourceValues: readonly string[];
  targetValues: readonly string[];
  missingFromSource?: readonly string[];
  missingFromTarget?: readonly string[];
  warning?: string | null;
}

export interface TranslationSimilarityResult {
  id: string;
  similarityRunId: string;
  translationGroupId: string | null;
  detectedSectionId: string | null;
  sectionCode?: string | null;
  sectionName?: string | null;
  containerId: string | null;
  sourceReference: string | null;
  groupLabel?: string | null;
  sourceLanguageCode: SupportedLanguageCode;
  targetLanguageCode: SupportedLanguageCode;
  sourceLanguage?: SupportedLanguageCode;
  targetLanguage?: SupportedLanguageCode;
  sourceMemberId: string | null;
  targetMemberId: string | null;
  sourceTextSnippet: string | null;
  targetTextSnippet: string | null;
  sourceTextHash: string;
  targetTextHash: string;
  similarityScore: number | null;
  similarityCategory: SimilarityCategory;
  confidence: number;
  confidenceScore?: number | null;
  structuralGroupConfidence?: number | null;
  ocrConfidence?: number | null;
  analysisStatus: SimilarityResultStatus;
  status?: SimilarityResultStatus;
  sourceCharacterCount: number;
  targetCharacterCount: number;
  lengthRatio: number | null;
  lengthRatioStatus?: ConsistencyStatus;
  numberConsistencyStatus: ConsistencyStatus;
  numberStatus?: ConsistencyStatus;
  numberDetails: Readonly<Record<string, unknown>>;
  dateConsistencyStatus: ConsistencyStatus;
  dateStatus?: ConsistencyStatus;
  dateDetails: Readonly<Record<string, unknown>>;
  measurementConsistencyStatus: ConsistencyStatus;
  measurementStatus?: ConsistencyStatus;
  measurementDetails: Readonly<Record<string, unknown>>;
  referenceConsistencyStatus: ConsistencyStatus;
  referenceStatus?: ConsistencyStatus;
  referenceDetails: Readonly<Record<string, unknown>>;
  negationConsistencyStatus: ConsistencyStatus;
  negationStatus?: ConsistencyStatus;
  negationDetails: Readonly<Record<string, unknown>>;
  chunkCountSource: number;
  chunkCountTarget: number;
  chunkCount?: number;
  findingCount: number;
  relatedFindingIds: readonly string[];
  metrics: Readonly<Record<string, unknown>>;
  warnings: readonly (string | Readonly<Record<string, unknown>>)[];
  createdAt: string;
}

export interface SimilarityResultListParams {
  sectionId?: string;
  sourceLanguage?: SupportedLanguageCode;
  targetLanguage?: SupportedLanguageCode;
  similarityCategory?: SimilarityCategory;
  minimumScore?: number;
  maximumScore?: number;
  hasNumberMismatch?: boolean;
  hasDateMismatch?: boolean;
  hasMeasurementMismatch?: boolean;
  hasReferenceMismatch?: boolean;
  hasNegationMismatch?: boolean;
  findingSeverity?: 'CRITICAL' | 'MAJOR' | 'MINOR' | 'INFO';
  search?: string;
  page: number;
  pageSize: number;
}

export type SimilarityResultList = PaginatedData<TranslationSimilarityResult>;

export interface SectionSimilaritySummary {
  id: string;
  similarityRunId: string;
  detectedSectionId: string | null;
  canonicalSectionCode: string;
  sectionCode?: string | null;
  sectionName?: string | null;
  sectionOrder?: number | null;
  totalGroups: number;
  eligibleGroups: number;
  analysedGroups: number;
  evaluatedGroups?: number;
  averageSimilarity: number | null;
  minimumSimilarity: number | null;
  lowSimilarityGroups: number;
  numberMismatches: number;
  dateMismatches: number;
  measurementMismatches: number;
  referenceMismatches: number;
  negationMismatches: number;
  highCount?: number;
  acceptableCount?: number;
  needsReviewCount?: number;
  lowCount?: number;
  notEvaluatedCount?: number;
  mismatchCount?: number;
  pairwiseSummary: Readonly<Record<string, unknown>>;
  metrics: Readonly<Record<string, unknown>>;
  createdAt: string;
}

export type SectionSimilarityList =
  readonly SectionSimilaritySummary[] | PaginatedData<SectionSimilaritySummary>;

export interface SimilarityHistoryParams {
  page: number;
  pageSize: number;
}

export type SimilarityHistory = PaginatedData<SimilarityRun>;

export interface SimilarityDownload {
  blob: Blob;
  fileName: string | null;
}

export interface SimilarityDocumentReference {
  document: DocumentReference | null;
  revision: DocumentReference | null;
}
