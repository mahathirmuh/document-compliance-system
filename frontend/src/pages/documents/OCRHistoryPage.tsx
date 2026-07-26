import { Download, Eye, RefreshCw, Search } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import { OCRStatusBadge } from '../../components/documents/OCRStatusBadge';
import {
  formatConfidence,
  ocrProfileLabels,
} from '../../components/documents/ocrDisplay';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { useOCRMutations } from '../../hooks/useOCR';
import { useOCRJobs } from '../../hooks/useOCRJobs';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import { terminalOCRJobStatuses } from '../../types/ocr';
import { downloadFile } from '../../utils/downloadFile';
import { formatDateTime } from '../../utils/formatters';

export function OCRHistoryPage() {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const [searchInput, setSearchInput] = useState('');
  const search = useDebouncedValue(searchInput.trim(), 400);
  const [page, setPage] = useState(1);
  const jobsQuery = useOCRJobs(
    {
      page,
      pageSize: 20,
      status: terminalOCRJobStatuses,
      sortBy: 'completedAt',
      sortOrder: 'desc',
      ...(search ? { search } : {}),
    },
    { pollActive: false },
  );
  const mutations = useOCRMutations();
  const { showToast } = useToast();

  const exportRun = async (
    runId: string,
    format: 'json' | 'txt',
    fallbackName: string,
  ): Promise<void> => {
    try {
      const result = await mutations.export.mutateAsync({ runId, format });
      downloadFile(result, `${fallbackName}_ocr.${format}`);
      showToast({
        tone: 'success',
        title: `OCR ${format.toUpperCase()} downloaded`,
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'OCR export failed',
        message: getApiErrorMessage(error, 'The export could not be downloaded.'),
      });
    }
  };

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Documents"
        title="OCR History"
        description="Review retained OCR runs, confidence, provider provenance, and exports. Re-OCR creates a new run without deleting this history."
      />
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <label className="block max-w-2xl text-xs font-semibold text-slate-700">
          Search history
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
              placeholder="Document code, revision, filename, or requester"
              className="min-h-11 w-full rounded-xl border border-slate-300 pl-10 pr-3 text-sm outline-none focus:border-blue-600"
            />
          </span>
        </label>
      </section>

      {jobsQuery.isLoading && (
        <div
          aria-label="Loading OCR history"
          className="h-72 animate-pulse rounded-3xl bg-slate-100"
        />
      )}
      {jobsQuery.error && (
        <p
          role="alert"
          className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700"
        >
          {getApiErrorMessage(jobsQuery.error, 'OCR history could not be loaded.')}
        </p>
      )}
      {jobsQuery.data && (
        <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="min-w-[1180px] divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  {[
                    'Completed At',
                    'Document',
                    'Revision',
                    'Filename',
                    'Provider',
                    'Profile',
                    'Pages Processed',
                    'Blocks',
                    'Average Confidence',
                    'Status',
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
                      {job.completedAt ? formatDateTime(job.completedAt) : '—'}
                    </td>
                    <td className="px-4 py-4 text-xs font-semibold text-slate-800">
                      {job.document.baseDocumentCode}
                    </td>
                    <td className="whitespace-nowrap px-4 py-4 text-xs text-slate-700">
                      {job.revision.revisionCode}
                    </td>
                    <td className="max-w-52 break-all px-4 py-4 text-xs text-slate-700">
                      {job.file.filename}
                    </td>
                    <td className="whitespace-nowrap px-4 py-4 text-xs text-slate-700">
                      {job.provider}
                    </td>
                    <td className="max-w-44 px-4 py-4 text-xs text-slate-700">
                      {ocrProfileLabels[job.languageProfile]}
                    </td>
                    <td className="whitespace-nowrap px-4 py-4 text-xs tabular-nums text-slate-700">
                      {job.processedPageNumbers.length.toLocaleString()}
                    </td>
                    <td className="whitespace-nowrap px-4 py-4 text-xs tabular-nums text-slate-700">
                      {summaryNumber(
                        job.resultSummary,
                        'totalBlocks',
                      )?.toLocaleString() ?? '—'}
                    </td>
                    <td className="whitespace-nowrap px-4 py-4 text-xs text-slate-700">
                      {formatConfidence(
                        summaryNumber(job.resultSummary, 'averageConfidence'),
                      )}
                    </td>
                    <td className="px-4 py-4">
                      <OCRStatusBadge status={job.status} />
                    </td>
                    <td className="whitespace-nowrap px-4 py-4 text-xs text-slate-700">
                      {job.requestedBy?.name ?? 'System'}
                    </td>
                    <td className="px-4 py-4">
                      {job.runId ? (
                        <div className="flex min-w-52 flex-wrap gap-1">
                          <Link
                            to={`/documents/${job.document.id}/revisions/${job.revision.id}/ocr-results?runId=${job.runId}`}
                            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-blue-700 hover:bg-blue-50"
                          >
                            <Eye className="size-3.5" aria-hidden="true" />
                            View
                          </Link>
                          {hasPermission('documents:reocr') &&
                            (job.status === 'COMPLETED' ||
                              job.status === 'PARTIALLY_COMPLETED') && (
                              <Link
                                to={`/documents/${job.document.id}/revisions/${job.revision.id}/ocr-results?runId=${job.runId}&reocr=true`}
                                className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-indigo-700 hover:bg-indigo-50"
                              >
                                <RefreshCw className="size-3.5" aria-hidden="true" />
                                Re-run
                              </Link>
                            )}
                          {(['json', 'txt'] as const).map((format) => (
                            <button
                              key={format}
                              type="button"
                              onClick={() =>
                                void exportRun(
                                  job.runId ?? '',
                                  format,
                                  `${job.document.baseDocumentCode}_${job.revision.revisionCode}`,
                                )
                              }
                              disabled={mutations.export.isPending}
                              className="inline-flex min-h-9 items-center gap-1 rounded-lg px-2 text-[10px] font-semibold uppercase text-slate-600 hover:bg-slate-100 disabled:opacity-50"
                            >
                              <Download className="size-3" aria-hidden="true" />
                              {format}
                            </button>
                          ))}
                        </div>
                      ) : (
                        <span className="text-xs text-slate-400">No run result</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {jobsQuery.data.items.length === 0 && (
            <p className="p-12 text-center text-sm text-slate-600">
              No OCR history matches this search.
            </p>
          )}
          {jobsQuery.data.totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-slate-200 px-5 py-4 text-xs text-slate-600">
              <span>
                Page {page} of {jobsQuery.data.totalPages}
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                  className="min-h-9 rounded-lg border border-slate-300 px-3 font-semibold disabled:opacity-50"
                >
                  Previous
                </button>
                <button
                  type="button"
                  disabled={page >= jobsQuery.data.totalPages}
                  onClick={() => setPage((current) => current + 1)}
                  className="min-h-9 rounded-lg border border-slate-300 px-3 font-semibold disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function summaryNumber(
  summary: Record<string, unknown> | null,
  key: string,
): number | null {
  const value = summary?.[key];
  return typeof value === 'number' ? value : null;
}
