import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect } from 'react';
import { FormProvider, useForm } from 'react-hook-form';

import { CodeInput } from '../CodeInput';
import { PercentageInput } from '../PercentageInput';
import type { MasterDataOption } from '../../../types/masterData';
import type {
  ValidationRule,
  ValidationRuleCreate,
  ValidationRuleUpdate,
} from '../../../types/validationRule';
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
import { ValidationRuleLanguageFields } from './ValidationRuleLanguageFields';
import { ValidationRuleSectionFields } from './ValidationRuleSectionFields';
import {
  validationRuleFormSchema,
  type ValidationRuleFormValues,
} from './validationRuleFormSchema';

interface ValidationRuleFormProps {
  validationRule: ValidationRule | null;
  documentTypes: readonly MasterDataOption[];
  isLoadingDocumentTypes: boolean;
  isPending: boolean;
  onCancel: () => void;
  onSubmit: (payload: ValidationRuleCreate | ValidationRuleUpdate) => Promise<void>;
}

const defaultSections = [
  'TITLE',
  'PURPOSE',
  'SCOPE',
  'RESPONSIBILITY',
  'PROCEDURE',
  'RECORDS',
  'REFERENCE',
] as const;

const getDefaults = (
  validationRule: ValidationRule | null,
): ValidationRuleFormValues => ({
  code: validationRule?.code ?? '',
  name: validationRule?.name ?? '',
  description: validationRule?.description ?? '',
  documentTypeId: validationRule?.documentTypeId ?? '',
  requiredIndonesian: validationRule?.requiredIndonesian ?? true,
  requiredEnglish: validationRule?.requiredEnglish ?? true,
  requiredChinese: validationRule?.requiredChinese ?? true,
  minimumIndonesianCoverage: validationRule?.minimumIndonesianCoverage ?? 95,
  minimumEnglishCoverage: validationRule?.minimumEnglishCoverage ?? 95,
  minimumChineseCoverage: validationRule?.minimumChineseCoverage ?? 95,
  validateLanguageOrder: validationRule?.validateLanguageOrder ?? true,
  languageOrder: validationRule?.languageOrder ?? (['id', 'en', 'zh'] as const),
  validateSections: validationRule?.validateSections ?? false,
  requiredSections: validationRule?.requiredSections ?? [...defaultSections],
  validateTables: validationRule?.validateTables ?? false,
  translationSimilarityWeight: validationRule?.translationSimilarityWeight ?? 25,
  glossaryComplianceWeight: validationRule?.glossaryComplianceWeight ?? 15,
  qualityScoreMode: validationRule?.qualityScoreMode ?? 'SEPARATE_QUALITY_SCORE',
  minimumComplianceScore: validationRule?.minimumComplianceScore ?? 95,
  partialComplianceScore: validationRule?.partialComplianceScore ?? 70,
  isDefault: validationRule?.isDefault ?? false,
  isActive: validationRule?.isActive ?? true,
});

export function ValidationRuleForm({
  documentTypes,
  isLoadingDocumentTypes,
  isPending,
  onCancel,
  onSubmit,
  validationRule,
}: ValidationRuleFormProps) {
  const methods = useForm<ValidationRuleFormValues>({
    resolver: zodResolver(validationRuleFormSchema),
    defaultValues: getDefaults(validationRule),
  });
  const {
    formState: { errors },
    handleSubmit,
    register,
    reset,
  } = methods;

  useEffect(() => reset(getDefaults(validationRule)), [reset, validationRule]);

  const submit = handleSubmit(async (values) => {
    await onSubmit({
      ...values,
      code: values.code.trim().toUpperCase(),
      name: values.name.trim(),
      description: values.description.trim() || null,
      documentTypeId: values.documentTypeId || null,
      isDefault: validationRule?.isDefault ?? values.isDefault,
      isActive: validationRule?.isActive ?? values.isActive,
    });
  });

  return (
    <FormProvider {...methods}>
      <form onSubmit={(event) => void submit(event)} noValidate>
        <div className="space-y-5">
          <section className="rounded-2xl border border-slate-200 p-4 sm:p-5">
            <h3 className="text-sm font-semibold text-slate-950">General</h3>
            <div className="mt-4 grid gap-5 sm:grid-cols-2">
              <label className={labelClassName}>
                Code
                <CodeInput
                  {...register('code')}
                  className="mt-1.5"
                  placeholder="e.g. SOP-3LANG"
                  aria-invalid={Boolean(errors.code)}
                />
                {errors.code && <p className={errorClassName}>{errors.code.message}</p>}
              </label>
              <label className={labelClassName}>
                Document type
                <select
                  {...register('documentTypeId')}
                  className={inputClassName}
                  disabled={isLoadingDocumentTypes}
                >
                  <option value="">
                    {isLoadingDocumentTypes
                      ? 'Loading document types...'
                      : 'Global rule'}
                  </option>
                  {documentTypes.map((type) => (
                    <option key={type.id} value={type.id}>
                      {type.code} — {type.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className={`${labelClassName} sm:col-span-2`}>
                Name
                <input
                  {...register('name')}
                  className={inputClassName}
                  placeholder="Validation rule name"
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
              <label className="flex items-center gap-3 text-sm font-medium text-slate-700">
                <span>
                  <input
                    {...register('isDefault')}
                    type="checkbox"
                    className={`${checkboxClassName} mr-3 ${
                      validationRule ? 'cursor-not-allowed opacity-50' : ''
                    }`}
                    aria-disabled={validationRule !== null}
                    onClick={(event) => {
                      if (validationRule) {
                        event.preventDefault();
                      }
                    }}
                  />
                  Default rule
                  {validationRule && ' (use Set default action)'}
                  {errors.isDefault && (
                    <span className={`${errorClassName} block`}>
                      {errors.isDefault.message}
                    </span>
                  )}
                </span>
              </label>
              <label className="flex items-center gap-3 text-sm font-medium text-slate-700">
                <input
                  {...register('isActive')}
                  type="checkbox"
                  className={`${checkboxClassName} ${
                    validationRule ? 'cursor-not-allowed opacity-50' : ''
                  }`}
                  aria-disabled={validationRule !== null}
                  onClick={(event) => {
                    if (validationRule) {
                      event.preventDefault();
                    }
                  }}
                />
                Active
                {validationRule && ' (use the row action to change status)'}
              </label>
            </div>
          </section>

          <ValidationRuleLanguageFields />
          <ValidationRuleSectionFields />

          <section className="rounded-2xl border border-slate-200 p-4 sm:p-5">
            <h3 className="text-sm font-semibold text-slate-950">Compliance score</h3>
            <div className="mt-4 grid gap-5 sm:grid-cols-2">
              <label className={labelClassName}>
                Minimum compliance score
                <PercentageInput
                  {...register('minimumComplianceScore', { valueAsNumber: true })}
                  className="mt-1.5"
                  aria-invalid={Boolean(errors.minimumComplianceScore)}
                />
                {errors.minimumComplianceScore && (
                  <p className={errorClassName}>
                    {errors.minimumComplianceScore.message}
                  </p>
                )}
              </label>
              <label className={labelClassName}>
                Partial compliance score
                <PercentageInput
                  {...register('partialComplianceScore', { valueAsNumber: true })}
                  className="mt-1.5"
                  aria-invalid={Boolean(errors.partialComplianceScore)}
                />
                {errors.partialComplianceScore && (
                  <p className={errorClassName}>
                    {errors.partialComplianceScore.message}
                  </p>
                )}
              </label>
            </div>
            <div className="mt-5 border-t border-slate-200 pt-5">
              <h4 className="text-sm font-semibold text-slate-900">
                Phase 9 quality score
              </h4>
              <p className="mt-1 text-sm text-slate-600">
                Structural compliance remains unchanged unless an inclusion mode is
                selected explicitly.
              </p>
              <div className="mt-4 grid gap-5 sm:grid-cols-3">
                <label className={labelClassName}>
                  Score mode
                  <select {...register('qualityScoreMode')} className={inputClassName}>
                    <option value="SEPARATE_QUALITY_SCORE">
                      Separate quality score
                    </option>
                    <option value="INCLUDE_IN_OVERALL_QUALITY_SCORE">
                      Include in overall quality
                    </option>
                    <option value="INCLUDE_IN_COMPLIANCE_SCORE">
                      Include in compliance score
                    </option>
                  </select>
                </label>
                <label className={labelClassName}>
                  Translation similarity weight
                  <PercentageInput
                    {...register('translationSimilarityWeight', {
                      valueAsNumber: true,
                    })}
                    className="mt-1.5"
                    aria-invalid={Boolean(errors.translationSimilarityWeight)}
                  />
                  {errors.translationSimilarityWeight && (
                    <p className={errorClassName}>
                      {errors.translationSimilarityWeight.message}
                    </p>
                  )}
                </label>
                <label className={labelClassName}>
                  Glossary compliance weight
                  <PercentageInput
                    {...register('glossaryComplianceWeight', {
                      valueAsNumber: true,
                    })}
                    className="mt-1.5"
                    aria-invalid={Boolean(errors.glossaryComplianceWeight)}
                  />
                  {errors.glossaryComplianceWeight && (
                    <p className={errorClassName}>
                      {errors.glossaryComplianceWeight.message}
                    </p>
                  )}
                </label>
              </div>
            </div>
          </section>
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
              : validationRule
                ? 'Save changes'
                : 'Create validation rule'}
          </button>
        </div>
      </form>
    </FormProvider>
  );
}
