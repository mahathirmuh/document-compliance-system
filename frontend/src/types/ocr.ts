import type { DocumentUserSummary } from './document';
import type { PaginatedData, SortOrder } from './masterData';
import type {
  ExtractionDocumentSummary,
  ExtractionFileSummary,
  ExtractionRevisionSummary,
} from './extraction';

export const ocrJobStatuses = [
  'QUEUED',
  'INSPECTING',
  'RENDERING',
  'PREPROCESSING',
  'RECOGNISING',
  'MERGING',
  'PERSISTING',
  'COMPLETED',
  'PARTIALLY_COMPLETED',
  'FAILED',
  'CANCEL_REQUESTED',
  'CANCELLED',
] as const;

export type OCRJobStatus = (typeof ocrJobStatuses)[number];

export const terminalOCRJobStatuses = [
  'COMPLETED',
  'PARTIALLY_COMPLETED',
  'FAILED',
  'CANCELLED',
] as const satisfies readonly OCRJobStatus[];

export const activeOCRJobStatuses = [
  'QUEUED',
  'INSPECTING',
  'RENDERING',
  'PREPROCESSING',
  'RECOGNISING',
  'MERGING',
  'PERSISTING',
  'CANCEL_REQUESTED',
] as const satisfies readonly OCRJobStatus[];

export const ocrLanguageProfiles = [
  'LATIN',
  'CHINESE_SIMPLIFIED',
  'AUTO_MULTILINGUAL',
] as const;

export type OCRLanguageProfile = (typeof ocrLanguageProfiles)[number];

export const ocrPreprocessingProfiles = ['NONE', 'STANDARD', 'AGGRESSIVE'] as const;

export type OCRPreprocessingProfile = (typeof ocrPreprocessingProfiles)[number];

export type OCRJobType = 'INITIAL_OCR' | 'RE_OCR' | 'MANUAL_PAGE_OCR';
export type OCRRunStatus = 'COMPLETED' | 'PARTIALLY_COMPLETED' | 'FAILED' | 'CANCELLED';
export type OCRPageStatus =
  'COMPLETED' | 'LOW_CONFIDENCE' | 'NO_TEXT_FOUND' | 'FAILED' | 'SKIPPED';

export interface OCRStartRequest {
  documentFileId: string;
  extractionRunId: string;
  languageProfile: OCRLanguageProfile;
  pageNumbers: number[] | null;
  preprocessingProfile: OCRPreprocessingProfile;
  force: boolean;
}

export interface OCRReprocessRequest {
  reason: string;
  pageNumbers: number[] | null;
  languageProfile: OCRLanguageProfile;
  preprocessingProfile: OCRPreprocessingProfile;
}

export interface OCRQueuedResult {
  jobId: string;
  status: OCRJobStatus;
  progress: number;
  pageNumbers: number[];
  documentFileId: string;
  runId: string | null;
}

export interface OCRError {
  code: string;
  message: string;
}

export interface OCRJobListItem {
  id: string;
  document: ExtractionDocumentSummary;
  revision: ExtractionRevisionSummary;
  file: ExtractionFileSummary;
  extractionRunId: string;
  jobType: OCRJobType;
  status: OCRJobStatus;
  progress: number;
  currentStage: string | null;
  languageProfile: OCRLanguageProfile;
  preprocessingProfile: OCRPreprocessingProfile;
  provider: string;
  providerVersion: string | null;
  pageNumbers: number[];
  processedPageNumbers: number[];
  failedPageNumbers: number[];
  requestedBy: DocumentUserSummary | null;
  requestedAt: string;
  startedAt: string | null;
  completedAt: string | null;
  cancelledAt: string | null;
  runId: string | null;
  resultSummary: Record<string, unknown> | null;
}

export interface OCRJob extends OCRJobListItem {
  attemptNumber: number;
  maximumAttempts: number;
  failedAt: string | null;
  error: OCRError | null;
}

export interface OCRJobListParams {
  search?: string;
  departmentId?: string;
  documentId?: string;
  revisionId?: string;
  documentFileId?: string;
  status?: OCRJobStatus | readonly OCRJobStatus[];
  languageProfile?: OCRLanguageProfile;
  requestedBy?: string;
  requestedFrom?: string;
  requestedTo?: string;
  page: number;
  pageSize: number;
  sortBy?: 'requestedAt' | 'completedAt' | 'status' | 'progress';
  sortOrder?: SortOrder;
}

export type OCRJobList = PaginatedData<OCRJobListItem>;

export interface OCRSummary {
  runId: string;
  status: OCRRunStatus;
  pageCountRequested: number;
  pageCountProcessed: number;
  pageCountFailed: number;
  totalBlocks: number;
  totalCharacters: number;
  averageConfidence: number | null;
  minimumConfidence: number | null;
  maximumConfidence: number | null;
  lowConfidenceBlocks: number;
  lowConfidenceThreshold: number;
  reviewConfidenceThreshold: number;
  warnings: string[];
}

export interface OCRRun extends OCRSummary {
  ocrJobId: string;
  document: ExtractionDocumentSummary;
  revision: ExtractionRevisionSummary;
  file: ExtractionFileSummary;
  sourceExtractionRunId: string;
  provider: string;
  providerVersion: string | null;
  languageProfile: OCRLanguageProfile;
  preprocessingProfile: OCRPreprocessingProfile;
  sourceSha256Hash: string;
  renderDpi: number;
  contentHash: string | null;
  metadata: Record<string, unknown> | null;
  startedAt: string;
  completedAt: string | null;
  createdAt: string;
  isLatest: boolean;
}

export interface OCRRunHistoryItem {
  id: string;
  ocrJobId: string;
  sourceExtractionRunId: string;
  status: OCRRunStatus;
  provider: string;
  providerVersion: string | null;
  languageProfile: OCRLanguageProfile;
  preprocessingProfile: OCRPreprocessingProfile;
  summary: OCRSummary;
  requestedBy: DocumentUserSummary | null;
  reOcrReason: string | null;
  completedAt: string | null;
  createdAt: string;
  isLatest: boolean;
}

export interface OCRPageResult {
  id: string;
  ocrRunId: string;
  pageNumber: number;
  status: OCRPageStatus;
  languageProfile: OCRLanguageProfile;
  renderWidth: number;
  renderHeight: number;
  renderDpi: number;
  rotationApplied: number;
  deskewAngle: number | null;
  blockCount: number;
  characterCount: number;
  averageConfidence: number | null;
  minimumConfidence: number | null;
  maximumConfidence: number | null;
  rawText: string;
  normalisedText: string;
  warningCodes: string[];
  contentHash: string | null;
  error: OCRError | null;
  metadata: Record<string, unknown> | null;
  createdAt: string;
}

export interface OCRBoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export type OCRPolygon = readonly (readonly [number, number])[];

export interface OCRBlock {
  id: string;
  ocrRunId: string;
  ocrPageResultId: string;
  pageNumber: number;
  blockOrder: number;
  text: string;
  normalisedText: string;
  confidence: number;
  polygon: OCRPolygon;
  bbox: OCRBoundingBox;
  providerModel: string;
  recognitionProfile: string;
  orientation: number;
  metadata: Record<string, unknown> | null;
  characterCount: number;
  createdAt: string;
}

export interface OCRPageListParams {
  status?: OCRPageStatus;
  page: number;
  pageSize: number;
}

export interface OCRBlockListParams {
  pageNumber?: number;
  minimumConfidence?: number;
  maximumConfidence?: number;
  search?: string;
  page: number;
  pageSize: number;
}

export type OCRPageList = PaginatedData<OCRPageResult>;
export type OCRBlockList = PaginatedData<OCRBlock>;
export type OCRRunHistory = PaginatedData<OCRRunHistoryItem>;

export interface OCRPageDetail {
  page: OCRPageResult;
  blocks: OCRBlock[];
}

export interface OCRHistoryParams {
  page: number;
  pageSize: number;
}

export interface OCRCancelResult {
  id: string;
  status: OCRJobStatus;
  progress: number;
  currentStage: string | null;
  cancelledAt: string | null;
}

export interface OCRDownload {
  blob: Blob;
  fileName: string | null;
}

export const isTerminalOCRStatus = (status: OCRJobStatus): boolean =>
  terminalOCRJobStatuses.includes(status as (typeof terminalOCRJobStatuses)[number]);

export const isActiveOCRStatus = (status: OCRJobStatus): boolean =>
  activeOCRJobStatuses.includes(status as (typeof activeOCRJobStatuses)[number]);

export const getOCRConfidenceCategory = (
  confidence: number,
  lowConfidenceThreshold: number,
  reviewConfidenceThreshold: number,
): 'HIGH' | 'REVIEW' | 'LOW' => {
  if (confidence >= reviewConfidenceThreshold) {
    return 'HIGH';
  }
  return confidence >= lowConfidenceThreshold ? 'REVIEW' : 'LOW';
};
