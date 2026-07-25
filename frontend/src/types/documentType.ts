import type {
  MasterDataAuditFields,
  MasterDataListParams,
  PaginatedData,
} from './masterData';

export const documentTypeCategories = [
  'PROCEDURE',
  'POLICY',
  'GUIDELINE',
  'FORM',
  'MANUAL',
  'PLAN',
  'OTHER',
] as const;

export type DocumentTypeCategory = (typeof documentTypeCategories)[number];

export interface DocumentTypeDefaultRule {
  id: string;
  code: string;
  name: string;
  isActive: boolean;
}

export interface DocumentType extends MasterDataAuditFields {
  id: string;
  code: string;
  name: string;
  category: DocumentTypeCategory | null;
  description: string | null;
  requiresSection: boolean;
  defaultValidationRuleId: string | null;
  defaultValidationRule?: DocumentTypeDefaultRule | null;
  isActive: boolean;
}

export interface DocumentTypeCreate {
  code: string;
  name: string;
  category: DocumentTypeCategory | null;
  description: string | null;
  requiresSection: boolean;
  defaultValidationRuleId: string | null;
  isActive: boolean;
}

export type DocumentTypeUpdate = DocumentTypeCreate;
export type DocumentTypeListParams = MasterDataListParams;
export type DocumentTypeList = PaginatedData<DocumentType>;
