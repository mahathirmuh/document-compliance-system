import { zodResolver } from '@hookform/resolvers/zod';
import { AlertTriangle } from 'lucide-react';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';

import { CodeInput } from '../CodeInput';
import type { MasterDataOption } from '../../../types/masterData';
import type { Section, SectionCreate, SectionUpdate } from '../../../types/section';
import {
  cancelButtonClassName,
  checkboxClassName,
  errorClassName,
  formActionsClassName,
  inputClassName,
  labelClassName,
  submitButtonClassName,
  textareaClassName,
} from './formStyles';

import { sectionFormSchema, type SectionFormValues } from './entityFormSchemas';

interface SectionFormProps {
  section: Section | null;
  departments: readonly MasterDataOption[];
  isLoadingDepartments: boolean;
  isPending: boolean;
  onCancel: () => void;
  onSubmit: (payload: SectionCreate | SectionUpdate) => Promise<void>;
}

const getDefaults = (section: Section | null): SectionFormValues => ({
  departmentId: section?.departmentId ?? '',
  code: section?.code ?? '',
  name: section?.name ?? '',
  description: section?.description ?? '',
  isActive: section?.isActive ?? true,
});

export function SectionForm({
  departments,
  isLoadingDepartments,
  isPending,
  onCancel,
  onSubmit,
  section,
}: SectionFormProps) {
  const {
    formState: { errors },
    handleSubmit,
    register,
    reset,
  } = useForm<SectionFormValues>({
    resolver: zodResolver(sectionFormSchema),
    defaultValues: getDefaults(section),
  });

  useEffect(() => reset(getDefaults(section)), [reset, section]);

  const currentDepartmentMissing =
    section !== null &&
    !departments.some((department) => department.id === section.departmentId);

  const submit = handleSubmit(async (values) => {
    await onSubmit({
      departmentId: values.departmentId,
      code: values.code.trim().toUpperCase(),
      name: values.name.trim(),
      description: values.description.trim() || null,
      isActive: section?.isActive ?? values.isActive,
    });
  });

  return (
    <form onSubmit={(event) => void submit(event)} noValidate>
      <div className="grid gap-5">
        <label className={labelClassName}>
          Department
          <select
            {...register('departmentId')}
            className={inputClassName}
            disabled={isLoadingDepartments}
            aria-invalid={Boolean(errors.departmentId)}
          >
            <option value="">
              {isLoadingDepartments ? 'Loading departments...' : 'Select department'}
            </option>
            {currentDepartmentMissing && section && (
              <option value={section.departmentId}>
                {section.department?.code ??
                  section.departmentCode ??
                  'Current department'}{' '}
                — inactive
              </option>
            )}
            {departments.map((department) => (
              <option key={department.id} value={department.id}>
                {department.code} — {department.name}
              </option>
            ))}
          </select>
          {errors.departmentId && (
            <p className={errorClassName}>{errors.departmentId.message}</p>
          )}
        </label>
        {currentDepartmentMissing && (
          <div className="flex gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-800">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            The current department is inactive. It remains visible for this record, but
            choose an active department before creating new assignments.
          </div>
        )}
        <label className={labelClassName}>
          Code
          <CodeInput
            {...register('code')}
            className="mt-1.5"
            placeholder="e.g. IER"
            aria-invalid={Boolean(errors.code)}
          />
          {errors.code && <p className={errorClassName}>{errors.code.message}</p>}
        </label>
        <label className={labelClassName}>
          Name
          <input
            {...register('name')}
            className={inputClassName}
            placeholder="Section name"
            aria-invalid={Boolean(errors.name)}
          />
          {errors.name && <p className={errorClassName}>{errors.name.message}</p>}
        </label>
        <label className={labelClassName}>
          Description
          <textarea
            {...register('description')}
            className={textareaClassName}
            placeholder="Optional description"
          />
        </label>
        <label className="flex items-center gap-3 text-sm font-medium text-slate-700">
          <input
            {...register('isActive')}
            type="checkbox"
            className={`${checkboxClassName} ${
              section !== null ? 'cursor-not-allowed opacity-50' : ''
            }`}
            aria-disabled={section !== null}
            onClick={(event) => {
              if (section !== null) {
                event.preventDefault();
              }
            }}
          />
          Active and available for selection
          {section && ' (use the row action to change status)'}
        </label>
      </div>
      <div className={formActionsClassName}>
        <button
          type="button"
          onClick={onCancel}
          disabled={isPending}
          className={cancelButtonClassName}
        >
          Cancel
        </button>
        <button type="submit" disabled={isPending} className={submitButtonClassName}>
          {isPending ? 'Saving...' : section ? 'Save changes' : 'Create section'}
        </button>
      </div>
    </form>
  );
}
