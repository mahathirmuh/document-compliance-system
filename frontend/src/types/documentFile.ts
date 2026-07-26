import type { DocumentUserSummary } from './document';
import type { PaginatedData } from './masterData';
import type { DocumentStorageProvider, RemoteSyncStatus } from './sharepoint';

export const supportedDocumentExtensions = ['pdf', 'docx', 'xlsx'] as const;

export type SupportedDocumentExtension = (typeof supportedDocumentExtensions)[number];

export const supportedDocumentMimeTypes = {
  pdf: 'application/pdf',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
} as const satisfies Record<SupportedDocumentExtension, string>;

export const documentFileStatuses = [
  'UPLOADING',
  'PENDING_SCAN',
  'AVAILABLE',
  'QUARANTINED',
  'SCAN_FAILED',
  'REPLACED',
  'DELETED',
  'FAILED',
] as const;

export type DocumentFileStatus = (typeof documentFileStatuses)[number];

export interface DocumentFileListItem {
  id: string;
  documentId: string;
  documentRevisionId: string;
  originalFilename: string;
  sanitizedFilename: string;
  fileExtension: SupportedDocumentExtension;
  mimeType: string;
  detectedMimeType: string;
  fileSize: number;
  sha256Hash: string;
  storageProvider: DocumentStorageProvider;
  fileStatus: DocumentFileStatus;
  sharepointConnectionId?: string | null;
  remoteDriveId?: string | null;
  remoteItemId?: string | null;
  remoteParentItemId?: string | null;
  remotePath?: string | null;
  remoteWebUrl?: string | null;
  remoteEtag?: string | null;
  remoteCtag?: string | null;
  remoteVersionId?: string | null;
  remoteLastModifiedAt?: string | null;
  remoteLastModifiedBy?: string | null;
  remoteSize?: number | null;
  remoteMimeType?: string | null;
  remoteSyncStatus?: RemoteSyncStatus;
  lastSyncedAt?: string | null;
  syncErrorCode?: string | null;
  syncErrorMessage?: string | null;
  isPrimary: boolean;
  isCurrent: boolean;
  uploadedBy: DocumentUserSummary | null;
  uploadedAt: string;
  replacedAt: string | null;
  replacedByFileId: string | null;
  deletedAt: string | null;
  deletionReason: string | null;
  baseDocumentCode: string;
  documentTitle: string;
  revisionCode: string;
  fullDocumentCode: string;
}

export interface DocumentFileDetail extends DocumentFileListItem {
  deletedBy: DocumentUserSummary | null;
  metadata: Record<string, unknown> | null;
  createdAt: string;
  updatedAt: string;
}

export interface DocumentFileDeleteRequest {
  reason: string;
}

export interface DocumentFileRestoreRequest {
  reason?: string | null;
  replaceCurrent?: boolean;
}

export interface DocumentFileHistoryParams {
  documentId?: string;
  revisionId?: string;
  uploadedBy?: string;
  fileStatus?: DocumentFileStatus;
  fileExtension?: SupportedDocumentExtension;
  uploadedFrom?: string;
  uploadedTo?: string;
  departmentId?: string;
  search?: string;
  page: number;
  pageSize: number;
}

export type DocumentFileList = DocumentFileListItem[];
export type DocumentFileHistory = PaginatedData<DocumentFileListItem>;

export interface DocumentFileDownload {
  blob: Blob;
  fileName: string | null;
}
