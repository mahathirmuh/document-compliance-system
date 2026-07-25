import type { DocumentReference, DocumentUserSummary } from './document';

export interface DocumentRevisionSummary {
  id: string;
  documentId: string;
  revisionCode: string;
  revisionNumber: number | null;
  fullDocumentCode: string;
  documentStatusId: string;
  validationRuleId: string | null;
  status: DocumentReference;
  validationRule: DocumentReference | null;
  issueDate: string | null;
  effectiveDate: string | null;
  reviewDate: string | null;
  expiryDate: string | null;
  sharepointUrl: string | null;
  externalReference: string | null;
  remarks: string | null;
  isCurrent: boolean;
  isSuperseded: boolean;
}

export interface DocumentRevisionListItem extends DocumentRevisionSummary {
  supersededAt: string | null;
  supersededByRevisionId: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface DocumentRevision extends DocumentRevisionListItem {
  createdBy: DocumentUserSummary | null;
  updatedBy: DocumentUserSummary | null;
}

export interface DocumentRevisionCreate {
  revisionCode: string;
  documentStatusId?: string | null;
  validationRuleId?: string | null;
  issueDate?: string | null;
  effectiveDate?: string | null;
  reviewDate?: string | null;
  expiryDate?: string | null;
  sharepointUrl?: string | null;
  externalReference?: string | null;
  remarks?: string | null;
  setAsCurrent?: boolean;
}

export interface DocumentRevisionUpdate {
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
  changeReason?: string | null;
}

export interface DocumentRevisionSetCurrentRequest {
  reason?: string | null;
}

export interface DocumentRevisionSupersedeRequest {
  supersededByRevisionId: string;
  reason: string;
}

export type DocumentRevisionList = readonly DocumentRevisionListItem[];
export type DocumentRevisionResponse = DocumentRevision;
