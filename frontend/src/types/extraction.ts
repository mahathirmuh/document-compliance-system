import type { DocumentUserSummary } from './document';
import type { SupportedDocumentExtension } from './documentFile';
import type { PaginatedData, SortOrder } from './masterData';

export const extractionJobStatuses = [
  'QUEUED',
  'INSPECTING',
  'EXTRACTING',
  'NORMALISING',
  'PERSISTING',
  'COMPLETED',
  'PARTIALLY_COMPLETED',
  'OCR_REQUIRED',
  'FAILED',
  'CANCEL_REQUESTED',
  'CANCELLED',
] as const;

export type ExtractionJobStatus = (typeof extractionJobStatuses)[number];

export const terminalExtractionStatuses = [
  'COMPLETED',
  'PARTIALLY_COMPLETED',
  'OCR_REQUIRED',
  'FAILED',
  'CANCELLED',
] as const satisfies readonly ExtractionJobStatus[];

export const activeExtractionStatuses = [
  'QUEUED',
  'INSPECTING',
  'EXTRACTING',
  'NORMALISING',
  'PERSISTING',
  'CANCEL_REQUESTED',
] as const satisfies readonly ExtractionJobStatus[];

export type ExtractionJobType =
  'INITIAL_EXTRACTION' | 'RE_EXTRACTION' | 'MANUAL_EXTRACTION';

export type ExtractorType = 'PDF' | 'DOCX' | 'XLSX';

export type ExtractionRunStatus = 'COMPLETED' | 'PARTIALLY_COMPLETED' | 'OCR_REQUIRED';

export interface ExtractionDocumentSummary {
  id: string;
  baseDocumentCode: string;
  title: string;
  departmentId: string;
}

export interface ExtractionRevisionSummary {
  id: string;
  revisionCode: string;
  fullDocumentCode: string;
}

export interface ExtractionFileSummary {
  id: string;
  filename: string;
  extension: SupportedDocumentExtension;
  sha256Hash: string;
}

export interface ExtractionError {
  code: string;
  message: string;
}

export interface ExtractionResultSummary {
  runId: string;
  status: ExtractionRunStatus;
  extractorType: ExtractorType;
  totalPages: number;
  totalSheets: number;
  totalBlocks: number;
  totalParagraphs: number;
  totalTables: number;
  totalCells: number;
  totalCharacters: number;
  totalWords: number;
  hasSelectableText: boolean;
  requiresOcr: boolean;
  warnings: string[];
}

export type ExtractionJobResultSummary = Omit<
  ExtractionResultSummary,
  'hasSelectableText'
> & {
  hasSelectableText?: boolean;
};

export interface ExtractionJob {
  id: string;
  document: ExtractionDocumentSummary;
  revision: ExtractionRevisionSummary;
  file: ExtractionFileSummary;
  jobType: ExtractionJobType;
  status: ExtractionJobStatus;
  progress: number;
  currentStage: string | null;
  requestedBy: DocumentUserSummary | null;
  requestedAt: string;
  startedAt: string | null;
  completedAt: string | null;
  cancelledAt: string | null;
  runId: string | null;
  resultSummary: ExtractionJobResultSummary | null;
}

export interface ExtractionJobDetail extends ExtractionJob {
  attemptNumber: number;
  maximumAttempts: number;
  failedAt: string | null;
  error: ExtractionError | null;
}

export interface ExtractionRequest {
  documentFileId: string;
  force?: boolean;
}

export interface ExtractionQueuedResult {
  jobId: string;
  status: ExtractionJobStatus;
  progress: number;
  documentFileId: string;
  reusedExistingResult: boolean;
  runId: string | null;
}

export interface ReExtractionRequest {
  reason: string;
}

export interface ExtractionCancelResult {
  id: string;
  status: ExtractionJobStatus;
  progress: number;
  currentStage: string | null;
  cancelledAt: string | null;
}

export interface ExtractionJobListParams {
  search?: string;
  departmentId?: string;
  documentId?: string;
  revisionId?: string;
  documentFileId?: string;
  extractorType?: ExtractorType;
  status?: ExtractionJobStatus | readonly ExtractionJobStatus[];
  requestedBy?: string;
  requestedFrom?: string;
  requestedTo?: string;
  page: number;
  pageSize: number;
  sortBy?: 'requestedAt' | 'completedAt' | 'status' | 'progress';
  sortOrder?: SortOrder;
}

export type ExtractionJobList = PaginatedData<ExtractionJob>;

export const isTerminalExtractionStatus = (status: ExtractionJobStatus): boolean =>
  terminalExtractionStatuses.includes(
    status as (typeof terminalExtractionStatuses)[number],
  );

export const isActiveExtractionStatus = (status: ExtractionJobStatus): boolean =>
  activeExtractionStatuses.includes(
    status as (typeof activeExtractionStatuses)[number],
  );

export const extractorTypeFromExtension = (
  extension: SupportedDocumentExtension,
): ExtractorType => extension.toUpperCase() as ExtractorType;
