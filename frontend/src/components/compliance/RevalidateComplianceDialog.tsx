import { useEffect, useState } from 'react';

export function RevalidateComplianceDialog({
  errorMessage,
  isOpen,
  isPending,
  onClose,
  onConfirm,
}: {
  isOpen: boolean;
  isPending: boolean;
  errorMessage?: string | null;
  onClose: () => void;
  onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState('');
  const [validationMessage, setValidationMessage] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setReason('');
      setValidationMessage(null);
    }
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  const submit = (): void => {
    const trimmed = reason.trim();
    if (!trimmed) {
      setValidationMessage('Revalidation reason is required.');
      return;
    }
    onConfirm(trimmed);
  };

  return (
    <div
      className="fixed inset-0 z-[100] grid place-items-center bg-slate-950/50 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="revalidate-title"
    >
      <div className="w-full max-w-lg rounded-3xl bg-white p-6 shadow-2xl">
        <h2 id="revalidate-title" className="text-lg font-semibold text-slate-950">
          Revalidate compliance
        </h2>
        <p className="mt-1 text-sm leading-6 text-slate-600">
          A new run will be created. Previous results and manual findings remain in
          history.
        </p>
        <label className="mt-5 block text-xs font-semibold text-slate-700">
          Reason
          <textarea
            autoFocus
            rows={4}
            maxLength={2000}
            value={reason}
            onChange={(event) => {
              setReason(event.target.value);
              setValidationMessage(null);
            }}
            className="mt-1.5 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
          />
        </label>
        {(validationMessage || errorMessage) && (
          <p role="alert" className="mt-2 text-xs text-rose-700">
            {validationMessage ?? errorMessage}
          </p>
        )}
        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            className="min-h-10 rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={isPending}
            className="min-h-10 rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white disabled:opacity-50"
          >
            {isPending ? 'Queueing…' : 'Queue Revalidation'}
          </button>
        </div>
      </div>
    </div>
  );
}
