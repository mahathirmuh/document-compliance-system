import { Ban } from 'lucide-react';

import type { ExtractionJob } from '../../types/extraction';

export function CancelExtractionDialog({
  isPending,
  job,
  onCancel,
  onConfirm,
}: {
  job: ExtractionJob | null;
  isPending: boolean;
  onCancel: () => void;
  onConfirm: () => Promise<void>;
}) {
  if (!job) {
    return null;
  }
  return (
    <div
      className="fixed inset-0 z-[90] grid place-items-center bg-slate-950/45 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="cancel-extraction-title"
    >
      <div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl">
        <span className="grid size-11 place-items-center rounded-2xl bg-amber-50 text-amber-700">
          <Ban className="size-5" aria-hidden="true" />
        </span>
        <h2
          id="cancel-extraction-title"
          className="mt-5 text-lg font-semibold text-slate-950"
        >
          Request extraction cancellation?
        </h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          The worker will stop at the next safe checkpoint. Cancellation may not be
          instant while one page, worksheet, or document element is being read.
        </p>
        <p className="mt-3 break-all text-xs font-semibold text-slate-800">
          {job.file.filename}
        </p>
        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={isPending}
            className="min-h-10 rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700"
          >
            Keep Running
          </button>
          <button
            type="button"
            onClick={() => void onConfirm()}
            disabled={isPending}
            className="min-h-10 rounded-xl bg-amber-600 px-4 text-sm font-semibold text-white hover:bg-amber-700 disabled:opacity-60"
          >
            {isPending ? 'Requesting...' : 'Request Cancellation'}
          </button>
        </div>
      </div>
    </div>
  );
}
