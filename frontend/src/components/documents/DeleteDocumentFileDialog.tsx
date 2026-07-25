import { zodResolver } from '@hookform/resolvers/zod';
import { Trash2, X } from 'lucide-react';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import {
  errorClassName,
  labelClassName,
  textareaClassName,
} from '../master-data/forms/formStyles';
import type { DocumentFileListItem } from '../../types/documentFile';

const deleteSchema = z.object({
  reason: z
    .string()
    .trim()
    .min(1, 'Deletion reason is required.')
    .max(1_000, 'Reason must be 1,000 characters or fewer.'),
});

type DeleteValues = z.infer<typeof deleteSchema>;

interface DeleteDocumentFileDialogProps {
  file: DocumentFileListItem | null;
  isPending: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => Promise<void>;
}

export function DeleteDocumentFileDialog({
  file,
  isPending,
  onClose,
  onConfirm,
}: DeleteDocumentFileDialogProps) {
  const {
    formState: { errors },
    handleSubmit,
    register,
    reset,
  } = useForm<DeleteValues>({
    resolver: zodResolver(deleteSchema),
    defaultValues: { reason: '' },
  });

  useEffect(() => {
    if (file) {
      reset({ reason: '' });
    }
  }, [file, reset]);

  if (!file) {
    return null;
  }

  const submit = handleSubmit(async ({ reason }) => onConfirm(reason.trim()));

  return (
    <div
      className="fixed inset-0 z-[90] grid place-items-center bg-slate-950/45 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-file-title"
    >
      <form
        onSubmit={(event) => void submit(event)}
        className="w-full max-w-lg rounded-3xl bg-white p-6 shadow-2xl"
        noValidate
      >
        <div className="flex items-start justify-between gap-4">
          <span className="grid size-11 place-items-center rounded-2xl bg-rose-50 text-rose-700">
            <Trash2 className="size-5" aria-hidden="true" />
          </span>
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            aria-label="Close delete file dialog"
            className="grid size-9 place-items-center rounded-xl text-slate-400 hover:bg-slate-100"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>
        <h2
          id="delete-file-title"
          className="mt-5 text-lg font-semibold text-slate-950"
        >
          Remove active physical file?
        </h2>
        <p className="mt-2 break-all text-sm font-semibold text-slate-800">
          {file.originalFilename}
        </p>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          File will be removed from active storage but retained in file history.
        </p>
        <label className={`${labelClassName} mt-5`}>
          Reason
          <textarea
            {...register('reason')}
            className={textareaClassName}
            placeholder="Explain why this file should be removed"
          />
          {errors.reason && <p className={errorClassName}>{errors.reason.message}</p>}
        </label>
        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            className="min-h-11 rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isPending}
            className="min-h-11 rounded-xl bg-rose-600 px-5 text-sm font-semibold text-white hover:bg-rose-700 disabled:opacity-60"
          >
            {isPending ? 'Removing...' : 'Remove File'}
          </button>
        </div>
      </form>
    </div>
  );
}
