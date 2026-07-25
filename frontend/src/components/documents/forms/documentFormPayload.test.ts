import { describe, expect, it } from 'vitest';

import type { DocumentFormValues } from './documentFormSchema';
import {
  buildDocumentCreatePayload,
  buildDocumentUpdatePayload,
} from './documentFormPayload';

const values: DocumentFormValues = {
  companyCode: ' mti ',
  departmentId: '11111111-1111-4111-8111-111111111111',
  sectionId: '',
  documentTypeId: '22222222-2222-4222-8222-222222222222',
  documentTypeRequiresSection: false,
  documentNumber: ' pol-001 ',
  title: ' Policy ',
  description: '',
  ownerDepartmentId: '',
  documentOwnerName: '',
  createInitialRevision: true,
  revisionCode: '1',
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
};

describe('document form payload mapping', () => {
  it('normalizes identity and initial revision values', () => {
    expect(buildDocumentCreatePayload(values)).toEqual(
      expect.objectContaining({
        companyCode: 'MTI',
        documentNumber: 'POL-001',
        title: 'Policy',
        sectionId: null,
        initialRevision: expect.objectContaining({
          revisionCode: 'Rev.001',
          setAsCurrent: true,
        }),
      }),
    );
  });

  it('only sends a change reason when the code changes', () => {
    expect(buildDocumentUpdatePayload(values).changeReason).toBeNull();
    expect(
      buildDocumentUpdatePayload({
        ...values,
        codeChanged: true,
        changeReason: 'Controlled correction',
      }).changeReason,
    ).toBe('Controlled correction');
  });
});
