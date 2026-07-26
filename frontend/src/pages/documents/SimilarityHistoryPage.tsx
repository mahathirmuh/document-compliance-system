import { Download, Eye, RefreshCw, Search, X } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import {
  Phase8ErrorAlert,
  Phase8FilterField,
  Phase8Loading,
  Phase8Pagination,
} from '../../components/compliance/Phase8TableUtilities';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { useSimilarityMutations } from '../../hooks/useSimilarity';
import { useSimilarityJobs } from '../../hooks/useSimilarityJobs';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type { SimilarityJob } from '../../types/similarity';
import { terminalSimilarityJobStatuses } from '../../types/similarity';
import { downloadFile } from '../../utils/downloadFile';
import { formatDateTime } from '../../utils/formatters';

const percent = (value: number | null | undefined): string =>
  value === null || value === undefined ? '—' : `${(value * 100).toFixed(1)}%`;

export function SimilarityHistoryPage() {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const [searchInput, setSearchInput] = useState('');
  const search = useDebouncedValue(searchInput.trim(), 350);
  const [page, setPage] = useState(1);
  const [rerunTarget, setRerunTarget] = useState<SimilarityJob | null>(null);
  const query = useSimilarityJobs({
    page,
    pageSize: 20,
    status: terminalSimilarityJobStatuses,
    sortBy: 'completedAt',
    sortOrder: 'desc',
    ...(search ? { search } : {}),
  });
  const mutations = useSimilarityMutations();
  const { showToast } = useToast();

  const exportRun = async (
    job: SimilarityJob,
    format: 'json' | 'xlsx',
  ): Promise<void> => {
    const runId = job.resultSummary?.runId;
    if (!runId) {
      return;
    }
    try {
      const result = await mutations.export.mutateAsync({ runId, format });
      downloadFile(
        result,
        `${job.document?.baseDocumentCode ?? 'document'}_similarity.${format}`,
      );
      showToast({ tone: 'success', title: `Similarity ${format.toUpperCase()} ready` });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Similarity export failed',
        message: getApiErrorMessage(error, 'Try the export again.'),
      });
    }
  };

  const rerun = async (reason: string): Promise<void> => {
    const runId = rerunTarget?.resultSummary?.runId;
    if (!runId) {
      return;
    }
    try {
      await mutations.rerun.mutateAsync({ runId, payload: { reason } });
      setRerunTarget(null);
      showToast({
        tone: 'success',
        title: 'Similarity re-analysis queued',
        message: 'The previous run remains available in history.',
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Re-analysis could not be queued',
        message: getApiErrorMessage(error, 'Review the run and try again.'),
      });
    }
  };

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Documents"
        title="Similarity History"
        description="Review completed local-model analyses, retain prior runs, and export bounded result datasets."
      />
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <Phase8FilterField label="Search">
          <span className="relative block max-w-xl">
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
              placeholder="Document code, revision, or model"
              className="min-h-11 w-full rounded-xl border border-slate-300 pl-10 pr-3 text-sm"
            />
          </span>
        </Phase8FilterField>
      </section>

      {query.isLoading && <Phase8Loading label="Loading similarity history" />}
      {query.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            query.error,
            'Similarity history could not be loaded.',
          )}
          onRetry={() => void query.refetch()}
        />
      )}
      {query.data && (
        <>
          <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
            <div className="overflow-x-auto">
              <table className="min-w-[86rem] divide-y divide-slate-200">
                <thead className="bg-slate-50">
                  <tr>
                    {[
                      'Completed At',
                      'Document Code',
                      'Revision',
                      'Model',
                      'Average Similarity',
                      'Low Groups',
                      'Number Mismatches',
                      'Negation Mismatches',
                      'Status',
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
                  {query.data.items.map((job) => {
                    const result = job.resultSummary;
                    const runId = result?.runId;
                    const viewPath = `/documents/${job.documentId}/revisions/${job.documentRevisionId}/similarity?fileId=${job.documentFileId}&runId=${runId ?? ''}`;
                    return (
                      <tr key={job.id}>
                        <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">
                          {job.completedAt ? formatDateTime(job.completedAt) : '—'}
                        </td>
                        <td className="px-4 py-3 text-xs font-semibold text-blue-700">
                          {job.document?.baseDocumentCode ?? job.documentId}
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-600">
                          {job.revision?.revisionCode ?? '—'}
                        </td>
                        <td className="max-w-56 truncate px-4 py-3 text-xs text-slate-600">
                          {job.modelName ?? '—'}
                        </td>
                        <td className="px-4 py-3 text-sm font-semibold text-slate-900">
                          {percent(result?.averageSimilarity)}
                        </td>
                        <td className="px-4 py-3 text-xs font-semibold text-rose-700">
                          {result?.lowSimilarityGroups ?? result?.lowGroups ?? '—'}
                        </td>
                        <td className="px-4 py-3 text-xs text-orange-700">
                          {result?.numberMismatches ?? '—'}
                        </td>
                        <td className="px-4 py-3 text-xs text-amber-700">
                          {result?.negationMismatches ?? '—'}
                        </td>
                        <td className="px-4 py-3 text-[10px] font-semibold text-slate-700">
                          {job.status.replaceAll('_', ' ')}
                        </td>
                        <td className="px-4 py-3">
                          {runId && (
                            <div className="flex min-w-max gap-1">
                              <Link
                                to={viewPath}
                                className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-2.5 text-xs font-semibold text-violet-700 hover:bg-violet-50"
                              >
                                <Eye className="size-3.5" aria-hidden="true" />
                                View Results
                              </Link>
                              {hasPermission('similarity:rerun') && (
                                <button
                                  type="button"
                                  onClick={() => setRerunTarget(job)}
                                  className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-2.5 text-xs font-semibold text-blue-700 hover:bg-blue-50"
                                >
                                  <RefreshCw className="size-3.5" aria-hidden="true" />
                                  Re-run
                                </button>
                              )}
                              {hasPermission('similarity:export') &&
                                (['json', 'xlsx'] as const).map((format) => (
                                  <button
                                    key={format}
                                    type="button"
                                    disabled={mutations.export.isPending}
                                    onClick={() => void exportRun(job, format)}
                                    className="inline-flex min-h-9 items-center gap-1 rounded-lg px-2 text-[10px] font-semibold uppercase text-slate-600 hover:bg-slate-100 disabled:opacity-50"
                                  >
                                    <Download className="size-3" aria-hidden="true" />
                                    {format}
                                  </button>
                                ))}
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {query.data.items.length === 0 && (
              <p className="px-6 py-12 text-center text-sm text-slate-500">
                No similarity history matches this search.
              </p>
            )}
          </div>
          <Phase8Pagination
            page={page}
            totalItems={query.data.totalItems}
            totalPages={query.data.totalPages}
            label="similarity runs"
            onPageChange={setPage}
          />
        </>
      )}
      <RerunSimilarityDialog
        open={rerunTarget !== null}
        pending={mutations.rerun.isPending}
        onClose={() => setRerunTarget(null)}
        onConfirm={rerun}
      />
    </div>
  );
}

function RerunSimilarityDialog({
  onClose,
  onConfirm,
  open,
  pending,
}: {
  open: boolean;
  pending: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => Promise<void>;
}) {
  const [reason, setReason] = useState('');
  const trimmed = reason.trim();
  if (!open) {
    return null;
  }
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="rerun-similarity-title"
      className="fixed inset-0 z-50 grid place-items-center bg-slate-950/50 p-4"
    >
      <form
        className="w-full max-w-lg rounded-3xl bg-white p-6 shadow-2xl"
        onSubmit={(event) => {
          event.preventDefault();
          if (trimmed) {
            void onConfirm(trimmed);
          }
        }}
      >
        <div className="flex items-start justify-between">
          <div>
            <h2 id="rerun-similarity-title" className="font-semibold text-slate-950">
              Re-run translation similarity
            </h2>
            <p className="mt-1 text-xs leading-5 text-slate-600">
              A reason is required for the audit trail. Previous results remain
              immutable.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="grid size-9 place-items-center rounded-lg hover:bg-slate-100"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>
        <label className="mt-5 block text-xs font-semibold text-slate-700">
          Re-run reason
          <textarea
            required
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            className="mt-1.5 min-h-28 w-full rounded-xl border border-slate-300 p-3 text-sm"
          />
        </label>
        {!trimmed && reason.length > 0 && (
          <p role="alert" className="mt-2 text-xs text-rose-700">
            Enter a reason containing visible characters.
          </p>
        )}
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="min-h-10 rounded-xl border border-slate-300 px-4 text-sm font-semibold"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!trimmed || pending}
            className="min-h-10 rounded-xl bg-violet-700 px-4 text-sm font-semibold text-white disabled:opacity-50"
          >
            Queue Re-run
          </button>
        </div>
      </form>
    </div>
  );
}
