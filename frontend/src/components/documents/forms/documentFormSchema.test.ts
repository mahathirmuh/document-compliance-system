import { describe, expect, it } from 'vitest';

import { documentFormSchema, type DocumentFormValues } from './documentFormSchema';
import { createRevisionFormSchema, revisionFormSchema } from './revisionFormSchema';

const validDocument = {
  companyCode: 'MTI',
  departmentId: '11111111-1111-4111-8111-111111111111',
  sectionId: '',
  documentTypeId: '22222222-2222-4222-8222-222222222222',
  documentTypeRequiresSection: false,
  documentNumber: '001',
  title: 'Document title',
  description: '',
  ownerDepartmentId: '',
  documentOwnerName: '',
  createInitialRevision: true,
  revisionCode: 'Rev.000',
  documentStatusId: '33333333-3333-4333-8333-333333333333',
  validationRuleId: '',
  issueDate: '',
  effectiveDate: '',
  reviewDate: '',
  expiryDate: '',
  sharepointUrl: '',
  externalReference: '',
  remarks: '',
  codeChanged: false,
  changeReason: '',
} satisfies DocumentFormValues;

const validRevision = {
  revisionCode: 'Rev.B-2',
  documentStatusId: validDocument.documentStatusId,
  validationRuleId: '',
  issueDate: '',
  effectiveDate: '',
  reviewDate: '',
  expiryDate: '',
  sharepointUrl: '',
  externalReference: '',
  remarks: '',
  changeReason: '',
  setAsCurrent: true,
};

describe('document form schema', () => {
  it('requires a section only when the document type requires it', () => {
    expect(documentFormSchema.safeParse(validDocument).success).toBe(true);
    const result = documentFormSchema.safeParse({
      ...validDocument,
      documentTypeRequiresSection: true,
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.flatten().fieldErrors.sectionId).toContain(
        'Section is required for this document type.',
      );
    }
  });

  it('matches backend company and document-number component rules', () => {
    expect(
      documentFormSchema.safeParse({
        ...validDocument,
        companyCode: 'MT-I',
      }).success,
    ).toBe(false);
    expect(
      documentFormSchema.safeParse({
        ...validDocument,
        companyCode: 'MTI_01',
        documentNumber: '2026.001-A',
      }).success,
    ).toBe(true);
  });

  it('requires a reason when an edit changes the document code', () => {
    const result = documentFormSchema.safeParse({
      ...validDocument,
      createInitialRevision: false,
      codeChanged: true,
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.flatten().fieldErrors.changeReason).toBeDefined();
    }
  });

  it('validates revision date order and SharePoint URL', () => {
    const result = revisionFormSchema.safeParse({
      revisionCode: '1',
      documentStatusId: validDocument.documentStatusId,
      validationRuleId: '',
      issueDate: '2026-07-25',
      effectiveDate: '2026-08-01',
      reviewDate: '2026-07-20',
      expiryDate: '2026-07-31',
      sharepointUrl: 'not-a-url',
      externalReference: '',
      remarks: '',
      changeReason: '',
      setAsCurrent: true,
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const errors = result.error.flatten().fieldErrors;
      expect(errors.reviewDate).toBeDefined();
      expect(errors.expiryDate).toBeDefined();
      expect(errors.sharepointUrl).toBeDefined();
    }
  });

  it('accepts only HTTP or HTTPS SharePoint URLs in both forms', () => {
    expect(
      documentFormSchema.safeParse({
        ...validDocument,
        sharepointUrl: 'ftp://example.com/document',
      }).success,
    ).toBe(false);
    expect(
      revisionFormSchema.safeParse({
        ...validRevision,
        sharepointUrl: 'ftp://example.com/document',
      }).success,
    ).toBe(false);
    expect(
      documentFormSchema.safeParse({
        ...validDocument,
        sharepointUrl: 'https://tenant.sharepoint.com/document',
      }).success,
    ).toBe(true);
    expect(
      revisionFormSchema.safeParse({
        ...validRevision,
        sharepointUrl: 'http://intranet.example.com/document',
      }).success,
    ).toBe(true);
  });

  it('matches backend numeric-or-letter-led revision rules in both forms', () => {
    expect(
      documentFormSchema.safeParse({
        ...validDocument,
        revisionCode: 'Rev.B-2',
      }).success,
    ).toBe(true);
    expect(revisionFormSchema.safeParse(validRevision).success).toBe(true);

    expect(
      documentFormSchema.safeParse({
        ...validDocument,
        revisionCode: '1A',
      }).success,
    ).toBe(false);
    expect(
      revisionFormSchema.safeParse({
        ...validRevision,
        revisionCode: 'Rev.1A',
      }).success,
    ).toBe(false);
  });

  it('requires a reason only for a normalized revision-code change', () => {
    const editSchema = createRevisionFormSchema('Rev.000');

    expect(
      editSchema.safeParse({
        ...validRevision,
        revisionCode: '0',
        changeReason: '',
      }).success,
    ).toBe(true);
    expect(
      editSchema.safeParse({
        ...validRevision,
        revisionCode: 'Rev.B-2',
        changeReason: '',
      }).success,
    ).toBe(false);
    expect(
      editSchema.safeParse({
        ...validRevision,
        revisionCode: 'Rev.B-2',
        changeReason: 'Align the controlled legacy code.',
      }).success,
    ).toBe(true);
  });
});
