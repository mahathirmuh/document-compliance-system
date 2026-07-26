import {
  ArrowLeft,
  Braces,
  Download,
  FileSearch,
  History,
  ListTree,
  RefreshCw,
  Search,
  Table2,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import { ContainerNavigator } from '../../components/documents/ContainerNavigator';
import { ExtractedBlockViewer } from '../../components/documents/ExtractedBlockViewer';
import { ExtractedTableViewer } from '../../components/documents/ExtractedTableViewer';
import { ExtractionErrorPanel } from '../../components/documents/ExtractionErrorPanel';
import { ExtractionProgress } from '../../components/documents/ExtractionProgress';
import { ExtractionStatusBadge } from '../../components/documents/ExtractionStatusBadge';
import { ExtractionSummaryCards } from '../../components/documents/ExtractionSummaryCards';
import { ExtractionWarningList } from '../../components/documents/ExtractionWarningList';
import { ReExtractionDialog } from '../../components/documents/ReExtractionDialog';
import { SafeHighlight } from '../../components/documents/SafeHighlight';
import { StartExtractionButton } from '../../components/documents/StartExtractionButton';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { useDocument } from '../../hooks/useDocument';
import { useDocumentFiles, useRevisionFiles } from '../../hooks/useDocumentFiles';
import { useExtractionJob, useExtractionMutations } from '../../hooks/useExtraction';
import { useExtractionJobs } from '../../hooks/useExtractionJobs';
import {
  useExtractedContentSearch,
  useExtractionBlocks,
  useExtractionContainers,
  useExtractionExport,
  useExtractionRun,
  useExtractionTables,
  useLatestExtraction,
} from '../../hooks/useExtractedContent';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type {
  ExtractedBlock,
  ExtractedContainer,
  ExtractionSearchResult,
} from '../../types/extractedContent';
import type { LanguageCode } from '../../types/languageDetection';
import { isActiveExtractionStatus } from '../../types/extraction';
import { downloadFile } from '../../utils/downloadFile';
import { formatDateTime } from '../../utils/formatters';

type ViewerMode = 'blocks' | 'raw' | 'tables';
type ContentSourceFilter = 'ALL' | 'NATIVE' | 'OCR';

export function ExtractedContentPage() {
  const { documentId = '', revisionId } = useParams();
  const [searchParams] = useSearchParams();
  const requestedRunId = searchParams.get('runId');
  const requestedContainerId = searchParams.get('containerId');
  const requestedBlockId = searchParams.get('blockId');
  const requestedOcrBlockId = searchParams.get('ocrBlockId');
  const requestedPageNumber = Number.parseInt(searchParams.get('page') ?? '', 10);
  const requestedWorksheet = searchParams.get('worksheet');
  const requestedCell = searchParams.get('cell');
  const requestedSourceReference = searchParams.get('sourceReference');
  const requestedSourceSearch = searchParams.get('sourceSearch');
  const hasRequestedPage =
    Number.isFinite(requestedPageNumber) && requestedPageNumber > 0;
  const effectiveSourceSearch = (
    requestedSourceReference ??
    requestedSourceSearch ??
    requestedCell ??
    (hasRequestedPage ? `page=${requestedPageNumber}` : '')
  )
    .trim()
    .slice(0, 500);
  const hasSourceTarget = Boolean(
    requestedContainerId ||
    requestedBlockId ||
    requestedOcrBlockId ||
    requestedWorksheet ||
    requestedCell ||
    requestedSourceReference ||
    requestedSourceSearch ||
    hasRequestedPage,
  );
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canViewContent = hasPermission('documents:view_extracted_content');
  const canTrackJobs =
    hasPermission('documents:view_extraction_history') ||
    hasPermission('documents:extract');
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
  const latestQuery = useLatestExtraction(
    file?.id ?? null,
    file !== null && requestedRunId === null && canViewContent,
  );
  const requestedRunQuery = useExtractionRun(
    requestedRunId,
    requestedRunId !== null && canViewContent,
  );
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
  const runId = run?.runId ?? null;
  const jobsQuery = useExtractionJobs(
    {
      page: 1,
      pageSize: 10,
      sortBy: 'requestedAt',
      sortOrder: 'desc',
      ...(file ? { documentFileId: file.id } : {}),
    },
    { enabled: file !== null && canTrackJobs, pollActive: true },
  );
  const activeJob =
    requestedRunId === null
      ? jobsQuery.data?.items.find((job) => isActiveExtractionStatus(job.status))
      : undefined;
  const lastFailedJob = jobsQuery.data?.items.find((job) => job.status === 'FAILED');
  const lastFailedJobQuery = useExtractionJob(lastFailedJob?.id ?? null, {
    enabled: canTrackJobs && lastFailedJob !== undefined,
  });
  const [containerPage, setContainerPage] = useState(
    hasRequestedPage ? Math.floor((requestedPageNumber - 1) / 100) + 1 : 1,
  );
  const [selectedContainerId, setSelectedContainerId] = useState<string | null>(
    requestedContainerId,
  );
  const [blockPage, setBlockPage] = useState(1);
  const [activeBlockId, setActiveBlockId] = useState<string | null>(
    requestedBlockId ?? requestedOcrBlockId,
  );
  const [sourceTargetActive, setSourceTargetActive] = useState(hasSourceTarget);
  const [viewerMode, setViewerMode] = useState<ViewerMode>('blocks');
  const [contentSourceFilter, setContentSourceFilter] = useState<ContentSourceFilter>(
    requestedOcrBlockId ? 'OCR' : 'ALL',
  );
  const [languageFilter, setLanguageFilter] = useState<LanguageCode | ''>('');
  const [searchInput, setSearchInput] = useState('');
  const searchQuery = useDebouncedValue(searchInput.trim(), 400);
  const [reextractOpen, setReextractOpen] = useState(false);
  const containersQuery = useExtractionContainers(
    runId,
    {
      page: containerPage,
      pageSize: 100,
      ...(sourceTargetActive && requestedWorksheet && !requestedContainerId
        ? { search: requestedWorksheet }
        : {}),
    },
    run !== null,
  );
  const containers = containersQuery.data?.items ?? [];
  const requestedContainer = containers.find(
    (container) =>
      container.id === requestedContainerId ||
      (requestedWorksheet !== null &&
        (container.name === requestedWorksheet ||
          container.title === requestedWorksheet)) ||
      (hasRequestedPage && container.containerIndex === requestedPageNumber),
  );
  const selectedContainer =
    containers.find((container) => container.id === selectedContainerId) ??
    requestedContainer ??
    containers[0] ??
    null;
  const effectiveContainerId =
    selectedContainerId ?? requestedContainer?.id ?? selectedContainer?.id ?? null;
  const blockPageSize = run?.extractorType === 'XLSX' ? 200 : 100;
  const blocksQuery = useExtractionBlocks(
    runId,
    {
      ...(effectiveContainerId ? { containerId: effectiveContainerId } : {}),
      ...(contentSourceFilter === 'ALL' ? {} : { contentSource: contentSourceFilter }),
      ...(languageFilter ? { languageCode: languageFilter } : {}),
      ...(sourceTargetActive && effectiveSourceSearch
        ? { search: effectiveSourceSearch }
        : {}),
      page: blockPage,
      pageSize: blockPageSize,
      sortOrder: 'asc',
    },
    run !== null && effectiveContainerId !== null,
  );
  const tablesQuery = useExtractionTables(
    runId,
    {
      ...(effectiveContainerId ? { containerId: effectiveContainerId } : {}),
      includeCells: true,
      page: 1,
      pageSize: 100,
    },
    run !== null && effectiveContainerId !== null,
  );
  const searchResultQuery = useExtractedContentSearch(
    runId,
    { q: searchQuery, page: 1, pageSize: 100 },
    searchQuery.length >= 2 && searchQuery.length <= 200,
  );
  const headings = useMemo(
    () =>
      (blocksQuery.data?.items ?? []).filter((block) => block.blockType === 'HEADING'),
    [blocksQuery.data?.items],
  );
  const rawTextPreview = useMemo(
    () =>
      (blocksQuery.data?.items ?? [])
        .map((block) =>
          run?.extractorType === 'XLSX'
            ? `${block.sourceReference}: ${block.text}`
            : block.text,
        )
        .join('\n'),
    [blocksQuery.data?.items, run?.extractorType],
  );
  const visibleBlocks = useMemo(
    () =>
      (blocksQuery.data?.items ?? []).filter((block) => {
        const source = block.contentSource ?? 'NATIVE';
        const sourceMatches =
          contentSourceFilter === 'ALL' || source === contentSourceFilter;
        const languageMatches =
          languageFilter === '' || block.languageCode === languageFilter;
        return sourceMatches && languageMatches;
      }),
    [blocksQuery.data?.items, contentSourceFilter, languageFilter],
  );
  const locatedSourceBlock = visibleBlocks.find(
    (block) =>
      block.id === requestedBlockId ||
      block.id === requestedOcrBlockId ||
      (requestedCell !== null &&
        (block.metadata?.coordinate === requestedCell ||
          block.sourceReference.includes(`cell=${requestedCell}`))) ||
      (requestedSourceReference !== null &&
        block.sourceReference === requestedSourceReference),
  );
  const effectiveActiveBlockId = activeBlockId ?? locatedSourceBlock?.id ?? null;
  const exportMutation = useExtractionExport();
  const mutations = useExtractionMutations();
  const { showToast } = useToast();

  const selectContainer = (container: ExtractedContainer): void => {
    setSourceTargetActive(false);
    setSelectedContainerId(container.id);
    setBlockPage(1);
    setActiveBlockId(null);
  };

  useEffect(() => {
    if (!sourceTargetActive || !effectiveActiveBlockId) {
      return;
    }
    const timeoutId = window.setTimeout(() => {
      document
        .getElementById(`block-${effectiveActiveBlockId}`)
        ?.scrollIntoView?.({ behavior: 'smooth', block: 'center' });
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [effectiveActiveBlockId, sourceTargetActive, visibleBlocks]);

  const openSearchResult = (result: ExtractionSearchResult): void => {
    setContainerPage(Math.floor(Math.max(0, result.containerIndex - 1) / 100) + 1);
    setSelectedContainerId(result.containerId);
    setBlockPage(Math.floor(Math.max(0, result.blockOrder - 1) / blockPageSize) + 1);
    setActiveBlockId(result.blockId);
    setViewerMode('blocks');
    window.setTimeout(() => {
      document
        .getElementById(`block-${result.blockId}`)
        ?.scrollIntoView?.({ behavior: 'smooth', block: 'center' });
    }, 0);
  };

  const exportRun = async (format: 'json' | 'txt'): Promise<void> => {
    if (!run) {
      return;
    }
    try {
      const result = await exportMutation.mutateAsync({
        runId: run.runId,
        format,
      });
      downloadFile(
        result,
        `${documentQuery.data?.baseDocumentCode ?? 'document'}_${
          run.revision.revisionCode
        }_extraction.${format}`,
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
    if (!file) {
      return;
    }
    try {
      await mutations.reextract.mutateAsync({
        fileId: file.id,
        payload: { reason },
      });
      setReextractOpen(false);
      showToast({
        tone: 'success',
        title: 'Re-extraction queued',
        message: 'This result remains available in extraction history.',
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Re-extraction could not be queued',
        message: getApiErrorMessage(error, 'Review the current file state.'),
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
      <div className="space-y-5" aria-label="Loading extracted content">
        <div className="h-28 animate-pulse rounded-3xl bg-slate-100" />
        <div className="grid gap-3 sm:grid-cols-3">
          {Array.from({ length: 6 }, (_, index) => (
            <div key={index} className="h-24 animate-pulse rounded-2xl bg-slate-100" />
          ))}
        </div>
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
          'The document, revision, file, or extraction run was not found within your scope.',
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
        The requested extraction run does not belong to this document or revision.
      </p>
    );
  }

  const documentRecord = documentQuery.data;
  const displayedRevision = run?.revision ?? revision;
  const displayedFilename = run?.file.filename ?? file?.originalFilename ?? 'No file';
  const displayedFileType =
    run?.file.extension.toUpperCase() ?? file?.fileExtension.toUpperCase() ?? '—';
  const backPath = `/documents/${documentRecord.id}?tab=files`;

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Documents"
        title="Extracted Content"
        description={`${documentRecord.baseDocumentCode} · ${displayedRevision.revisionCode}`}
        actions={
          <div className="flex flex-wrap gap-2">
            <Link
              to={backPath}
              className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 bg-white px-3.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              <ArrowLeft className="size-4" aria-hidden="true" />
              Document Files
            </Link>
            {file && hasPermission('documents:view_extraction_history') && (
              <Link
                to={`/documents/${documentRecord.id}/revisions/${displayedRevision.id}/extraction-history`}
                className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 bg-white px-3.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                <History className="size-4" aria-hidden="true" />
                History
              </Link>
            )}
            {hasPermission('documents:view_ocr_results') &&
              displayedFileType === 'PDF' && (
                <Link
                  to={`/documents/${documentRecord.id}/revisions/${displayedRevision.id}/ocr-results`}
                  className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 bg-white px-3.5 text-sm font-semibold text-blue-700 hover:bg-blue-50"
                >
                  OCR Results
                </Link>
              )}
            {hasPermission('documents:view_language_results') && (
              <Link
                to={`/documents/${documentRecord.id}/revisions/${displayedRevision.id}/language-results`}
                className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 bg-white px-3.5 text-sm font-semibold text-violet-700 hover:bg-violet-50"
              >
                Language Results
              </Link>
            )}
          </div>
        }
      />

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="grid gap-4 text-xs sm:grid-cols-2 xl:grid-cols-6">
          <HeaderField label="Document Code" value={documentRecord.baseDocumentCode} />
          <HeaderField label="Revision" value={displayedRevision.revisionCode} />
          <HeaderField label="Filename" value={displayedFilename} />
          <HeaderField label="File Type" value={displayedFileType} />
          <div>
            <p className="font-semibold text-slate-500">Extraction Status</p>
            <div className="mt-1">
              {activeJob ? (
                <ExtractionStatusBadge status={activeJob.status} />
              ) : run ? (
                <ExtractionStatusBadge status={run.status} />
              ) : (
                <span className="text-slate-800">Not Extracted</span>
              )}
            </div>
          </div>
          <HeaderField
            label="Extracted At"
            value={run ? formatDateTime(run.completedAt) : '—'}
          />
        </div>
      </section>

      {activeJob && (
        <section className="rounded-2xl border border-blue-200 bg-blue-50 p-5">
          <p className="text-sm font-semibold text-blue-950">
            Extraction is in progress
          </p>
          <div className="mt-3 max-w-xl">
            <ExtractionProgress
              progress={activeJob.progress}
              status={activeJob.status}
              currentStage={activeJob.currentStage}
            />
          </div>
        </section>
      )}

      {!run && !activeJob && (
        <section className="rounded-3xl border border-dashed border-slate-300 bg-white px-6 py-14 text-center">
          <FileSearch className="mx-auto size-9 text-slate-400" aria-hidden="true" />
          <h2 className="mt-4 text-lg font-semibold text-slate-950">
            No extracted content is available
          </h2>
          <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-600">
            Start background extraction for the current available PDF, DOCX, or XLSX
            file. No placeholder content will be displayed.
          </p>
          {file && !documentRecord.isArchived && (
            <div className="mt-5 flex justify-center">
              <StartExtractionButton fileId={file.id} />
            </div>
          )}
          {lastFailedJobQuery.data?.error && (
            <div className="mx-auto mt-5 max-w-xl text-left">
              <ExtractionErrorPanel error={lastFailedJobQuery.data.error} />
            </div>
          )}
        </section>
      )}

      {run && (
        <>
          <ExtractionSummaryCards summary={run} />
          <ExtractionWarningList warnings={run.warnings} />

          {run.status === 'OCR_REQUIRED' && (
            <section className="rounded-3xl border border-orange-200 bg-orange-50 p-6">
              <h2 className="text-lg font-semibold text-orange-950">
                Native selectable text was not detected
              </h2>
              <p className="mt-3 text-sm leading-6 text-orange-900">
                This merged viewer shows the latest authorized OCR blocks when OCR has
                completed. Native extraction provenance remains unchanged.
              </p>
            </section>
          )}
          <div className="grid gap-5 xl:grid-cols-[17rem_minmax(0,1fr)_20rem]">
            <aside className="self-start rounded-2xl border border-slate-200 bg-white p-4 xl:sticky xl:top-24">
              <p className="mb-3 text-xs font-semibold text-slate-950">
                {run.extractorType === 'PDF'
                  ? 'Pages'
                  : run.extractorType === 'XLSX'
                    ? 'Worksheets'
                    : 'Document Parts'}
              </p>
              {containersQuery.isLoading ? (
                <div className="h-44 animate-pulse rounded-xl bg-slate-100" />
              ) : (
                <ContainerNavigator
                  containers={containers}
                  selectedId={effectiveContainerId}
                  onSelect={selectContainer}
                />
              )}
              {containersQuery.data && containersQuery.data.totalPages > 1 && (
                <div className="mt-3 flex items-center justify-between text-[10px] text-slate-500">
                  <button
                    type="button"
                    onClick={() =>
                      setContainerPage((current) => Math.max(1, current - 1))
                    }
                    disabled={containerPage <= 1}
                    className="rounded-lg border border-slate-300 px-2 py-1 disabled:opacity-50"
                  >
                    Previous
                  </button>
                  <span>
                    {containerPage}/{containersQuery.data.totalPages}
                  </span>
                  <button
                    type="button"
                    onClick={() => setContainerPage((current) => current + 1)}
                    disabled={containerPage >= containersQuery.data.totalPages}
                    className="rounded-lg border border-slate-300 px-2 py-1 disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              )}
            </aside>

            <main className="min-w-0 space-y-4">
              {run.extractorType === 'DOCX' && (
                <p className="rounded-xl border border-blue-200 bg-blue-50 p-3 text-xs leading-5 text-blue-800">
                  DOCX content is displayed in source order. Page numbers may differ
                  from Microsoft Word.
                </p>
              )}
              {sourceTargetActive && (
                <p
                  role="status"
                  className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-800"
                >
                  Source navigation is scoped to the immutable extraction run
                  {hasRequestedPage ? `, page ${requestedPageNumber}` : ''}
                  {requestedWorksheet ? `, worksheet ${requestedWorksheet}` : ''}
                  {requestedCell ? `, cell ${requestedCell}` : ''}. The matching source
                  block is highlighted below.
                </p>
              )}
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-3">
                <div className="flex gap-1">
                  <ModeButton
                    active={viewerMode === 'blocks'}
                    label={run.extractorType === 'XLSX' ? 'Cells' : 'Blocks'}
                    icon={ListTree}
                    onClick={() => setViewerMode('blocks')}
                  />
                  <ModeButton
                    active={viewerMode === 'raw'}
                    label="Raw Text"
                    icon={Braces}
                    onClick={() => setViewerMode('raw')}
                  />
                  {(run.totalTables > 0 || run.extractorType === 'DOCX') && (
                    <ModeButton
                      active={viewerMode === 'tables'}
                      label="Tables"
                      icon={Table2}
                      onClick={() => setViewerMode('tables')}
                    />
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  <label className="text-[10px] font-semibold text-slate-600">
                    Content Source
                    <select
                      aria-label="Content Source"
                      value={contentSourceFilter}
                      onChange={(event) => {
                        setSourceTargetActive(false);
                        setContentSourceFilter(
                          event.target.value as ContentSourceFilter,
                        );
                        setBlockPage(1);
                      }}
                      className="ml-2 min-h-9 rounded-lg border border-slate-300 bg-white px-2 text-xs"
                    >
                      <option value="ALL">Native and OCR</option>
                      <option value="NATIVE">Native</option>
                      <option value="OCR">OCR</option>
                    </select>
                  </label>
                  <label className="text-[10px] font-semibold text-slate-600">
                    Detected Language
                    <select
                      aria-label="Detected Language"
                      value={languageFilter}
                      onChange={(event) => {
                        setSourceTargetActive(false);
                        setLanguageFilter(event.target.value as LanguageCode | '');
                        setBlockPage(1);
                      }}
                      className="ml-2 min-h-9 rounded-lg border border-slate-300 bg-white px-2 text-xs"
                    >
                      <option value="">All languages</option>
                      <option value="id">Indonesian</option>
                      <option value="en">English</option>
                      <option value="zh">Chinese</option>
                      <option value="mixed">Mixed</option>
                      <option value="unknown">Unknown</option>
                    </select>
                  </label>
                </div>
                {run.extractorType === 'DOCX' && headings.length > 0 && (
                  <label className="text-[10px] font-semibold text-slate-600">
                    Heading
                    <select
                      value=""
                      onChange={(event) => {
                        const heading = headings.find(
                          (candidate) => candidate.id === event.target.value,
                        );
                        if (heading) {
                          setActiveBlockId(heading.id);
                          document
                            .getElementById(`block-${heading.id}`)
                            ?.scrollIntoView?.({ behavior: 'smooth' });
                        }
                      }}
                      className="ml-2 min-h-9 rounded-lg border border-slate-300 bg-white px-2 text-xs"
                    >
                      <option value="">Jump to heading</option>
                      {headings.map((heading) => (
                        <option key={heading.id} value={heading.id}>
                          {heading.text.slice(0, 80)}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
              </div>

              {blocksQuery.error && (
                <p
                  role="alert"
                  className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700"
                >
                  {getApiErrorMessage(
                    blocksQuery.error,
                    'Extracted blocks could not be loaded.',
                  )}
                </p>
              )}
              {viewerMode === 'blocks' &&
                (blocksQuery.isLoading ? (
                  <div className="h-72 animate-pulse rounded-2xl bg-slate-100" />
                ) : (
                  <ExtractedBlockViewer
                    blocks={visibleBlocks}
                    extractorType={run.extractorType}
                    activeBlockId={effectiveActiveBlockId}
                    highlightQuery={searchQuery}
                    onSelectBlock={(block: ExtractedBlock) =>
                      setActiveBlockId(block.id)
                    }
                  />
                ))}
              {viewerMode === 'raw' && (
                <div className="space-y-3">
                  <p className="rounded-xl border border-blue-200 bg-blue-50 p-3 text-xs leading-5 text-blue-800">
                    Raw text is assembled from the current server-side page. Use the
                    page controls to continue, or export TXT for the complete result.
                  </p>
                  <pre className="min-h-64 overflow-x-auto whitespace-pre-wrap rounded-2xl border border-slate-200 bg-white p-5 font-mono text-xs leading-6 text-slate-700">
                    {rawTextPreview || 'No text in this result page.'}
                  </pre>
                </div>
              )}
              {viewerMode === 'tables' && (
                <ExtractedTableViewer tables={tablesQuery.data?.items ?? []} />
              )}
              {(viewerMode === 'blocks' || viewerMode === 'raw') &&
                blocksQuery.data &&
                blocksQuery.data.totalPages > 1 && (
                  <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-3 text-xs text-slate-600">
                    <span>
                      Page {blockPage} of {blocksQuery.data.totalPages} ·{' '}
                      {blocksQuery.data.totalItems.toLocaleString()}{' '}
                      {run.extractorType === 'XLSX' ? 'cells' : 'blocks'}
                    </span>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() =>
                          setBlockPage((current) => Math.max(1, current - 1))
                        }
                        disabled={blockPage <= 1}
                        className="min-h-9 rounded-lg border border-slate-300 px-3 font-semibold disabled:opacity-50"
                      >
                        Previous
                      </button>
                      <button
                        type="button"
                        onClick={() => setBlockPage((current) => current + 1)}
                        disabled={blockPage >= blocksQuery.data.totalPages}
                        className="min-h-9 rounded-lg border border-slate-300 px-3 font-semibold disabled:opacity-50"
                      >
                        Next
                      </button>
                    </div>
                  </div>
                )}
            </main>

            <aside className="space-y-4 self-start xl:sticky xl:top-24">
              <section className="rounded-2xl border border-slate-200 bg-white p-4">
                <label className="block text-xs font-semibold text-slate-800">
                  Search extracted content
                  <span className="relative mt-2 block">
                    <Search
                      className="pointer-events-none absolute left-3 top-3 size-4 text-slate-400"
                      aria-hidden="true"
                    />
                    <input
                      value={searchInput}
                      onChange={(event) => setSearchInput(event.target.value)}
                      minLength={2}
                      maxLength={200}
                      placeholder="At least 2 characters"
                      className="min-h-10 w-full rounded-xl border border-slate-300 pl-9 pr-3 text-xs outline-none focus:border-blue-600"
                    />
                  </span>
                </label>
                {searchInput.length === 1 && (
                  <p className="mt-2 text-[10px] text-amber-700">
                    Enter at least 2 characters.
                  </p>
                )}
                {searchResultQuery.data && (
                  <div className="mt-4">
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                      {searchResultQuery.data.totalMatches.toLocaleString()} results
                    </p>
                    <ul className="mt-2 max-h-80 space-y-2 overflow-y-auto">
                      {searchResultQuery.data.items.map((result) => (
                        <li key={result.blockId}>
                          <button
                            type="button"
                            onClick={() => openSearchResult(result)}
                            className="w-full rounded-xl border border-slate-200 p-3 text-left hover:border-blue-300 hover:bg-blue-50"
                          >
                            <span className="block text-[10px] font-semibold text-blue-700">
                              {result.containerName || result.sourceReference}
                            </span>
                            <span className="mt-1 block text-xs leading-5 text-slate-700">
                              <SafeHighlight
                                text={result.snippet}
                                query={searchQuery}
                              />
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {searchResultQuery.error && (
                  <p role="alert" className="mt-3 text-xs text-rose-700">
                    {getApiErrorMessage(
                      searchResultQuery.error,
                      'Search could not be completed.',
                    )}
                  </p>
                )}
              </section>

              <section className="rounded-2xl border border-slate-200 bg-white p-4">
                <p className="text-xs font-semibold text-slate-900">Metadata</p>
                <dl className="mt-3 space-y-3 text-[11px]">
                  <MetadataField label="Extractor" value={run.extractorType} />
                  <MetadataField label="Version" value={run.extractorVersion} />
                  <MetadataField
                    label="Source SHA-256"
                    value={run.sourceSha256Hash}
                    mono
                  />
                  <MetadataField
                    label="Content SHA-256"
                    value={run.contentHash ?? '—'}
                    mono
                  />
                </dl>
                {run.metadata && Object.keys(run.metadata).length > 0 && (
                  <details className="mt-4 text-[10px] text-slate-500">
                    <summary className="cursor-pointer font-semibold">
                      Extraction metadata
                    </summary>
                    <pre className="mt-2 max-h-64 overflow-auto rounded-lg bg-slate-50 p-2 font-mono">
                      {JSON.stringify(run.metadata, null, 2)}
                    </pre>
                  </details>
                )}
              </section>

              <section className="rounded-2xl border border-slate-200 bg-white p-4">
                <p className="text-xs font-semibold text-slate-900">Actions</p>
                <div className="mt-3 grid gap-2">
                  {hasPermission('documents:export_extracted_content') &&
                    (['json', 'txt'] as const).map((format) => (
                      <button
                        key={format}
                        type="button"
                        onClick={() => void exportRun(format)}
                        disabled={exportMutation.isPending}
                        className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-slate-300 text-xs font-semibold uppercase text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                      >
                        <Download className="size-3.5" aria-hidden="true" />
                        Export {format}
                      </button>
                    ))}
                  {file &&
                    file.isCurrent &&
                    file.fileStatus === 'AVAILABLE' &&
                    (!run || run.file.id === file.id) &&
                    !documentRecord.isArchived &&
                    hasPermission('documents:reextract') && (
                      <button
                        type="button"
                        onClick={() => setReextractOpen(true)}
                        className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl bg-indigo-50 text-xs font-semibold text-indigo-700 hover:bg-indigo-100"
                      >
                        <RefreshCw className="size-3.5" aria-hidden="true" />
                        Re-extract
                      </button>
                    )}
                </div>
              </section>
            </aside>
          </div>
        </>
      )}
      <ReExtractionDialog
        isOpen={reextractOpen}
        run={run}
        isPending={mutations.reextract.isPending}
        onClose={() => setReextractOpen(false)}
        onConfirm={reextract}
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

function MetadataField({
  label,
  mono = false,
  value,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="font-semibold text-slate-500">{label}</dt>
      <dd
        className={`mt-1 break-all text-slate-800 ${mono ? 'font-mono text-[9px]' : ''}`}
      >
        {value}
      </dd>
    </div>
  );
}

function ModeButton({
  active,
  icon: Icon,
  label,
  onClick,
}: {
  active: boolean;
  icon: typeof ListTree;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold ${
        active
          ? 'bg-slate-900 text-white'
          : 'text-slate-600 hover:bg-slate-100 hover:text-slate-950'
      }`}
    >
      <Icon className="size-3.5" aria-hidden="true" />
      {label}
    </button>
  );
}
