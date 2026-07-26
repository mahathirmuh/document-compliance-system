import { RefreshCw } from 'lucide-react';
import type { ReactNode } from 'react';

export function Phase8ErrorAlert({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="flex flex-col gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800 sm:flex-row sm:items-center sm:justify-between"
    >
      <span>{message}</span>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex min-h-9 items-center justify-center gap-2 rounded-lg border border-rose-200 bg-white px-3 text-xs font-semibold"
        >
          <RefreshCw className="size-3.5" aria-hidden="true" />
          Retry
        </button>
      )}
    </div>
  );
}

export function Phase8Loading({ label }: { label: string }) {
  return (
    <div aria-label={label} className="h-64 animate-pulse rounded-3xl bg-slate-100" />
  );
}

export function Phase8Pagination({
  label = 'records',
  onPageChange,
  onPageSizeChange,
  page,
  pageSize,
  pageSizeOptions = [20, 50, 100],
  totalItems,
  totalPages,
}: {
  page: number;
  totalItems: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  pageSize?: number;
  pageSizeOptions?: readonly number[];
  onPageSizeChange?: (pageSize: number) => void;
  label?: string;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 text-xs text-slate-600 sm:flex-row sm:items-center sm:justify-between">
      <span>
        Page {page} of {Math.max(1, totalPages)} · {totalItems.toLocaleString()} {label}
      </span>
      <div className="flex flex-wrap gap-2">
        {pageSize !== undefined && onPageSizeChange && (
          <label className="flex items-center gap-2 font-semibold">
            Per page
            <select
              aria-label={`${label} per page`}
              value={pageSize}
              onChange={(event) => onPageSizeChange(Number(event.target.value))}
              className="min-h-9 rounded-lg border border-slate-300 bg-white px-2"
            >
              {pageSizeOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
        )}
        <button
          type="button"
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={page <= 1}
          className="min-h-9 rounded-lg border border-slate-300 px-3 font-semibold disabled:opacity-50"
        >
          Previous
        </button>
        <button
          type="button"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          className="min-h-9 rounded-lg border border-slate-300 px-3 font-semibold disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
  );
}

export function Phase8FilterField({
  children,
  label,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="block text-xs font-semibold text-slate-700">
      {label}
      <span className="mt-1.5 block">{children}</span>
    </label>
  );
}
