import { z } from 'zod';

import {
  supportedLanguageCodes,
  validationSectionCodes,
} from '../../../types/validationRule';

const percentage = z
  .number({ invalid_type_error: 'Enter a number from 0 to 100.' })
  .min(0, 'Value must be at least 0.')
  .max(100, 'Value must be 100 or less.');

export const validationRuleFormSchema = z
  .object({
    code: z
      .string()
      .trim()
      .min(1, 'Code is required.')
      .max(20, 'Code must be 20 characters or fewer.')
      .regex(
        /^[A-Za-z0-9_-]+$/,
        'Use letters, numbers, underscores, and hyphens only.',
      ),
    name: z.string().trim().min(1, 'Name is required.').max(150),
    description: z.string().trim().max(2_000),
    documentTypeId: z.string(),
    requiredIndonesian: z.boolean(),
    requiredEnglish: z.boolean(),
    requiredChinese: z.boolean(),
    minimumIndonesianCoverage: percentage,
    minimumEnglishCoverage: percentage,
    minimumChineseCoverage: percentage,
    validateLanguageOrder: z.boolean(),
    languageOrder: z
      .array(z.enum(supportedLanguageCodes))
      .min(1, 'Choose at least one language for ordering.')
      .refine((items) => new Set(items).size === items.length, {
        message: 'Language order cannot contain duplicate languages.',
      }),
    validateSections: z.boolean(),
    requiredSections: z.array(z.enum(validationSectionCodes)),
    validateTables: z.boolean(),
    minimumComplianceScore: percentage,
    partialComplianceScore: percentage,
    isDefault: z.boolean(),
    isActive: z.boolean(),
  })
  .superRefine((values, context) => {
    if (
      !values.requiredIndonesian &&
      !values.requiredEnglish &&
      !values.requiredChinese
    ) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['requiredIndonesian'],
        message: 'At least one language must be required.',
      });
    }

    if (values.partialComplianceScore > values.minimumComplianceScore) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['partialComplianceScore'],
        message: 'Partial score cannot exceed the minimum compliance score.',
      });
    }

    if (values.validateSections && values.requiredSections.length === 0) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['requiredSections'],
        message: 'Choose at least one required section.',
      });
    }

    if (values.isDefault && !values.isActive) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['isDefault'],
        message: 'A default validation rule must be active.',
      });
    }
  });

export type ValidationRuleFormValues = z.infer<typeof validationRuleFormSchema>;
