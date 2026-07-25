import { zodResolver } from '@hookform/resolvers/zod';
import { GitCompareArrows } from 'lucide-react';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import type { DocumentRevisionListItem } from '../../types/documentRevision';
import {
  errorClassName,
  inputClassName,
  labelClassName,
  textareaClassName,
} from '../master-data/forms/formStyles';

const supersedeSchema = z.object({
  supersededByRevisionId: z.string().uuid('Select the replacing revision.'),
  reason: z
    .string()
    .trim()
    .min(1, 'Reason is required.')
    .max(1_000, 'Reason must be 1,000 characters or fewer.'),
});

type SupersedeValues = z.infer<typeof supersedeSchema>;

interface SupersedeRevisionDialogProps {
  revision: DocumentRevisionListItem | null;
  revisions: readonly DocumentRevisionListItem[];
  isPending: boolean;
  onClose: () => void;
  onConfirm: (values: SupersedeValues) => Promise<void>;
}

export function SupersedeRevisionDialog({
  isPending,
  onClose,
  onConfirm,
  revision,
  revisions,
}: SupersedeRevisionDialogProps) {
  const {
    formState: { errors },
    handleSubmit,
    register,
    reset,
  } = useForm<SupersedeValues>({
    resolver: zodResolver(supersedeSchema),
    defaultValues: { supersededByRevisionId: '', reason: '' },
  });

  useEffect(() => {
    if (revision) {
      reset({ supersededByRevisionId: '', reason: '' });
    }
  }, [reset, revision]);

  if (!revision) {
    return null;
  }
  const candidates = revisions.filter(
    (candidate) => candidate.id !== revision.id && !candidate.isSuperseded,
  );
  const submit = handleSubmit(onConfirm);

  return (
    <div
      className="fixed inset-0 z-[90] grid place-items-center bg-slate-950/45 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="supersede-title"
    >
      <form
        onSubmit={(event) => void submit(event)}
        className="w-full max-w-lg rounded-3xl bg-white p-6 shadow-2xl"
        noValidate
      >
        <div className="grid size-11 place-items-center rounded-2xl bg-amber-50 text-amber-700">
          <GitCompareArrows className="size-5" aria-hidden="true" />
        </div>
        <h2 id="supersede-title" className="mt-5 text-lg font-semibold text-slate-950">
          Supersede {revision.revisionCode}
        </h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Choose a different revision in this document as its replacement.
        </p>
        <label className={`${labelClassName} mt-5`}>
          Replacing Revision
          <select {...register('supersededByRevisionId')} className={inputClassName}>
            <option value="">Select revision</option>
            {candidates.map((candidate) => (
              <option key={candidate.id} value={candidate.id}>
                {candidate.revisionCode} — {candidate.fullDocumentCode}
              </option>
            ))}
          </select>
          {errors.supersededByRevisionId && (
            <p className={errorClassName}>{errors.supersededByRevisionId.message}</p>
          )}
        </label>
        <label className={`${labelClassName} mt-4`}>
          Reason
          <textarea
            {...register('reason')}
            className={textareaClassName}
            maxLength={1_000}
          />
          {errors.reason && <p className={errorClassName}>{errors.reason.message}</p>}
        </label>
        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            className="min-h-10 rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isPending || candidates.length === 0}
            className="min-h-10 rounded-xl bg-amber-600 px-4 text-sm font-semibold text-white hover:bg-amber-700 disabled:opacity-60"
          >
            {isPending ? 'Superseding...' : 'Supersede Revision'}
          </button>
        </div>
      </form>
    </div>
  );
}
