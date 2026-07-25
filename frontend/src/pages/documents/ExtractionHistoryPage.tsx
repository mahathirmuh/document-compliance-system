import { Download, Eye, History, RefreshCw, Search } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import { ExtractionStatusBadge } from '../../components/documents/ExtractionStatusBadge';
import { ReExtractionDialog } from '../../components/documents/ReExtractionDialog';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { useDocumentFormOptions } from '../../hooks/useDocumentFormOptions';
import { useExtractionMutations } from '../../hooks/useExtraction';
import { useExtractionJobs } from '../../hooks/useExtractionJobs';
import { useExtractionExport, useExtractionRun } from '../../hooks/useExtractedContent';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import {
  terminalExtractionStatuses,
  type ExtractionJob,
  type ExtractionJobStatus,
  type ExtractorType,
} from '../../types/extraction';
import { downloadFile } from '../../utils/downloadFile';
import { formatDateTime } from '../../utils/formatters';

export function ExtractionHistoryPage() {
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
  const [page, setPage] = useState(1);
  const [reextractJob, setReextractJob] = useState<ExtractionJob | null>(null);
  const optionsQuery = useDocumentFormOptions();
  const mutations = useExtractionMutations();
  const exportMutation = useExtractionExport();
  const { showToast } = useToast();
  const jobsQuery = useExtractionJobs({
    page,
    pageSize: 20,
    sortBy: 'completedAt',
    sortOrder: 'desc',
    ...(search ? { search } : {}),
    ...(departmentId ? { departmentId } : {}),
    ...(extractorType ? { extractorType } : {}),
    status: status || terminalExtractionStatuses,
  });
  const visibleJobs = jobsQuery.data?.items ?? [];
  const selectedRunId =
    reextractJob?.runId ?? reextractJob?.resultSummary?.runId ?? null;
  const selectedRunQuery = useExtractionRun(selectedRunId, selectedRunId !== null);

  const exportRun = async (
    job: ExtractionJob,
    format: 'json' | 'txt',
  ): Promise<void> => {
    const runId = job.runId ?? job.resultSummary?.runId;
    if (!runId) {
      return;
    }
    try {
      const result = await exportMutation.mutateAsync({ runId, format });
      downloadFile(
        result,
        `${job.document.baseDocumentCode}_${job.revision.revisionCode}_extraction.${format}`,
      );
      showToast({
        tone: 'success',
        title: `Extraction ${format.toUpperCase()} downloaded`,
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Extraction export failed',
        message: getApiErrorMessage(error, 'The export could not be downloaded.'),
      });
    }
  };

  const reextract = async (reason: string): Promise<void> => {
    if (!reextractJob) {
      return;
    }
    try {
      await mutations.reextract.mutateAsync({
        fileId: reextractJob.file.id,
        payload: { reason },
      });
      setReextractJob(null);
      showToast({
        tone: 'success',
        title: 'Re-extraction queued',
        message: 'Older extraction results remain in history.',
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Re-extraction could not be queued',
        message: getApiErrorMessage(error, 'Review the current file state.'),
      });
    }
  };

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Documents"
        title="Extraction History"
        description="Review completed, partial, OCR-required, failed, and cancelled extraction jobs within your data scope."
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
                maxLength={200}
                onChange={(event) => {
                  setSearchInput(event.target.value);
                  setPage(1);
                }}
                placeholder="Document code, title, or filename"
                className="min-h-11 w-full rounded-xl border border-slate-300 pl-10 pr-3 text-sm outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
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
          <FilterField label="Extractor">
            <select
              value={extractorType}
              onChange={(event) => {
                setExtractorType(event.target.value as ExtractorType | '');
                setPage(1);
              }}
              className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
            >
              <option value="">All extractors</option>
              <option value="PDF">PDF</option>
              <option value="DOCX">DOCX</option>
              <option value="XLSX">XLSX</option>
            </select>
          </FilterField>
          <FilterField label="Terminal Status">
            <select
              value={status}
              onChange={(event) => {
                setStatus(event.target.value as ExtractionJobStatus | '');
                setPage(1);
              }}
              className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
            >
              <option value="">All terminal statuses</option>
              {terminalExtractionStatuses.map((candidate) => (
                <option key={candidate} value={candidate}>
                  {candidate.replaceAll('_', ' ')}
                </option>
              ))}
            </select>
          </FilterField>
        </div>
      </section>

      {jobsQuery.isLoading && (
        <div
          className="h-72 animate-pulse rounded-3xl bg-slate-100"
          aria-label="Loading extraction history"
        />
      )}
      {jobsQuery.error && (
        <p
          role="alert"
          className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700"
        >
          {getApiErrorMessage(
            jobsQuery.error,
            'Extraction history could not be loaded.',
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
                      'Completed At',
                      'Document Code',
                      'Revision',
                      'Filename',
                      'Extractor',
                      'Status',
                      'Pages / Sheets',
                      'Blocks',
                      'Characters',
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
                  {visibleJobs.map((job) => (
                    <tr key={job.id} className="hover:bg-slate-50">
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">
                        {job.completedAt
                          ? formatDateTime(job.completedAt)
                          : job.cancelledAt
                            ? formatDateTime(job.cancelledAt)
                            : '—'}
                      </td>
                      <td className="px-4 py-3 text-xs font-semibold text-blue-700">
                        {job.document.baseDocumentCode}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">
                        {job.revision.revisionCode}
                      </td>
                      <td className="max-w-64 break-all px-4 py-3 text-xs text-slate-700">
                        {job.file.filename}
                      </td>
                      <td className="px-4 py-3 text-xs font-semibold text-slate-700">
                        {job.resultSummary?.extractorType ??
                          job.file.extension.toUpperCase()}
                      </td>
                      <td className="px-4 py-3">
                        <ExtractionStatusBadge status={job.status} />
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-600">
                        {job.resultSummary
                          ? job.resultSummary.totalPages ||
                            job.resultSummary.totalSheets ||
                            '—'
                          : '—'}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-600">
                        {job.resultSummary?.totalBlocks.toLocaleString() ?? '—'}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-600">
                        {job.resultSummary?.totalCharacters.toLocaleString() ?? '—'}
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
                              <Eye className="size-3.5" aria-hidden="true" />
                              View Content
                            </Link>
                          )}
                          <Link
                            to={`/documents/${job.document.id}/revisions/${job.revision.id}/extraction-history`}
                            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-slate-600 hover:bg-slate-100"
                          >
                            <History className="size-3.5" aria-hidden="true" />
                            History
                          </Link>
                          {(job.runId || job.resultSummary?.runId) &&
                            hasPermission('documents:export_extracted_content') &&
                            (['json', 'txt'] as const).map((format) => (
                              <button
                                key={format}
                                type="button"
                                onClick={() => void exportRun(job, format)}
                                disabled={exportMutation.isPending}
                                className="inline-flex min-h-9 items-center gap-1 rounded-lg px-2.5 text-[11px] font-semibold uppercase text-slate-600 hover:bg-slate-100 disabled:opacity-50"
                              >
                                <Download className="size-3" aria-hidden="true" />
                                {format}
                              </button>
                            ))}
                          {(job.runId || job.resultSummary?.runId) &&
                            hasPermission('documents:reextract') && (
                              <button
                                type="button"
                                onClick={() => setReextractJob(job)}
                                className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-indigo-700 hover:bg-indigo-50"
                              >
                                <RefreshCw className="size-3.5" aria-hidden="true" />
                                Re-extract
                              </button>
                            )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {visibleJobs.length === 0 && (
              <div className="px-6 py-12 text-center">
                <p className="text-sm font-semibold text-slate-900">
                  No extraction history matches these filters.
                </p>
              </div>
            )}
          </div>
          <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 text-xs text-slate-600 sm:flex-row sm:items-center sm:justify-between">
            <span>
              Page {page} of {Math.max(1, jobsQuery.data.totalPages)} ·{' '}
              {jobsQuery.data.totalItems.toLocaleString()} jobs
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
                disabled={page >= jobsQuery.data.totalPages}
                className="min-h-9 rounded-lg border border-slate-300 px-3 font-semibold disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
      <ReExtractionDialog
        isOpen={reextractJob !== null}
        run={selectedRunQuery.data ?? null}
        isPending={mutations.reextract.isPending}
        onClose={() => setReextractJob(null)}
        onConfirm={reextract}
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
