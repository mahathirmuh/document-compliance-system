import { CalendarRange, Search } from 'lucide-react';
import { useMemo, useState } from 'react';

import { getApiErrorMessage } from '../../api/errors';
import { DocumentFileTable } from '../../components/documents/DocumentFileTable';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { useDocumentFileHistory } from '../../hooks/useDocumentFileHistory';
import { useDocumentFormOptions } from '../../hooks/useDocumentFormOptions';
import { useAuthStore } from '../../store/authStore';
import type {
  DocumentFileStatus,
  SupportedDocumentExtension,
} from '../../types/documentFile';

export function UploadHistoryPage() {
  const user = useAuthStore((state) => state.user);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const departmentLocked = !hasPermission('documents:view_all_departments');
  const [search, setSearch] = useState('');
  const [departmentId, setDepartmentId] = useState(
    departmentLocked ? (user?.departmentId ?? '') : '',
  );
  const [fileExtension, setFileExtension] = useState<SupportedDocumentExtension | ''>(
    '',
  );
  const [fileStatus, setFileStatus] = useState<DocumentFileStatus | ''>('');
  const [uploadedBy, setUploadedBy] = useState('');
  const [uploadedFrom, setUploadedFrom] = useState('');
  const [uploadedTo, setUploadedTo] = useState('');
  const [page, setPage] = useState(1);
  const optionsQuery = useDocumentFormOptions();
  const params = {
    page,
    pageSize: 20,
    ...(search.trim() ? { search: search.trim() } : {}),
    ...(departmentId ? { departmentId } : {}),
    ...(fileExtension ? { fileExtension } : {}),
    ...(fileStatus ? { fileStatus } : {}),
    ...(uploadedBy ? { uploadedBy } : {}),
    ...(uploadedFrom ? { uploadedFrom } : {}),
    ...(uploadedTo ? { uploadedTo } : {}),
  };
  const historyQuery = useDocumentFileHistory(params);
  const uploaders = useMemo(() => {
    const values = new Map<string, string>();
    (historyQuery.data?.items ?? []).forEach((file) => {
      if (file.uploadedBy) {
        values.set(file.uploadedBy.id, file.uploadedBy.name);
      }
    });
    return [...values.entries()];
  }, [historyQuery.data?.items]);

  const resetFilters = (): void => {
    setSearch('');
    setDepartmentId(departmentLocked ? (user?.departmentId ?? '') : '');
    setFileExtension('');
    setFileStatus('');
    setUploadedBy('');
    setUploadedFrom('');
    setUploadedTo('');
    setPage(1);
  };

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Documents"
        title="Upload History"
        description="Review available, replaced, and deleted physical-file records within your department scope."
      />
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <label className="block text-xs font-semibold text-slate-700 xl:col-span-2">
            Search
            <span className="relative mt-1.5 block">
              <Search
                className="pointer-events-none absolute left-3 top-3.5 size-4 text-slate-400"
                aria-hidden="true"
              />
              <input
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value);
                  setPage(1);
                }}
                className="min-h-11 w-full rounded-xl border border-slate-300 pl-10 pr-3 text-sm outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
                placeholder="Filename, document code, or title"
              />
            </span>
          </label>
          <FilterField label="Department">
            <select
              value={departmentId}
              onChange={(event) => {
                setDepartmentId(event.target.value);
                setPage(1);
              }}
              disabled={departmentLocked}
              className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm disabled:bg-slate-100"
            >
              <option value="">
                {departmentLocked
                  ? 'No department assigned'
                  : 'All accessible departments'}
              </option>
              {(optionsQuery.data?.departments ?? []).map((department) => (
                <option key={department.id} value={department.id}>
                  {department.code} — {department.name}
                </option>
              ))}
            </select>
          </FilterField>
          <FilterField label="File Type">
            <select
              value={fileExtension}
              onChange={(event) => {
                setFileExtension(event.target.value as SupportedDocumentExtension | '');
                setPage(1);
              }}
              className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
            >
              <option value="">All types</option>
              <option value="pdf">PDF</option>
              <option value="docx">DOCX</option>
              <option value="xlsx">XLSX</option>
            </select>
          </FilterField>
          <FilterField label="File Status">
            <select
              value={fileStatus}
              onChange={(event) => {
                setFileStatus(event.target.value as DocumentFileStatus | '');
                setPage(1);
              }}
              className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
            >
              <option value="">All statuses</option>
              {[
                'UPLOADING',
                'AVAILABLE',
                'QUARANTINED',
                'REPLACED',
                'DELETED',
                'FAILED',
              ].map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </FilterField>
          <FilterField label="Uploaded By">
            <select
              value={uploadedBy}
              onChange={(event) => {
                setUploadedBy(event.target.value);
                setPage(1);
              }}
              className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
            >
              <option value="">All visible uploaders</option>
              {uploaders.map(([id, name]) => (
                <option key={id} value={id}>
                  {name}
                </option>
              ))}
            </select>
          </FilterField>
          <FilterField label="Uploaded From">
            <span className="relative block">
              <CalendarRange
                className="pointer-events-none absolute left-3 top-3.5 size-4 text-slate-400"
                aria-hidden="true"
              />
              <input
                type="date"
                value={uploadedFrom}
                onChange={(event) => {
                  setUploadedFrom(event.target.value);
                  setPage(1);
                }}
                className="min-h-11 w-full rounded-xl border border-slate-300 pl-10 pr-3 text-sm"
              />
            </span>
          </FilterField>
          <FilterField label="Uploaded To">
            <span className="relative block">
              <CalendarRange
                className="pointer-events-none absolute left-3 top-3.5 size-4 text-slate-400"
                aria-hidden="true"
              />
              <input
                type="date"
                value={uploadedTo}
                min={uploadedFrom || undefined}
                onChange={(event) => {
                  setUploadedTo(event.target.value);
                  setPage(1);
                }}
                className="min-h-11 w-full rounded-xl border border-slate-300 pl-10 pr-3 text-sm"
              />
            </span>
          </FilterField>
        </div>
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={resetFilters}
            className="min-h-9 rounded-lg border border-slate-300 px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            Reset Filters
          </button>
        </div>
      </section>

      {historyQuery.isLoading && (
        <div className="h-72 animate-pulse rounded-3xl bg-slate-100" />
      )}
      {historyQuery.error && (
        <div
          role="alert"
          className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700"
        >
          {getApiErrorMessage(
            historyQuery.error,
            'Upload history could not be loaded within your scope.',
          )}
        </div>
      )}
      {historyQuery.data && (
        <section className="space-y-4">
          <DocumentFileTable
            files={historyQuery.data.items}
            canDownload={hasPermission('documents:download')}
            canReplace={false}
            canDelete={false}
            canRestore={false}
            showDocument
            onReplace={() => undefined}
            onDelete={() => undefined}
            onRestore={() => undefined}
          />
          <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 text-xs text-slate-600 sm:flex-row sm:items-center sm:justify-between">
            <span>
              Page {historyQuery.data.page} of{' '}
              {Math.max(1, historyQuery.data.totalPages)} ·{' '}
              {historyQuery.data.totalItems.toLocaleString()} files
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setPage((current) => Math.max(1, current - 1))}
                disabled={page <= 1}
                className="min-h-9 rounded-lg border border-slate-300 px-3 font-semibold disabled:opacity-50"
              >
                Previous
              </button>
              <button
                type="button"
                onClick={() => setPage((current) => current + 1)}
                disabled={page >= historyQuery.data.totalPages}
                className="min-h-9 rounded-lg border border-slate-300 px-3 font-semibold disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

function FilterField({
  children,
  label,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block text-xs font-semibold text-slate-700">
      {label}
      <span className="mt-1.5 block">{children}</span>
    </label>
  );
}
