import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';

import { CodeInput } from '../CodeInput';
import type {
  Department,
  DepartmentCreate,
  DepartmentUpdate,
} from '../../../types/department';
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

import { departmentFormSchema, type DepartmentFormValues } from './entityFormSchemas';

interface DepartmentFormProps {
  department: Department | null;
  isPending: boolean;
  onCancel: () => void;
  onSubmit: (payload: DepartmentCreate | DepartmentUpdate) => Promise<void>;
}

const getDefaults = (department: Department | null): DepartmentFormValues => ({
  code: department?.code ?? '',
  name: department?.name ?? '',
  description: department?.description ?? '',
  isActive: department?.isActive ?? true,
});

export function DepartmentForm({
  department,
  isPending,
  onCancel,
  onSubmit,
}: DepartmentFormProps) {
  const {
    formState: { errors },
    handleSubmit,
    register,
    reset,
  } = useForm<DepartmentFormValues>({
    resolver: zodResolver(departmentFormSchema),
    defaultValues: getDefaults(department),
  });

  useEffect(() => reset(getDefaults(department)), [department, reset]);

  const submit = handleSubmit(async (values) => {
    await onSubmit({
      code: values.code.trim().toUpperCase(),
      name: values.name.trim(),
      description: values.description.trim() || null,
      isActive: department?.isActive ?? values.isActive,
    });
  });

  return (
    <form onSubmit={(event) => void submit(event)} noValidate>
      <div className="grid gap-5">
        <label className={labelClassName}>
          Code
          <CodeInput
            {...register('code')}
            className="mt-1.5"
            placeholder="e.g. HRM"
            aria-invalid={Boolean(errors.code)}
          />
          {errors.code && <p className={errorClassName}>{errors.code.message}</p>}
        </label>
        <label className={labelClassName}>
          Name
          <input
            {...register('name')}
            className={inputClassName}
            placeholder="Department name"
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
            aria-invalid={Boolean(errors.description)}
          />
          {errors.description && (
            <p className={errorClassName}>{errors.description.message}</p>
          )}
        </label>
        <label className="flex items-center gap-3 text-sm font-medium text-slate-700">
          <input
            {...register('isActive')}
            type="checkbox"
            className={`${checkboxClassName} ${
              department !== null ? 'cursor-not-allowed opacity-50' : ''
            }`}
            aria-disabled={department !== null}
            onClick={(event) => {
              if (department !== null) {
                event.preventDefault();
              }
            }}
          />
          Active and available for selection
          {department && ' (use the row action to change status)'}
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
          {isPending ? 'Saving...' : department ? 'Save changes' : 'Create department'}
        </button>
      </div>
    </form>
  );
}
