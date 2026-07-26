import type {
  MasterDataAuditFields,
  MasterDataListParams,
  MasterDataOption,
  PaginatedData,
} from './masterData';

export const supportedLanguageCodes = ['id', 'en', 'zh'] as const;
export type SupportedLanguageCode = (typeof supportedLanguageCodes)[number];

export const validationSectionCodes = [
  'TITLE',
  'PURPOSE',
  'SCOPE',
  'DEFINITION',
  'REFERENCE',
  'RESPONSIBILITY',
  'PROCEDURE',
  'RECORDS',
  'ATTACHMENT',
  'REVISION_HISTORY',
  'APPROVAL',
  'DISTRIBUTION',
] as const;

export type ValidationSectionCode = (typeof validationSectionCodes)[number];

export const qualityScoreModes = [
  'SEPARATE_QUALITY_SCORE',
  'INCLUDE_IN_COMPLIANCE_SCORE',
  'INCLUDE_IN_OVERALL_QUALITY_SCORE',
] as const;
export type QualityScoreMode = (typeof qualityScoreModes)[number];

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
  validateDocumentCode: boolean;
  validateLanguagePresence: boolean;
  validateLanguageCoverage: boolean;
  validateContainerCompleteness: boolean;
  validateTranslationGroups: boolean;
  validateCells: boolean;
  requiredLanguages: SupportedLanguageCode[];
  sectionAliasProfileId: string | null;
  sectionAliasProfile?: MasterDataOption | null;
  minimumLanguageBlockCoverage: Partial<Record<SupportedLanguageCode, number>>;
  minimumLanguageCharacterCoverage: Partial<Record<SupportedLanguageCode, number>>;
  maximumUnknownBlockPercentage: number;
  maximumMixedBlockPercentage: number;
  documentCodeWeight: number;
  languagePresenceWeight: number;
  languageCoverageWeight: number;
  sectionCompletenessWeight: number;
  languageOrderWeight: number;
  translationGroupWeight: number;
  tableCompletenessWeight: number;
  translationSimilarityWeight: number;
  glossaryComplianceWeight: number;
  qualityScoreMode: QualityScoreMode;
  criticalFindingScoreCap: number;
  majorFindingPenalty: number;
  minorFindingPenalty: number;
  compliantScore: number;
  partiallyCompliantScore: number;
  needsReviewScore: number;
  failOnMissingRequiredLanguage: boolean;
  failOnMissingRequiredSection: boolean;
  failOnCriticalFinding: boolean;
  validationOptions: Record<string, unknown>;
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
  translationSimilarityWeight: number;
  glossaryComplianceWeight: number;
  qualityScoreMode: QualityScoreMode;
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
