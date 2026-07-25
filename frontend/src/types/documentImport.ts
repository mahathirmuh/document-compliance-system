export const documentImportModes = [
  'CREATE_ONLY',
  'CREATE_AND_ADD_REVISION',
  'UPSERT_METADATA',
] as const;

export type DocumentImportMode = (typeof documentImportModes)[number];

export const documentImportRowStatuses = [
  'VALID_CREATE',
  'VALID_ADD_REVISION',
  'DUPLICATE',
  'INVALID',
  'WARNING',
] as const;

export type DocumentImportRowStatus = (typeof documentImportRowStatuses)[number];

export type DocumentImportRowData = Record<string, unknown>;

export interface DocumentImportPreviewRow {
  rowNumber: number;
  status: DocumentImportRowStatus;
  baseDocumentCode: string | null;
  revisionCode: string | null;
  title: string | null;
  departmentCode: string | null;
  documentTypeCode: string | null;
  data: DocumentImportRowData;
  errors: string[];
  warnings: string[];
}

export interface DocumentImportPreview {
  totalRows: number;
  validCreateRows: number;
  validAddRevisionRows: number;
  warningRows: number;
  duplicateRows: number;
  invalidRows: number;
  rows: DocumentImportPreviewRow[];
  warnings: string[];
}

export interface DocumentImportConfirmRequest {
  mode: DocumentImportMode;
}

export interface DocumentImportResult {
  mode: DocumentImportMode;
  totalRows: number;
  documentsCreated: number;
  revisionsAdded: number;
  metadataUpdated: number;
  duplicatesSkipped: number;
  invalidSkipped: number;
  failed: number;
}

export type DocumentImportPreviewResponse = DocumentImportPreview;
export type DocumentImportResultResponse = DocumentImportResult;
