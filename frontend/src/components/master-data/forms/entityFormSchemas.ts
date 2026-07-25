import { z } from 'zod';

import { documentTypeCategories } from '../../../types/documentType';

const standardCode = z
  .string()
  .trim()
  .min(1, 'Code is required.')
  .max(20, 'Code must be 20 characters or fewer.')
  .regex(/^[A-Za-z0-9_]+$/, 'Use letters, numbers, and underscores only.');

const flexibleCode = z
  .string()
  .trim()
  .min(1, 'Code is required.')
  .max(20, 'Code must be 20 characters or fewer.')
  .regex(/^[A-Za-z0-9_-]+$/, 'Use letters, numbers, underscores, and hyphens only.');

export const departmentFormSchema = z.object({
  code: standardCode,
  name: z
    .string()
    .trim()
    .min(1, 'Name is required.')
    .max(150, 'Name must be 150 characters or fewer.'),
  description: z
    .string()
    .trim()
    .max(1_000, 'Description must be 1,000 characters or fewer.'),
  isActive: z.boolean(),
});

export type DepartmentFormValues = z.infer<typeof departmentFormSchema>;

export const sectionFormSchema = z.object({
  departmentId: z.string().uuid('Select a valid department.'),
  code: standardCode,
  name: z
    .string()
    .trim()
    .min(1, 'Name is required.')
    .max(150, 'Name must be 150 characters or fewer.'),
  description: z.string().trim().max(1_000),
  isActive: z.boolean(),
});

export type SectionFormValues = z.infer<typeof sectionFormSchema>;

export const documentTypeFormSchema = z.object({
  code: flexibleCode,
  name: z.string().trim().min(1, 'Name is required.').max(150),
  category: z.union([z.enum(documentTypeCategories), z.literal('')]),
  description: z.string().trim().max(1_000),
  requiresSection: z.boolean(),
  defaultValidationRuleId: z.string(),
  isActive: z.boolean(),
});

export type DocumentTypeFormValues = z.infer<typeof documentTypeFormSchema>;

export const documentStatusFormSchema = z.object({
  code: standardCode,
  name: z.string().trim().min(1, 'Name is required.').max(150),
  description: z.string().trim().max(1_000),
  displayOrder: z
    .number({ invalid_type_error: 'Display order is required.' })
    .int('Display order must be an integer.')
    .min(0, 'Display order cannot be negative.'),
  isInitial: z.boolean(),
  isFinal: z.boolean(),
  isObsolete: z.boolean(),
  isActive: z.boolean(),
});

export type DocumentStatusFormValues = z.infer<typeof documentStatusFormSchema>;
