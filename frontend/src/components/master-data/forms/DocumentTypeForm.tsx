import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';

import { CodeInput } from '../CodeInput';
import {
  documentTypeCategories,
  type DocumentType,
  type DocumentTypeCreate,
  type DocumentTypeUpdate,
} from '../../../types/documentType';
import type { MasterDataOption } from '../../../types/masterData';
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
  documentTypeFormSchema,
  type DocumentTypeFormValues,
} from './entityFormSchemas';

interface DocumentTypeFormProps {
  documentType: DocumentType | null;
  validationRules: readonly MasterDataOption[];
  isLoadingRules: boolean;
  isPending: boolean;
  onCancel: () => void;
  onSubmit: (payload: DocumentTypeCreate | DocumentTypeUpdate) => Promise<void>;
}

const getDefaults = (documentType: DocumentType | null): DocumentTypeFormValues => ({
  code: documentType?.code ?? '',
  name: documentType?.name ?? '',
  category: documentType?.category ?? '',
  description: documentType?.description ?? '',
  requiresSection: documentType?.requiresSection ?? true,
  defaultValidationRuleId: documentType?.defaultValidationRuleId ?? '',
  isActive: documentType?.isActive ?? true,
});

export function DocumentTypeForm({
  documentType,
  isLoadingRules,
  isPending,
  onCancel,
  onSubmit,
  validationRules,
}: DocumentTypeFormProps) {
  const {
    formState: { errors },
    handleSubmit,
    register,
    reset,
  } = useForm<DocumentTypeFormValues>({
    resolver: zodResolver(documentTypeFormSchema),
    defaultValues: getDefaults(documentType),
  });

  useEffect(() => reset(getDefaults(documentType)), [documentType, reset]);

  const submit = handleSubmit(async (values) => {
    await onSubmit({
      code: values.code.trim().toUpperCase(),
      name: values.name.trim(),
      category: values.category || null,
      description: values.description.trim() || null,
      requiresSection: values.requiresSection,
      defaultValidationRuleId: values.defaultValidationRuleId || null,
      isActive: documentType?.isActive ?? values.isActive,
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
            placeholder="e.g. SOP"
            aria-invalid={Boolean(errors.code)}
          />
          {errors.code && <p className={errorClassName}>{errors.code.message}</p>}
        </label>
        <label className={labelClassName}>
          Category
          <select {...register('category')} className={inputClassName}>
            <option value="">No category</option>
            {documentTypeCategories.map((category) => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </select>
        </label>
        <label className={`${labelClassName} sm:col-span-2`}>
          Name
          <input
            {...register('name')}
            className={inputClassName}
            placeholder="Document type name"
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
        <label className={`${labelClassName} sm:col-span-2`}>
          Default validation rule
          <select
            {...register('defaultValidationRuleId')}
            className={inputClassName}
            disabled={isLoadingRules}
          >
            <option value="">
              {isLoadingRules ? 'Loading rules...' : 'No default rule'}
            </option>
            {validationRules.map((rule) => (
              <option key={rule.id} value={rule.id}>
                {rule.code} — {rule.name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-3 text-sm font-medium text-slate-700">
          <input
            {...register('requiresSection')}
            type="checkbox"
            className={checkboxClassName}
          />
          Requires section
        </label>
        <label className="flex items-center gap-3 text-sm font-medium text-slate-700">
          <input
            {...register('isActive')}
            type="checkbox"
            className={`${checkboxClassName} ${
              documentType !== null ? 'cursor-not-allowed opacity-50' : ''
            }`}
            aria-disabled={documentType !== null}
            onClick={(event) => {
              if (documentType !== null) {
                event.preventDefault();
              }
            }}
          />
          Active{documentType && ' (use the row action to change status)'}
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
          {isPending
            ? 'Saving...'
            : documentType
              ? 'Save changes'
              : 'Create document type'}
        </button>
      </div>
    </form>
  );
}
