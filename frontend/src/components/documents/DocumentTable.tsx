import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
} from 'lucide-react';

import { ArchivedBadge } from './ArchivedBadge';
import { DocumentActionsMenu } from './DocumentActionsMenu';
import { DocumentCodeField } from './DocumentCodeField';
import { DocumentStatusBadge } from './DocumentStatusBadge';
import { RevisionBadge } from './RevisionBadge';
import { SharePointLink } from './SharePointLink';
import type { DocumentListItem } from '../../types/document';
import { masterDataPageSizes, type SortOrder } from '../../types/masterData';
import { formatDate, formatDateTime } from '../../utils/formatters';

interface DocumentTableProps {
  items: readonly DocumentListItem[];
  isLoading: boolean;
  errorMessage?: string | null;
  page: number;
  pageSize: number;
  totalItems: number;
  totalPages: number;
  sortBy: string;
  sortOrder: SortOrder;
  selectedIds: ReadonlySet<string>;
  canUpdate: boolean;
  canArchive: boolean;
  canRestore: boolean;
  canManageRevisions: boolean;
  canSelect: boolean;
  onSelectionChange: (ids: Set<string>) => void;
  onSort: (key: string) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onArchive: (document: DocumentListItem) => void;
  onRestore: (document: DocumentListItem) => void;
  onRetry: () => void;
}

const sortableColumns = [
  ['baseDocumentCode', 'Base Document Code'],
  ['title', 'Title'],
  ['department', 'Department'],
  ['documentType', 'Document Type'],
] as const;

export function DocumentTable({
  canArchive,
  canManageRevisions,
  canSelect,
  canRestore,
  canUpdate,
  errorMessage,
  isLoading,
  items,
  onArchive,
  onPageChange,
  onPageSizeChange,
  onRestore,
  onRetry,
  onSelectionChange,
  onSort,
  page,
  pageSize,
  selectedIds,
  sortBy,
  sortOrder,
  totalItems,
  totalPages,
}: DocumentTableProps) {
  const allPageSelected =
    canSelect &&
    items.length > 0 &&
    items.every((document) => selectedIds.has(document.id));
  const toggleAll = (): void => {
    const next = new Set(selectedIds);
    items.forEach((document) => {
      if (allPageSelected) {
        next.delete(document.id);
      } else {
        next.add(document.id);
      }
    });
    onSelectionChange(next);
  };
  const toggleOne = (id: string): void => {
    const next = new Set(selectedIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    onSelectionChange(next);
  };

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="hidden overflow-x-auto lg:block">
        <table className="min-w-[94rem] divide-y divide-slate-200">
          <thead className="bg-slate-50">
            <tr>
              <th className="w-12 px-4 py-3">
                {canSelect && (
                  <input
                    type="checkbox"
                    checked={allPageSelected}
                    onChange={toggleAll}
                    aria-label="Select all documents on this page"
                    className="size-4 rounded border-slate-300 text-blue-700 focus:ring-blue-600"
                  />
                )}
              </th>
              {sortableColumns.map(([key, label]) => (
                <SortableHeader
                  key={key}
                  columnKey={key}
                  label={label}
                  sortBy={sortBy}
                  sortOrder={sortOrder}
                  onSort={onSort}
                />
              ))}
              <StaticHeader label="Section" />
              <StaticHeader label="Current Revision" />
              <StaticHeader label="Status" />
              <SortableHeader
                columnKey="effectiveDate"
                label="Effective Date"
                sortBy={sortBy}
                sortOrder={sortOrder}
                onSort={onSort}
              />
              <StaticHeader label="SharePoint" />
              <SortableHeader
                columnKey="updatedAt"
                label="Updated At"
                sortBy={sortBy}
                sortOrder={sortOrder}
                onSort={onSort}
              />
              <StaticHeader label="Actions" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {isLoading
              ? Array.from({ length: 5 }, (_, index) => (
                  <tr key={`loading-${index}`} aria-label="Loading document row">
                    {Array.from({ length: 12 }, (__, cellIndex) => (
                      <td key={cellIndex} className="px-4 py-4">
                        <div className="h-4 w-full max-w-28 animate-pulse rounded bg-slate-100" />
                      </td>
                    ))}
                  </tr>
                ))
              : items.map((document) => (
                  <tr
                    key={document.id}
                    className={`transition hover:bg-slate-50/70 ${
                      selectedIds.has(document.id) ? 'bg-blue-50/50' : ''
                    }`}
                  >
                    <td className="px-4 py-3">
                      {canSelect && (
                        <input
                          type="checkbox"
                          checked={selectedIds.has(document.id)}
                          onChange={() => toggleOne(document.id)}
                          aria-label={`Select ${document.baseDocumentCode}`}
                          className="size-4 rounded border-slate-300 text-blue-700 focus:ring-blue-600"
                        />
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="max-w-56">
                        <DocumentCodeField code={document.baseDocumentCode} />
                        {document.isArchived && (
                          <div className="mt-1.5">
                            <ArchivedBadge />
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="max-w-xs px-4 py-3 text-sm font-medium text-slate-950">
                      <span className="line-clamp-2">{document.title}</span>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-600">
                      <span className="font-semibold text-slate-800">
                        {document.department.code}
                      </span>
                      <span className="block max-w-36 truncate text-xs text-slate-500">
                        {document.department.name}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-600">
                      {document.documentType.code}
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-600">
                      {document.section?.code ?? '—'}
                    </td>
                    <td className="px-4 py-3">
                      <RevisionBadge
                        revisionCode={document.currentRevision?.revisionCode ?? null}
                        isCurrent
                      />
                    </td>
                    <td className="px-4 py-3">
                      <DocumentStatusBadge
                        code={document.currentRevision?.status.code ?? null}
                        name={document.currentRevision?.status.name ?? null}
                      />
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">
                      {formatDate(document.currentRevision?.effectiveDate)}
                    </td>
                    <td className="px-4 py-3">
                      <SharePointLink
                        url={document.currentRevision?.sharepointUrl ?? null}
                        compact
                      />
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">
                      {formatDateTime(document.updatedAt)}
                    </td>
                    <td className="px-3 py-3">
                      <DocumentActionsMenu
                        document={document}
                        canUpdate={canUpdate}
                        canArchive={canArchive}
                        canRestore={canRestore}
                        canManageRevisions={canManageRevisions}
                        onArchive={onArchive}
                        onRestore={onRestore}
                      />
                    </td>
                  </tr>
                ))}
          </tbody>
        </table>
      </div>

      <div className="divide-y divide-slate-100 lg:hidden">
        {isLoading
          ? Array.from({ length: 4 }, (_, index) => (
              <div
                key={index}
                className="space-y-3 p-4"
                aria-label="Loading document card"
              >
                <div className="h-4 w-2/3 animate-pulse rounded bg-slate-100" />
                <div className="h-3 w-full animate-pulse rounded bg-slate-100" />
                <div className="h-8 w-1/2 animate-pulse rounded bg-slate-100" />
              </div>
            ))
          : items.map((document) => (
              <article
                key={document.id}
                className={selectedIds.has(document.id) ? 'bg-blue-50/50 p-4' : 'p-4'}
              >
                <div className="flex items-start gap-3">
                  {canSelect && (
                    <input
                      type="checkbox"
                      checked={selectedIds.has(document.id)}
                      onChange={() => toggleOne(document.id)}
                      aria-label={`Select ${document.baseDocumentCode}`}
                      className="mt-0.5 size-4 rounded border-slate-300 text-blue-700 focus:ring-blue-600"
                    />
                  )}
                  <div className="min-w-0 flex-1">
                    <DocumentCodeField code={document.baseDocumentCode} />
                    <h3 className="mt-2 text-sm font-semibold text-slate-950">
                      {document.title}
                    </h3>
                    <p className="mt-1 text-xs text-slate-500">
                      {document.department.code} · {document.documentType.code}
                      {document.section ? ` · ${document.section.code}` : ''}
                    </p>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <RevisionBadge
                        revisionCode={document.currentRevision?.revisionCode ?? null}
                        isCurrent
                      />
                      <DocumentStatusBadge
                        code={document.currentRevision?.status.code ?? null}
                        name={document.currentRevision?.status.name ?? null}
                      />
                      {document.isArchived && <ArchivedBadge />}
                    </div>
                    <div className="mt-3">
                      <DocumentActionsMenu
                        document={document}
                        canUpdate={canUpdate}
                        canArchive={canArchive}
                        canRestore={canRestore}
                        canManageRevisions={canManageRevisions}
                        onArchive={onArchive}
                        onRestore={onRestore}
                      />
                    </div>
                  </div>
                </div>
              </article>
            ))}
      </div>

      {!isLoading && errorMessage && (
        <div className="flex min-h-48 flex-col items-center justify-center px-6 py-10 text-center">
          <p className="text-sm font-semibold text-rose-700">
            Document register could not be loaded
          </p>
          <p className="mt-1 max-w-lg text-xs leading-5 text-slate-500">
            {errorMessage}
          </p>
          <button
            type="button"
            onClick={onRetry}
            className="mt-4 inline-flex min-h-9 items-center gap-2 rounded-xl border border-slate-300 px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            <RefreshCw className="size-3.5" aria-hidden="true" />
            Try again
          </button>
        </div>
      )}
      {!isLoading && !errorMessage && items.length === 0 && (
        <div className="flex min-h-52 flex-col items-center justify-center px-6 py-10 text-center">
          <p className="text-sm font-semibold text-slate-900">No documents found</p>
          <p className="mt-1 max-w-md text-xs leading-5 text-slate-500">
            Adjust the active filters or add the first document to this register.
          </p>
        </div>
      )}
      {!isLoading && !errorMessage && items.length > 0 && (
        <TablePagination
          page={page}
          pageSize={pageSize}
          totalItems={totalItems}
          totalPages={totalPages}
          onPageChange={onPageChange}
          onPageSizeChange={onPageSizeChange}
        />
      )}
    </div>
  );
}

function StaticHeader({ label }: { label: string }) {
  return (
    <th className="whitespace-nowrap px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-500">
      {label}
    </th>
  );
}

function SortableHeader({
  columnKey,
  label,
  onSort,
  sortBy,
  sortOrder,
}: {
  columnKey: string;
  label: string;
  sortBy: string;
  sortOrder: SortOrder;
  onSort: (key: string) => void;
}) {
  const isSorted = sortBy === columnKey;
  const SortIcon = isSorted
    ? sortOrder === 'desc'
      ? ArrowDown
      : ArrowUp
    : ArrowUpDown;
  return (
    <th className="whitespace-nowrap px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-500">
      <button
        type="button"
        onClick={() => onSort(columnKey)}
        className="inline-flex items-center gap-1.5 hover:text-slate-900"
      >
        {label}
        <SortIcon
          className={`size-3.5 ${isSorted ? 'text-blue-700' : 'text-slate-300'}`}
          aria-hidden="true"
        />
      </button>
    </th>
  );
}

function TablePagination({
  onPageChange,
  onPageSizeChange,
  page,
  pageSize,
  totalItems,
  totalPages,
}: {
  page: number;
  pageSize: number;
  totalItems: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}) {
  const first = (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, totalItems);
  return (
    <footer className="flex flex-col gap-3 border-t border-slate-200 bg-slate-50/70 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-xs text-slate-500">
        Showing {first}–{last} of {totalItems}
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-xs text-slate-500">
          Rows
          <select
            value={pageSize}
            onChange={(event) => onPageSizeChange(Number(event.target.value))}
            className="min-h-9 rounded-lg border border-slate-300 bg-white px-2 text-xs font-semibold text-slate-700"
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
        <button
          type="button"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          aria-label="Previous page"
          className="grid size-9 place-items-center rounded-lg border border-slate-300 bg-white text-slate-600 disabled:opacity-40"
        >
          <ChevronLeft className="size-4" aria-hidden="true" />
        </button>
        <button
          type="button"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          aria-label="Next page"
          className="grid size-9 place-items-center rounded-lg border border-slate-300 bg-white text-slate-600 disabled:opacity-40"
        >
          <ChevronRight className="size-4" aria-hidden="true" />
        </button>
      </div>
    </footer>
  );
}
