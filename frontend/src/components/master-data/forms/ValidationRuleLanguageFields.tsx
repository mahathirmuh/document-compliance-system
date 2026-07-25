import { ArrowDown, ArrowUp, GripVertical } from 'lucide-react';
import { useFormContext } from 'react-hook-form';

import { PercentageInput } from '../PercentageInput';
import type { SupportedLanguageCode } from '../../../types/validationRule';
import { checkboxClassName, errorClassName, labelClassName } from './formStyles';
import type { ValidationRuleFormValues } from './validationRuleFormSchema';

const languages: ReadonlyArray<{
  code: SupportedLanguageCode;
  label: string;
  requiredField: 'requiredIndonesian' | 'requiredEnglish' | 'requiredChinese';
  coverageField:
    'minimumIndonesianCoverage' | 'minimumEnglishCoverage' | 'minimumChineseCoverage';
}> = [
  {
    code: 'id',
    label: 'Indonesian',
    requiredField: 'requiredIndonesian',
    coverageField: 'minimumIndonesianCoverage',
  },
  {
    code: 'en',
    label: 'English',
    requiredField: 'requiredEnglish',
    coverageField: 'minimumEnglishCoverage',
  },
  {
    code: 'zh',
    label: 'Chinese',
    requiredField: 'requiredChinese',
    coverageField: 'minimumChineseCoverage',
  },
];

export function ValidationRuleLanguageFields() {
  const {
    formState: { errors },
    register,
    setValue,
    watch,
  } = useFormContext<ValidationRuleFormValues>();
  const languageOrder = watch('languageOrder');
  const validateLanguageOrder = watch('validateLanguageOrder');

  const moveLanguage = (index: number, direction: -1 | 1): void => {
    const target = index + direction;
    if (target < 0 || target >= languageOrder.length) {
      return;
    }
    const next = [...languageOrder];
    const currentLanguage = next[index];
    const targetLanguage = next[target];
    if (!currentLanguage || !targetLanguage) {
      return;
    }
    next[index] = targetLanguage;
    next[target] = currentLanguage;
    setValue('languageOrder', next, { shouldDirty: true, shouldValidate: true });
  };

  return (
    <>
      <section className="rounded-2xl border border-slate-200 p-4 sm:p-5">
        <h3 className="text-sm font-semibold text-slate-950">Required languages</h3>
        <p className="mt-1 text-xs leading-5 text-slate-500">
          Choose at least one language and its minimum coverage.
        </p>
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          {languages.map(({ coverageField, label, requiredField }) => (
            <div key={requiredField} className="rounded-xl bg-slate-50 p-3">
              <label className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                <input
                  {...register(requiredField)}
                  type="checkbox"
                  className={checkboxClassName}
                />
                {label}
              </label>
              <label className={`${labelClassName} mt-3`}>
                Minimum coverage
                <PercentageInput
                  {...register(coverageField, { valueAsNumber: true })}
                  className="mt-1.5"
                  aria-invalid={Boolean(errors[coverageField])}
                />
                {errors[coverageField] && (
                  <p className={errorClassName}>{errors[coverageField]?.message}</p>
                )}
              </label>
            </div>
          ))}
        </div>
        {errors.requiredIndonesian && (
          <p className={errorClassName}>{errors.requiredIndonesian.message}</p>
        )}
      </section>

      <section className="rounded-2xl border border-slate-200 p-4 sm:p-5">
        <label className="flex items-center gap-3 text-sm font-semibold text-slate-800">
          <input
            {...register('validateLanguageOrder')}
            type="checkbox"
            className={checkboxClassName}
          />
          Validate language order
        </label>
        <p className="mt-1 text-xs leading-5 text-slate-500">
          Move languages into the sequence expected in compliant documents.
        </p>
        <ol
          className={`mt-4 space-y-2 ${validateLanguageOrder ? '' : 'opacity-50'}`}
          aria-label="Language validation order"
        >
          {languageOrder.map((code, index) => {
            const language = languages.find((item) => item.code === code);
            return (
              <li
                key={code}
                className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2"
              >
                <GripVertical className="size-4 text-slate-400" aria-hidden="true" />
                <span className="min-w-0 flex-1 text-sm font-medium text-slate-700">
                  {language?.label ?? code}
                </span>
                <button
                  type="button"
                  disabled={!validateLanguageOrder || index === 0}
                  onClick={() => moveLanguage(index, -1)}
                  aria-label={`Move ${language?.label ?? code} up`}
                  className="grid size-8 place-items-center rounded-lg text-slate-500 hover:bg-white disabled:opacity-30"
                >
                  <ArrowUp className="size-3.5" aria-hidden="true" />
                </button>
                <button
                  type="button"
                  disabled={
                    !validateLanguageOrder || index === languageOrder.length - 1
                  }
                  onClick={() => moveLanguage(index, 1)}
                  aria-label={`Move ${language?.label ?? code} down`}
                  className="grid size-8 place-items-center rounded-lg text-slate-500 hover:bg-white disabled:opacity-30"
                >
                  <ArrowDown className="size-3.5" aria-hidden="true" />
                </button>
              </li>
            );
          })}
        </ol>
        {errors.languageOrder && (
          <p className={errorClassName}>{errors.languageOrder.message}</p>
        )}
      </section>
    </>
  );
}
