import type { DocumentUserSummary } from './document';
import type { PaginatedData } from './masterData';

export const glossaryScopeTypes = [
  'GLOBAL',
  'DEPARTMENT',
  'DOCUMENT_TYPE',
  'DEPARTMENT_DOCUMENT_TYPE',
] as const;
export type GlossaryScopeType = (typeof glossaryScopeTypes)[number];
export const glossaryExceptionScopeTypes = [
  'GLOBAL',
  'DEPARTMENT',
  'DOCUMENT',
  'DOCUMENT_REVISION',
  'DOCUMENT_FILE',
  'SECTION',
] as const;
export type GlossaryExceptionScopeType = (typeof glossaryExceptionScopeTypes)[number];

export const glossaryTermTypes = [
  'PREFERRED',
  'REQUIRED',
  'FORBIDDEN',
  'REFERENCE',
  'ABBREVIATION',
] as const;
export type GlossaryTermType = (typeof glossaryTermTypes)[number];

export const glossaryVariantTypes = [
  'SYNONYM',
  'ABBREVIATION',
  'SPELLING',
  'LEGACY',
  'FORBIDDEN_VARIANT',
] as const;
export type GlossaryVariantType = (typeof glossaryVariantTypes)[number];

export const glossaryExceptionTypes = [
  'ALLOW_VARIANT',
  'IGNORE_TERM',
  'ALLOW_MISSING_TRANSLATION',
  'ALLOW_FORBIDDEN_TERM',
] as const;
export type GlossaryExceptionType = (typeof glossaryExceptionTypes)[number];
export type GlossaryLanguageCode = 'id' | 'en' | 'zh';
export type GlossarySeverity = 'CRITICAL' | 'MAJOR' | 'MINOR' | 'INFO';
export type GlossaryExportFormat = 'json' | 'xlsx';

export interface GlossaryProfile {
  id: string;
  code: string;
  name: string;
  description: string | null;
  scopeType: GlossaryScopeType;
  departmentId: string | null;
  documentTypeId: string | null;
  isDefault: boolean;
  isActive: boolean;
  version: number;
  termCount?: number;
  createdBy: DocumentUserSummary | string | null;
  updatedBy: DocumentUserSummary | string | null;
  createdAt: string;
  updatedAt: string;
}

export interface GlossaryProfileCreate {
  code: string;
  name: string;
  description?: string | null;
  scopeType: GlossaryScopeType;
  departmentId?: string | null;
  documentTypeId?: string | null;
  isDefault?: boolean;
  isActive?: boolean;
}

export type GlossaryProfileUpdate = Partial<GlossaryProfileCreate>;

export interface GlossaryTranslation {
  id: string;
  glossaryTermId: string;
  languageCode: GlossaryLanguageCode;
  termText: string;
  normalisedTerm: string;
  isPreferred: boolean;
  isForbidden: boolean;
  isRequired: boolean;
  priority: number;
  usageNote: string | null;
  exampleText: string | null;
  isActive: boolean;
  variants?: readonly GlossaryVariant[];
  createdAt: string;
  updatedAt: string;
}

export interface GlossaryTranslationCreate {
  languageCode: GlossaryLanguageCode;
  termText: string;
  isPreferred?: boolean;
  isForbidden?: boolean;
  isRequired?: boolean;
  priority?: number;
  usageNote?: string | null;
  exampleText?: string | null;
  isActive?: boolean;
}

export type GlossaryTranslationUpdate = Partial<GlossaryTranslationCreate>;

export interface GlossaryVariant {
  id: string;
  glossaryTranslationId: string;
  variantText: string;
  normalisedVariant: string;
  variantType: GlossaryVariantType;
  isAllowed: boolean;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface GlossaryVariantCreate {
  variantText: string;
  variantType: GlossaryVariantType;
  isAllowed?: boolean;
  isActive?: boolean;
}

export type GlossaryVariantUpdate = Partial<GlossaryVariantCreate>;

export interface GlossaryTerm {
  id: string;
  glossaryProfileId: string;
  profileCode?: string | null;
  termCode: string;
  conceptName: string;
  description: string | null;
  termType: GlossaryTermType;
  severity: GlossarySeverity;
  isCaseSensitive: boolean;
  matchWholeWord: boolean;
  allowInflection: boolean;
  isRegex: boolean;
  isActive: boolean;
  notes: string | null;
  translations: readonly GlossaryTranslation[];
  createdBy: DocumentUserSummary | string | null;
  updatedBy: DocumentUserSummary | string | null;
  createdAt: string;
  updatedAt: string;
}

export interface GlossaryTermCreate {
  glossaryProfileId: string;
  termCode: string;
  conceptName: string;
  description?: string | null;
  termType: GlossaryTermType;
  severity: GlossarySeverity;
  isCaseSensitive?: boolean;
  matchWholeWord?: boolean;
  allowInflection?: boolean;
  isRegex?: boolean;
  isActive?: boolean;
  notes?: string | null;
}

export type GlossaryTermUpdate = Partial<Omit<GlossaryTermCreate, 'glossaryProfileId'>>;

export interface GlossaryException {
  id: string;
  glossaryTermId: string;
  termCode?: string | null;
  scopeType: GlossaryExceptionScopeType;
  departmentId: string | null;
  documentId: string | null;
  documentRevisionId: string | null;
  documentFileId: string | null;
  sectionDefinitionId: string | null;
  languageCode: GlossaryLanguageCode | null;
  exceptionType: GlossaryExceptionType;
  reason: string;
  effectiveFrom: string | null;
  effectiveTo: string | null;
  isActive: boolean;
  isEffective?: boolean;
  isExpired?: boolean;
  approvedBy: string | null;
  createdBy: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface GlossaryExceptionCreate {
  glossaryTermId: string;
  scopeType: GlossaryExceptionScopeType;
  departmentId?: string | null;
  documentId?: string | null;
  documentRevisionId?: string | null;
  documentFileId?: string | null;
  sectionDefinitionId?: string | null;
  languageCode?: GlossaryLanguageCode | null;
  exceptionType: GlossaryExceptionType;
  reason: string;
  effectiveFrom?: string | null;
  effectiveTo?: string | null;
  isActive?: boolean;
  approvedBy?: string | null;
}

export type GlossaryExceptionUpdate = Partial<
  Omit<GlossaryExceptionCreate, 'glossaryTermId'>
>;

export interface GlossaryListParams {
  page: number;
  pageSize: number;
  search?: string;
  profileId?: string;
  languageCode?: GlossaryLanguageCode;
  termType?: GlossaryTermType;
  isActive?: boolean;
  departmentId?: string;
}

export type GlossaryProfileList = PaginatedData<GlossaryProfile>;
export type GlossaryTermList = PaginatedData<GlossaryTerm>;
export type GlossaryExceptionList = PaginatedData<GlossaryException>;

export interface GlossaryExportParams {
  departmentId?: string;
  profileIds?: readonly string[];
  includeInactive?: boolean;
}

export interface GlossaryImportIssue {
  sheet: string;
  rowNumber: number;
  field: string | null;
  code: string;
  message: string;
}

export interface GlossaryImportSheetSummary {
  sheet: string;
  totalRows: number;
  validRows: number;
  invalidRows: number;
}

export interface GlossaryImportPreview {
  valid: boolean;
  totalRows: number;
  validRows: number;
  invalidRows: number;
  sheets: readonly GlossaryImportSheetSummary[];
  issues: readonly GlossaryImportIssue[];
  preview: Readonly<Record<string, readonly Readonly<Record<string, unknown>>[]>>;
  warnings: readonly string[];
}

export interface GlossaryImportConfirmRequest {
  file: File;
  mode?: 'CREATE_ONLY' | 'UPSERT';
}

export interface GlossaryImportResult {
  mode: 'CREATE_ONLY' | 'UPSERT';
  totalRows: number;
  created: Readonly<Record<string, number>>;
  updated: Readonly<Record<string, number>>;
  skipped: Readonly<Record<string, number>>;
}

export interface GlossaryTestMatchRequest {
  text: string;
  languageCode: GlossaryLanguageCode;
  profileIds: readonly string[];
  departmentId?: string | null;
  documentTypeId?: string | null;
}

export interface GlossaryTestMatchResult {
  glossaryTermId: string;
  glossaryTranslationId: string | null;
  glossaryVariantId: string | null;
  termCode: string;
  conceptName: string;
  languageCode: GlossaryLanguageCode;
  matchedText: string;
  normalisedMatchedText: string;
  matchType: string;
  isPreferred: boolean;
  isForbidden: boolean;
  isAllowedVariant: boolean;
  exceptionApplied: boolean;
  exceptionId: string | null;
  exceptionType: GlossaryExceptionType | null;
  startOffset: number;
  endOffset: number;
}

export interface GlossaryTestMatchResponse {
  profileIds: readonly string[];
  totalMatches: number;
  matches: readonly GlossaryTestMatchResult[];
  warnings: readonly string[];
}

export interface GlossaryDownload {
  blob: Blob;
  fileName: string | null;
}

export type GlossaryMutationResult =
  | GlossaryProfile
  | GlossaryTerm
  | GlossaryTranslation
  | GlossaryVariant
  | GlossaryException;
