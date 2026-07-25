import { z } from 'zod';

import {
  isValidRevisionCode,
  normalizeRevisionCode,
} from '../../../utils/documentCodes';
import { isHttpUrl } from '../../../utils/urls';

const optionalUrl = z
  .string()
  .trim()
  .max(2_000, 'URL must be 2,000 characters or fewer.')
  .refine((value) => !value || isHttpUrl(value), {
    message: 'Enter a valid HTTP or HTTPS URL.',
  });

const revisionFormBaseSchema = z.object({
  revisionCode: z
    .string()
    .trim()
    .min(1, 'Revision is required.')
    .max(30, 'Revision must be 30 characters or fewer.')
    .refine(
      isValidRevisionCode,
      'Use numbers, or start with a letter and use only letters, numbers, dots, or dashes.',
    ),
  documentStatusId: z.string().uuid('Select a document status.'),
  validationRuleId: z.string(),
  issueDate: z.string(),
  effectiveDate: z.string(),
  reviewDate: z.string(),
  expiryDate: z.string(),
  sharepointUrl: optionalUrl,
  externalReference: z.string().trim().max(500),
  remarks: z.string().trim().max(5_000),
  changeReason: z
    .string()
    .trim()
    .max(1_000, 'Change reason must be 1,000 characters or fewer.'),
  setAsCurrent: z.boolean(),
});

export const createRevisionFormSchema = (originalRevisionCode?: string | null) =>
  revisionFormBaseSchema.superRefine((values, context) => {
    if (
      values.effectiveDate &&
      values.expiryDate &&
      values.expiryDate < values.effectiveDate
    ) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['expiryDate'],
        message: 'Expiry date cannot be before the effective date.',
      });
    }
    if (values.issueDate && values.reviewDate && values.reviewDate < values.issueDate) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['reviewDate'],
        message: 'Review date cannot be before the issue date.',
      });
    }

    if (
      originalRevisionCode &&
      normalizeRevisionCode(values.revisionCode) !==
        normalizeRevisionCode(originalRevisionCode) &&
      !values.changeReason
    ) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['changeReason'],
        message: 'Change reason is required when changing the revision code.',
      });
    }
  });

export const revisionFormSchema = createRevisionFormSchema();

export type RevisionFormValues = z.infer<typeof revisionFormSchema>;
