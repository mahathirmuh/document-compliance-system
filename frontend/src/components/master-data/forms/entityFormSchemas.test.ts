import { describe, expect, it } from 'vitest';

import {
  departmentFormSchema,
  documentStatusFormSchema,
  documentTypeFormSchema,
  sectionFormSchema,
} from './entityFormSchemas';
import { validationRuleFormSchema } from './validationRuleFormSchema';

const validRule = {
  code: 'DEFAULT-3LANG',
  name: 'Default Three-Language Validation',
  description: '',
  documentTypeId: '',
  requiredIndonesian: true,
  requiredEnglish: true,
  requiredChinese: true,
  minimumIndonesianCoverage: 95,
  minimumEnglishCoverage: 95,
  minimumChineseCoverage: 95,
  validateLanguageOrder: true,
  languageOrder: ['id', 'en', 'zh'],
  validateSections: false,
  requiredSections: [],
  validateTables: false,
  minimumComplianceScore: 95,
  partialComplianceScore: 70,
  isDefault: true,
  isActive: true,
} as const;

describe('master data form schemas', () => {
  it('rejects invalid department codes and missing names', () => {
    const result = departmentFormSchema.safeParse({
      code: 'HR M',
      name: '',
      description: '',
      isActive: true,
    });
    expect(result.success).toBe(false);
  });

  it('requires a valid department dependency for sections', () => {
    const result = sectionFormSchema.safeParse({
      departmentId: 'not-a-uuid',
      code: 'IER',
      name: 'Industrial Relations',
      description: '',
      isActive: true,
    });
    expect(result.success).toBe(false);
  });

  it('validates required document type fields', () => {
    const result = documentTypeFormSchema.safeParse({
      code: '',
      name: '',
      category: '',
      description: '',
      requiresSection: true,
      defaultValidationRuleId: '',
      isActive: true,
    });
    expect(result.success).toBe(false);
  });

  it('rejects a negative document status display order', () => {
    const result = documentStatusFormSchema.safeParse({
      code: 'DRAFT',
      name: 'Draft',
      description: '',
      displayOrder: -1,
      isInitial: true,
      isFinal: false,
      isObsolete: false,
      isActive: true,
    });
    expect(result.success).toBe(false);
  });

  it('requires at least one language and valid percentages', () => {
    const result = validationRuleFormSchema.safeParse({
      ...validRule,
      requiredIndonesian: false,
      requiredEnglish: false,
      requiredChinese: false,
      minimumEnglishCoverage: 101,
    });
    expect(result.success).toBe(false);
  });

  it('rejects a partial score above minimum compliance', () => {
    const result = validationRuleFormSchema.safeParse({
      ...validRule,
      minimumComplianceScore: 70,
      partialComplianceScore: 71,
    });
    expect(result.success).toBe(false);
  });

  it('accepts unique supported language ordering without toggle equality', () => {
    const result = validationRuleFormSchema.safeParse({
      ...validRule,
      requiredEnglish: false,
      languageOrder: ['zh', 'id', 'en'],
    });
    expect(result.success).toBe(true);
  });
});
