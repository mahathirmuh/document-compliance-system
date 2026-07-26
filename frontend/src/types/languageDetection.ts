import type { DocumentUserSummary } from './document';
import type { PaginatedData, SortOrder } from './masterData';
import type {
  ExtractionDocumentSummary,
  ExtractionFileSummary,
  ExtractionJobStatus,
  ExtractionRevisionSummary,
} from './extraction';
import type { OCRJobStatus } from './ocr';

export const languageCodes = ['id', 'en', 'zh', 'mixed', 'unknown', 'other'] as const;

export type LanguageCode = (typeof languageCodes)[number];

export const languageDetectionJobStatuses = [
  'QUEUED',
  'LOADING_CONTENT',
  'DETECTING',
  'AGGREGATING',
  'PERSISTING',
  'COMPLETED',
  'PARTIALLY_COMPLETED',
  'FAILED',
  'CANCEL_REQUESTED',
  'CANCELLED',
] as const;

export type LanguageDetectionJobStatus = (typeof languageDetectionJobStatuses)[number];
export type LanguageDetectionDocumentStatus =
  'NOT_STARTED' | LanguageDetectionJobStatus;

export const terminalLanguageDetectionStatuses = [
  'COMPLETED',
  'PARTIALLY_COMPLETED',
  'FAILED',
  'CANCELLED',
] as const satisfies readonly LanguageDetectionJobStatus[];

export const activeLanguageDetectionStatuses = [
  'QUEUED',
  'LOADING_CONTENT',
  'DETECTING',
  'AGGREGATING',
  'PERSISTING',
  'CANCEL_REQUESTED',
] as const satisfies readonly LanguageDetectionJobStatus[];

export type LanguageDetectionRunStatus = 'COMPLETED' | 'PARTIALLY_COMPLETED' | 'FAILED';
export type LanguageSourceType = 'NATIVE_EXTRACTION' | 'OCR';
export type LanguageEligibilityStatus = 'ELIGIBLE' | 'INELIGIBLE';
export type LanguagePresenceStatus =
  'PRESENT' | 'NOT_PRESENT' | 'INSUFFICIENT_EVIDENCE';

export interface LanguageDetectionStartRequest {
  documentFileId: string;
  extractionRunId: string;
  ocrRunId: string | null;
  force: boolean;
}

export interface LanguageRedetectRequest {
  reason: string;
}

export interface LanguageDetectionQueuedResult {
  jobId: string;
  status: LanguageDetectionJobStatus;
  progress: number;
  documentFileId: string;
  extractionRunId: string;
  ocrRunId: string | null;
  runId: string | null;
  reusedExistingResult: boolean;
}

export interface LanguageDetectionError {
  code: string;
  message: string;
}

export interface LanguageDetectionJobListItem {
  id: string;
  document: ExtractionDocumentSummary;
  revision: ExtractionRevisionSummary;
  file: ExtractionFileSummary;
  extractionRunId: string;
  ocrRunId: string | null;
  jobType: 'INITIAL_DETECTION' | 'RE_DETECTION';
  status: LanguageDetectionJobStatus;
  progress: number;
  currentStage: string | null;
  requestedBy: DocumentUserSummary | null;
  requestedAt: string;
  startedAt: string | null;
  completedAt: string | null;
  cancelledAt: string | null;
  runId: string | null;
  resultSummary: Record<string, unknown> | null;
}

export interface LanguageDetectionJob extends LanguageDetectionJobListItem {
  attemptNumber: number;
  maximumAttempts: number;
  failedAt: string | null;
  error: LanguageDetectionError | null;
}

export interface LanguageDetectionJobListParams {
  search?: string;
  departmentId?: string;
  documentId?: string;
  revisionId?: string;
  documentFileId?: string;
  status?: LanguageDetectionJobStatus | readonly LanguageDetectionJobStatus[];
  requestedBy?: string;
  requestedFrom?: string;
  requestedTo?: string;
  page: number;
  pageSize: number;
  sortBy?: 'requestedAt' | 'completedAt' | 'status' | 'progress';
  sortOrder?: SortOrder;
}

export type LanguageDetectionJobList = PaginatedData<LanguageDetectionJobListItem>;

export interface LanguageDetectionDocumentListItem {
  document: ExtractionDocumentSummary;
  revision: ExtractionRevisionSummary;
  file: ExtractionFileSummary;
  extractionStatus: ExtractionJobStatus | null;
  ocrStatus: OCRJobStatus | null;
  languageDetectionStatus: LanguageDetectionJobStatus | null;
  languageProgress: number | null;
  languageCurrentStage: string | null;
  extractionRunId: string | null;
  ocrRunId: string | null;
  languageDetectionRunId: string | null;
  languagePresence: LanguagePresenceSummary | null;
  lastDetected: string | null;
  sourceReady: boolean;
}

export interface LanguageDetectionDocumentListParams {
  search?: string;
  departmentId?: string;
  status?: LanguageDetectionDocumentStatus;
  page: number;
  pageSize: number;
  sortBy?: 'documentCode' | 'filename' | 'uploadedAt';
  sortOrder?: SortOrder;
}

export type LanguageDetectionDocumentList =
  PaginatedData<LanguageDetectionDocumentListItem>;

export interface LanguageScore {
  languageCode: LanguageCode;
  score: number;
}

export interface ScriptStatistics {
  latinCharacterCount: number;
  hanCharacterCount: number;
  digitCount: number;
  punctuationCount: number;
  dominantScript: 'LATIN' | 'HAN' | 'MIXED' | 'NONE';
  hanRatio: number;
}

export interface LanguageCoverageValues {
  id: number;
  en: number;
  zh: number;
  mixed: number;
  unknown: number;
  other: number;
}

export interface LanguageCoverage {
  blockCoverage: LanguageCoverageValues;
  characterCoverage: LanguageCoverageValues;
  preliminary: boolean;
  disclaimer: string;
}

export interface LanguagePresenceSummary {
  id: LanguagePresenceStatus;
  en: LanguagePresenceStatus;
  zh: LanguagePresenceStatus;
}

export interface LanguageAverageConfidence {
  id: number | null;
  en: number | null;
  zh: number | null;
}

export interface LanguageSummary {
  runId: string;
  totalBlocks: number;
  eligibleBlocks: number;
  detectedBlocks: number;
  unknownBlocks: number;
  mixedBlocks: number;
  indonesianBlocks: number;
  englishBlocks: number;
  chineseBlocks: number;
  otherBlocks: number;
  totalCharacters: number;
  indonesianCharacters: number;
  englishCharacters: number;
  chineseCharacters: number;
  mixedCharacters: number;
  unknownCharacters: number;
  averageConfidence: number | null;
  averageConfidenceByLanguage: LanguageAverageConfidence;
  languagePresence: LanguagePresenceSummary;
  coverage: LanguageCoverage;
  preliminaryLabel: string;
}

export interface LanguageDetectionRun extends LanguageSummary {
  documentFileId: string;
  documentId: string;
  documentRevisionId: string;
  extractionRunId: string;
  ocrRunId: string | null;
  jobId: string;
  detectorName: string;
  detectorVersion: string;
  status: LanguageDetectionRunStatus;
  sourceContentHash: string;
  warnings: string[];
  metadata: Record<string, unknown> | null;
  requestedBy: DocumentUserSummary | null;
  startedAt: string;
  completedAt: string;
  createdAt: string;
  isLatest: boolean;
}

export interface LanguageDetectionHistoryItem {
  id: string;
  jobId: string;
  detectorName: string;
  detectorVersion: string;
  status: LanguageDetectionRunStatus;
  sourceContentHash: string;
  totalBlocks: number;
  detectedBlocks: number;
  unknownBlocks: number;
  averageConfidence: number | null;
  requestedBy: DocumentUserSummary | null;
  redetectionReason: string | null;
  completedAt: string;
  isLatest: boolean;
}

export interface LanguageBlockResult {
  id: string;
  extractedBlockId: string | null;
  ocrBlockId: string | null;
  containerId: string | null;
  sourceType: LanguageSourceType;
  sourceReference: string;
  text: string;
  languageCode: LanguageCode;
  primaryLanguageCode: LanguageCode;
  confidence: number;
  sourceConfidence: number | null;
  isMixed: boolean;
  detectedLanguages: LanguageScore[];
  scriptStatistics: ScriptStatistics;
  eligibilityStatus: LanguageEligibilityStatus;
  eligibilityReason: string | null;
  characterCount: number;
  latinCharacterCount: number;
  hanCharacterCount: number;
  wordCount: number;
  metadata: Record<string, unknown> | null;
  createdAt: string;
}

export interface LanguageContainerSummary {
  id: string;
  containerId: string | null;
  containerType: string;
  containerName: string | null;
  containerIndex: number;
  totalBlocks: number;
  eligibleBlocks: number;
  indonesianBlocks: number;
  englishBlocks: number;
  chineseBlocks: number;
  mixedBlocks: number;
  unknownBlocks: number;
  otherBlocks: number;
  indonesianCharacters: number;
  englishCharacters: number;
  chineseCharacters: number;
  mixedCharacters: number;
  unknownCharacters: number;
  dominantLanguage: LanguageCode;
  languagePresence: Record<'id' | 'en' | 'zh', boolean>;
  coverage: LanguageCoverage;
  createdAt: string;
}

export interface LanguageBlockListParams {
  languageCode?: LanguageCode;
  sourceType?: LanguageSourceType;
  containerId?: string;
  minimumConfidence?: number;
  maximumConfidence?: number;
  isMixed?: boolean;
  eligibilityStatus?: LanguageEligibilityStatus;
  search?: string;
  page: number;
  pageSize: number;
}

export interface LanguageContainerListParams {
  page: number;
  pageSize: number;
}

export type LanguageBlockList = PaginatedData<LanguageBlockResult>;
export type LanguageContainerList = PaginatedData<LanguageContainerSummary>;
export type LanguageDetectionHistory = PaginatedData<LanguageDetectionHistoryItem>;

export interface LanguageHistoryParams {
  page: number;
  pageSize: number;
}

export interface LanguageDetectionCancelResult {
  id: string;
  status: LanguageDetectionJobStatus;
  progress: number;
  currentStage: string | null;
  cancelledAt: string | null;
}

export interface LanguageDownload {
  blob: Blob;
  fileName: string | null;
}

export const isTerminalLanguageDetectionStatus = (
  status: LanguageDetectionJobStatus,
): boolean =>
  terminalLanguageDetectionStatuses.includes(
    status as (typeof terminalLanguageDetectionStatuses)[number],
  );

export const isActiveLanguageDetectionStatus = (
  status: LanguageDetectionJobStatus,
): boolean =>
  activeLanguageDetectionStatuses.includes(
    status as (typeof activeLanguageDetectionStatuses)[number],
  );

export const languageLabels: Record<LanguageCode, string> = {
  id: 'Bahasa Indonesia',
  en: 'English',
  zh: '中文 / Mandarin',
  mixed: 'Mixed',
  unknown: 'Unknown',
  other: 'Other',
};
