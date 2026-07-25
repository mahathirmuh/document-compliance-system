import { X } from 'lucide-react';
import { useEffect, useState } from 'react';

export function RedetectLanguageDialog({
  isOpen,
  isPending,
  onClose,
  onConfirm,
}: {
  isOpen: boolean;
  isPending: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState('');
  const error =
    reason.trim().length === 0
      ? 'A reason is required.'
      : reason.trim().length > 1_000
        ? 'Reason must be 1,000 characters or fewer.'
        : null;

  useEffect(() => {
    if (isOpen) {
      setReason('');
    }
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Re-detect languages"
      className="fixed inset-0 z-[70] grid place-items-center bg-slate-950/55 p-4"
    >
      <form
        className="w-full max-w-lg rounded-3xl bg-white p-6 shadow-2xl"
        onSubmit={(event) => {
          event.preventDefault();
          if (!error) {
            onConfirm(reason.trim());
          }
        }}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">
              Re-detect languages
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              A new result will be created from the current merged content. The previous
              result remains in history.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="grid size-9 place-items-center rounded-xl text-slate-500 hover:bg-slate-100"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>
        <label
          htmlFor="language-redetect-reason"
          className="mt-5 block text-xs font-semibold text-slate-700"
        >
          Reason
        </label>
        <textarea
          id="language-redetect-reason"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          maxLength={1_000}
          rows={4}
          aria-describedby={error ? 'language-redetect-reason-error' : undefined}
          className="mt-1.5 w-full rounded-xl border border-slate-300 p-3 text-sm"
        />
        {error && (
          <p id="language-redetect-reason-error" className="mt-1 text-xs text-rose-700">
            {error}
          </p>
        )}
        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            className="min-h-10 rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isPending || Boolean(error)}
            className="min-h-10 rounded-xl bg-violet-700 px-4 text-sm font-semibold text-white disabled:opacity-50"
          >
            {isPending ? 'Queueing…' : 'Queue Re-detection'}
          </button>
        </div>
      </form>
    </div>
  );
}
