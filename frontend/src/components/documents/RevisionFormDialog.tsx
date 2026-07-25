import { zodResolver } from '@hookform/resolvers/zod';
import { GitBranchPlus, X } from 'lucide-react';
import { useEffect, useMemo } from 'react';
import { useForm } from 'react-hook-form';

import type { DocumentFormBaseOption } from '../../types/documentFormOptions';
import type {
  DocumentRevisionCreate,
  DocumentRevisionListItem,
  DocumentRevisionUpdate,
} from '../../types/documentRevision';
import { normalizeRevisionCode } from '../../utils/documentCodes';
import {
  checkboxClassName,
  errorClassName,
  inputClassName,
  labelClassName,
  textareaClassName,
} from '../master-data/forms/formStyles';
import {
  createRevisionFormSchema,
  type RevisionFormValues,
} from './forms/revisionFormSchema';

interface RevisionFormDialogProps {
  isOpen: boolean;
  revision?: DocumentRevisionListItem | null;
  statuses: readonly RevisionSelectOption[];
  validationRules: readonly RevisionSelectOption[];
  isPending: boolean;
  onClose: () => void;
  onSubmit: (payload: DocumentRevisionCreate | DocumentRevisionUpdate) => Promise<void>;
}

interface RevisionSelectOption extends DocumentFormBaseOption {
  isActive?: boolean;
}

const defaults = (revision?: DocumentRevisionListItem | null): RevisionFormValues => ({
  revisionCode: revision?.revisionCode ?? 'Rev.000',
  documentStatusId: revision?.documentStatusId ?? '',
  validationRuleId: revision?.validationRuleId ?? '',
  issueDate: revision?.issueDate ?? '',
  effectiveDate: revision?.effectiveDate ?? '',
  reviewDate: revision?.reviewDate ?? '',
  expiryDate: revision?.expiryDate ?? '',
  sharepointUrl: revision?.sharepointUrl ?? '',
  externalReference: revision?.externalReference ?? '',
  remarks: revision?.remarks ?? '',
  changeReason: '',
  setAsCurrent: revision?.isCurrent ?? true,
});

const emptyToNull = (value: string): string | null => value.trim() || null;

export function RevisionFormDialog({
  isOpen,
  isPending,
  onClose,
  onSubmit,
  revision,
  statuses,
  validationRules,
}: RevisionFormDialogProps) {
  const schema = useMemo(
    () => createRevisionFormSchema(revision?.revisionCode),
    [revision?.revisionCode],
  );
  const {
    formState: { errors },
    handleSubmit,
    register,
    reset,
    watch,
  } = useForm<RevisionFormValues>({
    resolver: zodResolver(schema),
    defaultValues: defaults(revision),
  });
  const revisionCode = watch('revisionCode');
  const revisionCodeChanged =
    revision !== null &&
    revision !== undefined &&
    normalizeRevisionCode(revisionCode) !==
      normalizeRevisionCode(revision.revisionCode);

  useEffect(() => {
    if (isOpen) {
      reset(defaults(revision));
    }
  }, [isOpen, reset, revision]);

  if (!isOpen) {
    return null;
  }

  const submit = handleSubmit(async (values) => {
    const codeChanged =
      revision !== null &&
      revision !== undefined &&
      normalizeRevisionCode(values.revisionCode) !==
        normalizeRevisionCode(revision.revisionCode);
    const common = {
      revisionCode: normalizeRevisionCode(values.revisionCode),
      documentStatusId: values.documentStatusId,
      validationRuleId: emptyToNull(values.validationRuleId),
      issueDate: emptyToNull(values.issueDate),
      effectiveDate: emptyToNull(values.effectiveDate),
      reviewDate: emptyToNull(values.reviewDate),
      expiryDate: emptyToNull(values.expiryDate),
      sharepointUrl: emptyToNull(values.sharepointUrl),
      externalReference: emptyToNull(values.externalReference),
      remarks: emptyToNull(values.remarks),
    };
    await onSubmit(
      revision
        ? {
            ...common,
            ...(codeChanged ? { changeReason: values.changeReason.trim() } : {}),
          }
        : { ...common, setAsCurrent: values.setAsCurrent },
    );
  });

  const statusOptions = [...statuses];
  if (
    revision &&
    !statusOptions.some((status) => status.id === revision.documentStatusId)
  ) {
    statusOptions.push({
      id: revision.status.id,
      code: revision.status.code,
      name: revision.status.name,
      isActive: false,
    });
  }
  const ruleOptions = [...validationRules];
  if (
    revision?.validationRule &&
    !ruleOptions.some((rule) => rule.id === revision.validationRuleId)
  ) {
    ruleOptions.push({
      id: revision.validationRule.id,
      code: revision.validationRule.code,
      name: revision.validationRule.name,
      isActive: false,
    });
  }

  return (
    <div
      className="fixed inset-0 z-[90] grid place-items-center bg-slate-950/50 p-3 backdrop-blur-sm sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="revision-form-title"
    >
      <form
        onSubmit={(event) => void submit(event)}
        className="flex max-h-[94vh] w-full max-w-3xl flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-2xl"
        noValidate
      >
        <header className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-5 sm:px-7">
          <div className="flex items-start gap-3">
            <div className="grid size-10 place-items-center rounded-xl bg-blue-50 text-blue-700">
              <GitBranchPlus className="size-5" aria-hidden="true" />
            </div>
            <div>
              <h2
                id="revision-form-title"
                className="text-lg font-semibold text-slate-950"
              >
                {revision ? 'Edit Revision' : 'Add Revision'}
              </h2>
              <p className="mt-1 text-xs text-slate-500">
                Revision codes are normalized when saved.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            aria-label="Close revision form"
            className="grid size-9 place-items-center rounded-xl text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-5 py-6 sm:px-7">
          <div className="grid gap-5 md:grid-cols-2">
            <Field label="Revision Code" error={errors.revisionCode?.message}>
              <input
                {...register('revisionCode')}
                className={inputClassName}
                placeholder="Rev.001"
                maxLength={30}
              />
            </Field>
            <Field label="Document Status" error={errors.documentStatusId?.message}>
              <select {...register('documentStatusId')} className={inputClassName}>
                <option value="">Select status</option>
                {statusOptions.map((status) => (
                  <option key={status.id} value={status.id}>
                    {status.code} — {status.name}
                    {status.isActive === false ? ' (current/inactive)' : ''}
                  </option>
                ))}
              </select>
            </Field>
            <label className={labelClassName}>
              Validation Rule
              <select {...register('validationRuleId')} className={inputClassName}>
                <option value="">No validation rule</option>
                {ruleOptions.map((rule) => (
                  <option key={rule.id} value={rule.id}>
                    {rule.code} — {rule.name}
                    {rule.isActive === false ? ' (current/inactive)' : ''}
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
            <DateField
              label="Issue Date"
              name="issueDate"
              register={register}
              error={errors.issueDate?.message}
            />
            <DateField
              label="Effective Date"
              name="effectiveDate"
              register={register}
              error={errors.effectiveDate?.message}
            />
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
                maxLength={500}
              />
            </label>
            <label className={`${labelClassName} md:col-span-2`}>
              Remarks
              <textarea {...register('remarks')} className={textareaClassName} />
            </label>
            {revisionCodeChanged && (
              <label className={`${labelClassName} md:col-span-2`}>
                Change Reason
                <textarea
                  {...register('changeReason')}
                  className={textareaClassName}
                  placeholder="Explain why the controlled revision code is changing"
                  maxLength={1_000}
                />
                <span className="text-xs font-normal leading-5 text-amber-700">
                  Changing a revision code also regenerates its full document code and
                  requires an audit reason.
                </span>
                {errors.changeReason && (
                  <p className={errorClassName}>{errors.changeReason.message}</p>
                )}
              </label>
            )}
            {!revision && (
              <label className="flex items-center gap-3 text-sm font-medium text-slate-700 md:col-span-2">
                <input
                  {...register('setAsCurrent')}
                  type="checkbox"
                  className={checkboxClassName}
                />
                Set this revision as current
              </label>
            )}
          </div>
        </div>
        <footer className="flex justify-end gap-3 border-t border-slate-200 bg-slate-50 px-5 py-4 sm:px-7">
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            className="min-h-10 rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700 hover:bg-white disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isPending}
            className="min-h-10 rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white hover:bg-blue-800 disabled:opacity-60"
          >
            {isPending ? 'Saving...' : revision ? 'Save Revision' : 'Add Revision'}
          </button>
        </footer>
      </form>
    </div>
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
  register: ReturnType<typeof useForm<RevisionFormValues>>['register'];
  error?: string | undefined;
}) {
  return (
    <Field label={label} error={error}>
      <input {...register(name)} type="date" className={inputClassName} />
    </Field>
  );
}
