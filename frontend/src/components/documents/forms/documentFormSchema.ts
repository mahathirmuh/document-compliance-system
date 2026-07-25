import { z } from 'zod';

import { isValidRevisionCode } from '../../../utils/documentCodes';
import { isHttpUrl } from '../../../utils/urls';

const optionalText = (maximum: number) =>
  z
    .string()
    .trim()
    .max(maximum, `Must be ${maximum.toLocaleString()} characters or fewer.`);

const optionalUrl = z
  .string()
  .trim()
  .max(2_000, 'URL must be 2,000 characters or fewer.')
  .refine((value) => !value || isHttpUrl(value), {
    message: 'Enter a valid HTTP or HTTPS URL.',
  });

export const documentFormSchema = z
  .object({
    companyCode: z
      .string()
      .trim()
      .min(1, 'Company code is required.')
      .max(20, 'Company code must be 20 characters or fewer.')
      .regex(/^[A-Za-z0-9_]+$/, 'Use only letters, numbers, or underscores.'),
    departmentId: z.string().uuid('Select a department.'),
    sectionId: z.string(),
    documentTypeId: z.string().uuid('Select a document type.'),
    documentTypeRequiresSection: z.boolean(),
    documentNumber: z
      .string()
      .trim()
      .min(1, 'Document number is required.')
      .max(50, 'Document number must be 50 characters or fewer.')
      .regex(
        /^[A-Za-z0-9._-]+$/,
        'Use letters, numbers, dots, dashes, or underscores.',
      ),
    title: z
      .string()
      .trim()
      .min(1, 'Document title is required.')
      .max(500, 'Document title must be 500 characters or fewer.'),
    description: optionalText(10_000),
    ownerDepartmentId: z.string(),
    documentOwnerName: optionalText(150),
    createInitialRevision: z.boolean(),
    revisionCode: z.string().trim().max(30, 'Revision must be 30 characters or fewer.'),
    documentStatusId: z.string(),
    validationRuleId: z.string(),
    issueDate: z.string(),
    effectiveDate: z.string(),
    reviewDate: z.string(),
    expiryDate: z.string(),
    sharepointUrl: optionalUrl,
    externalReference: optionalText(500),
    remarks: optionalText(5_000),
    codeChanged: z.boolean(),
    changeReason: optionalText(1_000),
  })
  .superRefine((values, context) => {
    if (values.documentTypeRequiresSection && !values.sectionId) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['sectionId'],
        message: 'Section is required for this document type.',
      });
    }

    if (values.createInitialRevision) {
      if (!values.revisionCode) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['revisionCode'],
          message: 'Revision is required.',
        });
      } else if (!isValidRevisionCode(values.revisionCode)) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['revisionCode'],
          message:
            'Use numbers, or start with a letter and use only letters, numbers, dots, or dashes.',
        });
      }
      if (!values.documentStatusId) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['documentStatusId'],
          message: 'Document status is required.',
        });
      }
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
      if (
        values.issueDate &&
        values.reviewDate &&
        values.reviewDate < values.issueDate
      ) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['reviewDate'],
          message: 'Review date cannot be before the issue date.',
        });
      }
    }

    if (values.codeChanged && !values.changeReason) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['changeReason'],
        message: 'Explain why the document code is changing.',
      });
    }
  });

export type DocumentFormValues = z.infer<typeof documentFormSchema>;
