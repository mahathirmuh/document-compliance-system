import type {
  MasterDataAuditFields,
  MasterDataListParams,
  PaginatedData,
} from './masterData';

export const supportedLanguageCodes = ['id', 'en', 'zh'] as const;
export type SupportedLanguageCode = (typeof supportedLanguageCodes)[number];

export const validationSectionCodes = [
  'TITLE',
  'PURPOSE',
  'SCOPE',
  'DEFINITION',
  'RESPONSIBILITY',
  'PROCEDURE',
  'RECORDS',
  'REFERENCE',
  'ATTACHMENT',
  'REVISION_HISTORY',
] as const;

export type ValidationSectionCode = (typeof validationSectionCodes)[number];

export interface ValidationRuleDocumentType {
  id: string;
  code: string;
  name: string;
  isActive: boolean;
}

export interface ValidationRule extends MasterDataAuditFields {
  id: string;
  name: string;
  code: string;
  description: string | null;
  documentTypeId: string | null;
  documentType?: ValidationRuleDocumentType | null;
  requiredIndonesian: boolean;
  requiredEnglish: boolean;
  requiredChinese: boolean;
  minimumIndonesianCoverage: number;
  minimumEnglishCoverage: number;
  minimumChineseCoverage: number;
  validateLanguageOrder: boolean;
  languageOrder: SupportedLanguageCode[];
  validateSections: boolean;
  requiredSections: ValidationSectionCode[];
  validateTables: boolean;
  minimumComplianceScore: number;
  partialComplianceScore: number;
  isDefault: boolean;
  isActive: boolean;
}

export interface ValidationRuleCreate {
  name: string;
  code: string;
  description: string | null;
  documentTypeId: string | null;
  requiredIndonesian: boolean;
  requiredEnglish: boolean;
  requiredChinese: boolean;
  minimumIndonesianCoverage: number;
  minimumEnglishCoverage: number;
  minimumChineseCoverage: number;
  validateLanguageOrder: boolean;
  languageOrder: SupportedLanguageCode[];
  validateSections: boolean;
  requiredSections: ValidationSectionCode[];
  validateTables: boolean;
  minimumComplianceScore: number;
  partialComplianceScore: number;
  isDefault: boolean;
  isActive: boolean;
}

export type ValidationRuleUpdate = ValidationRuleCreate;

export interface ValidationRuleListParams extends MasterDataListParams {
  documentTypeId?: string;
  isDefault?: boolean;
}

export type ValidationRuleList = PaginatedData<ValidationRule>;
