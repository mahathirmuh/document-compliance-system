import { useFormContext } from 'react-hook-form';

import { validationSectionCodes } from '../../../types/validationRule';
import { checkboxClassName, errorClassName } from './formStyles';
import type { ValidationRuleFormValues } from './validationRuleFormSchema';

export function ValidationRuleSectionFields() {
  const {
    formState: { errors },
    register,
    watch,
  } = useFormContext<ValidationRuleFormValues>();
  const validateSections = watch('validateSections');

  return (
    <section className="rounded-2xl border border-slate-200 p-4 sm:p-5">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="flex items-center gap-3 text-sm font-semibold text-slate-800">
          <input
            {...register('validateSections')}
            type="checkbox"
            className={checkboxClassName}
          />
          Validate required sections
        </label>
        <label className="flex items-center gap-3 text-sm font-semibold text-slate-800">
          <input
            {...register('validateTables')}
            type="checkbox"
            className={checkboxClassName}
          />
          Validate tables
        </label>
      </div>
      <fieldset
        className={`mt-5 grid gap-2 sm:grid-cols-2 ${validateSections ? '' : 'opacity-50'}`}
        disabled={!validateSections}
      >
        <legend className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
          Required sections
        </legend>
        {validationSectionCodes.map((section) => (
          <label
            key={section}
            className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            <input
              {...register('requiredSections')}
              type="checkbox"
              value={section}
              className={checkboxClassName}
            />
            {section.replaceAll('_', ' ')}
          </label>
        ))}
      </fieldset>
      {errors.requiredSections && (
        <p className={errorClassName}>{errors.requiredSections.message}</p>
      )}
    </section>
  );
}
