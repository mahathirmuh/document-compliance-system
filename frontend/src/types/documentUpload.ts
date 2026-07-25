import type { DocumentFileStatus, SupportedDocumentExtension } from './documentFile';
import type { UploadSessionStatus, UploadSessionType } from './uploadSession';

export const fileIdentificationStatuses = [
  'IDENTIFIED',
  'PARTIALLY_IDENTIFIED',
  'NOT_IDENTIFIED',
  'DUPLICATE_FILE',
  'INVALID',
] as const;

export type FileIdentificationStatus = (typeof fileIdentificationStatuses)[number];

export const uploadProposedActions = [
  'ATTACH_TO_EXISTING_REVISION',
  'CREATE_DOCUMENT_AND_REVISION',
  'ADD_NEW_REVISION',
  'REPLACE_CURRENT_FILE',
  'MANUAL_REVIEW',
  'SKIP',
] as const;

export type UploadProposedAction = (typeof uploadProposedActions)[number];

export const uploadSessionItemStatuses = [
  'PENDING',
  'READY',
  'COMMITTED',
  'SKIPPED',
  'FAILED',
  'CANCELLED',
] as const;

export type UploadSessionItemStatus = (typeof uploadSessionItemStatuses)[number];

export interface ParsedDocumentMetadata {
  companyCode?: string | null;
  departmentCode?: string | null;
  sectionCode?: string | null;
  documentTypeCode?: string | null;
  documentNumber?: string | null;
  revisionCode?: string | null;
  baseDocumentCode?: string | null;
  fullDocumentCode?: string | null;
}

export interface MatchedUploadDocument {
  id: string;
  baseDocumentCode: string;
  title: string;
}

export interface MatchedUploadRevision {
  id: string;
  revisionCode: string;
  fullDocumentCode?: string | null;
}

export interface UploadSessionItem {
  uploadItemId: string;
  originalFilename: string;
  sanitizedFilename: string;
  fileExtension: SupportedDocumentExtension | null;
  mimeType: string | null;
  detectedMimeType: string | null;
  fileSize: number | null;
  sha256Hash: string | null;
  identificationStatus: FileIdentificationStatus;
  proposedAction: UploadProposedAction;
  parsedMetadata: ParsedDocumentMetadata | null;
  matchedDocument: MatchedUploadDocument | null;
  matchedRevision: MatchedUploadRevision | null;
  duplicateWarning?: FileDuplicateWarning | null;
  warnings: string[];
  errors: string[];
  status: UploadSessionItemStatus;
  quarantineReason?: string | null;
}

export interface UploadPreviewResponse {
  sessionId: string;
  sessionType: UploadSessionType;
  status: UploadSessionStatus;
  totalFiles: number;
  totalSize: number;
  expiresAt: string;
  committedAt: string | null;
  cancelledAt: string | null;
  items: UploadSessionItem[];
}

export interface FileDuplicateWarning {
  message: string;
  sameRevision: boolean;
  documentId?: string | null;
  revisionId?: string | null;
  baseDocumentCode?: string | null;
}

export interface UploadConfirmationMetadata {
  companyCode?: string | null;
  departmentId?: string | null;
  sectionId?: string | null;
  documentTypeId?: string | null;
  documentNumber?: string | null;
  title?: string | null;
  description?: string | null;
  revisionCode?: string | null;
  documentStatusId?: string | null;
  validationRuleId?: string | null;
  issueDate?: string | null;
  effectiveDate?: string | null;
  reviewDate?: string | null;
  expiryDate?: string | null;
  sharepointUrl?: string | null;
  externalReference?: string | null;
  remarks?: string | null;
  setAsCurrentRevision?: boolean;
  reason?: string | null;
  allowDuplicate?: boolean;
}

export interface UploadConfirmationItem {
  uploadItemId: string;
  action: UploadProposedAction;
  documentId?: string | null;
  revisionId?: string | null;
  metadata?: UploadConfirmationMetadata | null;
}

export interface UploadConfirmationRequest {
  items: UploadConfirmationItem[];
}

export interface UploadConfirmationItemResult {
  uploadItemId: string;
  action: UploadProposedAction;
  status: UploadSessionItemStatus;
  documentId: string | null;
  revisionId: string | null;
  documentFileId: string | null;
  baseDocumentCode: string | null;
  revisionCode: string | null;
  fileStatus: DocumentFileStatus | null;
  error: string | null;
}

export interface UploadConfirmationResult {
  sessionId: string;
  status: UploadSessionStatus;
  items: UploadConfirmationItemResult[];
  total?: number;
  committed?: number;
  skipped?: number;
  failed?: number;
  documentsCreated?: number;
  revisionsCreated?: number;
  filesAttached?: number;
  filesReplaced?: number;
  committedAt?: string | null;
}

export type UploadProgressHandler = (progress: number) => void;
