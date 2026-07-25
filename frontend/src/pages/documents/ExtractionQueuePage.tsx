import { Ban, CalendarRange, ExternalLink, Search } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import { CancelExtractionDialog } from '../../components/documents/CancelExtractionDialog';
import { ExtractionProgress } from '../../components/documents/ExtractionProgress';
import { ExtractionStatusBadge } from '../../components/documents/ExtractionStatusBadge';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { useDocumentFormOptions } from '../../hooks/useDocumentFormOptions';
import { useExtractionMutations } from '../../hooks/useExtraction';
import { useExtractionJobs } from '../../hooks/useExtractionJobs';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import {
  extractionJobStatuses,
  type ExtractionJob,
  type ExtractionJobStatus,
  type ExtractorType,
  isActiveExtractionStatus,
} from '../../types/extraction';
import { formatDateTime } from '../../utils/formatters';

export function ExtractionQueuePage() {
  const user = useAuthStore((state) => state.user);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const departmentLocked = !hasPermission('documents:view_all_departments');
  const [searchInput, setSearchInput] = useState('');
  const search = useDebouncedValue(searchInput.trim(), 400);
  const [departmentId, setDepartmentId] = useState(
    departmentLocked ? (user?.departmentId ?? '') : '',
  );
  const [extractorType, setExtractorType] = useState<ExtractorType | ''>('');
  const [status, setStatus] = useState<ExtractionJobStatus | ''>('');
  const [requestedBy, setRequestedBy] = useState('');
  const [requestedFrom, setRequestedFrom] = useState('');
  const [requestedTo, setRequestedTo] = useState('');
  const [page, setPage] = useState(1);
  const [cancelTarget, setCancelTarget] = useState<ExtractionJob | null>(null);
  const optionsQuery = useDocumentFormOptions();
  const mutations = useExtractionMutations();
  const { showToast } = useToast();
  const jobsQuery = useExtractionJobs(
    {
      page,
      pageSize: 20,
      sortBy: 'requestedAt',
      sortOrder: 'desc',
      ...(search ? { search } : {}),
      ...(departmentId ? { departmentId } : {}),
      ...(extractorType ? { extractorType } : {}),
      ...(status ? { status } : {}),
      ...(requestedBy ? { requestedBy } : {}),
      ...(requestedFrom ? { requestedFrom } : {}),
      ...(requestedTo ? { requestedTo } : {}),
    },
    { pollActive: true },
  );
  const requesters = useMemo(() => {
    const values = new Map<string, string>();
    (jobsQuery.data?.items ?? []).forEach((job) => {
      if (job.requestedBy) {
        values.set(job.requestedBy.id, job.requestedBy.name);
      }
    });
    return [...values.entries()];
  }, [jobsQuery.data?.items]);

  const cancel = async (): Promise<void> => {
    if (!cancelTarget) {
      return;
    }
    try {
      await mutations.cancel.mutateAsync(cancelTarget.id);
      setCancelTarget(null);
      showToast({
        tone: 'success',
        title: 'Cancellation requested',
        message: 'The worker will stop at the next safe checkpoint.',
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Cancellation could not be requested',
        message: getApiErrorMessage(error, 'The job state may have changed.'),
      });
    }
  };

  const resetFilters = (): void => {
    setSearchInput('');
    setDepartmentId(departmentLocked ? (user?.departmentId ?? '') : '');
    setExtractorType('');
    setStatus('');
    setRequestedBy('');
    setRequestedFrom('');
    setRequestedTo('');
    setPage(1);
  };

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Documents"
        title="Extraction Queue"
        description="Track background PDF, DOCX, and XLSX extraction jobs. Active jobs refresh every three seconds."
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
                value={searchInput}
                onChange={(event) => {
                  setSearchInput(event.target.value);
                  setPage(1);
                }}
                className="min-h-11 w-full rounded-xl border border-slate-300 pl-10 pr-3 text-sm outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
                placeholder="Document code, title, or filename"
                maxLength={200}
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
              value={extractorType}
              onChange={(event) => {
                setExtractorType(event.target.value as ExtractorType | '');
                setPage(1);
              }}
              className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
            >
              <option value="">All supported types</option>
              <option value="PDF">PDF</option>
              <option value="DOCX">DOCX</option>
              <option value="XLSX">XLSX</option>
            </select>
          </FilterField>
          <FilterField label="Status">
            <select
              value={status}
              onChange={(event) => {
                setStatus(event.target.value as ExtractionJobStatus | '');
                setPage(1);
              }}
              className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
            >
              <option value="">All statuses</option>
              {extractionJobStatuses.map((candidate) => (
                <option key={candidate} value={candidate}>
                  {candidate.replaceAll('_', ' ')}
                </option>
              ))}
            </select>
          </FilterField>
          <FilterField label="Requested By">
            <select
              value={requestedBy}
              onChange={(event) => {
                setRequestedBy(event.target.value);
                setPage(1);
              }}
              className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
            >
              <option value="">All visible requesters</option>
              {requesters.map(([id, name]) => (
                <option key={id} value={id}>
                  {name}
                </option>
              ))}
            </select>
          </FilterField>
          <DateField
            label="Requested From"
            value={requestedFrom}
            onChange={(value) => {
              setRequestedFrom(value);
              setPage(1);
            }}
          />
          <DateField
            label="Requested To"
            value={requestedTo}
            min={requestedFrom}
            onChange={(value) => {
              setRequestedTo(value);
              setPage(1);
            }}
          />
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

      {jobsQuery.isLoading && (
        <div
          className="h-72 animate-pulse rounded-3xl bg-slate-100"
          aria-label="Loading extraction queue"
        />
      )}
      {jobsQuery.error && (
        <p
          role="alert"
          className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700"
        >
          {getApiErrorMessage(
            jobsQuery.error,
            'Extraction queue could not be loaded within your scope.',
          )}
        </p>
      )}
      {jobsQuery.data && (
        <>
          <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
            <div className="overflow-x-auto">
              <table className="min-w-[100rem] divide-y divide-slate-200">
                <thead className="bg-slate-50">
                  <tr>
                    {[
                      'Requested At',
                      'Document Code',
                      'Title',
                      'Revision',
                      'Filename',
                      'File Type',
                      'Status',
                      'Progress',
                      'Requested By',
                      'Actions',
                    ].map((heading) => (
                      <th
                        key={heading}
                        className="whitespace-nowrap px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-500"
                      >
                        {heading}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {jobsQuery.data.items.map((job) => (
                    <tr key={job.id} className="hover:bg-slate-50">
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">
                        {formatDateTime(job.requestedAt)}
                      </td>
                      <td className="px-4 py-3 text-xs font-semibold text-blue-700">
                        {job.document.baseDocumentCode}
                      </td>
                      <td className="max-w-56 truncate px-4 py-3 text-xs text-slate-700">
                        {job.document.title}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">
                        {job.revision.revisionCode}
                      </td>
                      <td className="max-w-64 break-all px-4 py-3 text-xs font-semibold text-slate-800">
                        {job.file.filename}
                      </td>
                      <td className="px-4 py-3 text-xs font-semibold text-slate-600">
                        {job.file.extension.toUpperCase()}
                      </td>
                      <td className="px-4 py-3">
                        <ExtractionStatusBadge status={job.status} />
                      </td>
                      <td className="px-4 py-3">
                        <ExtractionProgress
                          progress={job.progress}
                          status={job.status}
                          currentStage={job.currentStage}
                        />
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-600">
                        {job.requestedBy?.name ?? 'Unknown user'}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex min-w-max gap-1">
                          {(job.runId || job.resultSummary?.runId) && (
                            <Link
                              to={`/documents/${job.document.id}/revisions/${job.revision.id}/extracted-content?runId=${job.runId ?? job.resultSummary?.runId}`}
                              className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-blue-700 hover:bg-blue-50"
                            >
                              View Result
                            </Link>
                          )}
                          <Link
                            to={`/documents/${job.document.id}`}
                            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-slate-600 hover:bg-slate-100"
                          >
                            <ExternalLink className="size-3.5" aria-hidden="true" />
                            Open Document
                          </Link>
                          {hasPermission('documents:cancel_extraction') &&
                            isActiveExtractionStatus(job.status) &&
                            job.status !== 'CANCEL_REQUESTED' && (
                              <button
                                type="button"
                                onClick={() => setCancelTarget(job)}
                                className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-amber-700 hover:bg-amber-50"
                              >
                                <Ban className="size-3.5" aria-hidden="true" />
                                Cancel
                              </button>
                            )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {jobsQuery.data.items.length === 0 && (
              <div className="px-6 py-12 text-center">
                <p className="text-sm font-semibold text-slate-900">
                  No extraction jobs match these filters.
                </p>
              </div>
            )}
          </div>
          <Pagination
            page={page}
            totalItems={jobsQuery.data.totalItems}
            totalPages={jobsQuery.data.totalPages}
            onPageChange={setPage}
          />
        </>
      )}
      <CancelExtractionDialog
        job={cancelTarget}
        isPending={mutations.cancel.isPending}
        onCancel={() => setCancelTarget(null)}
        onConfirm={cancel}
      />
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

function DateField({
  label,
  min,
  onChange,
  value,
}: {
  label: string;
  value: string;
  min?: string;
  onChange: (value: string) => void;
}) {
  return (
    <FilterField label={label}>
      <span className="relative block">
        <CalendarRange
          className="pointer-events-none absolute left-3 top-3.5 size-4 text-slate-400"
          aria-hidden="true"
        />
        <input
          type="date"
          value={value}
          min={min || undefined}
          onChange={(event) => onChange(event.target.value)}
          className="min-h-11 w-full rounded-xl border border-slate-300 pl-10 pr-3 text-sm"
        />
      </span>
    </FilterField>
  );
}

function Pagination({
  onPageChange,
  page,
  totalItems,
  totalPages,
}: {
  page: number;
  totalItems: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 text-xs text-slate-600 sm:flex-row sm:items-center sm:justify-between">
      <span>
        Page {page} of {Math.max(1, totalPages)} · {totalItems.toLocaleString()} jobs
      </span>
      <div className="flex gap-2">
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
