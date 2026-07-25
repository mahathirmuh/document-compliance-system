import { render, screen } from '@testing-library/react';
import { useForm } from 'react-hook-form';
import { describe, expect, it } from 'vitest';

import { DocumentIdentityFields } from './DocumentIdentityFields';
import type { DocumentFormValues } from './documentFormSchema';

const defaults: DocumentFormValues = {
  companyCode: 'MTI',
  departmentId: '11111111-1111-4111-8111-111111111111',
  sectionId: '',
  documentTypeId: '',
  documentTypeRequiresSection: false,
  documentNumber: '',
  title: '',
  description: '',
  ownerDepartmentId: '',
  documentOwnerName: '',
  createInitialRevision: false,
  revisionCode: 'Rev.000',
  documentStatusId: '',
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

function Harness({ departmentLocked }: { departmentLocked: boolean }) {
  const {
    formState: { errors },
    register,
  } = useForm<DocumentFormValues>({ defaultValues: defaults });
  return (
    <DocumentIdentityFields
      register={register}
      errors={errors}
      departments={[
        {
          id: defaults.departmentId,
          code: 'HRM',
          name: 'Human Resource',
        },
      ]}
      sections={[]}
      documentTypes={[]}
      isLoading={false}
      isLoadingSections={false}
      departmentLocked={departmentLocked}
      selectedDepartmentId={defaults.departmentId}
      onDepartmentChange={() => undefined}
      readOnly={false}
    />
  );
}

describe('DocumentIdentityFields department scope', () => {
  it('locks the department for a Department User', () => {
    render(<Harness departmentLocked />);
    expect(screen.getByRole('combobox', { name: /Department/ })).toBeDisabled();
    expect(
      screen.getByText(/Department Users can only maintain documents/),
    ).toBeInTheDocument();
  });

  it('allows an authorized cross-department user to select a department', () => {
    render(<Harness departmentLocked={false} />);
    expect(screen.getByRole('combobox', { name: /Department/ })).toBeEnabled();
  });
});
