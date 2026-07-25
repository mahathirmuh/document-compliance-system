import { X } from 'lucide-react';

import type { OCRJobListItem } from '../../types/ocr';

export function CancelOCRDialog({
  isPending,
  job,
  onCancel,
  onConfirm,
}: {
  job: OCRJobListItem | null;
  isPending: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  if (!job) {
    return null;
  }
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Request OCR cancellation?"
      className="fixed inset-0 z-[70] grid place-items-center bg-slate-950/55 p-4"
    >
      <section className="w-full max-w-lg rounded-3xl bg-white p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">
              Request OCR cancellation?
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              The worker checks cancellation between pages and OCR passes. A page
              currently being recognised may finish first, and completed page results
              remain in partial history.
            </p>
          </div>
          <button
            type="button"
            onClick={onCancel}
            aria-label="Close"
            className="grid size-9 shrink-0 place-items-center rounded-xl text-slate-500 hover:bg-slate-100"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>
        <p className="mt-4 rounded-xl bg-slate-50 p-3 text-xs text-slate-700">
          {job.document.baseDocumentCode} · {job.file.filename}
        </p>
        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={isPending}
            className="min-h-10 rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700 disabled:opacity-50"
          >
            Keep Running
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isPending}
            className="min-h-10 rounded-xl bg-amber-600 px-4 text-sm font-semibold text-white disabled:opacity-50"
          >
            {isPending ? 'Requesting…' : 'Request Cancellation'}
          </button>
        </div>
      </section>
    </div>
  );
}
