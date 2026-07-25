import { zodResolver } from '@hookform/resolvers/zod';
import { AlertTriangle, Replace, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { FileDropzone } from './FileDropzone';
import {
  errorClassName,
  labelClassName,
  textareaClassName,
} from '../master-data/forms/formStyles';
import type { DocumentFileListItem } from '../../types/documentFile';
import { shortFileHash } from '../../utils/documentFiles';

const replaceSchema = z.object({
  reason: z
    .string()
    .trim()
    .min(1, 'Replacement reason is required.')
    .max(1_000, 'Reason must be 1,000 characters or fewer.'),
  acknowledgeSensitive: z.boolean(),
});

type ReplaceValues = z.infer<typeof replaceSchema>;

interface ReplaceDocumentFileDialogProps {
  file: DocumentFileListItem | null;
  revisionStatus?: string | null;
  isPending: boolean;
  onClose: () => void;
  onConfirm: (
    file: File,
    reason: string,
    onProgress: (progress: number) => void,
  ) => Promise<void>;
}

const sensitiveStatuses = new Set(['FINAL', 'EFFECTIVE', 'APPROVED', 'PUBLISHED']);

export function ReplaceDocumentFileDialog({
  file,
  isPending,
  onClose,
  onConfirm,
  revisionStatus,
}: ReplaceDocumentFileDialogProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [fileError, setFileError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const sensitive = sensitiveStatuses.has(revisionStatus?.toUpperCase() ?? '');
  const {
    formState: { errors },
    handleSubmit,
    register,
    reset,
    watch,
  } = useForm<ReplaceValues>({
    resolver: zodResolver(replaceSchema),
    defaultValues: { reason: '', acknowledgeSensitive: false },
  });

  useEffect(() => {
    if (file) {
      setFiles([]);
      setFileError(null);
      setProgress(0);
      reset({ reason: '', acknowledgeSensitive: false });
    }
  }, [file, reset]);

  if (!file) {
    return null;
  }

  const submit = handleSubmit(async ({ acknowledgeSensitive, reason }) => {
    const replacement = files[0];
    if (!replacement) {
      setFileError('Select a replacement PDF, DOCX, or XLSX.');
      return;
    }
    if (sensitive && !acknowledgeSensitive) {
      return;
    }
    setFileError(null);
    await onConfirm(replacement, reason.trim(), setProgress);
  });

  return (
    <div
      className="fixed inset-0 z-[90] overflow-y-auto bg-slate-950/45 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="replace-file-title"
    >
      <form
        onSubmit={(event) => {
          if (!files[0]) {
            setFileError('Select a replacement PDF, DOCX, or XLSX.');
          }
          void submit(event);
        }}
        className="mx-auto my-4 w-full max-w-2xl rounded-3xl bg-white p-6 shadow-2xl"
        noValidate
      >
        <div className="flex items-start justify-between gap-4">
          <span className="grid size-11 place-items-center rounded-2xl bg-amber-50 text-amber-700">
            <Replace className="size-5" aria-hidden="true" />
          </span>
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            aria-label="Close replace file dialog"
            className="grid size-9 place-items-center rounded-xl text-slate-400 hover:bg-slate-100"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>
        <h2
          id="replace-file-title"
          className="mt-5 text-lg font-semibold text-slate-950"
        >
          Replace physical file
        </h2>
        <div className="mt-4 rounded-2xl bg-slate-50 p-4">
          <p className="break-all text-sm font-semibold text-slate-900">
            {file.originalFilename}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Hash {shortFileHash(file.sha256Hash)} · Revision {file.revisionCode}
            {revisionStatus ? ` · ${revisionStatus}` : ''}
          </p>
        </div>
        {sensitive && (
          <div className="mt-4 flex gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-900">
            <AlertTriangle className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
            <div>
              <p className="text-sm font-semibold">Sensitive revision replacement</p>
              <p className="mt-1 text-xs leading-5">
                This revision is final or effective. The server only permits a Super
                Admin or Document Controller to continue.
              </p>
            </div>
          </div>
        )}
        <div className="mt-5">
          <FileDropzone
            files={files}
            onFilesChange={(next) => {
              setFiles(next);
              setFileError(null);
            }}
            disabled={isPending}
            label="Select replacement document file"
          />
          {fileError && <p className={errorClassName}>{fileError}</p>}
        </div>
        <label className={`${labelClassName} mt-5`}>
          Reason
          <textarea
            {...register('reason')}
            className={textareaClassName}
            placeholder="Explain why this file must be replaced"
          />
          {errors.reason && <p className={errorClassName}>{errors.reason.message}</p>}
        </label>
        {sensitive && (
          <label className="mt-4 flex items-start gap-3 text-sm text-slate-700">
            <input
              {...register('acknowledgeSensitive')}
              type="checkbox"
              className="mt-0.5 size-4 rounded border-slate-300"
            />
            I understand the existing file remains in history and this sensitive
            replacement is audited.
          </label>
        )}
        {isPending && (
          <div className="mt-5" role="status">
            <div className="flex justify-between text-xs font-semibold text-slate-700">
              <span>Uploading replacement</span>
              <span>{progress}%</span>
            </div>
            <div
              role="progressbar"
              aria-label="Replacement upload progress"
              aria-valuenow={progress}
              aria-valuemin={0}
              aria-valuemax={100}
              className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100"
            >
              <div className="h-full bg-blue-700" style={{ width: `${progress}%` }} />
            </div>
          </div>
        )}
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
            disabled={isPending || (sensitive && !watch('acknowledgeSensitive'))}
            className="min-h-11 rounded-xl bg-amber-600 px-5 text-sm font-semibold text-white hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isPending ? 'Replacing...' : 'Replace File'}
          </button>
        </div>
      </form>
    </div>
  );
}
