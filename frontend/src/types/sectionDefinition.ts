import type {
  BinaryDownload,
  ImportMode,
  MasterDataAuditFields,
  PaginatedData,
  SortOrder,
} from './masterData';

export const sectionAliasLanguages = ['id', 'en', 'zh', 'any'] as const;
export type SectionAliasLanguage = (typeof sectionAliasLanguages)[number];

export const sectionAliasMatchTypes = [
  'EXACT',
  'PREFIX',
  'CONTAINS',
  'REGEX',
  'FUZZY',
] as const;
export type SectionAliasMatchType = (typeof sectionAliasMatchTypes)[number];

export interface SectionAliasProfile extends MasterDataAuditFields {
  id: string;
  code: string;
  name: string;
  description: string | null;
  isDefault: boolean;
  isActive: boolean;
}

export interface SectionDefinition extends MasterDataAuditFields {
  id: string;
  profileId: string;
  profile?: SectionAliasProfile;
  canonicalCode: string;
  displayName: string;
  description: string | null;
  displayOrder: number;
  isRequiredDefault: boolean;
  isRepeatable: boolean;
  isActive: boolean;
  aliases?: SectionAlias[];
}

export interface SectionAlias extends MasterDataAuditFields {
  id: string;
  sectionDefinitionId: string;
  canonicalCode?: string;
  languageCode: SectionAliasLanguage;
  aliasText: string;
  normalisedAlias: string;
  matchType: SectionAliasMatchType;
  priority: number;
  isRegex: boolean;
  isActive: boolean;
}

export interface SectionAliasProfileListParams {
  search?: string;
  isActive?: boolean;
  page: number;
  pageSize: number;
  sortBy?: string;
  sortOrder?: SortOrder;
}

export interface SectionDefinitionListParams {
  profileId?: string;
  search?: string;
  isActive?: boolean;
  page: number;
  pageSize: number;
  sortBy?: string;
  sortOrder?: SortOrder;
}

export interface SectionAliasListParams {
  sectionDefinitionId?: string;
  profileId?: string;
  languageCode?: SectionAliasLanguage;
  search?: string;
  isActive?: boolean;
  page: number;
  pageSize: number;
  sortBy?: string;
  sortOrder?: SortOrder;
}

export type SectionAliasProfileList = PaginatedData<SectionAliasProfile>;
export type SectionDefinitionList = PaginatedData<SectionDefinition>;
export type SectionAliasList = PaginatedData<SectionAlias>;

export interface SectionAliasProfileCreate {
  code: string;
  name: string;
  description?: string | null;
  isDefault?: boolean;
  isActive?: boolean;
}

export type SectionAliasProfileUpdate = Partial<SectionAliasProfileCreate>;

export interface SectionDefinitionCreate {
  profileId: string;
  canonicalCode: string;
  displayName: string;
  description?: string | null;
  displayOrder: number;
  isRequiredDefault?: boolean;
  isRepeatable?: boolean;
  isActive?: boolean;
}

export type SectionDefinitionUpdate = Partial<
  Omit<SectionDefinitionCreate, 'profileId'>
>;

export interface SectionAliasCreate {
  sectionDefinitionId: string;
  languageCode: SectionAliasLanguage;
  aliasText: string;
  matchType: SectionAliasMatchType;
  priority: number;
  isRegex?: boolean;
  isActive?: boolean;
}

export type SectionAliasUpdate = Partial<
  Omit<SectionAliasCreate, 'sectionDefinitionId'>
>;

export interface SectionHeadingMatchRequest {
  headingText: string;
  profileId?: string | null;
}

export interface SectionHeadingMatchResult {
  matched: boolean;
  sectionDefinitionId: string | null;
  canonicalCode: string | null;
  displayName: string | null;
  languageCode: SectionAliasLanguage | null;
  matchType: SectionAliasMatchType | null;
  confidence: number;
  normalisedHeading: string;
  requiresReview: boolean;
}

export interface SectionDefinitionImportPreviewRow {
  sheetName: 'Section Definitions' | 'Section Aliases';
  rowNumber: number;
  status: 'VALID' | 'INVALID' | 'DUPLICATE';
  data: Record<string, unknown>;
  errors: string[];
}

export interface SectionDefinitionImportPreview {
  importToken: string;
  definitions: number;
  aliases: number;
  validRows: number;
  invalidRows: number;
  duplicateRows: number;
  rows: SectionDefinitionImportPreviewRow[];
  warnings: string[];
}

export interface SectionDefinitionImportConfirmRequest {
  importToken: string;
  mode: ImportMode;
}

export interface SectionDefinitionImportResult {
  totalRows: number;
  created: number;
  updated: number;
  skipped: number;
  failed: number;
}

export type SectionDefinitionDownload = BinaryDownload;
