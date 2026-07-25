import { zodResolver } from '@hookform/resolvers/zod';
import { CheckCircle2 } from 'lucide-react';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import type { DocumentFormStatusOption } from '../../types/documentFormOptions';
import { errorClassName, textareaClassName } from '../master-data/forms/formStyles';

const schema = z.object({
  reason: z
    .string()
    .trim()
    .min(1, 'Reason is required.')
    .max(1_000, 'Reason must be 1,000 characters or fewer.'),
});

type Values = z.infer<typeof schema>;

interface BulkUpdateStatusDialogProps {
  status: DocumentFormStatusOption | null;
  documentCount: number;
  isPending: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => Promise<void>;
}

export function BulkUpdateStatusDialog({
  documentCount,
  isPending,
  onClose,
  onConfirm,
  status,
}: BulkUpdateStatusDialogProps) {
  const {
    formState: { errors },
    handleSubmit,
    register,
    reset,
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { reason: '' },
  });
  useEffect(() => reset({ reason: '' }), [reset, status]);

  if (!status) {
    return null;
  }
  const submit = handleSubmit(async ({ reason }) => onConfirm(reason.trim()));

  return (
    <div
      className="fixed inset-0 z-[90] grid place-items-center bg-slate-950/45 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="bulk-status-title"
    >
      <form
        onSubmit={(event) => void submit(event)}
        className="w-full max-w-lg rounded-3xl bg-white p-6 shadow-2xl"
        noValidate
      >
        <div className="grid size-11 place-items-center rounded-2xl bg-blue-50 text-blue-700">
          <CheckCircle2 className="size-5" aria-hidden="true" />
        </div>
        <h2
          id="bulk-status-title"
          className="mt-5 text-lg font-semibold text-slate-950"
        >
          Update {documentCount} current revisions?
        </h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Current revision status will change to {status.code} — {status.name}.
          Documents without a current revision are reported as failures.
        </p>
        <label className="mt-5 block text-xs font-semibold text-slate-700">
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
            disabled={isPending}
            className="min-h-10 rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white hover:bg-blue-800 disabled:opacity-60"
          >
            {isPending ? 'Updating...' : 'Update Status'}
          </button>
        </div>
      </form>
    </div>
  );
}
