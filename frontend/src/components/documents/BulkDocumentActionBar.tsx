import { Archive, CheckCircle2, RotateCcw, X } from 'lucide-react';
import { useState } from 'react';

import type { DocumentFormStatusOption } from '../../types/documentFormOptions';

interface BulkDocumentActionBarProps {
  selectedCount: number;
  isArchivedView: boolean;
  statuses: readonly DocumentFormStatusOption[];
  canArchive: boolean;
  canRestore: boolean;
  canUpdateStatus: boolean;
  isPending: boolean;
  onClear: () => void;
  onArchive: () => void;
  onRestore: () => void;
  onUpdateStatus: (statusId: string) => void;
}

export function BulkDocumentActionBar({
  canArchive,
  canRestore,
  canUpdateStatus,
  isArchivedView,
  isPending,
  onArchive,
  onClear,
  onRestore,
  onUpdateStatus,
  selectedCount,
  statuses,
}: BulkDocumentActionBarProps) {
  const [statusId, setStatusId] = useState('');

  if (selectedCount === 0) {
    return null;
  }

  return (
    <div
      className="sticky top-20 z-20 flex flex-col gap-3 rounded-2xl border border-blue-200 bg-blue-950 px-4 py-3 text-white shadow-xl sm:flex-row sm:items-center"
      role="toolbar"
      aria-label="Bulk document actions"
    >
      <div className="flex flex-1 items-center justify-between gap-3">
        <p className="text-sm font-semibold">{selectedCount} selected</p>
        <button
          type="button"
          onClick={onClear}
          disabled={isPending}
          className="grid size-8 place-items-center rounded-lg text-blue-200 hover:bg-white/10 hover:text-white sm:hidden"
          aria-label="Clear selection"
        >
          <X className="size-4" aria-hidden="true" />
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {!isArchivedView && canUpdateStatus && (
          <div className="flex items-center gap-2">
            <select
              value={statusId}
              onChange={(event) => setStatusId(event.target.value)}
              disabled={isPending}
              aria-label="Bulk document status"
              className="min-h-9 max-w-44 rounded-lg border border-white/20 bg-white px-2.5 text-xs font-semibold text-slate-900"
            >
              <option value="">Select status</option>
              {statuses.map((status) => (
                <option key={status.id} value={status.id}>
                  {status.code} — {status.name}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => statusId && onUpdateStatus(statusId)}
              disabled={isPending || !statusId}
              className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-blue-600 px-3 text-xs font-semibold hover:bg-blue-500 disabled:opacity-50"
            >
              <CheckCircle2 className="size-3.5" aria-hidden="true" />
              Update status
            </button>
          </div>
        )}
        {!isArchivedView && canArchive && (
          <button
            type="button"
            onClick={onArchive}
            disabled={isPending}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-amber-500 px-3 text-xs font-semibold text-slate-950 hover:bg-amber-400 disabled:opacity-50"
          >
            <Archive className="size-3.5" aria-hidden="true" />
            Archive
          </button>
        )}
        {isArchivedView && canRestore && (
          <button
            type="button"
            onClick={onRestore}
            disabled={isPending}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-emerald-500 px-3 text-xs font-semibold text-emerald-950 hover:bg-emerald-400 disabled:opacity-50"
          >
            <RotateCcw className="size-3.5" aria-hidden="true" />
            Restore
          </button>
        )}
        <button
          type="button"
          onClick={onClear}
          disabled={isPending}
          className="hidden size-9 place-items-center rounded-lg text-blue-200 hover:bg-white/10 hover:text-white sm:grid"
          aria-label="Clear selection"
        >
          <X className="size-4" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
