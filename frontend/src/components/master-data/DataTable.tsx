import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
} from 'lucide-react';
import type { ReactNode } from 'react';

import { EmptyMasterDataState } from './EmptyMasterDataState';
import { masterDataPageSizes, type SortOrder } from '../../types/masterData';

export interface DataTableColumn<TItem> {
  key: string;
  header: string;
  render: (item: TItem) => ReactNode;
  sortable?: boolean;
  headerClassName?: string;
  cellClassName?: string;
}

interface DataTableProps<TItem> {
  columns: readonly DataTableColumn<TItem>[];
  items: readonly TItem[];
  getRowKey: (item: TItem) => string;
  isLoading: boolean;
  errorMessage?: string | null;
  onRetry?: () => void;
  page: number;
  pageSize: number;
  totalItems: number;
  totalPages: number;
  sortBy?: string;
  sortOrder?: SortOrder;
  onSort: (key: string) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  emptyTitle?: string;
  emptyDescription?: string;
}

export function DataTable<TItem>({
  columns,
  emptyDescription,
  emptyTitle,
  errorMessage,
  getRowKey,
  isLoading,
  items,
  onPageChange,
  onPageSizeChange,
  onRetry,
  onSort,
  page,
  pageSize,
  sortBy,
  sortOrder,
  totalItems,
  totalPages,
}: DataTableProps<TItem>) {
  const firstItem = totalItems === 0 ? 0 : (page - 1) * pageSize + 1;
  const lastItem = Math.min(page * pageSize, totalItems);

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200">
          <thead className="bg-slate-50">
            <tr>
              {columns.map((column) => {
                const isSorted = sortBy === column.key;
                const SortIcon = isSorted
                  ? sortOrder === 'desc'
                    ? ArrowDown
                    : ArrowUp
                  : ArrowUpDown;
                return (
                  <th
                    key={column.key}
                    scope="col"
                    className={`whitespace-nowrap px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.09em] text-slate-500 ${column.headerClassName ?? ''}`}
                  >
                    {column.sortable ? (
                      <button
                        type="button"
                        onClick={() => onSort(column.key)}
                        className="inline-flex items-center gap-1.5 rounded-md transition hover:text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
                      >
                        {column.header}
                        <SortIcon
                          className={`size-3.5 ${
                            isSorted ? 'text-blue-700' : 'text-slate-300'
                          }`}
                          aria-hidden="true"
                        />
                      </button>
                    ) : (
                      column.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {isLoading
              ? Array.from({ length: Math.min(pageSize, 6) }, (_, index) => (
                  <tr key={`loading-${index}`} aria-label="Loading row">
                    {columns.map((column) => (
                      <td key={column.key} className="px-4 py-4">
                        <div className="h-4 w-full max-w-32 animate-pulse rounded bg-slate-100" />
                      </td>
                    ))}
                  </tr>
                ))
              : items.map((item) => (
                  <tr key={getRowKey(item)} className="transition hover:bg-slate-50/70">
                    {columns.map((column) => (
                      <td
                        key={column.key}
                        className={`px-4 py-3.5 text-sm text-slate-600 ${column.cellClassName ?? ''}`}
                      >
                        {column.render(item)}
                      </td>
                    ))}
                  </tr>
                ))}
          </tbody>
        </table>
      </div>

      {!isLoading && errorMessage && (
        <div className="flex min-h-48 flex-col items-center justify-center px-6 py-10 text-center">
          <p className="text-sm font-semibold text-rose-700">
            Master data could not be loaded
          </p>
          <p className="mt-1 max-w-lg text-xs leading-5 text-slate-500">
            {errorMessage}
          </p>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="mt-4 inline-flex min-h-9 items-center gap-2 rounded-xl border border-slate-300 px-3 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
            >
              <RefreshCw className="size-3.5" aria-hidden="true" />
              Try again
            </button>
          )}
        </div>
      )}

      {!isLoading && !errorMessage && items.length === 0 && (
        <EmptyMasterDataState
          {...(emptyTitle ? { title: emptyTitle } : {})}
          {...(emptyDescription ? { description: emptyDescription } : {})}
        />
      )}

      {!isLoading && !errorMessage && items.length > 0 && (
        <footer className="flex flex-col gap-3 border-t border-slate-200 bg-slate-50/70 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-slate-500">
            Showing <span className="font-semibold text-slate-700">{firstItem}</span>–
            <span className="font-semibold text-slate-700">{lastItem}</span> of{' '}
            <span className="font-semibold text-slate-700">{totalItems}</span>
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 text-xs text-slate-500">
              Rows
              <select
                value={pageSize}
                onChange={(event) => onPageSizeChange(Number(event.target.value))}
                className="min-h-9 rounded-lg border border-slate-300 bg-white px-2 text-xs font-semibold text-slate-700 outline-none focus:border-blue-600"
                aria-label="Rows per page"
              >
                {masterDataPageSizes.map((size) => (
                  <option key={size} value={size}>
                    {size}
                  </option>
                ))}
              </select>
            </label>
            <span className="text-xs font-medium text-slate-600">
              Page {page} of {Math.max(totalPages, 1)}
            </span>
            <div className="flex gap-1">
              <button
                type="button"
                aria-label="Previous page"
                disabled={page <= 1}
                onClick={() => onPageChange(page - 1)}
                className="grid size-9 place-items-center rounded-lg border border-slate-300 bg-white text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <ChevronLeft className="size-4" aria-hidden="true" />
              </button>
              <button
                type="button"
                aria-label="Next page"
                disabled={page >= totalPages}
                onClick={() => onPageChange(page + 1)}
                className="grid size-9 place-items-center rounded-lg border border-slate-300 bg-white text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <ChevronRight className="size-4" aria-hidden="true" />
              </button>
            </div>
          </div>
        </footer>
      )}
    </div>
  );
}
