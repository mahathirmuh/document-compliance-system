import { Ban, CheckCircle2, Download, GitCompareArrows, Play } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import {
  Phase8ErrorAlert,
  Phase8FilterField,
  Phase8Loading,
  Phase8Pagination,
} from '../../components/compliance/Phase8TableUtilities';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { RevisionDiff } from '../../components/revision-comparison/RevisionDiff';
import { useDocumentRevisions } from '../../hooks/useDocumentRevisions';
import { useRevisionFiles } from '../../hooks/useDocumentFiles';
import { useDocuments } from '../../hooks/useDocuments';
import {
  useRevisionChanges,
  useRevisionComparison,
  useRevisionComparisonJob,
  useRevisionComparisonMutations,
  useRevisionComparisonSummary,
  useRevisionFindingChanges,
  useRevisionLanguageChanges,
  useRevisionSectionChanges,
} from '../../hooks/useRevisionComparison';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import {
  isTerminalRevisionComparisonJobStatus,
  revisionChangeTypes,
  type RevisionChangeType,
  type RevisionComparisonSummary,
  type RevisionFindingChange,
  type RevisionLanguageChange,
  type RevisionSectionChange,
} from '../../types/revisionComparison';
import { downloadFile } from '../../utils/downloadFile';

type ResultTab =
  | 'summary'
  | 'sections'
  | 'languages'
  | 'content'
  | 'compliance'
  | 'similarity'
  | 'glossary'
  | 'findings';

export function RevisionComparisonPage() {
  const { documentId: routeDocumentId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const [documentId, setDocumentId] = useState(
    routeDocumentId ?? searchParams.get('documentId') ?? '',
  );
  const [baseRevisionId, setBaseRevisionId] = useState(
    searchParams.get('baseRevisionId') ?? '',
  );
  const [targetRevisionId, setTargetRevisionId] = useState(
    searchParams.get('targetRevisionId') ?? '',
  );
  const [jobId, setJobId] = useState<string | null>(searchParams.get('jobId'));
  const [comparisonId, setComparisonId] = useState<string | null>(
    searchParams.get('comparisonId'),
  );
  const [tab, setTab] = useState<ResultTab>('summary');
  const [changeType, setChangeType] = useState<RevisionChangeType | ''>('');
  const [languageCode, setLanguageCode] = useState('');
  const [page, setPage] = useState(1);
  const documentsQuery = useDocuments({
    page: 1,
    pageSize: 100,
    sortBy: 'baseDocumentCode',
    sortOrder: 'asc',
  });
  const revisionsQuery = useDocumentRevisions(documentId || null);
  const baseFilesQuery = useRevisionFiles(documentId || null, baseRevisionId || null);
  const targetFilesQuery = useRevisionFiles(
    documentId || null,
    targetRevisionId || null,
  );
  const jobQuery = useRevisionComparisonJob(jobId);
  const activeComparisonId =
    comparisonId ?? jobQuery.data?.resultSummary?.comparisonId ?? null;
  const comparisonQuery = useRevisionComparison(activeComparisonId);
  const summaryQuery = useRevisionComparisonSummary(activeComparisonId);
  const changesQuery = useRevisionChanges(activeComparisonId, {
    page,
    pageSize: 50,
    ...(changeType ? { changeType } : {}),
    ...(languageCode ? { languageCode: languageCode as 'id' | 'en' | 'zh' } : {}),
  });
  const sectionsQuery = useRevisionSectionChanges(activeComparisonId);
  const languagesQuery = useRevisionLanguageChanges(activeComparisonId);
  const findingsQuery = useRevisionFindingChanges(activeComparisonId);
  const mutations = useRevisionComparisonMutations();
  const { showToast } = useToast();

  useEffect(() => {
    const resultId = jobQuery.data?.resultSummary?.comparisonId;
    if (resultId) {
      setComparisonId(resultId);
      navigate(
        `?documentId=${documentId}&baseRevisionId=${baseRevisionId}&targetRevisionId=${targetRevisionId}&comparisonId=${resultId}`,
        { replace: true },
      );
    }
  }, [
    baseRevisionId,
    documentId,
    jobQuery.data?.resultSummary?.comparisonId,
    navigate,
    targetRevisionId,
  ]);

  const baseFile = (baseFilesQuery.data ?? []).find(
    (file) => file.isCurrent && file.fileStatus === 'AVAILABLE',
  );
  const targetFile = (targetFilesQuery.data ?? []).find(
    (file) => file.isCurrent && file.fileStatus === 'AVAILABLE',
  );
  const sameRevision = Boolean(baseRevisionId) && baseRevisionId === targetRevisionId;
  const prerequisitesReady =
    Boolean(documentId && baseRevisionId && targetRevisionId) &&
    !sameRevision &&
    Boolean(baseFile && targetFile);

  const sectionChanges = normalizeList<RevisionSectionChange>(sectionsQuery.data);
  const languageChanges = normalizeList<RevisionLanguageChange>(languagesQuery.data);
  const findingChanges = normalizeList<RevisionFindingChange>(findingsQuery.data);
  const glossaryViolationChange = numberValue(
    comparisonQuery.data?.summary.glossaryViolationChange,
  );

  const start = async (): Promise<void> => {
    if (!prerequisitesReady) {
      return;
    }
    try {
      const job = await mutations.start.mutateAsync({
        documentId,
        baseRevisionId,
        targetRevisionId,
        force: false,
      });
      setJobId(job.jobId);
      setComparisonId(job.comparisonId);
      showToast({
        tone: 'success',
        title: 'Revision comparison queued',
        message: 'Canonical alignment and language-aware comparison have started.',
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Revision comparison could not be queued',
        message: getApiErrorMessage(
          error,
          'Check compatible processing runs for both revisions.',
        ),
      });
    }
  };

  const exportComparison = async (format: 'json' | 'xlsx' | 'pdf'): Promise<void> => {
    if (!activeComparisonId) {
      return;
    }
    try {
      const result = await mutations.export.mutateAsync({
        comparisonId: activeComparisonId,
        format,
      });
      downloadFile(result, `revision_comparison.${format}`);
      showToast({
        tone: 'success',
        title: `Revision ${format.toUpperCase()} ready`,
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Revision export failed',
        message: getApiErrorMessage(error, 'Try again.'),
      });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <MasterDataPageHeader
          eyebrow="Documents"
          title="Revision Comparison"
          description="Compare canonical sections, multilingual content, scores, terminology, and finding state without changing either revision."
        />
        {activeComparisonId && hasPermission('revision_comparison:export') && (
          <div className="flex gap-2">
            {(['json', 'xlsx', 'pdf'] as const).map((format) => (
              <button
                key={format}
                type="button"
                onClick={() => void exportComparison(format)}
                disabled={mutations.export.isPending}
                className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 px-3 text-xs font-semibold uppercase text-slate-700 disabled:opacity-50"
              >
                <Download className="size-4" aria-hidden="true" />
                {format}
              </button>
            ))}
          </div>
        )}
      </div>

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="grid gap-5 lg:grid-cols-4">
          <StepHeader step="1" title="Select Revisions" />
          <StepHeader step="2" title="Prerequisite Check" />
          <StepHeader step="3" title="Run Comparison" />
          <StepHeader step="4" title="Review Result" />
        </div>
        <div className="mt-5 grid gap-4 lg:grid-cols-3">
          <Phase8FilterField label="Select Document">
            <select
              value={documentId}
              disabled={Boolean(routeDocumentId)}
              onChange={(event) => {
                setDocumentId(event.target.value);
                setBaseRevisionId('');
                setTargetRevisionId('');
                setJobId(null);
                setComparisonId(null);
              }}
              className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm disabled:bg-slate-100"
            >
              <option value="">Select document</option>
              {(documentsQuery.data?.items ?? []).map((document) => (
                <option key={document.id} value={document.id}>
                  {document.baseDocumentCode} — {document.title}
                </option>
              ))}
            </select>
          </Phase8FilterField>
          <Phase8FilterField label="Select Base Revision">
            <select
              value={baseRevisionId}
              disabled={!documentId}
              onChange={(event) => {
                setBaseRevisionId(event.target.value);
                setComparisonId(null);
              }}
              className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm disabled:bg-slate-100"
            >
              <option value="">Select base revision</option>
              {(revisionsQuery.data ?? []).map((revision) => (
                <option key={revision.id} value={revision.id}>
                  {revision.revisionCode}
                  {revision.isCurrent ? ' (current)' : ''}
                </option>
              ))}
            </select>
          </Phase8FilterField>
          <Phase8FilterField label="Select Target Revision">
            <select
              value={targetRevisionId}
              disabled={!documentId}
              onChange={(event) => {
                setTargetRevisionId(event.target.value);
                setComparisonId(null);
              }}
              className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm disabled:bg-slate-100"
            >
              <option value="">Select target revision</option>
              {(revisionsQuery.data ?? []).map((revision) => (
                <option key={revision.id} value={revision.id}>
                  {revision.revisionCode}
                  {revision.isCurrent ? ' (current)' : ''}
                </option>
              ))}
            </select>
          </Phase8FilterField>
        </div>

        {sameRevision && (
          <p
            role="alert"
            className="mt-4 rounded-xl bg-rose-50 p-3 text-xs text-rose-800"
          >
            Base and target revision must be different.
          </p>
        )}
        {baseRevisionId && targetRevisionId && !sameRevision && (
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <Prerequisite
              label="Base revision current file"
              ready={Boolean(baseFile)}
              loading={baseFilesQuery.isLoading}
            />
            <Prerequisite
              label="Target revision current file"
              ready={Boolean(targetFile)}
              loading={targetFilesQuery.isLoading}
            />
          </div>
        )}
        <div className="mt-5 flex flex-wrap gap-2">
          {hasPermission('revision_comparison:run') && (
            <button
              type="button"
              onClick={() => void start()}
              disabled={!prerequisitesReady || mutations.start.isPending}
              className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-indigo-700 px-4 text-sm font-semibold text-white disabled:opacity-50"
            >
              <Play className="size-4" aria-hidden="true" />
              Run Comparison
            </button>
          )}
          {jobId &&
            jobQuery.data &&
            !jobQuery.data.resultSummary?.comparisonId &&
            !isTerminalRevisionComparisonJobStatus(jobQuery.data.status) &&
            hasPermission('revision_comparison:run') && (
              <button
                type="button"
                onClick={() => void mutations.cancel.mutateAsync(jobId)}
                disabled={mutations.cancel.isPending}
                className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 text-xs font-semibold text-amber-800 disabled:opacity-50"
              >
                <Ban className="size-4" aria-hidden="true" />
                Cancel
              </button>
            )}
        </div>
      </section>

      {jobId && jobQuery.data && !jobQuery.data.resultSummary?.comparisonId && (
        <section className="rounded-2xl border border-indigo-200 bg-indigo-50 p-5">
          <div className="flex justify-between text-xs font-semibold text-indigo-900">
            <span>{jobQuery.data.currentStage?.replaceAll('_', ' ') ?? 'Queued'}</span>
            <span>{jobQuery.data.progress}%</span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-indigo-100">
            <span
              className="block h-full bg-indigo-700"
              style={{
                width: `${Math.max(0, Math.min(100, jobQuery.data.progress))}%`,
              }}
            />
          </div>
          <p className="mt-2 text-xs text-indigo-800">
            {jobQuery.data.status.replaceAll('_', ' ')} · polling every three seconds
          </p>
          {jobQuery.data.errorMessage && (
            <p role="alert" className="mt-2 text-xs text-rose-800">
              {jobQuery.data.errorMessage}
            </p>
          )}
        </section>
      )}

      {activeComparisonId && (comparisonQuery.isLoading || summaryQuery.isLoading) && (
        <Phase8Loading label="Loading revision comparison" />
      )}
      {(comparisonQuery.error ?? summaryQuery.error) && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            comparisonQuery.error ?? summaryQuery.error,
            'Revision comparison could not be loaded.',
          )}
        />
      )}

      {activeComparisonId && comparisonQuery.data && summaryQuery.data && (
        <>
          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-9">
            {[
              ['Total Changes', summaryQuery.data.totalChanges],
              ['Added', summaryQuery.data.added],
              ['Removed', summaryQuery.data.removed],
              ['Modified', summaryQuery.data.modified],
              ['Moved', summaryQuery.data.moved],
              [
                'Compliance Score Change',
                scoreChange(summaryQuery.data.complianceScoreChange),
              ],
              [
                'Similarity Change',
                scoreChange(summaryQuery.data.similarityScoreChange),
              ],
              ['New Findings', summaryQuery.data.newFindings],
              ['No Longer Reproduced', summaryQuery.data.noLongerReproduced],
            ].map(([label, value]) => (
              <div
                key={label}
                className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
              >
                <p className="text-[9px] font-semibold uppercase tracking-wide text-slate-500">
                  {label}
                </p>
                <p className="mt-2 text-xl font-semibold text-slate-950">{value}</p>
              </div>
            ))}
          </section>
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <span className="text-xs font-semibold text-slate-500">Classification</span>
            <span
              className={`ml-3 rounded-full px-3 py-1 text-xs font-semibold ${classificationStyle(
                summaryQuery.data.classification,
              )}`}
            >
              {summaryQuery.data.classification}
            </span>
          </div>

          <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
            <div className="flex overflow-x-auto border-b border-slate-200 px-3">
              {(
                [
                  ['summary', 'Summary'],
                  ['sections', 'Sections'],
                  ['languages', 'Languages'],
                  ['content', 'Content Changes'],
                  ['compliance', 'Compliance'],
                  ['similarity', 'Similarity'],
                  ['glossary', 'Glossary'],
                  ['findings', 'Findings'],
                ] as const
              ).map(([candidate, label]) => (
                <button
                  key={candidate}
                  type="button"
                  onClick={() => setTab(candidate)}
                  className={`min-h-12 border-b-2 px-4 text-xs font-semibold ${
                    tab === candidate
                      ? 'border-indigo-700 text-indigo-700'
                      : 'border-transparent text-slate-500'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="p-5">
              {tab === 'summary' && (
                <div className="grid gap-5 lg:grid-cols-2">
                  <SummaryList
                    title="Key Regressions"
                    values={revisionRegressionSignals(
                      summaryQuery.data,
                      languageChanges,
                      glossaryViolationChange,
                    )}
                    empty="No key regressions detected."
                    tone="regression"
                  />
                  <SummaryList
                    title="Key Improvements"
                    values={revisionImprovementSignals(
                      summaryQuery.data,
                      languageChanges,
                      glossaryViolationChange,
                    )}
                    empty="No key improvements detected."
                    tone="improvement"
                  />
                </div>
              )}
              {tab === 'sections' && <SectionChangesTable rows={sectionChanges} />}
              {tab === 'languages' && <LanguageChangesTable rows={languageChanges} />}
              {tab === 'content' && (
                <div className="space-y-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <FilterSelect
                      label="Change Type"
                      value={changeType}
                      onChange={(value) => {
                        setChangeType(value as RevisionChangeType | '');
                        setPage(1);
                      }}
                      options={[
                        ['', 'All changes'],
                        ...revisionChangeTypes.map((type) => [type, type] as const),
                      ]}
                    />
                    <FilterSelect
                      label="Language"
                      value={languageCode}
                      onChange={(value) => {
                        setLanguageCode(value);
                        setPage(1);
                      }}
                      options={[
                        ['', 'All languages'],
                        ['id', 'Indonesian'],
                        ['en', 'English'],
                        ['zh', 'Chinese'],
                      ]}
                    />
                  </div>
                  {(changesQuery.data?.items ?? []).map((change) => (
                    <RevisionDiff key={change.id} change={change} />
                  ))}
                  {(changesQuery.data?.items.length ?? 0) === 0 && (
                    <p className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">
                      No content changes match these filters.
                    </p>
                  )}
                </div>
              )}
              {tab === 'compliance' && (
                <ComparisonMetrics
                  rows={[
                    [
                      'Compliance score change',
                      scoreChange(comparisonQuery.data.complianceScoreChange),
                    ],
                    ['New findings', String(comparisonQuery.data.newFindings)],
                    [
                      'No longer reproduced',
                      String(comparisonQuery.data.removedFindings),
                    ],
                    [
                      'Severity changes',
                      String(comparisonQuery.data.severityChangeCount),
                    ],
                    ['Classification', comparisonQuery.data.classification],
                  ]}
                />
              )}
              {tab === 'similarity' && (
                <ComparisonMetrics
                  rows={[
                    [
                      'Translation similarity change',
                      scoreChange(comparisonQuery.data.similarityScoreChange),
                    ],
                    [
                      'Modified translation groups',
                      String(comparisonQuery.data.modifiedTranslationGroups),
                    ],
                    [
                      'Added translation groups',
                      String(comparisonQuery.data.addedTranslationGroups),
                    ],
                    [
                      'Removed translation groups',
                      String(comparisonQuery.data.removedTranslationGroups),
                    ],
                  ]}
                />
              )}
              {tab === 'glossary' && (
                <ComparisonMetrics
                  rows={[
                    ['Glossary violation change', scoreChange(glossaryViolationChange)],
                    [
                      'Interpretation',
                      glossaryViolationChange !== null && glossaryViolationChange > 0
                        ? 'More glossary violations in target'
                        : glossaryViolationChange !== null &&
                            glossaryViolationChange < 0
                          ? 'Fewer glossary violations in target'
                          : glossaryViolationChange === null
                            ? 'Not evaluated'
                            : 'No net glossary violation change',
                    ],
                  ]}
                />
              )}
              {tab === 'findings' && <FindingChangesTable rows={findingChanges} />}
            </div>
          </section>
          {tab === 'content' && changesQuery.data && (
            <Phase8Pagination
              page={page}
              pageSize={50}
              totalItems={changesQuery.data.totalItems}
              totalPages={changesQuery.data.totalPages}
              label="revision changes"
              onPageChange={setPage}
            />
          )}
          <p className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-900">
            Revision comparison uses automated alignment and bounded text snapshots.
            Review low-confidence alignment manually. No source content or finding
            status is changed automatically.
          </p>
        </>
      )}
    </div>
  );
}

function normalizeList<T>(
  data: readonly T[] | { items: readonly T[] } | undefined,
): readonly T[] {
  if (!data) {
    return [];
  }
  return 'items' in data ? data.items : data;
}

function StepHeader({ step, title }: { step: string; title: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="grid size-8 place-items-center rounded-full bg-indigo-100 text-xs font-semibold text-indigo-800">
        {step}
      </span>
      <span className="text-xs font-semibold text-slate-800">{title}</span>
    </div>
  );
}

function Prerequisite({
  label,
  loading,
  ready,
}: {
  label: string;
  loading: boolean;
  ready: boolean;
}) {
  return (
    <div
      className={`flex items-center gap-2 rounded-xl border p-3 text-xs ${
        ready
          ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
          : 'border-amber-200 bg-amber-50 text-amber-800'
      }`}
    >
      {ready ? (
        <CheckCircle2 className="size-4" aria-hidden="true" />
      ) : (
        <GitCompareArrows className="size-4" aria-hidden="true" />
      )}
      {label}: {loading ? 'checking…' : ready ? 'ready' : 'missing available file'}
    </div>
  );
}

function FilterSelect({
  label,
  onChange,
  options,
  value,
}: {
  label: string;
  value: string;
  options: readonly (readonly [string, string])[];
  onChange: (value: string) => void;
}) {
  return (
    <Phase8FilterField label={label}>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
      >
        {options.map(([optionValue, optionLabel]) => (
          <option key={optionValue || 'all'} value={optionValue}>
            {optionLabel}
          </option>
        ))}
      </select>
    </Phase8FilterField>
  );
}

function SummaryList({
  empty,
  title,
  tone,
  values,
}: {
  title: string;
  values: readonly string[];
  empty: string;
  tone: 'regression' | 'improvement';
}) {
  return (
    <section>
      <h2 className="text-sm font-semibold text-slate-950">{title}</h2>
      <ul className="mt-3 space-y-2">
        {(values.length ? values : [empty]).map((value) => (
          <li
            key={value}
            className={`rounded-xl p-3 text-xs ${
              tone === 'regression'
                ? 'bg-rose-50 text-rose-800'
                : 'bg-emerald-50 text-emerald-800'
            }`}
          >
            {value}
          </li>
        ))}
      </ul>
    </section>
  );
}

function SectionChangesTable({ rows }: { rows: readonly RevisionSectionChange[] }) {
  return (
    <SimpleTable
      headings={['Section', 'Added', 'Removed', 'Modified', 'Moved', 'Unchanged']}
      rows={rows.map((row) => [
        row.sectionKey,
        row.added,
        row.removed,
        row.modified,
        row.moved,
        row.unchanged,
      ])}
      empty="No section changes."
    />
  );
}

function LanguageChangesTable({ rows }: { rows: readonly RevisionLanguageChange[] }) {
  return (
    <SimpleTable
      headings={[
        'Language',
        'Base Coverage',
        'Target Coverage',
        'Change',
        'Base Presence',
        'Target Presence',
        'Regression',
        'Groups Added',
        'Groups Removed',
        'Groups Modified',
        'New Missing Language',
        'Fixed Missing Language',
      ]}
      rows={rows.map((row) => [
        row.languageCode.toUpperCase(),
        coverageValue(row.baseCoverage, row.baseCount),
        coverageValue(row.targetCoverage, row.targetCount),
        coverageChange(row.coverageChange),
        row.basePresence ? 'Present' : 'Missing',
        row.targetPresence ? 'Present' : 'Missing',
        row.regression ? 'Yes' : 'No',
        row.additions,
        row.removals,
        row.modifications,
        !row.targetPresence && row.basePresence ? 1 : 0,
        row.fixedMissingLanguage ? 1 : 0,
      ])}
      empty="No language changes."
    />
  );
}

function FindingChangesTable({ rows }: { rows: readonly RevisionFindingChange[] }) {
  return (
    <SimpleTable
      headings={[
        'Finding Code',
        'Base Severity',
        'Target Severity',
        'Comparison Status',
        'Base Status',
        'Target Status',
        'Section',
        'Language',
        'Location',
      ]}
      rows={rows.map((row) => [
        row.findingCode,
        row.baseSeverity ?? '—',
        row.targetSeverity ?? '—',
        row.comparisonStatus.replaceAll('_', ' '),
        row.baseStatus ?? '—',
        row.targetStatus ?? '—',
        row.section ?? '—',
        row.language?.toUpperCase() ?? '—',
        row.location ?? '—',
      ])}
      empty="No finding comparison records."
    />
  );
}

function SimpleTable({
  empty,
  headings,
  rows,
}: {
  headings: readonly string[];
  rows: readonly (readonly (string | number)[])[];
  empty: string;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-200">
        <thead className="bg-slate-50">
          <tr>
            {headings.map((heading) => (
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
          {rows.map((row, rowIndex) => (
            <tr key={`${String(row[0])}-${rowIndex}`}>
              {row.map((value, columnIndex) => (
                <td
                  key={`${columnIndex}-${String(value)}`}
                  className="max-w-72 px-4 py-3 text-xs text-slate-700"
                >
                  {value}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && (
        <p className="p-8 text-center text-sm text-slate-500">{empty}</p>
      )}
    </div>
  );
}

function ComparisonMetrics({ rows }: { rows: readonly (readonly [string, string])[] }) {
  return (
    <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {rows.map(([label, value]) => (
        <div key={label} className="rounded-xl bg-slate-50 p-4">
          <dt className="text-[10px] font-semibold uppercase text-slate-500">
            {label}
          </dt>
          <dd className="mt-2 text-sm font-semibold text-slate-950">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

const scoreChange = (value: number | null): string => {
  if (value === null) {
    return 'Not evaluated';
  }
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}`;
};

const coverageValue = (value: number | null, count: number): string =>
  value === null ? `Not evaluated (${count} blocks)` : `${value.toFixed(2)}%`;

const coverageChange = (value: number | null): string => {
  if (value === null) {
    return 'Not evaluated';
  }
  return `${value > 0 ? '+' : ''}${value.toFixed(2)} pp`;
};

const numberValue = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? value : null;

const revisionRegressionSignals = (
  summary: RevisionComparisonSummary,
  languages: readonly RevisionLanguageChange[],
  glossaryChange: number | null,
): readonly string[] => {
  const signals: string[] = [];
  if (summary.complianceScoreChange !== null && summary.complianceScoreChange < 0) {
    signals.push('Compliance score decreased.');
  }
  if (summary.similarityScoreChange !== null && summary.similarityScoreChange < 0) {
    signals.push('Translation similarity decreased.');
  }
  if (summary.newFindings > 0) {
    signals.push(`${summary.newFindings} new finding(s) were reproduced.`);
  }
  languages
    .filter((language) => language.regression)
    .forEach((language) =>
      signals.push(
        `${language.languageCode.toUpperCase()} language presence regressed.`,
      ),
    );
  if (glossaryChange !== null && glossaryChange > 0) {
    signals.push(`${glossaryChange} additional glossary violation(s).`);
  }
  return signals;
};

const revisionImprovementSignals = (
  summary: RevisionComparisonSummary,
  languages: readonly RevisionLanguageChange[],
  glossaryChange: number | null,
): readonly string[] => {
  const signals: string[] = [];
  if (summary.complianceScoreChange !== null && summary.complianceScoreChange > 0) {
    signals.push('Compliance score improved.');
  }
  if (summary.similarityScoreChange !== null && summary.similarityScoreChange > 0) {
    signals.push('Translation similarity improved.');
  }
  if (summary.noLongerReproduced > 0) {
    signals.push(`${summary.noLongerReproduced} finding(s) are no longer reproduced.`);
  }
  languages
    .filter((language) => language.fixedMissingLanguage)
    .forEach((language) =>
      signals.push(
        `${language.languageCode.toUpperCase()} missing-language state was fixed.`,
      ),
    );
  if (glossaryChange !== null && glossaryChange < 0) {
    signals.push(`${Math.abs(glossaryChange)} fewer glossary violation(s).`);
  }
  return signals;
};

const classificationStyle = (
  classification: 'IMPROVED' | 'REGRESSED' | 'UNCHANGED' | 'MIXED',
): string => {
  switch (classification) {
    case 'IMPROVED':
      return 'bg-emerald-100 text-emerald-800';
    case 'REGRESSED':
      return 'bg-rose-100 text-rose-800';
    case 'MIXED':
      return 'bg-amber-100 text-amber-800';
    case 'UNCHANGED':
      return 'bg-slate-100 text-slate-700';
  }
};
