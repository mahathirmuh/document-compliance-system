import type { FieldErrors, UseFormRegister } from 'react-hook-form';

import type {
  DocumentFormBaseOption,
  DocumentFormDepartmentOption,
  DocumentFormSectionOption,
  DocumentFormTypeOption,
} from '../../../types/documentFormOptions';
import {
  errorClassName,
  inputClassName,
  labelClassName,
} from '../../master-data/forms/formStyles';
import type { DocumentFormValues } from './documentFormSchema';

interface DocumentIdentityFieldsProps {
  register: UseFormRegister<DocumentFormValues>;
  onDepartmentChange: () => void;
  errors: FieldErrors<DocumentFormValues>;
  departments: readonly DocumentFormDepartmentOption[];
  sections: readonly DocumentFormSectionOption[];
  documentTypes: readonly DocumentFormTypeOption[];
  currentDepartment?: DocumentFormBaseOption | null;
  currentSection?: DocumentFormBaseOption | null;
  currentDocumentType?: DocumentFormTypeOption | null;
  isLoading: boolean;
  isLoadingSections: boolean;
  departmentLocked: boolean;
  selectedDepartmentId: string;
  readOnly: boolean;
}

export function DocumentIdentityFields({
  currentDepartment,
  currentDocumentType,
  currentSection,
  departmentLocked,
  departments,
  documentTypes,
  errors,
  isLoading,
  isLoadingSections,
  onDepartmentChange,
  readOnly,
  register,
  selectedDepartmentId,
  sections,
}: DocumentIdentityFieldsProps) {
  const departmentRegistration = register('departmentId');
  const includeCurrentDepartment =
    currentDepartment &&
    !departments.some((department) => department.id === currentDepartment.id);
  const includeCurrentSection =
    currentSection && !sections.some((section) => section.id === currentSection.id);
  const includeCurrentDocumentType =
    currentDocumentType &&
    !documentTypes.some((documentType) => documentType.id === currentDocumentType.id);

  return (
    <fieldset disabled={readOnly} className="rounded-2xl border border-slate-200 p-5">
      <legend className="px-2 text-sm font-semibold text-slate-950">
        Document Identity
      </legend>
      <div className="grid gap-5 md:grid-cols-2">
        <Field label="Company Code" error={errors.companyCode?.message}>
          <input
            {...register('companyCode')}
            className={inputClassName}
            placeholder="MTI"
            maxLength={20}
          />
        </Field>
        <Field label="Department" error={errors.departmentId?.message}>
          {departmentLocked ? (
            <>
              <select value={selectedDepartmentId} className={inputClassName} disabled>
                <DepartmentOptions
                  departments={departments}
                  currentDepartment={currentDepartment ?? null}
                  includeCurrentDepartment={Boolean(includeCurrentDepartment)}
                  isLoading={isLoading}
                />
              </select>
              <input type="hidden" {...register('departmentId')} />
            </>
          ) : (
            <select
              {...departmentRegistration}
              onChange={(event) => {
                void departmentRegistration.onChange(event);
                onDepartmentChange();
              }}
              className={inputClassName}
              disabled={readOnly || isLoading}
            >
              <DepartmentOptions
                departments={departments}
                currentDepartment={currentDepartment ?? null}
                includeCurrentDepartment={Boolean(includeCurrentDepartment)}
                isLoading={isLoading}
              />
            </select>
          )}
          {departmentLocked && (
            <p className="mt-1.5 text-xs text-slate-500">
              Department Users can only maintain documents in their assigned department.
            </p>
          )}
        </Field>
        <Field label="Section" error={errors.sectionId?.message}>
          <select
            {...register('sectionId')}
            className={inputClassName}
            disabled={readOnly || isLoadingSections}
          >
            <option value="">
              {isLoadingSections ? 'Loading sections...' : 'No section'}
            </option>
            {includeCurrentSection && currentSection && (
              <option value={currentSection.id}>
                {currentSection.code} — {currentSection.name} (current)
              </option>
            )}
            {sections.map((section) => (
              <option key={section.id} value={section.id}>
                {section.code} — {section.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Document Type" error={errors.documentTypeId?.message}>
          <select
            {...register('documentTypeId')}
            className={inputClassName}
            disabled={readOnly || isLoading}
          >
            <option value="">
              {isLoading ? 'Loading document types...' : 'Select document type'}
            </option>
            {includeCurrentDocumentType && currentDocumentType && (
              <option value={currentDocumentType.id}>
                {currentDocumentType.code} — {currentDocumentType.name} (current)
              </option>
            )}
            {documentTypes.map((documentType) => (
              <option key={documentType.id} value={documentType.id}>
                {documentType.code} — {documentType.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Document Number" error={errors.documentNumber?.message}>
          <input
            {...register('documentNumber')}
            className={inputClassName}
            placeholder="001 or 2026-001"
            maxLength={50}
          />
        </Field>
      </div>
    </fieldset>
  );
}

function DepartmentOptions({
  currentDepartment,
  departments,
  includeCurrentDepartment,
  isLoading,
}: {
  currentDepartment?: DocumentFormBaseOption | null;
  departments: readonly DocumentFormDepartmentOption[];
  includeCurrentDepartment: boolean;
  isLoading: boolean;
}) {
  return (
    <>
      <option value="">
        {isLoading ? 'Loading departments...' : 'Select department'}
      </option>
      {includeCurrentDepartment && currentDepartment && (
        <option value={currentDepartment.id}>
          {currentDepartment.code} — {currentDepartment.name} (current)
        </option>
      )}
      {departments.map((department) => (
        <option key={department.id} value={department.id}>
          {department.code} — {department.name}
        </option>
      ))}
    </>
  );
}

function Field({
  children,
  error,
  label,
}: {
  label: string;
  error?: string | undefined;
  children: React.ReactNode;
}) {
  return (
    <label className={labelClassName}>
      {label}
      {children}
      {error && <p className={errorClassName}>{error}</p>}
    </label>
  );
}
