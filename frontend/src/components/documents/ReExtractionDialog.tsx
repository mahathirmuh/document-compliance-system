import { zodResolver } from '@hookform/resolvers/zod';
import { RefreshCw, X } from 'lucide-react';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import {
  errorClassName,
  labelClassName,
  textareaClassName,
} from '../master-data/forms/formStyles';
import type { ExtractorType } from '../../types/extraction';
import { formatDateTime } from '../../utils/formatters';

const reExtractionSchema = z.object({
  reason: z
    .string()
    .trim()
    .min(1, 'Re-extraction reason is required.')
    .max(1_000, 'Reason must be 1,000 characters or fewer.'),
});

type ReExtractionValues = z.infer<typeof reExtractionSchema>;

export interface ReExtractionRunInfo {
  extractorType: ExtractorType;
  extractorVersion: string;
  sourceSha256Hash: string;
  contentHash: string | null;
  completedAt: string;
}

export function ReExtractionDialog({
  isOpen,
  isPending,
  onClose,
  onConfirm,
  run,
}: {
  isOpen: boolean;
  run: ReExtractionRunInfo | null;
  isPending: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => Promise<void>;
}) {
  const {
    formState: { errors },
    handleSubmit,
    register,
    reset,
  } = useForm<ReExtractionValues>({
    resolver: zodResolver(reExtractionSchema),
    defaultValues: { reason: '' },
  });

  useEffect(() => {
    if (isOpen) {
      reset({ reason: '' });
    }
  }, [isOpen, reset]);

  if (!isOpen) {
    return null;
  }

  const submit = handleSubmit(async ({ reason }) => onConfirm(reason.trim()));

  return (
    <div
      className="fixed inset-0 z-[90] grid place-items-center bg-slate-950/45 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="re-extraction-title"
    >
      <form
        onSubmit={(event) => void submit(event)}
        className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-3xl bg-white p-6 shadow-2xl"
        noValidate
      >
        <div className="flex items-start justify-between gap-4">
          <span className="grid size-11 place-items-center rounded-2xl bg-indigo-50 text-indigo-700">
            <RefreshCw className="size-5" aria-hidden="true" />
          </span>
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            aria-label="Close re-extraction dialog"
            className="grid size-9 place-items-center rounded-xl text-slate-400 hover:bg-slate-100"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>
        <h2
          id="re-extraction-title"
          className="mt-5 text-lg font-semibold text-slate-950"
        >
          Re-extract document content?
        </h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          A new extraction run will be created. The current and all older results remain
          read-only in extraction history.
        </p>
        {run && (
          <dl className="mt-4 grid gap-3 rounded-2xl bg-slate-50 p-4 text-xs sm:grid-cols-2">
            <div>
              <dt className="font-semibold text-slate-500">Current extractor</dt>
              <dd className="mt-1 text-slate-900">
                {run.extractorType} {run.extractorVersion}
              </dd>
            </div>
            <div>
              <dt className="font-semibold text-slate-500">Last extracted</dt>
              <dd className="mt-1 text-slate-900">{formatDateTime(run.completedAt)}</dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="font-semibold text-slate-500">Source hash</dt>
              <dd className="mt-1 break-all font-mono text-[10px] text-slate-700">
                {run.sourceSha256Hash}
              </dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="font-semibold text-slate-500">Content hash</dt>
              <dd className="mt-1 break-all font-mono text-[10px] text-slate-700">
                {run.contentHash ?? 'No content hash'}
              </dd>
            </div>
          </dl>
        )}
        <label className={`${labelClassName} mt-5`}>
          Reason
          <textarea
            {...register('reason')}
            className={textareaClassName}
            placeholder="Explain why a new extraction run is required"
            maxLength={1_000}
            autoFocus
          />
          {errors.reason && <p className={errorClassName}>{errors.reason.message}</p>}
        </label>
        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            className="min-h-10 rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isPending}
            className="min-h-10 rounded-xl bg-indigo-700 px-5 text-sm font-semibold text-white hover:bg-indigo-800 disabled:opacity-60"
          >
            {isPending ? 'Queueing...' : 'Queue Re-extraction'}
          </button>
        </div>
      </form>
    </div>
  );
}
