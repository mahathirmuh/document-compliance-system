import {
  ArrowLeft,
  ArrowRightLeft,
  Download,
  FileCheck2,
  Play,
  RefreshCw,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import {
  LanguageComplianceTable,
  LanguageOrderFilters,
  LanguageOrderGroupTable,
  SectionDetailDialog,
  SectionComplianceTable,
} from '../../components/compliance/ComplianceDataViews';
import {
  emptyLanguageOrderFilters,
  type LanguageOrderFiltersValue,
} from '../../components/compliance/languageOrderFilters';
import { ComplianceScorePanel } from '../../components/compliance/ComplianceScorePanel';
import { ComplianceStatusBadge } from '../../components/compliance/ComplianceStatusBadge';
import { FindingsTable } from '../../components/compliance/FindingsTable';
import {
  Phase8ErrorAlert,
  Phase8Loading,
  Phase8Pagination,
} from '../../components/compliance/Phase8TableUtilities';
import { RevalidateComplianceDialog } from '../../components/compliance/RevalidateComplianceDialog';
import {
  useComplianceComparison,
  useComplianceMutations,
  useComplianceRun,
  useComplianceScoreBreakdown,
  useComplianceSummary,
  useDetectedSections,
  useLatestCompliance,
  useTranslationGroups,
} from '../../hooks/useCompliance';
import { useComplianceHistory } from '../../hooks/useComplianceHistory';
import { useDocument } from '../../hooks/useDocument';
import { useRevisionFiles } from '../../hooks/useDocumentFiles';
import { useLatestExtraction } from '../../hooks/useExtractedContent';
import { useFindings } from '../../hooks/useFindings';
import { useLatestLanguageDetection } from '../../hooks/useLanguageResults';
import { useLatestOCR } from '../../hooks/useOCR';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type {
  ComplianceRun,
  DetectedSection,
  TranslationGroupListParams,
} from '../../types/compliance';
import { downloadFile } from '../../utils/downloadFile';
import { formatDateTime } from '../../utils/formatters';

type ComplianceTab =
  'summary' | 'languages' | 'sections' | 'language-order' | 'findings' | 'history';

const tabs: readonly { id: ComplianceTab; label: string }[] = [
  { id: 'summary', label: 'Summary' },
  { id: 'languages', label: 'Languages' },
  { id: 'sections', label: 'Sections' },
  { id: 'language-order', label: 'Language Order' },
  { id: 'findings', label: 'Findings' },
  { id: 'history', label: 'Validation History' },
];

export function DocumentCompliancePage() {
  const { documentId = '', revisionId: routeRevisionId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedTab = searchParams.get('tab');
  const tab = tabs.some((candidate) => candidate.id === requestedTab)
    ? (requestedTab as ComplianceTab)
    : 'summary';
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const documentQuery = useDocument(documentId || null);
  const revisionId = routeRevisionId ?? documentQuery.data?.currentRevision?.id ?? null;
  const revision = documentQuery.data?.revisions.find(
    (candidate) => candidate.id === revisionId,
  );
  const filesQuery = useRevisionFiles(documentId || null, revisionId);
  const requestedFileId = searchParams.get('fileId');
  const selectedFile =
    filesQuery.data?.find((file) => file.id === requestedFileId) ??
    filesQuery.data?.find(
      (file) => file.isCurrent && file.fileStatus === 'AVAILABLE',
    ) ??
    null;
  const fileId = selectedFile?.id ?? null;
  const extractionQuery = useLatestExtraction(fileId);
  const ocrQuery = useLatestOCR(fileId);
  const languageQuery = useLatestLanguageDetection(fileId);
  const latestQuery = useLatestCompliance(fileId);
  const requestedRunId = searchParams.get('runId');
  const runId = requestedRunId ?? latestQuery.data?.id ?? null;
  const runQuery = useComplianceRun(runId);
  const summaryQuery = useComplianceSummary(runId);
  const scoreQuery = useComplianceScoreBreakdown(runId);
  const [sectionPage, setSectionPage] = useState(1);
  const [sectionPageSize, setSectionPageSize] = useState(20);
  const [groupPage, setGroupPage] = useState(1);
  const [groupPageSize, setGroupPageSize] = useState(20);
  const [groupFilterDraft, setGroupFilterDraft] = useState<LanguageOrderFiltersValue>({
    ...emptyLanguageOrderFilters,
  });
  const [groupFilters, setGroupFilters] = useState<LanguageOrderFiltersValue>({
    ...emptyLanguageOrderFilters,
  });
  const [selectedSection, setSelectedSection] = useState<DetectedSection | null>(null);
  const sectionsQuery = useDetectedSections(
    runId,
    { page: sectionPage, pageSize: sectionPageSize },
    { enabled: tab === 'sections' },
  );
  const sectionOptionsQuery = useDetectedSections(
    runId,
    { page: 1, pageSize: 100 },
    { enabled: tab === 'language-order' },
  );
  const groupParams: TranslationGroupListParams = {
    page: groupPage,
    pageSize: groupPageSize,
    ...(groupFilters.completeness === 'COMPLETE'
      ? { isComplete: true }
      : groupFilters.completeness === 'INCOMPLETE'
        ? { isComplete: false }
        : {}),
    ...(groupFilters.orderInvalidOnly ? { isOrderValid: false } : {}),
    ...(groupFilters.lowConfidenceOnly ? { lowConfidence: true } : {}),
    ...(groupFilters.detectedSectionId
      ? { detectedSectionId: groupFilters.detectedSectionId }
      : {}),
    ...(groupFilters.containerId ? { containerId: groupFilters.containerId } : {}),
  };
  const groupsQuery = useTranslationGroups(runId, groupParams, {
    enabled: tab === 'language-order',
  });
  const relatedGroupsQuery = useTranslationGroups(
    runId,
    {
      page: 1,
      pageSize: 100,
      ...(selectedSection ? { detectedSectionId: selectedSection.id } : {}),
    },
    { enabled: selectedSection !== null },
  );
  const [historyPage, setHistoryPage] = useState(1);
  const historyQuery = useComplianceHistory(fileId, {
    page: historyPage,
    pageSize: 20,
  });
  const previousRun =
    historyQuery.data?.items.find((candidate) => candidate.id !== runId) ?? null;
  const compareRequested = searchParams.get('compare') === 'previous';
  const comparisonQuery = useComplianceComparison(
    compareRequested ? runId : null,
    compareRequested ? (previousRun?.id ?? null) : null,
  );
  const findingsQuery = useFindings(
    {
      page: 1,
      pageSize: 50,
      sortBy: 'severity',
      sortOrder: 'desc',
      ...(runId ? { complianceRunId: runId } : {}),
    },
    { enabled: runId !== null && tab === 'findings' },
  );
  const relatedFindingsQuery = useFindings(
    {
      page: 1,
      pageSize: 100,
      ...(runId ? { complianceRunId: runId } : {}),
      ...(selectedSection ? { detectedSectionId: selectedSection.id } : {}),
    },
    { enabled: runId !== null && selectedSection !== null },
  );
  const mutations = useComplianceMutations();
  const [revalidateOpen, setRevalidateOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const { showToast } = useToast();
  const extraction = extractionQuery.data;
  const latestOCR = ocrQuery.data;
  const latestLanguage = languageQuery.data;
  const ocrRequired = extraction?.requiresOcr === true;
  const prerequisites = [
    {
      label: 'Physical document',
      ready: selectedFile !== null,
      guidance: 'Upload an available current PDF, DOCX, or XLSX file.',
    },
    {
      label: 'Extraction',
      ready: extraction !== null && extraction !== undefined,
      guidance: 'Run content extraction for the current physical file.',
    },
    {
      label: 'OCR',
      ready: !ocrRequired || (latestOCR !== null && latestOCR !== undefined),
      guidance: 'Complete OCR because this PDF does not have reliable selectable text.',
    },
    {
      label: 'Language detection',
      ready: latestLanguage !== null && latestLanguage !== undefined,
      guidance: 'Run language detection on the compatible extracted or OCR content.',
    },
    {
      label: 'Validation rule',
      ready:
        revision?.validationRuleId !== null && revision?.validationRuleId !== undefined,
      guidance: 'Assign an active validation rule to this revision.',
    },
  ] as const;
  const missingPrerequisites = prerequisites.filter((item) => !item.ready);
  const canStart =
    hasPermission('compliance:validate') && missingPrerequisites.length === 0;

  const setQueryState = (changes: Record<string, string | null>): void => {
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current);
        Object.entries(changes).forEach(([key, value]) => {
          if (value === null) {
            next.delete(key);
          } else {
            next.set(key, value);
          }
        });
        return next;
      },
      { replace: true },
    );
  };

  useEffect(() => {
    if (
      searchParams.get('action') === 'revalidate' &&
      runId &&
      hasPermission('compliance:revalidate')
    ) {
      setActionError(null);
      setRevalidateOpen(true);
      setSearchParams(
        (current) => {
          const next = new URLSearchParams(current);
          next.delete('action');
          return next;
        },
        { replace: true },
      );
    }
  }, [hasPermission, runId, searchParams, setSearchParams]);

  const startValidation = async (): Promise<void> => {
    if (!fileId || !extraction || !latestLanguage) {
      return;
    }
    setActionError(null);
    try {
      const result = await mutations.start.mutateAsync({
        documentFileId: fileId,
        extractionRunId: extraction.runId,
        ocrRunId: latestOCR?.runId ?? null,
        languageDetectionRunId: latestLanguage.runId,
        validationRuleId: revision?.validationRuleId ?? null,
        force: false,
      });
      showToast({
        tone: 'success',
        title: result.reusedExistingResult
          ? 'Existing compliance result loaded'
          : 'Compliance validation queued',
      });
      if (result.runId) {
        setQueryState({ runId: result.runId });
      }
    } catch (error: unknown) {
      setActionError(
        getApiErrorMessage(error, 'Compliance validation could not be started.'),
      );
    }
  };

  const revalidate = async (reason: string): Promise<void> => {
    if (!runId) {
      return;
    }
    setActionError(null);
    try {
      await mutations.revalidate.mutateAsync({ runId, payload: { reason } });
      setRevalidateOpen(false);
      showToast({
        tone: 'success',
        title: 'Revalidation queued',
        message: 'This run remains unchanged and available for comparison.',
      });
    } catch (error: unknown) {
      setActionError(
        getApiErrorMessage(error, 'The revalidation could not be queued.'),
      );
    }
  };

  const exportRun = async (format: 'json' | 'xlsx'): Promise<void> => {
    if (!runId) {
      return;
    }
    try {
      const result = await mutations.export.mutateAsync({ runId, format });
      downloadFile(
        result,
        `${documentQuery.data?.baseDocumentCode ?? 'document'}_compliance.${format}`,
      );
      showToast({
        tone: 'success',
        title: `Compliance ${format.toUpperCase()} downloaded`,
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Compliance export failed',
        message: getApiErrorMessage(error, 'The export could not be downloaded.'),
      });
    }
  };

  if (documentQuery.isLoading || filesQuery.isLoading) {
    return <Phase8Loading label="Loading document compliance" />;
  }
  if (documentQuery.error || !documentQuery.data) {
    return (
      <Phase8ErrorAlert
        message={getApiErrorMessage(
          documentQuery.error,
          'The document was not found or is outside your scope.',
        )}
      />
    );
  }

  const document = documentQuery.data;

  return (
    <div className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
        <Link
          to={`/documents/${document.id}`}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-blue-700"
        >
          <ArrowLeft className="size-3.5" aria-hidden="true" />
          Document Details
        </Link>
        <div className="mt-5 flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-sm font-semibold text-blue-700">
                {document.baseDocumentCode}
              </span>
              {runQuery.data && (
                <ComplianceStatusBadge status={runQuery.data.complianceStatus} />
              )}
            </div>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
              Document Compliance
            </h1>
            <p className="mt-2 text-sm text-slate-500">
              {document.title} · {revision?.revisionCode ?? 'No revision'} ·{' '}
              {selectedFile?.originalFilename ?? 'No current file'}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Validation Rule: {revision?.validationRule?.name ?? 'Not assigned'}
              {runQuery.data?.completedAt
                ? ` · Validated ${formatDateTime(runQuery.data.completedAt)}`
                : ''}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {canStart && !runId && (
              <button
                type="button"
                onClick={() => void startValidation()}
                disabled={mutations.start.isPending}
                className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white disabled:opacity-50"
              >
                <Play className="size-4" aria-hidden="true" />
                Run Validation
              </button>
            )}
            {runId && hasPermission('compliance:revalidate') && (
              <button
                type="button"
                onClick={() => {
                  setActionError(null);
                  setRevalidateOpen(true);
                }}
                className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-violet-200 bg-violet-50 px-3.5 text-sm font-semibold text-violet-700"
              >
                <RefreshCw className="size-4" aria-hidden="true" />
                Revalidate
              </button>
            )}
            {runId && previousRun && (
              <button
                type="button"
                onClick={() =>
                  setQueryState({
                    compare: compareRequested ? null : 'previous',
                  })
                }
                className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 px-3.5 text-sm font-semibold text-slate-700"
              >
                <ArrowRightLeft className="size-4" aria-hidden="true" />
                {compareRequested ? 'Hide Comparison' : 'Compare Previous'}
              </button>
            )}
            {runId &&
              hasPermission('compliance:export') &&
              (['xlsx', 'json'] as const).map((format) => (
                <button
                  key={format}
                  type="button"
                  onClick={() => void exportRun(format)}
                  disabled={mutations.export.isPending}
                  className="inline-flex min-h-10 items-center gap-1.5 rounded-xl border border-slate-300 px-3 text-xs font-semibold uppercase text-slate-700 disabled:opacity-50"
                >
                  <Download className="size-3.5" aria-hidden="true" />
                  {format}
                </button>
              ))}
            {runId && (
              <Link
                to={`/compliance/findings?runId=${runId}`}
                className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 px-3.5 text-sm font-semibold text-slate-700"
              >
                Open Findings
              </Link>
            )}
          </div>
        </div>
      </section>

      {filesQuery.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            filesQuery.error,
            'The revision’s physical files could not be loaded.',
          )}
        />
      )}
      {actionError && <Phase8ErrorAlert message={actionError} />}

      {!runId && (
        <PrerequisitePanel
          prerequisites={prerequisites}
          canStart={canStart}
          isPending={mutations.start.isPending}
          onStart={() => void startValidation()}
        />
      )}
      {runId &&
        (runQuery.isLoading ||
          summaryQuery.isLoading ||
          scoreQuery.isLoading ||
          (tab === 'sections' && sectionsQuery.isLoading) ||
          (tab === 'language-order' && groupsQuery.isLoading)) && (
          <Phase8Loading label="Loading compliance result" />
        )}
      {runId &&
        (runQuery.error ||
          summaryQuery.error ||
          scoreQuery.error ||
          (tab === 'sections' && sectionsQuery.error) ||
          (tab === 'language-order' && groupsQuery.error)) && (
          <Phase8ErrorAlert
            message={getApiErrorMessage(
              runQuery.error ??
                summaryQuery.error ??
                scoreQuery.error ??
                (tab === 'sections' ? sectionsQuery.error : null) ??
                (tab === 'language-order' ? groupsQuery.error : null),
              'The compliance result could not be loaded.',
            )}
          />
        )}

      {runQuery.data && summaryQuery.data && (
        <>
          <ComplianceScorePanel
            score={runQuery.data.complianceScore}
            status={runQuery.data.complianceStatus}
            breakdown={scoreQuery.data ?? null}
            reasons={[
              ...summaryQuery.data.warnings,
              ...(summaryQuery.data.prerequisiteErrors ?? []),
            ]}
          />
          {compareRequested && previousRun && (
            <ComparisonPanel
              current={runQuery.data}
              previous={previousRun}
              comparison={comparisonQuery.data}
              error={comparisonQuery.error}
            />
          )}
          <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
            <div className="flex overflow-x-auto border-b border-slate-200 px-4 sm:px-6">
              {tabs.map((candidate) => (
                <button
                  key={candidate.id}
                  type="button"
                  onClick={() => {
                    setSelectedSection(null);
                    setQueryState({
                      tab: candidate.id === 'summary' ? null : candidate.id,
                    });
                  }}
                  className={`min-h-13 whitespace-nowrap border-b-2 px-4 text-sm font-semibold ${
                    tab === candidate.id
                      ? 'border-blue-700 text-blue-700'
                      : 'border-transparent text-slate-500'
                  }`}
                >
                  {candidate.label}
                </button>
              ))}
            </div>
            <div className="p-5 sm:p-6">
              {tab === 'summary' && (
                <SummaryTab run={runQuery.data} summary={summaryQuery.data} />
              )}
              {tab === 'languages' && (
                <LanguageComplianceTable summary={summaryQuery.data} />
              )}
              {tab === 'sections' && (
                <>
                  <SectionComplianceTable
                    sections={sectionsQuery.data?.items ?? []}
                    documentId={document.id}
                    revisionId={revisionId}
                    extractionRunId={runQuery.data.extractionRunId}
                    onViewDetails={setSelectedSection}
                  />
                  {sectionsQuery.data && (
                    <Phase8Pagination
                      page={sectionsQuery.data.page}
                      pageSize={sectionsQuery.data.pageSize}
                      totalItems={sectionsQuery.data.totalItems}
                      totalPages={sectionsQuery.data.totalPages}
                      label="detected sections"
                      onPageChange={setSectionPage}
                      onPageSizeChange={(pageSize) => {
                        setSectionPage(1);
                        setSectionPageSize(pageSize);
                      }}
                    />
                  )}
                </>
              )}
              {tab === 'language-order' && (
                <>
                  <LanguageOrderFilters
                    value={groupFilterDraft}
                    sections={sectionOptionsQuery.data?.items ?? []}
                    onChange={setGroupFilterDraft}
                    onApply={() => {
                      setGroupPage(1);
                      setGroupFilters({
                        ...groupFilterDraft,
                        containerId: groupFilterDraft.containerId.trim(),
                      });
                    }}
                    onReset={() => {
                      const reset = { ...emptyLanguageOrderFilters };
                      setGroupPage(1);
                      setGroupFilterDraft(reset);
                      setGroupFilters(reset);
                    }}
                  />
                  <LanguageOrderGroupTable
                    groups={groupsQuery.data?.items ?? []}
                    sections={sectionOptionsQuery.data?.items ?? []}
                  />
                  {groupsQuery.data && (
                    <Phase8Pagination
                      page={groupsQuery.data.page}
                      pageSize={groupsQuery.data.pageSize}
                      totalItems={groupsQuery.data.totalItems}
                      totalPages={groupsQuery.data.totalPages}
                      label="translation groups"
                      onPageChange={setGroupPage}
                      onPageSizeChange={(pageSize) => {
                        setGroupPage(1);
                        setGroupPageSize(pageSize);
                      }}
                    />
                  )}
                </>
              )}
              {tab === 'findings' && (
                <>
                  {findingsQuery.error && (
                    <Phase8ErrorAlert
                      message={getApiErrorMessage(
                        findingsQuery.error,
                        'Findings for this run could not be loaded.',
                      )}
                    />
                  )}
                  <FindingsTable findings={findingsQuery.data?.items ?? []} />
                </>
              )}
              {tab === 'history' && (
                <ComplianceHistoryTable
                  runs={historyQuery.data?.items ?? []}
                  currentRunId={runQuery.data.id}
                  documentId={document.id}
                  revisionId={revisionId}
                  fileId={fileId}
                />
              )}
            </div>
          </section>
          {tab === 'history' && historyQuery.data && (
            <Phase8Pagination
              page={historyPage}
              totalItems={historyQuery.data.totalItems}
              totalPages={historyQuery.data.totalPages}
              label="compliance runs"
              onPageChange={setHistoryPage}
            />
          )}
        </>
      )}

      <SectionDetailDialog
        section={selectedSection}
        documentId={document.id}
        revisionId={revisionId}
        {...(runQuery.data ? { extractionRunId: runQuery.data.extractionRunId } : {})}
        findings={relatedFindingsQuery.data?.items ?? []}
        groups={relatedGroupsQuery.data?.items ?? []}
        isLoadingRelated={
          relatedFindingsQuery.isLoading || relatedGroupsQuery.isLoading
        }
        onClose={() => setSelectedSection(null)}
      />
      <RevalidateComplianceDialog
        isOpen={revalidateOpen}
        isPending={mutations.revalidate.isPending}
        errorMessage={actionError}
        onClose={() => setRevalidateOpen(false)}
        onConfirm={(reason) => void revalidate(reason)}
      />
    </div>
  );
}

function PrerequisitePanel({
  canStart,
  isPending,
  onStart,
  prerequisites,
}: {
  prerequisites: readonly {
    label: string;
    ready: boolean;
    guidance: string;
  }[];
  canStart: boolean;
  isPending: boolean;
  onStart: () => void;
}) {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-blue-50 text-blue-700">
          <FileCheck2 className="size-5" aria-hidden="true" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-slate-950">
            No compliance result is available
          </h2>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            Compliance validation uses compatible extraction, OCR when required,
            language detection, and the assigned validation rule.
          </p>
        </div>
      </div>
      <ul className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {prerequisites.map((item) => (
          <li
            key={item.label}
            className={`rounded-2xl border p-3 ${
              item.ready
                ? 'border-emerald-200 bg-emerald-50'
                : 'border-amber-200 bg-amber-50'
            }`}
          >
            <p
              className={`text-xs font-semibold ${
                item.ready ? 'text-emerald-800' : 'text-amber-900'
              }`}
            >
              {item.label}: {item.ready ? 'Ready' : 'Required'}
            </p>
            {!item.ready && (
              <p className="mt-1 text-xs leading-5 text-amber-800">{item.guidance}</p>
            )}
          </li>
        ))}
      </ul>
      {canStart && (
        <button
          type="button"
          onClick={onStart}
          disabled={isPending}
          className="mt-5 inline-flex min-h-10 items-center gap-2 rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white disabled:opacity-50"
        >
          <Play className="size-4" aria-hidden="true" />
          {isPending ? 'Queueing…' : 'Run Validation'}
        </button>
      )}
    </section>
  );
}

function SummaryTab({
  run,
  summary,
}: {
  run: ComplianceRun;
  summary: NonNullable<ReturnType<typeof useComplianceSummary>['data']>;
}) {
  const cards = [
    ['Required Languages', summary.requiredLanguages.length],
    [
      'Missing Languages',
      summary.missingLanguages?.length ?? run.missingLanguages.length,
    ],
    ['Required Sections', summary.requiredSections],
    ['Complete Sections', summary.completeSections],
    ['Translation Groups', summary.translationGroups.total],
    ['Incomplete Groups', summary.translationGroups.incomplete],
    ['Total Findings', summary.findings.total],
    ['Open Findings', summary.findings.open ?? run.openFindings],
  ] as const;
  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map(([label, value]) => (
          <div key={label} className="rounded-2xl bg-slate-50 p-4">
            <p className="text-2xl font-semibold text-slate-950">{value}</p>
            <p className="mt-1 text-xs text-slate-500">{label}</p>
          </div>
        ))}
      </div>
      {(run.missingLanguages.length > 0 || run.missingSections.length > 0) && (
        <div className="grid gap-4 md:grid-cols-2">
          <MissingCard
            title="Missing Languages"
            values={run.missingLanguages.map((code) =>
              code === 'id'
                ? 'Bahasa Indonesia'
                : code === 'en'
                  ? 'English'
                  : '中文 / Mandarin',
            )}
          />
          <MissingCard title="Missing Sections" values={run.missingSections} />
        </div>
      )}
      <p className="rounded-2xl border border-blue-200 bg-blue-50 p-4 text-xs leading-5 text-blue-800">
        Phase 8 validates structure, presence, coverage, order, and completeness. It
        does not claim that translations have equivalent meaning.
      </p>
    </div>
  );
}

function MissingCard({ title, values }: { title: string; values: readonly string[] }) {
  return (
    <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4">
      <p className="text-xs font-semibold text-rose-900">{title}</p>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-rose-800">
        {values.map((value) => (
          <li key={value}>{value}</li>
        ))}
      </ul>
    </div>
  );
}

function ComparisonPanel({
  comparison,
  current,
  error,
  previous,
}: {
  current: ComplianceRun;
  previous: ComplianceRun;
  comparison: ReturnType<typeof useComplianceComparison>['data'] | undefined;
  error: unknown;
}) {
  if (error) {
    return (
      <Phase8ErrorAlert
        message={getApiErrorMessage(error, 'The run comparison could not be loaded.')}
      />
    );
  }
  return (
    <section className="rounded-3xl border border-indigo-200 bg-indigo-50 p-5">
      <h2 className="text-sm font-semibold text-indigo-950">
        Comparison with previous run
      </h2>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <CompareMetric
          label="Score Change"
          value={
            comparison
              ? `${comparison.scoreChange >= 0 ? '+' : ''}${comparison.scoreChange.toFixed(1)}`
              : `${((current.complianceScore ?? 0) - (previous.complianceScore ?? 0)).toFixed(1)}`
          }
        />
        <CompareMetric
          label="Status"
          value={`${previous.complianceStatus.replaceAll('_', ' ')} → ${current.complianceStatus.replaceAll('_', ' ')}`}
        />
        <CompareMetric
          label="New Findings"
          value={comparison?.newFindings.toString() ?? 'Loading…'}
        />
        <CompareMetric
          label="No Longer Reproduced"
          value={comparison?.resolvedCandidates.toString() ?? 'Loading…'}
        />
        <CompareMetric
          label="Repeated"
          value={comparison?.repeatedFindings.toString() ?? 'Loading…'}
        />
      </div>
      <p className="mt-3 text-xs text-indigo-800">
        Comparison never changes a finding status automatically.
      </p>
    </section>
  );
}

function CompareMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-white/70 p-3">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-indigo-600">
        {label}
      </p>
      <p className="mt-1 text-sm font-semibold text-indigo-950">{value}</p>
    </div>
  );
}

function ComplianceHistoryTable({
  currentRunId,
  documentId,
  fileId,
  revisionId,
  runs,
}: {
  runs: readonly ComplianceRun[];
  currentRunId: string;
  documentId: string;
  revisionId: string | null;
  fileId: string | null;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-[52rem] divide-y divide-slate-200">
        <thead className="bg-slate-50">
          <tr>
            {[
              'Validated At',
              'Status',
              'Score',
              'Findings',
              'Requested By',
              'Result',
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
          {runs.map((run) => (
            <tr key={run.id}>
              <td className="px-4 py-3 text-xs text-slate-600">
                {run.completedAt ? formatDateTime(run.completedAt) : '—'}
              </td>
              <td className="px-4 py-3">
                <ComplianceStatusBadge status={run.complianceStatus} />
              </td>
              <td className="px-4 py-3 text-sm font-semibold text-slate-900">
                {run.complianceScore?.toFixed(1) ?? '—'}
              </td>
              <td className="px-4 py-3 text-xs text-slate-600">{run.totalFindings}</td>
              <td className="px-4 py-3 text-xs text-slate-600">
                {run.requestedBy?.name ?? 'Unknown user'}
              </td>
              <td className="px-4 py-3">
                {run.id === currentRunId ? (
                  <span className="text-xs font-semibold text-blue-700">
                    Current view
                  </span>
                ) : (
                  <Link
                    to={`/documents/${documentId}${revisionId ? `/revisions/${revisionId}` : ''}/compliance?${new URLSearchParams(
                      {
                        ...(fileId ? { fileId } : {}),
                        runId: run.id,
                      },
                    ).toString()}`}
                    className="text-xs font-semibold text-blue-700"
                  >
                    Open Run
                  </Link>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
