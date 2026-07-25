import type { PaginatedData, SortOrder } from './masterData';
import type {
  DocumentRevisionCreate,
  DocumentRevisionListItem,
  DocumentRevisionSummary,
} from './documentRevision';

export interface DocumentReference {
  id: string;
  code: string;
  name: string;
  isActive?: boolean;
}

export interface DocumentUserSummary {
  id: string;
  name: string;
  email?: string | null;
}

export const documentSortFields = [
  'baseDocumentCode',
  'title',
  'companyCode',
  'department',
  'documentType',
  'createdAt',
  'updatedAt',
  'effectiveDate',
] as const;

export type DocumentSortField = (typeof documentSortFields)[number];

export interface DocumentListParams {
  search?: string;
  baseDocumentCode?: string;
  departmentId?: string;
  sectionId?: string;
  documentTypeId?: string;
  documentStatusId?: string;
  validationRuleId?: string;
  revisionCode?: string;
  companyCode?: string;
  isArchived?: boolean;
  hasSharePointUrl?: boolean;
  createdBy?: string;
  createdFrom?: string;
  createdTo?: string;
  effectiveFrom?: string;
  effectiveTo?: string;
  page: number;
  pageSize: number;
  sortBy?: DocumentSortField;
  sortOrder?: SortOrder;
}

export interface DocumentListItem {
  id: string;
  companyCode: string;
  departmentId: string;
  sectionId: string | null;
  documentTypeId: string;
  documentNumber: string;
  baseDocumentCode: string;
  title: string;
  department: DocumentReference;
  section: DocumentReference | null;
  documentType: DocumentReference;
  currentRevision: DocumentRevisionSummary | null;
  isArchived: boolean;
  updatedAt: string;
}

export type DocumentList = PaginatedData<DocumentListItem>;
export type DocumentListResponse = DocumentList;
export type DocumentFilter = DocumentListParams;

export type DocumentInitialRevisionCreate = DocumentRevisionCreate;

export interface DocumentCreate {
  companyCode?: string | null;
  departmentId: string;
  sectionId?: string | null;
  documentTypeId: string;
  documentNumber: string;
  title: string;
  description?: string | null;
  ownerDepartmentId?: string | null;
  documentOwnerName?: string | null;
  initialRevision?: DocumentInitialRevisionCreate | null;
}

export interface DocumentUpdate {
  companyCode?: string | null;
  departmentId?: string | null;
  sectionId?: string | null;
  documentTypeId?: string | null;
  documentNumber?: string | null;
  title?: string | null;
  description?: string | null;
  ownerDepartmentId?: string | null;
  documentOwnerName?: string | null;
  changeReason?: string | null;
}

export interface DocumentResponse extends DocumentListItem {
  description: string | null;
  ownerDepartmentId: string | null;
  documentOwnerName: string | null;
  currentRevisionId: string | null;
  ownerDepartment: DocumentReference | null;
  archivedAt: string | null;
  archivedBy: DocumentUserSummary | null;
  archiveReason: string | null;
  createdBy: DocumentUserSummary | null;
  updatedBy: DocumentUserSummary | null;
  createdAt: string;
}

export interface DocumentDetail extends DocumentResponse {
  revisions: DocumentRevisionListItem[];
}

export type DocumentDetailResponse = DocumentDetail;

export interface DocumentArchiveRequest {
  reason: string;
}

export interface DocumentRestoreRequest {
  reason?: string | null;
}

export interface DocumentParseRequest {
  value: string;
}

export interface DocumentParseResponse {
  companyCode: string;
  department: DocumentReference;
  section: DocumentReference | null;
  documentType: DocumentReference;
  documentNumber: string;
  baseDocumentCode: string;
  revisionCode: string | null;
  fullDocumentCode: string | null;
  fileExtension: 'pdf' | 'docx' | 'xlsx' | null;
  warnings: string[];
}

export interface DocumentBulkArchiveRequest {
  documentIds: string[];
  reason: string;
}

export interface DocumentBulkRestoreRequest {
  documentIds: string[];
}

export interface DocumentBulkUpdateStatusRequest {
  documentIds: string[];
  documentStatusId: string;
  reason: string;
}

export interface DocumentBulkItemResult {
  documentId: string;
  success: boolean;
  message: string;
}

export interface DocumentBulkResult {
  operation: 'archive' | 'restore' | 'update-status';
  total: number;
  succeeded: number;
  failed: number;
  results: DocumentBulkItemResult[];
}

export type DocumentExportParams = Omit<DocumentListParams, 'page' | 'pageSize'>;
