import { zodResolver } from '@hookform/resolvers/zod';
import { AlertTriangle } from 'lucide-react';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';

import { CodeInput } from '../CodeInput';
import type {
  DocumentStatus,
  DocumentStatusCreate,
  DocumentStatusUpdate,
} from '../../../types/documentStatus';
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

import {
  documentStatusFormSchema,
  type DocumentStatusFormValues,
} from './entityFormSchemas';

interface DocumentStatusFormProps {
  documentStatus: DocumentStatus | null;
  isPending: boolean;
  onCancel: () => void;
  onSubmit: (payload: DocumentStatusCreate | DocumentStatusUpdate) => Promise<void>;
}

const getDefaults = (
  documentStatus: DocumentStatus | null,
): DocumentStatusFormValues => ({
  code: documentStatus?.code ?? '',
  name: documentStatus?.name ?? '',
  description: documentStatus?.description ?? '',
  displayOrder: documentStatus?.displayOrder ?? 0,
  isInitial: documentStatus?.isInitial ?? false,
  isFinal: documentStatus?.isFinal ?? false,
  isObsolete: documentStatus?.isObsolete ?? false,
  isActive: documentStatus?.isActive ?? true,
});

export function DocumentStatusForm({
  documentStatus,
  isPending,
  onCancel,
  onSubmit,
}: DocumentStatusFormProps) {
  const {
    formState: { errors },
    handleSubmit,
    register,
    reset,
    watch,
  } = useForm<DocumentStatusFormValues>({
    resolver: zodResolver(documentStatusFormSchema),
    defaultValues: getDefaults(documentStatus),
  });

  useEffect(() => reset(getDefaults(documentStatus)), [documentStatus, reset]);
  const isInitial = watch('isInitial');

  const submit = handleSubmit(async (values) => {
    await onSubmit({
      ...values,
      code: values.code.trim().toUpperCase(),
      name: values.name.trim(),
      description: values.description.trim() || null,
      isActive: documentStatus?.isActive ?? values.isActive,
    });
  });

  return (
    <form onSubmit={(event) => void submit(event)} noValidate>
      <div className="grid gap-5 sm:grid-cols-2">
        <label className={labelClassName}>
          Code
          <CodeInput
            {...register('code')}
            className="mt-1.5"
            placeholder="e.g. DRAFT"
            aria-invalid={Boolean(errors.code)}
          />
          {errors.code && <p className={errorClassName}>{errors.code.message}</p>}
        </label>
        <label className={labelClassName}>
          Display order
          <input
            {...register('displayOrder', { valueAsNumber: true })}
            type="number"
            min={0}
            className={inputClassName}
            aria-invalid={Boolean(errors.displayOrder)}
          />
          {errors.displayOrder && (
            <p className={errorClassName}>{errors.displayOrder.message}</p>
          )}
        </label>
        <label className={`${labelClassName} sm:col-span-2`}>
          Name
          <input
            {...register('name')}
            className={inputClassName}
            placeholder="Status name"
            aria-invalid={Boolean(errors.name)}
          />
          {errors.name && <p className={errorClassName}>{errors.name.message}</p>}
        </label>
        <label className={`${labelClassName} sm:col-span-2`}>
          Description
          <textarea
            {...register('description')}
            className={textareaClassName}
            placeholder="Optional description"
          />
        </label>
        {isInitial && (
          <div className="flex gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-800 sm:col-span-2">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            Only one status can be initial. Saving this value may replace or be rejected
            against the existing initial status according to backend policy.
          </div>
        )}
        <fieldset className="grid gap-3 sm:col-span-2 sm:grid-cols-2">
          <legend className="sr-only">Status behavior</legend>
          {[
            ['isInitial', 'Initial status'],
            ['isFinal', 'Final status'],
            ['isObsolete', 'Obsolete status'],
            ['isActive', 'Active'],
          ].map(([field, label]) => (
            <label
              key={field}
              className="flex items-center gap-3 text-sm font-medium text-slate-700"
            >
              <input
                {...register(
                  field as 'isInitial' | 'isFinal' | 'isObsolete' | 'isActive',
                )}
                type="checkbox"
                className={`${checkboxClassName} ${
                  field === 'isActive' && documentStatus !== null
                    ? 'cursor-not-allowed opacity-50'
                    : ''
                }`}
                aria-disabled={field === 'isActive' && documentStatus !== null}
                onClick={(event) => {
                  if (field === 'isActive' && documentStatus !== null) {
                    event.preventDefault();
                  }
                }}
              />
              {label}
              {field === 'isActive' &&
                documentStatus &&
                ' (use the row action to change status)'}
            </label>
          ))}
        </fieldset>
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
          {isPending
            ? 'Saving...'
            : documentStatus
              ? 'Save changes'
              : 'Create document status'}
        </button>
      </div>
    </form>
  );
}
