import { ArrowLeft, Download, History, RefreshCw, Search } from 'lucide-react';
import { useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import { LanguageBadge } from '../../components/documents/LanguageBadge';
import { LanguageBlockTable } from '../../components/documents/LanguageBlockTable';
import { LanguageCoveragePanel } from '../../components/documents/LanguageCoveragePanel';
import { LanguagePresenceCards } from '../../components/documents/LanguagePresenceCards';
import { LanguageProgress } from '../../components/documents/LanguageProgress';
import { LanguageStatusBadge } from '../../components/documents/LanguageStatusBadge';
import { RedetectLanguageDialog } from '../../components/documents/RedetectLanguageDialog';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { useDocument } from '../../hooks/useDocument';
import { useDocumentFiles, useRevisionFiles } from '../../hooks/useDocumentFiles';
import { useLanguageDetectionMutations } from '../../hooks/useLanguageDetection';
import { useLanguageDetectionJobs } from '../../hooks/useLanguageDetectionJobs';
import {
  useLanguageBlocks,
  useLanguageContainers,
  useLanguageDetectionHistory,
  useLanguageDetectionRun,
  useLanguageSummary,
  useLatestLanguageDetection,
} from '../../hooks/useLanguageResults';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import {
  isActiveLanguageDetectionStatus,
  languageCodes,
  languageLabels,
  type LanguageCode,
  type LanguageSourceType,
} from '../../types/languageDetection';
import { downloadFile } from '../../utils/downloadFile';
import { formatDateTime } from '../../utils/formatters';

export function LanguageResultPage() {
  const { documentId = '', revisionId } = useParams();
  const [searchParams] = useSearchParams();
  const requestedRunId = searchParams.get('runId');
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
  const latestQuery = useLatestLanguageDetection(
    file?.id ?? null,
    file !== null && requestedRunId === null,
  );
  const requestedRunQuery = useLanguageDetectionRun(
    requestedRunId,
    requestedRunId !== null,
  );
  const requestedRun = requestedRunQuery.data ?? null;
  const requestedRunMismatch =
    requestedRun !== null &&
    (requestedRun.documentId !== documentId ||
      (revisionId !== undefined && requestedRun.documentRevisionId !== revisionId));
  const run = requestedRunId
    ? requestedRunMismatch
      ? null
      : requestedRun
    : (latestQuery.data ?? null);
  const displayedFile =
    (run
      ? files.find((candidate) => candidate.id === run.documentFileId)
      : undefined) ?? file;
  const canRedetectRun =
    hasPermission('documents:redetect_language') &&
    displayedFile?.isCurrent === true &&
    displayedFile.fileStatus === 'AVAILABLE' &&
    documentQuery.data?.isArchived !== true;
  const runId = run?.runId ?? null;
  const summaryQuery = useLanguageSummary(runId, run !== null);
  const [languageCode, setLanguageCode] = useState<LanguageCode | ''>('');
  const [sourceType, setSourceType] = useState<LanguageSourceType | ''>('');
  const [containerId, setContainerId] = useState('');
  const [minimumConfidence, setMinimumConfidence] = useState('');
  const [maximumConfidence, setMaximumConfidence] = useState('');
  const [mixedOnly, setMixedOnly] = useState(false);
  const [searchInput, setSearchInput] = useState('');
  const search = useDebouncedValue(searchInput.trim(), 400);
  const [blockPage, setBlockPage] = useState(1);
  const containersQuery = useLanguageContainers(
    runId,
    { page: 1, pageSize: 500 },
    run !== null,
  );
  const blocksQuery = useLanguageBlocks(
    runId,
    {
      page: blockPage,
      pageSize: 100,
      ...(languageCode ? { languageCode } : {}),
      ...(sourceType ? { sourceType } : {}),
      ...(containerId ? { containerId } : {}),
      ...(minimumConfidence ? { minimumConfidence: Number(minimumConfidence) } : {}),
      ...(maximumConfidence ? { maximumConfidence: Number(maximumConfidence) } : {}),
      ...(mixedOnly ? { isMixed: true } : {}),
      ...(search ? { search } : {}),
    },
    run !== null,
  );
  const historyQuery = useLanguageDetectionHistory(
    displayedFile?.id ?? null,
    { page: 1, pageSize: 10 },
    displayedFile !== null && hasPermission('documents:view_language_results'),
  );
  const jobsQuery = useLanguageDetectionJobs(
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
      ? jobsQuery.data?.items.find((job) => isActiveLanguageDetectionStatus(job.status))
      : undefined;
  const [redetectOpen, setRedetectOpen] = useState(false);
  const mutations = useLanguageDetectionMutations();
  const { showToast } = useToast();

  const exportRun = async (format: 'json' | 'xlsx'): Promise<void> => {
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
        `${documentQuery.data?.baseDocumentCode ?? 'document'}_${
          revision?.revisionCode ?? 'revision'
        }_languages.${format}`,
      );
      showToast({
        tone: 'success',
        title: `Language ${format.toUpperCase()} downloaded`,
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Language export failed',
        message: getApiErrorMessage(error, 'The export could not be downloaded.'),
      });
    }
  };

  const redetect = async (reason: string): Promise<void> => {
    if (!run) {
      return;
    }
    try {
      await mutations.redetect.mutateAsync({
        runId: run.runId,
        payload: { reason },
      });
      setRedetectOpen(false);
      showToast({
        tone: 'success',
        title: 'Language re-detection queued',
        message: 'This result remains available in detection history.',
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Language re-detection could not be queued',
        message: getApiErrorMessage(error, 'Review the current source content.'),
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
      <div aria-label="Loading language results" className="space-y-5">
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
          'The document, revision, file, or language result was not found within your scope.',
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
        The requested language detection run does not belong to this document or
        revision.
      </p>
    );
  }

  const documentRecord = documentQuery.data;
  const backPath = `/documents/${documentRecord.id}?tab=files`;

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Documents"
        title="Language Results"
        description={`${documentRecord.baseDocumentCode} · ${revision.revisionCode}`}
        actions={
          <Link
            to={backPath}
            className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 bg-white px-3.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            <ArrowLeft className="size-4" aria-hidden="true" />
            Document Files
          </Link>
        }
      />

      {activeJob && (
        <section className="rounded-2xl border border-violet-200 bg-violet-50 p-5">
          <h2 className="text-sm font-semibold text-violet-950">
            Language detection is in progress
          </h2>
          <div className="mt-3 max-w-xl">
            <LanguageProgress
              status={activeJob.status}
              progress={activeJob.progress}
              currentStage={activeJob.currentStage}
            />
          </div>
        </section>
      )}

      {!run && !activeJob && (
        <section className="rounded-3xl border border-dashed border-slate-300 bg-white p-10 text-center">
          <h2 className="text-lg font-semibold text-slate-950">
            No language result yet
          </h2>
          <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-600">
            Run language detection after native extraction or OCR content is available.
          </p>
        </section>
      )}

      {run && (
        <>
          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="grid gap-4 text-xs sm:grid-cols-2 xl:grid-cols-6">
              <HeaderField
                label="Document Code"
                value={documentRecord.baseDocumentCode}
              />
              <HeaderField label="Revision" value={revision.revisionCode} />
              <HeaderField
                label="Filename"
                value={displayedFile?.originalFilename ?? 'Historical file'}
              />
              <HeaderField label="Detector" value={run.detectorName} />
              <HeaderField label="Version" value={run.detectorVersion} />
              <div>
                <p className="font-semibold text-slate-500">Status</p>
                <div className="mt-1">
                  <LanguageStatusBadge status={run.status} />
                </div>
              </div>
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-slate-100 pt-4">
              <span className="text-xs text-slate-500">
                Completed {formatDateTime(run.completedAt)}
              </span>
              <span className="text-xs text-slate-500">
                Sources: native extraction{run.ocrRunId ? ' + OCR' : ''}
              </span>
              <div className="ml-auto flex flex-wrap gap-2">
                {hasPermission('documents:export_language_results') &&
                  (['json', 'xlsx'] as const).map((format) => (
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
                {canRedetectRun && (
                  <button
                    type="button"
                    onClick={() => setRedetectOpen(true)}
                    className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-violet-50 px-3 text-xs font-semibold text-violet-700 hover:bg-violet-100"
                  >
                    <RefreshCw className="size-3.5" aria-hidden="true" />
                    Re-detect
                  </button>
                )}
              </div>
            </div>
          </section>

          {summaryQuery.isLoading && (
            <div className="h-48 animate-pulse rounded-3xl bg-slate-100" />
          )}
          {summaryQuery.error && (
            <p
              role="alert"
              className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700"
            >
              {getApiErrorMessage(
                summaryQuery.error,
                'Language summary could not be loaded.',
              )}
            </p>
          )}
          {summaryQuery.data && (
            <>
              <LanguagePresenceCards summary={summaryQuery.data} />
              <LanguageCoveragePanel coverage={summaryQuery.data.coverage} />
            </>
          )}

          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-slate-950">
                  Container Summary
                </h2>
                <p className="mt-1 text-xs text-slate-500">
                  Coverage grouped by page, document part, or worksheet.
                </p>
              </div>
            </div>
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-xs">
                <thead className="bg-slate-50">
                  <tr>
                    {[
                      'Container',
                      'Type',
                      'Dominant Language',
                      'Blocks',
                      'Eligible',
                      'ID',
                      'EN',
                      'ZH',
                      'Mixed',
                      'Unknown',
                    ].map((heading) => (
                      <th
                        key={heading}
                        className="whitespace-nowrap px-3 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-500"
                      >
                        {heading}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {(containersQuery.data?.items ?? []).map((container) => (
                    <tr key={container.id}>
                      <td className="whitespace-nowrap px-3 py-3 font-semibold text-slate-800">
                        {container.containerName ?? `#${container.containerIndex}`}
                      </td>
                      <td className="whitespace-nowrap px-3 py-3 text-slate-600">
                        {container.containerType}
                      </td>
                      <td className="whitespace-nowrap px-3 py-3">
                        <LanguageBadge code={container.dominantLanguage} />
                      </td>
                      {[
                        container.totalBlocks,
                        container.eligibleBlocks,
                        container.indonesianBlocks,
                        container.englishBlocks,
                        container.chineseBlocks,
                        container.mixedBlocks,
                        container.unknownBlocks,
                      ].map((value, index) => (
                        <td
                          key={index}
                          className="whitespace-nowrap px-3 py-3 tabular-nums text-slate-700"
                        >
                          {value.toLocaleString()}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="space-y-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-sm font-semibold text-slate-950">Block Results</h2>
              <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-6">
                <label className="text-xs font-semibold text-slate-700 xl:col-span-2">
                  Search
                  <span className="relative mt-1.5 block">
                    <Search
                      className="pointer-events-none absolute left-3 top-3 size-4 text-slate-400"
                      aria-hidden="true"
                    />
                    <input
                      value={searchInput}
                      onChange={(event) => {
                        setSearchInput(event.target.value);
                        setBlockPage(1);
                      }}
                      className="min-h-10 w-full rounded-xl border border-slate-300 pl-9 pr-3 text-xs"
                    />
                  </span>
                </label>
                <label className="text-xs font-semibold text-slate-700">
                  Language
                  <select
                    aria-label="Language"
                    value={languageCode}
                    onChange={(event) => {
                      setLanguageCode(event.target.value as LanguageCode | '');
                      setBlockPage(1);
                    }}
                    className="mt-1.5 min-h-10 w-full rounded-xl border border-slate-300 bg-white px-2 text-xs"
                  >
                    <option value="">All languages</option>
                    {languageCodes.map((code) => (
                      <option key={code} value={code}>
                        {languageLabels[code]}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-xs font-semibold text-slate-700">
                  Source Type
                  <select
                    aria-label="Source Type"
                    value={sourceType}
                    onChange={(event) => {
                      setSourceType(event.target.value as LanguageSourceType | '');
                      setBlockPage(1);
                    }}
                    className="mt-1.5 min-h-10 w-full rounded-xl border border-slate-300 bg-white px-2 text-xs"
                  >
                    <option value="">Native and OCR</option>
                    <option value="NATIVE_EXTRACTION">Native</option>
                    <option value="OCR">OCR</option>
                  </select>
                </label>
                <label className="text-xs font-semibold text-slate-700">
                  Container
                  <select
                    aria-label="Container"
                    value={containerId}
                    onChange={(event) => {
                      setContainerId(event.target.value);
                      setBlockPage(1);
                    }}
                    className="mt-1.5 min-h-10 w-full rounded-xl border border-slate-300 bg-white px-2 text-xs"
                  >
                    <option value="">All containers</option>
                    {(containersQuery.data?.items ?? []).map((container) => (
                      <option
                        key={container.id}
                        value={container.containerId ?? container.id}
                      >
                        {container.containerName ?? `#${container.containerIndex}`}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex items-end gap-2 pb-2 text-xs font-semibold text-slate-700">
                  <input
                    type="checkbox"
                    checked={mixedOnly}
                    onChange={(event) => {
                      setMixedOnly(event.target.checked);
                      setBlockPage(1);
                    }}
                    className="size-4 rounded border-slate-300"
                  />
                  Mixed only
                </label>
              </div>
              <div className="mt-3 flex flex-wrap gap-3">
                <label className="text-xs font-semibold text-slate-700">
                  Minimum confidence
                  <input
                    aria-label="Minimum Confidence"
                    type="number"
                    min="0"
                    max="1"
                    step="0.05"
                    value={minimumConfidence}
                    onChange={(event) => {
                      setMinimumConfidence(event.target.value);
                      setBlockPage(1);
                    }}
                    className="ml-2 min-h-9 w-24 rounded-lg border border-slate-300 px-2 text-xs"
                  />
                </label>
                <label className="text-xs font-semibold text-slate-700">
                  Maximum confidence
                  <input
                    aria-label="Maximum Confidence"
                    type="number"
                    min="0"
                    max="1"
                    step="0.05"
                    value={maximumConfidence}
                    onChange={(event) => {
                      setMaximumConfidence(event.target.value);
                      setBlockPage(1);
                    }}
                    className="ml-2 min-h-9 w-24 rounded-lg border border-slate-300 px-2 text-xs"
                  />
                </label>
              </div>
            </div>
            {blocksQuery.isLoading ? (
              <div className="h-72 animate-pulse rounded-2xl bg-slate-100" />
            ) : blocksQuery.error ? (
              <p
                role="alert"
                className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700"
              >
                {getApiErrorMessage(
                  blocksQuery.error,
                  'Language block results could not be loaded.',
                )}
              </p>
            ) : (
              <LanguageBlockTable
                blocks={blocksQuery.data?.items ?? []}
                sourceContext={{
                  documentId: run.documentId,
                  revisionId: run.documentRevisionId,
                  extractionRunId: run.extractionRunId,
                }}
              />
            )}
            {blocksQuery.data && blocksQuery.data.totalPages > 1 && (
              <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-3 text-xs text-slate-600">
                <span>
                  Page {blockPage} of {blocksQuery.data.totalPages} ·{' '}
                  {blocksQuery.data.totalItems.toLocaleString()} blocks
                </span>
                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={blockPage <= 1}
                    onClick={() => setBlockPage((current) => Math.max(1, current - 1))}
                    className="min-h-9 rounded-lg border border-slate-300 px-3 font-semibold disabled:opacity-50"
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    disabled={blockPage >= blocksQuery.data.totalPages}
                    onClick={() => setBlockPage((current) => current + 1)}
                    className="min-h-9 rounded-lg border border-slate-300 px-3 font-semibold disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </section>

          {historyQuery.data && historyQuery.data.items.length > 0 && (
            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center gap-2">
                <History className="size-4 text-slate-500" aria-hidden="true" />
                <h2 className="text-sm font-semibold text-slate-950">
                  Detection History
                </h2>
              </div>
              <ol className="mt-4 space-y-2">
                {historyQuery.data.items.map((item) => (
                  <li
                    key={item.id}
                    className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 p-3 text-xs"
                  >
                    <LanguageStatusBadge status={item.status} />
                    <span className="text-slate-600">
                      {formatDateTime(item.completedAt)}
                    </span>
                    <span className="text-slate-600">
                      {item.detectorName} {item.detectorVersion}
                    </span>
                    <Link
                      to={`?runId=${item.id}`}
                      className="ml-auto font-semibold text-violet-700"
                    >
                      View
                    </Link>
                  </li>
                ))}
              </ol>
            </section>
          )}
        </>
      )}

      <RedetectLanguageDialog
        isOpen={redetectOpen}
        isPending={mutations.redetect.isPending}
        onClose={() => setRedetectOpen(false)}
        onConfirm={(reason) => void redetect(reason)}
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
