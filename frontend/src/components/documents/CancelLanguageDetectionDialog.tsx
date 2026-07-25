import type { LanguageDetectionJobListItem } from '../../types/languageDetection';

export function CancelLanguageDetectionDialog({
  isPending,
  job,
  onClose,
  onConfirm,
}: {
  job: LanguageDetectionJobListItem | null;
  isPending: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  if (!job) {
    return null;
  }
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Cancel language detection?"
      className="fixed inset-0 z-[70] grid place-items-center bg-slate-950/55 p-4"
    >
      <section className="w-full max-w-lg rounded-3xl bg-white p-6 shadow-2xl">
        <h2 className="text-lg font-semibold text-slate-950">
          Cancel language detection?
        </h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          The worker will stop at its next safe checkpoint. Previously completed results
          are not overwritten.
        </p>
        <p className="mt-4 rounded-xl bg-slate-50 p-3 text-xs text-slate-700">
          {job.document.baseDocumentCode} · {job.file.filename}
        </p>
        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
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
