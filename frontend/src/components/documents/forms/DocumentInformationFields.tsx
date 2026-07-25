import type { FieldErrors, UseFormRegister } from 'react-hook-form';

import type { DocumentFormDepartmentOption } from '../../../types/documentFormOptions';
import {
  errorClassName,
  inputClassName,
  labelClassName,
  textareaClassName,
} from '../../master-data/forms/formStyles';
import type { DocumentFormValues } from './documentFormSchema';

interface DocumentInformationFieldsProps {
  register: UseFormRegister<DocumentFormValues>;
  errors: FieldErrors<DocumentFormValues>;
  departments: readonly DocumentFormDepartmentOption[];
  readOnly: boolean;
}

export function DocumentInformationFields({
  departments,
  errors,
  readOnly,
  register,
}: DocumentInformationFieldsProps) {
  return (
    <fieldset disabled={readOnly} className="rounded-2xl border border-slate-200 p-5">
      <legend className="px-2 text-sm font-semibold text-slate-950">
        Document Information
      </legend>
      <div className="grid gap-5 md:grid-cols-2">
        <label className={`${labelClassName} md:col-span-2`}>
          Document Title
          <input
            {...register('title')}
            className={inputClassName}
            placeholder="Controlled document title"
            maxLength={500}
          />
          {errors.title && <p className={errorClassName}>{errors.title.message}</p>}
        </label>
        <label className={`${labelClassName} md:col-span-2`}>
          Description
          <textarea
            {...register('description')}
            className={textareaClassName}
            placeholder="Optional document description"
          />
        </label>
        <label className={labelClassName}>
          Owner Department
          <select {...register('ownerDepartmentId')} className={inputClassName}>
            <option value="">Same as controlling department</option>
            {departments.map((department) => (
              <option key={department.id} value={department.id}>
                {department.code} — {department.name}
              </option>
            ))}
          </select>
        </label>
        <label className={labelClassName}>
          Document Owner Name
          <input
            {...register('documentOwnerName')}
            className={inputClassName}
            placeholder="Optional owner or custodian"
            maxLength={150}
          />
          {errors.documentOwnerName && (
            <p className={errorClassName}>{errors.documentOwnerName.message}</p>
          )}
        </label>
      </div>
    </fieldset>
  );
}
