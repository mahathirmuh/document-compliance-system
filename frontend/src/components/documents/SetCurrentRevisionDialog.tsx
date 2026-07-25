import { CheckCircle2 } from 'lucide-react';
import { useEffect, useState } from 'react';

import type { DocumentRevisionListItem } from '../../types/documentRevision';

interface SetCurrentRevisionDialogProps {
  revision: DocumentRevisionListItem | null;
  isPending: boolean;
  onClose: () => void;
  onConfirm: (reason: string | null) => Promise<void>;
}

export function SetCurrentRevisionDialog({
  isPending,
  onClose,
  onConfirm,
  revision,
}: SetCurrentRevisionDialogProps) {
  const [reason, setReason] = useState('');
  useEffect(() => setReason(''), [revision]);

  if (!revision) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-[90] grid place-items-center bg-slate-950/45 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="set-current-title"
    >
      <section className="w-full max-w-lg rounded-3xl bg-white p-6 shadow-2xl">
        <div className="grid size-11 place-items-center rounded-2xl bg-blue-50 text-blue-700">
          <CheckCircle2 className="size-5" aria-hidden="true" />
        </div>
        <h2
          id="set-current-title"
          className="mt-5 text-lg font-semibold text-slate-950"
        >
          Set {revision.revisionCode} as current?
        </h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          The existing current revision becomes non-current. It is not automatically
          superseded.
        </p>
        <label className="mt-5 block text-xs font-semibold text-slate-700">
          Reason (optional)
          <textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            maxLength={1_000}
            className="mt-1.5 min-h-24 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-600"
          />
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
            type="button"
            onClick={() => void onConfirm(reason.trim() || null)}
            disabled={isPending}
            className="min-h-10 rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white hover:bg-blue-800 disabled:opacity-60"
          >
            {isPending ? 'Updating...' : 'Set Current'}
          </button>
        </div>
      </section>
    </div>
  );
}
