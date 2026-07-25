import { Ban, ExternalLink, Search } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import { CancelOCRDialog } from '../../components/documents/CancelOCRDialog';
import { OCRProgress } from '../../components/documents/OCRProgress';
import { ocrProfileLabels } from '../../components/documents/ocrDisplay';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { useDocumentFormOptions } from '../../hooks/useDocumentFormOptions';
import { useOCRMutations } from '../../hooks/useOCR';
import { useOCRJobs } from '../../hooks/useOCRJobs';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import {
  isActiveOCRStatus,
  ocrJobStatuses,
  ocrLanguageProfiles,
  type OCRJobListItem,
  type OCRJobStatus,
  type OCRLanguageProfile,
} from '../../types/ocr';
import { formatDateTime } from '../../utils/formatters';

export function OCRQueuePage() {
  const user = useAuthStore((state) => state.user);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const departmentLocked = !hasPermission('documents:view_all_departments');
  const [searchInput, setSearchInput] = useState('');
  const search = useDebouncedValue(searchInput.trim(), 400);
  const [departmentId, setDepartmentId] = useState(
    departmentLocked ? (user?.departmentId ?? '') : '',
  );
  const [status, setStatus] = useState<OCRJobStatus | ''>('');
  const [languageProfile, setLanguageProfile] = useState<OCRLanguageProfile | ''>('');
  const [requestedBy, setRequestedBy] = useState('');
  const [requestedFrom, setRequestedFrom] = useState('');
  const [requestedTo, setRequestedTo] = useState('');
  const [page, setPage] = useState(1);
  const [cancelTarget, setCancelTarget] = useState<OCRJobListItem | null>(null);
  const optionsQuery = useDocumentFormOptions();
  const jobsQuery = useOCRJobs(
    {
      page,
      pageSize: 20,
      sortBy: 'requestedAt',
      sortOrder: 'desc',
      ...(search ? { search } : {}),
      ...(departmentId ? { departmentId } : {}),
      ...(status ? { status } : {}),
      ...(languageProfile ? { languageProfile } : {}),
      ...(requestedBy ? { requestedBy } : {}),
      ...(requestedFrom
        ? { requestedFrom: localDayBoundary(requestedFrom, 'start') }
        : {}),
      ...(requestedTo ? { requestedTo: localDayBoundary(requestedTo, 'end') } : {}),
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
  const mutations = useOCRMutations();
  const { showToast } = useToast();

  const cancel = async (): Promise<void> => {
    if (!cancelTarget) {
      return;
    }
    try {
      await mutations.cancel.mutateAsync(cancelTarget.id);
      setCancelTarget(null);
      showToast({
        tone: 'success',
        title: 'OCR cancellation requested',
        message: 'The worker will stop at the next safe checkpoint.',
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'OCR cancellation could not be requested',
        message: getApiErrorMessage(error, 'The job state may have changed.'),
      });
    }
  };

  const resetFilters = (): void => {
    setSearchInput('');
    setDepartmentId(departmentLocked ? (user?.departmentId ?? '') : '');
    setStatus('');
    setLanguageProfile('');
    setRequestedBy('');
    setRequestedFrom('');
    setRequestedTo('');
    setPage(1);
  };

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Documents"
        title="OCR Queue"
        description="Track local scanned-PDF OCR jobs. Active rows refresh every three seconds; OCR is never sent to a cloud service."
      />
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
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
                placeholder="Document code, filename, or requester"
                className="min-h-11 w-full rounded-xl border border-slate-300 pl-10 pr-3 text-sm outline-none focus:border-blue-600"
              />
            </span>
          </label>
          <label className="text-xs font-semibold text-slate-700">
            Department
            <select
              aria-label="Department"
              value={departmentId}
              disabled={departmentLocked}
              onChange={(event) => {
                setDepartmentId(event.target.value);
                setPage(1);
              }}
              className="mt-1.5 min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm disabled:bg-slate-100"
            >
              {!departmentLocked && <option value="">All departments</option>}
              {(optionsQuery.data?.departments ?? []).map((department) => (
                <option key={department.id} value={department.id}>
                  {department.code} · {department.name}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs font-semibold text-slate-700">
            Status
            <select
              aria-label="Status"
              value={status}
              onChange={(event) => {
                setStatus(event.target.value as OCRJobStatus | '');
                setPage(1);
              }}
              className="mt-1.5 min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
            >
              <option value="">All statuses</option>
              {ocrJobStatuses.map((value) => (
                <option key={value} value={value}>
                  {value.replaceAll('_', ' ')}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs font-semibold text-slate-700">
            Language Profile
            <select
              aria-label="Language Profile"
              value={languageProfile}
              onChange={(event) => {
                setLanguageProfile(event.target.value as OCRLanguageProfile | '');
                setPage(1);
              }}
              className="mt-1.5 min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
            >
              <option value="">All profiles</option>
              {ocrLanguageProfiles.map((value) => (
                <option key={value} value={value}>
                  {ocrProfileLabels[value]}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="mt-4 flex flex-wrap items-end gap-3">
          <label className="min-w-56 text-xs font-semibold text-slate-700">
            Requested By
            <select
              value={requestedBy}
              onChange={(event) => {
                setRequestedBy(event.target.value);
                setPage(1);
              }}
              className="mt-1.5 min-h-10 w-full rounded-xl border border-slate-300 bg-white px-3 text-xs"
            >
              <option value="">All requesters</option>
              {requesters.map(([id, name]) => (
                <option key={id} value={id}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label className="min-w-44 text-xs font-semibold text-slate-700">
            Requested From
            <input
              aria-label="Requested From"
              type="date"
              value={requestedFrom}
              max={requestedTo || undefined}
              onChange={(event) => {
                setRequestedFrom(event.target.value);
                setPage(1);
              }}
              className="mt-1.5 min-h-10 w-full rounded-xl border border-slate-300 bg-white px-3 text-xs"
            />
          </label>
          <label className="min-w-44 text-xs font-semibold text-slate-700">
            Requested To
            <input
              aria-label="Requested To"
              type="date"
              value={requestedTo}
              min={requestedFrom || undefined}
              onChange={(event) => {
                setRequestedTo(event.target.value);
                setPage(1);
              }}
              className="mt-1.5 min-h-10 w-full rounded-xl border border-slate-300 bg-white px-3 text-xs"
            />
          </label>
          <button
            type="button"
            onClick={resetFilters}
            className="min-h-10 rounded-xl border border-slate-300 px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            Reset Filters
          </button>
          {departmentLocked && (
            <p className="ml-auto text-[11px] text-slate-500">
              Results are locked to your department.
            </p>
          )}
        </div>
      </section>

      {jobsQuery.isLoading && (
        <div
          aria-label="Loading OCR queue"
          className="h-72 animate-pulse rounded-3xl bg-slate-100"
        />
      )}
      {jobsQuery.error && (
        <p
          role="alert"
          className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700"
        >
          {getApiErrorMessage(jobsQuery.error, 'OCR jobs could not be loaded.')}
        </p>
      )}
      {jobsQuery.data && (
        <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="min-w-[1180px] divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  {[
                    'Requested At',
                    'Document',
                    'Revision',
                    'Filename',
                    'Pages',
                    'Language Profile',
                    'Status / Progress',
                    'Requested By',
                    'Actions',
                  ].map((heading) => (
                    <th
                      key={heading}
                      className="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-500"
                    >
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {jobsQuery.data.items.map((job) => (
                  <tr key={job.id} className="align-top hover:bg-slate-50">
                    <td className="whitespace-nowrap px-4 py-4 text-xs text-slate-600">
                      {formatDateTime(job.requestedAt)}
                    </td>
                    <td className="px-4 py-4">
                      <Link
                        to={`/documents/${job.document.id}`}
                        className="text-xs font-semibold text-blue-700 hover:text-blue-900"
                      >
                        {job.document.baseDocumentCode}
                      </Link>
                    </td>
                    <td className="whitespace-nowrap px-4 py-4 text-xs text-slate-700">
                      {job.revision.revisionCode}
                    </td>
                    <td className="max-w-60 break-all px-4 py-4 text-xs text-slate-700">
                      {job.file.filename}
                    </td>
                    <td className="whitespace-nowrap px-4 py-4 text-xs text-slate-700">
                      {job.pageNumbers.length > 0
                        ? job.pageNumbers.join(', ')
                        : 'Auto-selected'}
                    </td>
                    <td className="px-4 py-4 text-xs text-slate-700">
                      {ocrProfileLabels[job.languageProfile]}
                    </td>
                    <td className="min-w-60 px-4 py-4">
                      <OCRProgress
                        status={job.status}
                        progress={job.progress}
                        currentStage={job.currentStage}
                      />
                    </td>
                    <td className="whitespace-nowrap px-4 py-4 text-xs text-slate-700">
                      {job.requestedBy?.name ?? 'System'}
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex flex-wrap gap-1">
                        {job.runId && hasPermission('documents:view_ocr_results') && (
                          <Link
                            to={`/documents/${job.document.id}/revisions/${job.revision.id}/ocr-results?runId=${job.runId}`}
                            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-blue-700 hover:bg-blue-50"
                          >
                            View
                          </Link>
                        )}
                        <Link
                          to={`/documents/${job.document.id}`}
                          aria-label={`Open ${job.document.baseDocumentCode}`}
                          className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-slate-600 hover:bg-slate-100"
                        >
                          <ExternalLink className="size-3.5" aria-hidden="true" />
                          Open
                        </Link>
                        {hasPermission('documents:cancel_ocr') &&
                          isActiveOCRStatus(job.status) &&
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
            <p className="p-12 text-center text-sm text-slate-600">
              No OCR jobs match the selected filters.
            </p>
          )}
          <Pagination
            page={page}
            totalPages={jobsQuery.data.totalPages}
            onPageChange={setPage}
          />
        </section>
      )}
      <CancelOCRDialog
        job={cancelTarget}
        isPending={mutations.cancel.isPending}
        onCancel={() => setCancelTarget(null)}
        onConfirm={() => void cancel()}
      />
    </div>
  );
}

function localDayBoundary(value: string, boundary: 'start' | 'end'): string {
  const time = boundary === 'start' ? '00:00:00.000' : '23:59:59.999';
  return new Date(`${value}T${time}`).toISOString();
}

function Pagination({
  onPageChange,
  page,
  totalPages,
}: {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}) {
  if (totalPages <= 1) {
    return null;
  }
  return (
    <div className="flex items-center justify-between border-t border-slate-200 px-5 py-4 text-xs text-slate-600">
      <span>
        Page {page} of {totalPages}
      </span>
      <div className="flex gap-2">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => onPageChange(Math.max(1, page - 1))}
          className="min-h-9 rounded-lg border border-slate-300 px-3 font-semibold disabled:opacity-50"
        >
          Previous
        </button>
        <button
          type="button"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
          className="min-h-9 rounded-lg border border-slate-300 px-3 font-semibold disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
  );
}
