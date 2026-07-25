import type { FieldErrors, UseFormRegister } from 'react-hook-form';

import type {
  DocumentFormStatusOption,
  DocumentFormValidationRuleOption,
} from '../../../types/documentFormOptions';
import {
  checkboxClassName,
  errorClassName,
  inputClassName,
  labelClassName,
  textareaClassName,
} from '../../master-data/forms/formStyles';
import type { DocumentFormValues } from './documentFormSchema';

interface InitialRevisionFieldsProps {
  register: UseFormRegister<DocumentFormValues>;
  errors: FieldErrors<DocumentFormValues>;
  statuses: readonly DocumentFormStatusOption[];
  validationRules: readonly DocumentFormValidationRuleOption[];
  enabled: boolean;
  readOnly: boolean;
}

export function InitialRevisionFields({
  enabled,
  errors,
  readOnly,
  register,
  statuses,
  validationRules,
}: InitialRevisionFieldsProps) {
  return (
    <fieldset disabled={readOnly} className="rounded-2xl border border-slate-200 p-5">
      <legend className="px-2 text-sm font-semibold text-slate-950">
        Initial Revision
      </legend>
      <label className="flex items-center gap-3 text-sm font-medium text-slate-700">
        <input
          {...register('createInitialRevision')}
          type="checkbox"
          className={checkboxClassName}
        />
        Create initial revision with this document
      </label>
      {enabled && (
        <div className="mt-5 grid gap-5 md:grid-cols-2">
          <Field label="Revision Code" error={errors.revisionCode?.message}>
            <input
              {...register('revisionCode')}
              className={inputClassName}
              placeholder="Rev.000"
              maxLength={30}
            />
          </Field>
          <Field label="Document Status" error={errors.documentStatusId?.message}>
            <select {...register('documentStatusId')} className={inputClassName}>
              <option value="">Select status</option>
              {statuses.map((status) => (
                <option key={status.id} value={status.id}>
                  {status.code} — {status.name}
                  {status.isInitial ? ' (initial)' : ''}
                </option>
              ))}
            </select>
          </Field>
          <label className={labelClassName}>
            Validation Rule
            <select {...register('validationRuleId')} className={inputClassName}>
              <option value="">Resolve backend default</option>
              {validationRules.map((rule) => (
                <option key={rule.id} value={rule.id}>
                  {rule.code} — {rule.name}
                  {rule.isDefault ? ' (default)' : ''}
                </option>
              ))}
            </select>
          </label>
          <Field label="SharePoint URL" error={errors.sharepointUrl?.message}>
            <input
              {...register('sharepointUrl')}
              type="url"
              className={inputClassName}
              placeholder="https://tenant.sharepoint.com/..."
            />
          </Field>
          <DateField label="Issue Date" name="issueDate" register={register} />
          <DateField label="Effective Date" name="effectiveDate" register={register} />
          <DateField
            label="Review Date"
            name="reviewDate"
            register={register}
            error={errors.reviewDate?.message}
          />
          <DateField
            label="Expiry Date"
            name="expiryDate"
            register={register}
            error={errors.expiryDate?.message}
          />
          <label className={labelClassName}>
            External Reference
            <input
              {...register('externalReference')}
              className={inputClassName}
              placeholder="Legacy register reference"
              maxLength={500}
            />
          </label>
          <label className={`${labelClassName} md:col-span-2`}>
            Remarks
            <textarea
              {...register('remarks')}
              className={textareaClassName}
              placeholder="Optional revision notes"
            />
          </label>
        </div>
      )}
    </fieldset>
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

function DateField({
  error,
  label,
  name,
  register,
}: {
  label: string;
  name: 'issueDate' | 'effectiveDate' | 'reviewDate' | 'expiryDate';
  register: UseFormRegister<DocumentFormValues>;
  error?: string | undefined;
}) {
  return (
    <Field label={label} error={error}>
      <input {...register(name)} type="date" className={inputClassName} />
    </Field>
  );
}
