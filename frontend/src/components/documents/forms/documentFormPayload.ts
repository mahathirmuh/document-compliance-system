import type { DocumentCreate, DocumentUpdate } from '../../../types/document';
import { normalizeRevisionCode } from '../../../utils/documentCodes';
import type { DocumentFormValues } from './documentFormSchema';

const emptyToNull = (value: string): string | null => value.trim() || null;

export const buildDocumentCreatePayload = (
  values: DocumentFormValues,
): DocumentCreate => ({
  companyCode: values.companyCode.trim().toUpperCase(),
  departmentId: values.departmentId,
  sectionId: emptyToNull(values.sectionId),
  documentTypeId: values.documentTypeId,
  documentNumber: values.documentNumber.trim().toUpperCase(),
  title: values.title.trim(),
  description: emptyToNull(values.description),
  ownerDepartmentId: emptyToNull(values.ownerDepartmentId),
  documentOwnerName: emptyToNull(values.documentOwnerName),
  initialRevision: values.createInitialRevision
    ? {
        revisionCode: normalizeRevisionCode(values.revisionCode),
        documentStatusId: emptyToNull(values.documentStatusId),
        validationRuleId: emptyToNull(values.validationRuleId),
        issueDate: emptyToNull(values.issueDate),
        effectiveDate: emptyToNull(values.effectiveDate),
        reviewDate: emptyToNull(values.reviewDate),
        expiryDate: emptyToNull(values.expiryDate),
        sharepointUrl: emptyToNull(values.sharepointUrl),
        externalReference: emptyToNull(values.externalReference),
        remarks: emptyToNull(values.remarks),
        setAsCurrent: true,
      }
    : null,
});

export const buildDocumentUpdatePayload = (
  values: DocumentFormValues,
): DocumentUpdate => ({
  companyCode: values.companyCode.trim().toUpperCase(),
  departmentId: values.departmentId,
  sectionId: emptyToNull(values.sectionId),
  documentTypeId: values.documentTypeId,
  documentNumber: values.documentNumber.trim().toUpperCase(),
  title: values.title.trim(),
  description: emptyToNull(values.description),
  ownerDepartmentId: emptyToNull(values.ownerDepartmentId),
  documentOwnerName: emptyToNull(values.documentOwnerName),
  changeReason: values.codeChanged ? emptyToNull(values.changeReason) : null,
});
