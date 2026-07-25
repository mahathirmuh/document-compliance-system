import type {
  ExtractionDocumentSummary,
  ExtractionFileSummary,
  ExtractionResultSummary,
  ExtractionRevisionSummary,
  ExtractionRunStatus,
  ExtractorType,
} from './extraction';
import type { PaginatedData } from './masterData';
import type { LanguageCode } from './languageDetection';

export type ExtractedContainerType =
  'PDF_PAGE' | 'DOCX_BODY' | 'DOCX_HEADER' | 'DOCX_FOOTER' | 'XLSX_WORKSHEET';

export type ExtractedBlockType =
  | 'TEXT'
  | 'PARAGRAPH'
  | 'HEADING'
  | 'TABLE'
  | 'TABLE_ROW'
  | 'TABLE_CELL'
  | 'HEADER'
  | 'FOOTER'
  | 'WORKSHEET_TITLE'
  | 'CELL'
  | 'MERGED_CELL'
  | 'FORMULA'
  | 'PAGE_NUMBER'
  | 'UNKNOWN';

export interface ExtractionRun extends ExtractionResultSummary {
  extractionJobId: string;
  document: ExtractionDocumentSummary;
  revision: ExtractionRevisionSummary;
  file: ExtractionFileSummary;
  extractorVersion: string;
  sourceSha256Hash: string;
  sourceFileSize: number;
  contentHash: string | null;
  metadata: Record<string, unknown> | null;
  startedAt: string;
  completedAt: string;
  createdAt: string;
  requestedBy?: {
    id: string;
    name: string;
  } | null;
  reExtractionReason?: string | null;
  isLatest: boolean;
}

export interface ExtractionRunHistoryItem {
  id: string;
  extractionJobId: string;
  extractorType: ExtractorType;
  extractorVersion: string;
  status: ExtractionRunStatus;
  sourceSha256Hash: string;
  contentHash: string | null;
  summary: ExtractionResultSummary;
  requestedBy: {
    id: string;
    name: string;
  } | null;
  reExtractionReason: string | null;
  warnings: string[];
  completedAt: string;
  isLatest: boolean;
}

export interface ExtractedContainer {
  id: string;
  extractionRunId: string;
  containerType: ExtractedContainerType;
  containerIndex: number;
  name: string | null;
  title: string | null;
  characterCount: number;
  wordCount: number;
  metadata: Record<string, unknown> | null;
  createdAt: string;
}

export interface ExtractedBlock {
  id: string;
  extractionRunId: string;
  containerId: string;
  parentBlockId: string | null;
  blockType: ExtractedBlockType;
  blockOrder: number;
  sourceReference: string;
  text: string;
  normalisedText: string;
  styleName: string | null;
  headingLevel: number | null;
  location: Record<string, unknown> | null;
  metadata: Record<string, unknown> | null;
  characterCount: number;
  wordCount: number;
  contentSource?: 'NATIVE' | 'OCR';
  languageCode?: LanguageCode | null;
  languageConfidence?: number | null;
  ocrConfidence?: number | null;
  createdAt: string;
}

export interface ExtractedTableCell {
  id: string;
  extractedTableId: string;
  rowIndex: number;
  columnIndex: number;
  rowSpan: number;
  columnSpan: number;
  coordinate: string | null;
  text: string;
  normalisedText: string;
  metadata: Record<string, unknown> | null;
  createdAt: string;
}

export interface ExtractedTable {
  id: string;
  extractionRunId: string;
  containerId: string;
  sourceReference: string;
  tableIndex: number;
  rowCount: number;
  columnCount: number;
  metadata: Record<string, unknown> | null;
  cells: ExtractedTableCell[];
  createdAt: string;
}

export interface ExtractionSearchResult {
  blockId: string;
  blockOrder: number;
  containerId: string;
  containerIndex: number;
  containerName: string | null;
  sourceReference: string;
  blockType: ExtractedBlockType;
  snippet: string;
  location: Record<string, unknown> | null;
}

export interface ExtractedContentSearchResponse {
  query: string;
  totalMatches: number;
  items: ExtractionSearchResult[];
}

export interface ExtractionContainerListParams {
  containerType?: ExtractedContainerType;
  search?: string;
  page: number;
  pageSize: number;
}

export interface ExtractionBlockListParams {
  containerId?: string;
  blockType?: ExtractedBlockType;
  contentSource?: 'NATIVE' | 'OCR';
  languageCode?: LanguageCode;
  search?: string;
  page: number;
  pageSize: number;
  sortOrder?: 'asc' | 'desc';
}

export interface ExtractionTableListParams {
  containerId?: string;
  search?: string;
  includeCells?: boolean;
  page: number;
  pageSize: number;
}

export interface ExtractionSearchParams {
  q: string;
  page?: number;
  pageSize?: number;
}

export type ExtractedContainerList = PaginatedData<ExtractedContainer>;
export type ExtractedBlockList = PaginatedData<ExtractedBlock>;
export type ExtractedTableList = PaginatedData<ExtractedTable>;
export type ExtractionRunHistory = PaginatedData<ExtractionRunHistoryItem>;

export interface ExtractionDownload {
  blob: Blob;
  fileName: string | null;
}

export interface ExtractionFileState {
  runId: string;
  status: ExtractionRunStatus;
  extractorType: ExtractorType;
  completedAt: string;
  totalBlocks: number;
  totalCharacters: number;
  requiresOcr: boolean;
}
