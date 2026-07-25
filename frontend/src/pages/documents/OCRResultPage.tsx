import { ArrowLeft, Download, History, RefreshCw } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import {
  OCRPageViewer,
  type OCRConfidenceFilter,
} from '../../components/documents/OCRPageViewer';
import { OCRProgress } from '../../components/documents/OCRProgress';
import { OCRStatusBadge } from '../../components/documents/OCRStatusBadge';
import { OCRSummaryCards } from '../../components/documents/OCRSummaryCards';
import { ReOCRDialog } from '../../components/documents/ReOCRDialog';
import {
  formatConfidence,
  ocrPreprocessingLabels,
  ocrProfileLabels,
} from '../../components/documents/ocrDisplay';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { useDocument } from '../../hooks/useDocument';
import { useDocumentFiles, useRevisionFiles } from '../../hooks/useDocumentFiles';
import {
  useLatestOCR,
  useOCRBlocks,
  useOCRMutations,
  useOCRPage,
  useOCRPages,
  useOCRRun,
} from '../../hooks/useOCR';
import { useOCRJobs } from '../../hooks/useOCRJobs';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import { isActiveOCRStatus, type OCRReprocessRequest } from '../../types/ocr';
import { downloadFile } from '../../utils/downloadFile';
import { formatDateTime } from '../../utils/formatters';

export function OCRResultPage() {
  const { documentId = '', revisionId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedRunId = searchParams.get('runId');
  const shouldOpenReocr = searchParams.get('reocr') === 'true';
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const documentQuery = useDocument(documentId || null);
  const documentFilesQuery = useDocumentFiles(revisionId ? null : documentId || null);
  const revisionFilesQuery = useRevisionFiles(
    revisionId ? documentId || null : null,
    revisionId ?? null,
  );
  const files = revisionId
    ? (revisionFilesQuery.data ?? [])
    : (documentFilesQuery.data ?? []);
  const revision =
    documentQuery.data?.revisions.find((item) => item.id === revisionId) ??
    documentQuery.data?.currentRevision ??
    null;
  const file =
    files.find(
      (candidate) =>
        candidate.isCurrent &&
        candidate.fileStatus === 'AVAILABLE' &&
        (!revision || candidate.documentRevisionId === revision.id),
    ) ?? null;
  const latestQuery = useLatestOCR(
    file?.id ?? null,
    file !== null && requestedRunId === null,
  );
  const requestedRunQuery = useOCRRun(requestedRunId, requestedRunId !== null);
  const requestedRun = requestedRunQuery.data ?? null;
  const requestedRunMismatch =
    requestedRun !== null &&
    (requestedRun.document.id !== documentId ||
      (revisionId !== undefined && requestedRun.revision.id !== revisionId));
  const run = requestedRunId
    ? requestedRunMismatch
      ? null
      : requestedRun
    : (latestQuery.data ?? null);
  const displayedFile =
    (run ? files.find((candidate) => candidate.id === run.file.id) : undefined) ?? file;
  const canReOCRRun =
    hasPermission('documents:reocr') &&
    displayedFile?.isCurrent === true &&
    displayedFile.fileStatus === 'AVAILABLE' &&
    documentQuery.data?.isArchived !== true;
  const runId = run?.runId ?? null;
  const jobsQuery = useOCRJobs(
    {
      ...(file ? { documentFileId: file.id } : {}),
      page: 1,
      pageSize: 10,
      sortBy: 'requestedAt',
      sortOrder: 'desc',
    },
    { enabled: file !== null && requestedRunId === null, pollActive: true },
  );
  const activeJob =
    requestedRunId === null
      ? jobsQuery.data?.items.find((job) => isActiveOCRStatus(job.status))
      : undefined;
  const pagesQuery = useOCRPages(runId, { page: 1, pageSize: 500 }, run !== null);
  const [selectedPageNumber, setSelectedPageNumber] = useState<number | null>(null);
  const selectedListPage =
    pagesQuery.data?.items.find((page) => page.pageNumber === selectedPageNumber) ??
    pagesQuery.data?.items[0] ??
    null;
  const effectivePageNumber =
    selectedPageNumber ?? selectedListPage?.pageNumber ?? null;
  const pageQuery = useOCRPage(runId, effectivePageNumber, run !== null);
  const page = pageQuery.data?.page ?? selectedListPage;
  const [confidenceFilter, setConfidenceFilter] = useState<OCRConfidenceFilter>('ALL');
  const blocksQuery = useOCRBlocks(
    runId,
    {
      ...(effectivePageNumber ? { pageNumber: effectivePageNumber } : {}),
      page: 1,
      pageSize: 500,
    },
    run !== null && effectivePageNumber !== null,
  );
  const [reocrOpen, setReocrOpen] = useState(false);
  const mutations = useOCRMutations();
  const { showToast } = useToast();

  useEffect(() => {
    if (pagesQuery.data?.items[0] && selectedPageNumber === null) {
      setSelectedPageNumber(pagesQuery.data.items[0].pageNumber);
    }
  }, [pagesQuery.data?.items, selectedPageNumber]);

  useEffect(() => {
    if (shouldOpenReocr && run && canReOCRRun) {
      setReocrOpen(true);
      const next = new URLSearchParams(searchParams);
      next.delete('reocr');
      setSearchParams(next, { replace: true });
    }
  }, [canReOCRRun, run, searchParams, setSearchParams, shouldOpenReocr]);

  const summary = run;

  const exportRun = async (format: 'json' | 'txt'): Promise<void> => {
    if (!run) {
      return;
    }
    try {
      const result = await mutations.export.mutateAsync({
        runId: run.runId,
        format,
      });
      downloadFile(
        result,
        `${run.document.baseDocumentCode}_${run.revision.revisionCode}_ocr.${format}`,
      );
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

  const reocr = async (payload: OCRReprocessRequest): Promise<void> => {
    if (!run) {
      return;
    }
    try {
      await mutations.reocr.mutateAsync({ runId: run.runId, payload });
      setReocrOpen(false);
      showToast({
        tone: 'success',
        title: 'Re-OCR queued',
        message: 'This OCR run remains available in history.',
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Re-OCR could not be queued',
        message: getApiErrorMessage(error, 'Review the run and page selection.'),
      });
    }
  };

  const isLoading =
    documentQuery.isLoading ||
    documentFilesQuery.isLoading ||
    revisionFilesQuery.isLoading ||
    latestQuery.isLoading ||
    requestedRunQuery.isLoading;
  const pageError =
    documentQuery.error ||
    documentFilesQuery.error ||
    revisionFilesQuery.error ||
    latestQuery.error ||
    requestedRunQuery.error;

  if (isLoading) {
    return (
      <div aria-label="Loading OCR results" className="space-y-5">
        <div className="h-28 animate-pulse rounded-3xl bg-slate-100" />
        <div className="h-96 animate-pulse rounded-3xl bg-slate-100" />
      </div>
    );
  }

  if (pageError || !documentQuery.data || !revision) {
    return (
      <p
        role="alert"
        className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700"
      >
        {getApiErrorMessage(
          pageError,
          'The document, revision, file, or OCR result was not found within your scope.',
        )}
      </p>
    );
  }

  if (requestedRunMismatch) {
    return (
      <p
        role="alert"
        className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700"
      >
        The requested OCR run does not belong to this document or revision.
      </p>
    );
  }

  const documentRecord = documentQuery.data;
  const backPath = `/documents/${documentRecord.id}?tab=files`;

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Documents"
        title="OCR Results"
        description={`${documentRecord.baseDocumentCode} · ${run?.revision.revisionCode ?? revision.revisionCode}`}
        actions={
          <div className="flex flex-wrap gap-2">
            <Link
              to={backPath}
              className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 bg-white px-3.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              <ArrowLeft className="size-4" aria-hidden="true" />
              Document Files
            </Link>
            {hasPermission('documents:view_ocr_history') && (
              <Link
                to="/documents/ocr-history"
                className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 bg-white px-3.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                <History className="size-4" aria-hidden="true" />
                OCR History
              </Link>
            )}
          </div>
        }
      />

      {activeJob && (
        <section className="rounded-2xl border border-blue-200 bg-blue-50 p-5">
          <h2 className="text-sm font-semibold text-blue-950">
            OCR processing is in progress
          </h2>
          <div className="mt-3 max-w-xl">
            <OCRProgress
              status={activeJob.status}
              progress={activeJob.progress}
              currentStage={activeJob.currentStage}
            />
          </div>
        </section>
      )}

      {!run && !activeJob && (
        <section className="rounded-3xl border border-dashed border-slate-300 bg-white p-10 text-center">
          <h2 className="text-lg font-semibold text-slate-950">No OCR result yet</h2>
          <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-600">
            OCR is available only for current PDF files with pages that need OCR. Start
            it from the document file intelligence panel.
          </p>
        </section>
      )}

      {run && summary && (
        <>
          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="grid gap-4 text-xs sm:grid-cols-2 xl:grid-cols-6">
              <HeaderField
                label="Document Code"
                value={run.document.baseDocumentCode}
              />
              <HeaderField label="Revision" value={run.revision.revisionCode} />
              <HeaderField label="Filename" value={run.file.filename} />
              <HeaderField label="Provider" value={run.provider} />
              <HeaderField
                label="Language Profile"
                value={ocrProfileLabels[run.languageProfile]}
              />
              <div>
                <p className="font-semibold text-slate-500">OCR Status</p>
                <div className="mt-1">
                  <OCRStatusBadge status={run.status} />
                </div>
              </div>
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-slate-100 pt-4">
              <span className="text-xs text-slate-500">
                Completed {run.completedAt ? formatDateTime(run.completedAt) : '—'}
              </span>
              <span className="text-xs text-slate-500">
                {run.renderDpi} DPI · {ocrPreprocessingLabels[run.preprocessingProfile]}
              </span>
              <span className="text-xs text-slate-500">
                Confidence {formatConfidence(run.averageConfidence)}
              </span>
              <div className="ml-auto flex flex-wrap gap-2">
                {(['json', 'txt'] as const).map((format) => (
                  <button
                    key={format}
                    type="button"
                    onClick={() => void exportRun(format)}
                    disabled={mutations.export.isPending}
                    className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-slate-300 px-3 text-xs font-semibold uppercase text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                  >
                    <Download className="size-3.5" aria-hidden="true" />
                    {format}
                  </button>
                ))}
                {canReOCRRun && (
                  <button
                    type="button"
                    onClick={() => setReocrOpen(true)}
                    className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-indigo-50 px-3 text-xs font-semibold text-indigo-700 hover:bg-indigo-100"
                  >
                    <RefreshCw className="size-3.5" aria-hidden="true" />
                    Re-run OCR
                  </button>
                )}
              </div>
            </div>
          </section>

          <OCRSummaryCards summary={summary} />

          <div className="grid gap-5 xl:grid-cols-[16rem_minmax(0,1fr)]">
            <aside className="self-start rounded-2xl border border-slate-200 bg-white p-4 xl:sticky xl:top-24">
              <h2 className="text-xs font-semibold text-slate-950">OCR pages</h2>
              {pagesQuery.isLoading ? (
                <div className="mt-3 h-44 animate-pulse rounded-xl bg-slate-100" />
              ) : (
                <ol className="mt-3 max-h-[70vh] space-y-2 overflow-y-auto">
                  {(pagesQuery.data?.items ?? []).map((item) => (
                    <li key={item.id}>
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedPageNumber(item.pageNumber);
                          setConfidenceFilter('ALL');
                        }}
                        className={`w-full rounded-xl border p-3 text-left ${
                          effectivePageNumber === item.pageNumber
                            ? 'border-blue-300 bg-blue-50'
                            : 'border-slate-200 hover:bg-slate-50'
                        }`}
                      >
                        <span className="block text-xs font-semibold text-slate-900">
                          Page {item.pageNumber}
                        </span>
                        <span className="mt-1 block text-[10px] text-slate-500">
                          {item.blockCount} blocks ·{' '}
                          {formatConfidence(item.averageConfidence)}
                        </span>
                      </button>
                    </li>
                  ))}
                </ol>
              )}
            </aside>
            <main>
              {page ? (
                <OCRPageViewer
                  page={page}
                  blocks={blocksQuery.data?.items ?? []}
                  isLoading={blocksQuery.isLoading}
                  confidenceFilter={confidenceFilter}
                  lowConfidenceThreshold={run.lowConfidenceThreshold}
                  reviewConfidenceThreshold={run.reviewConfidenceThreshold}
                  onConfidenceFilterChange={setConfidenceFilter}
                />
              ) : (
                <p className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-600">
                  This OCR run has no page result.
                </p>
              )}
            </main>
          </div>
        </>
      )}

      <ReOCRDialog
        isOpen={reocrOpen}
        run={run}
        isPending={mutations.reocr.isPending}
        onClose={() => setReocrOpen(false)}
        onConfirm={(payload) => void reocr(payload)}
      />
    </div>
  );
}

function HeaderField({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="font-semibold text-slate-500">{label}</p>
      <p className="mt-1 break-words text-slate-900">{value}</p>
    </div>
  );
}
