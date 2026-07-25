import { zodResolver } from '@hookform/resolvers/zod';
import { Archive, X } from 'lucide-react';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import {
  errorClassName,
  labelClassName,
  textareaClassName,
} from '../master-data/forms/formStyles';

const archiveSchema = z.object({
  reason: z
    .string()
    .trim()
    .min(1, 'Archive reason is required.')
    .max(1_000, 'Archive reason must be 1,000 characters or fewer.'),
});

type ArchiveFormValues = z.infer<typeof archiveSchema>;

interface ArchiveDocumentDialogProps {
  isOpen: boolean;
  documentCount?: number;
  isPending: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => Promise<void>;
}

export function ArchiveDocumentDialog({
  documentCount = 1,
  isOpen,
  isPending,
  onClose,
  onConfirm,
}: ArchiveDocumentDialogProps) {
  const {
    formState: { errors },
    handleSubmit,
    register,
    reset,
  } = useForm<ArchiveFormValues>({
    resolver: zodResolver(archiveSchema),
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

  const submit = handleSubmit(async ({ reason }) => {
    await onConfirm(reason.trim());
  });

  return (
    <div
      className="fixed inset-0 z-[90] grid place-items-center bg-slate-950/45 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="archive-dialog-title"
    >
      <form
        onSubmit={(event) => void submit(event)}
        className="w-full max-w-lg rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl"
        noValidate
      >
        <div className="flex items-start justify-between gap-4">
          <div className="grid size-11 place-items-center rounded-2xl bg-amber-50 text-amber-700">
            <Archive className="size-5" aria-hidden="true" />
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            aria-label="Close archive dialog"
            className="grid size-9 place-items-center rounded-xl text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>
        <h2
          id="archive-dialog-title"
          className="mt-5 text-lg font-semibold text-slate-950"
        >
          Archive {documentCount === 1 ? 'document' : `${documentCount} documents`}?
        </h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Archived records remain available with their revisions and can be restored
          later. No file or metadata is deleted.
        </p>
        <label className={`${labelClassName} mt-5`}>
          Reason
          <textarea
            {...register('reason')}
            className={textareaClassName}
            placeholder="Explain why the document is being archived"
            aria-invalid={Boolean(errors.reason)}
            autoFocus
          />
          {errors.reason && <p className={errorClassName}>{errors.reason.message}</p>}
        </label>
        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            className="min-h-10 rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isPending}
            className="min-h-10 rounded-xl bg-amber-600 px-4 text-sm font-semibold text-white hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isPending ? 'Archiving...' : 'Archive'}
          </button>
        </div>
      </form>
    </div>
  );
}
