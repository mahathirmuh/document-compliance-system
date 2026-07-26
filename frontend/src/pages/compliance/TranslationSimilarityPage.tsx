import { Download, Eye, Languages, Play, RefreshCw, Search } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import {
  Phase8ErrorAlert,
  Phase8FilterField,
  Phase8Loading,
  Phase8Pagination,
} from '../../components/compliance/Phase8TableUtilities';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import {
  ConsistencyBadge,
  SimilarityCategoryBadge,
} from '../../components/similarity/SimilarityCategoryBadge';
import { SimilarityDetailDialog } from '../../components/similarity/SimilarityDetailDialog';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { useDocument } from '../../hooks/useDocument';
import { useRevisionFiles } from '../../hooks/useDocumentFiles';
import {
  useLatestSimilarity,
  useSectionSimilarity,
  useSimilarity,
  useSimilarityHistory,
  useSimilarityMutations,
  useSimilarityResults,
  useSimilaritySummary,
} from '../../hooks/useSimilarity';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import {
  similarityCategories,
  type SectionSimilaritySummary,
  type SimilarityCategory,
  type SimilarityResultListParams,
  type SupportedLanguageCode,
  type TranslationSimilarityResult,
} from '../../types/similarity';
import { downloadFile } from '../../utils/downloadFile';
import { formatDateTime } from '../../utils/formatters';

const languageNames: Record<SupportedLanguageCode, string> = {
  id: 'Indonesian',
  en: 'English',
  zh: 'Chinese',
};

const boundedSnippet = (value: string | null | undefined, maximum = 180): string => {
  const normalized = value?.trim() || 'Text unavailable';
  return normalized.length > maximum
    ? `${normalized.slice(0, maximum).trimEnd()}…`
    : normalized;
};

const displayPercent = (value: number | null | undefined): string =>
  value === null || value === undefined ? '—' : `${(value * 100).toFixed(1)}%`;

type ConsistencyFilter =
  '' | 'number' | 'date' | 'measurement' | 'reference' | 'negation';

export function TranslationSimilarityPage() {
  const { documentId: routeDocumentId, revisionId: routeRevisionId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const documentQuery = useDocument(routeDocumentId ?? null);
  const effectiveRevisionId =
    routeRevisionId ?? documentQuery.data?.currentRevision?.id ?? null;
  const filesQuery = useRevisionFiles(routeDocumentId ?? null, effectiveRevisionId);
  const resolvedFile =
    (filesQuery.data ?? []).find(
      (file) => file.isCurrent && file.fileStatus === 'AVAILABLE',
    ) ?? null;
  const fileId = searchParams.get('fileId') ?? resolvedFile?.id ?? null;
  const requestedRunId = searchParams.get('runId');
  const latestQuery = useLatestSimilarity(fileId);
  const runId = requestedRunId ?? latestQuery.data?.id ?? null;
  const runQuery = useSimilarity(runId);
  const summaryQuery = useSimilaritySummary(runId);
  const sectionsQuery = useSectionSimilarity(runId);
  const historyQuery = useSimilarityHistory(fileId, { page: 1, pageSize: 10 });
  const mutations = useSimilarityMutations();
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const { showToast } = useToast();

  const [searchInput, setSearchInput] = useState('');
  const search = useDebouncedValue(searchInput.trim(), 350);
  const [pair, setPair] = useState('');
  const [sectionId, setSectionId] = useState('');
  const [category, setCategory] = useState<SimilarityCategory | ''>('');
  const [minimumScore, setMinimumScore] = useState('');
  const [maximumScore, setMaximumScore] = useState('');
  const [consistencyIssue, setConsistencyIssue] = useState<ConsistencyFilter>('');
  const [findingSeverity, setFindingSeverity] = useState('');
  const [page, setPage] = useState(1);
  const [selectedResult, setSelectedResult] =
    useState<TranslationSimilarityResult | null>(null);
  const [rerunReason, setRerunReason] = useState('');

  const [sourceLanguage, targetLanguage] = pair
    ? (pair.split('-') as [SupportedLanguageCode, SupportedLanguageCode])
    : [undefined, undefined];
  const resultParams: SimilarityResultListParams = {
    page,
    pageSize: 50,
    ...(search ? { search } : {}),
    ...(sectionId ? { sectionId } : {}),
    ...(category ? { similarityCategory: category } : {}),
    ...(sourceLanguage ? { sourceLanguage } : {}),
    ...(targetLanguage ? { targetLanguage } : {}),
    ...(minimumScore ? { minimumScore: Number(minimumScore) } : {}),
    ...(maximumScore ? { maximumScore: Number(maximumScore) } : {}),
    ...(findingSeverity
      ? {
          findingSeverity: findingSeverity as 'CRITICAL' | 'MAJOR' | 'MINOR' | 'INFO',
        }
      : {}),
    ...(consistencyIssue === 'number' ? { hasNumberMismatch: true } : {}),
    ...(consistencyIssue === 'date' ? { hasDateMismatch: true } : {}),
    ...(consistencyIssue === 'measurement' ? { hasMeasurementMismatch: true } : {}),
    ...(consistencyIssue === 'reference' ? { hasReferenceMismatch: true } : {}),
    ...(consistencyIssue === 'negation' ? { hasNegationMismatch: true } : {}),
  };
  const resultsQuery = useSimilarityResults(runId, resultParams);

  const sections = useMemo<readonly SectionSimilaritySummary[]>(() => {
    const data = sectionsQuery.data;
    if (!data) {
      return [];
    }
    return 'items' in data ? data.items : data;
  }, [sectionsQuery.data]);
  const summary = summaryQuery.data;
  const categoryCount = (key: string): number => summary?.categories[key] ?? 0;
  const mismatchCount = (key: string): number => summary?.mismatches[key] ?? 0;

  const start = async (): Promise<void> => {
    if (!fileId) {
      return;
    }
    try {
      const result = await mutations.start.mutateAsync({
        documentFileId: fileId,
        force: false,
      });
      showToast({
        tone: 'success',
        title: 'Translation similarity queued',
        message: 'The local model worker will process this file.',
      });
      navigate(`/documents/similarity-queue?jobId=${result.id}`);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Similarity could not be queued',
        message: getApiErrorMessage(error, 'Check processing prerequisites.'),
      });
    }
  };

  const rerun = async (): Promise<void> => {
    if (!runId || !rerunReason.trim()) {
      return;
    }
    try {
      const queued = await mutations.rerun.mutateAsync({
        runId,
        payload: { reason: rerunReason.trim() },
      });
      setRerunReason('');
      showToast({
        tone: 'success',
        title: 'Similarity re-analysis queued',
        message: 'The existing result remains available.',
      });
      navigate(`/documents/similarity-queue?jobId=${queued.id}`);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Re-analysis could not be queued',
        message: getApiErrorMessage(error, 'Review the reason and try again.'),
      });
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
        `${runQuery.data?.document?.baseDocumentCode ?? 'document'}_similarity.${format}`,
      );
      showToast({ tone: 'success', title: `${format.toUpperCase()} export ready` });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Similarity export failed',
        message: getApiErrorMessage(error, 'Try again.'),
      });
    }
  };

  const loadingContext =
    (routeDocumentId && documentQuery.isLoading) ||
    (routeDocumentId && filesQuery.isLoading) ||
    latestQuery.isLoading;
  const loadError =
    documentQuery.error ?? filesQuery.error ?? latestQuery.error ?? runQuery.error;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <MasterDataPageHeader
          eyebrow="Compliance"
          title="Translation Similarity"
          description="Local multilingual review signals for Indonesian, English, and Chinese translation groups."
        />
        <div className="flex flex-wrap gap-2">
          {runId &&
            hasPermission('similarity:export') &&
            (['json', 'xlsx'] as const).map((format) => (
              <button
                key={format}
                type="button"
                disabled={mutations.export.isPending}
                onClick={() => void exportRun(format)}
                className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 bg-white px-3.5 text-xs font-semibold uppercase text-slate-700 disabled:opacity-50"
              >
                <Download className="size-4" aria-hidden="true" />
                {format}
              </button>
            ))}
          {fileId && hasPermission('similarity:run') && !runId && (
            <button
              type="button"
              disabled={mutations.start.isPending}
              onClick={() => void start()}
              className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-violet-700 px-4 text-sm font-semibold text-white disabled:opacity-50"
            >
              <Play className="size-4" aria-hidden="true" />
              Run Similarity
            </button>
          )}
        </div>
      </div>

      <p className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-900">
        Similarity is an automated review signal and does not guarantee that both texts
        have identical legal or technical meaning.
      </p>

      {loadingContext && <Phase8Loading label="Loading similarity context" />}
      {loadError && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            loadError,
            'Similarity context could not be loaded.',
          )}
          onRetry={() => {
            void latestQuery.refetch();
            void runQuery.refetch();
          }}
        />
      )}

      {!loadingContext && !loadError && !fileId && (
        <EmptyPanel
          title="Select a processed document file"
          message="Open this workspace from a document revision, or include a fileId query parameter. Extracted and compliance content is required."
        />
      )}
      {!loadingContext && !loadError && fileId && !runId && (
        <EmptyPanel
          title="Translation similarity is not evaluated"
          message="Run the local model after extraction, language detection, and compliance grouping are available."
          action={
            hasPermission('similarity:run') ? (
              <button
                type="button"
                disabled={mutations.start.isPending}
                onClick={() => void start()}
                className="mt-5 inline-flex min-h-10 items-center gap-2 rounded-xl bg-violet-700 px-4 text-sm font-semibold text-white disabled:opacity-50"
              >
                <Play className="size-4" aria-hidden="true" />
                Run Similarity
              </button>
            ) : null
          }
        />
      )}

      {runId && runQuery.data && (
        <>
          <section>
            <div className="flex items-end justify-between">
              <div>
                <h2 className="text-sm font-semibold text-slate-950">
                  Similarity Summary
                </h2>
                <p className="mt-1 text-xs text-slate-500">
                  {runQuery.data.modelName} · completed{' '}
                  {runQuery.data.completedAt
                    ? formatDateTime(runQuery.data.completedAt)
                    : '—'}
                </p>
              </div>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-[10px] font-semibold text-slate-700">
                {runQuery.data.status.replaceAll('_', ' ')}
              </span>
            </div>
            {summaryQuery.isLoading && (
              <Phase8Loading label="Loading similarity summary" />
            )}
            {summaryQuery.error && (
              <Phase8ErrorAlert
                message={getApiErrorMessage(
                  summaryQuery.error,
                  'Similarity summary could not be loaded.',
                )}
              />
            )}
            {summaryQuery.data && (
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
                {(
                  [
                    [
                      'Average Similarity',
                      displayPercent(summaryQuery.data.averageSimilarity),
                    ],
                    [
                      'Minimum Similarity',
                      displayPercent(summaryQuery.data.minimumSimilarity),
                    ],
                    ['Groups Analysed', summaryQuery.data.analysedGroupCount],
                    ['High', categoryCount('HIGH')],
                    ['Acceptable', categoryCount('ACCEPTABLE')],
                    [
                      'Needs Review',
                      categoryCount('NEEDS_REVIEW') +
                        categoryCount('ACCEPTABLE_OR_REVIEW'),
                    ],
                    ['Low', categoryCount('LOW')],
                    ['Not Evaluated', categoryCount('NOT_EVALUATED')],
                  ] as const
                ).map(([label, value]) => (
                  <SummaryCard key={label} label={label} value={String(value)} />
                ))}
              </div>
            )}
          </section>

          <section>
            <h2 className="text-sm font-semibold text-slate-950">
              Language Pair Cards
            </h2>
            <div className="mt-3 grid gap-3 lg:grid-cols-3">
              {(
                [
                  ['id', 'en'],
                  ['id', 'zh'],
                  ['en', 'zh'],
                ] as const
              ).map(([source, target]) => {
                const pairKey = `${source}-${target}`;
                const pairAverage = summary?.pairAverages[pairKey] ?? null;
                return (
                  <article
                    key={`${source}-${target}`}
                    className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
                  >
                    <div className="flex items-center gap-2">
                      <Languages
                        className="size-4 text-violet-700"
                        aria-hidden="true"
                      />
                      <h3 className="text-sm font-semibold text-slate-950">
                        {languageNames[source]} ↔ {languageNames[target]}
                      </h3>
                    </div>
                    <p className="mt-4 text-3xl font-semibold tracking-tight text-slate-950">
                      {displayPercent(pairAverage)}
                    </p>
                    <div className="mt-3 flex gap-3 text-[10px] text-slate-600">
                      <span>{summary?.analysedGroupCount ?? 0} groups</span>
                      <span className="text-rose-700">{categoryCount('LOW')} low</span>
                      <span className="text-amber-700">
                        {categoryCount('NEEDS_REVIEW') +
                          categoryCount('ACCEPTABLE_OR_REVIEW')}{' '}
                        review
                      </span>
                    </div>
                  </article>
                );
              })}
            </div>
          </section>

          <section>
            <h2 className="text-sm font-semibold text-slate-950">Section Summary</h2>
            <div className="mt-3 overflow-x-auto rounded-2xl border border-slate-200 bg-white">
              <table className="min-w-full divide-y divide-slate-200">
                <thead className="bg-slate-50">
                  <tr>
                    {['Section', 'Groups', 'Average', 'Minimum', 'Low', 'Issues'].map(
                      (heading) => (
                        <th
                          key={heading}
                          className="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-500"
                        >
                          {heading}
                        </th>
                      ),
                    )}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {sections.map((section) => (
                    <tr key={section.id}>
                      <td className="px-4 py-3 text-xs font-semibold text-slate-900">
                        {section.canonicalSectionCode || 'Unmapped'}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-600">
                        {section.analysedGroups}/{section.totalGroups}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-700">
                        {displayPercent(section.averageSimilarity)}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-700">
                        {displayPercent(section.minimumSimilarity)}
                      </td>
                      <td className="px-4 py-3 text-xs font-semibold text-rose-700">
                        {section.lowSimilarityGroups}
                      </td>
                      <td className="px-4 py-3 text-xs text-amber-700">
                        {section.numberMismatches +
                          section.dateMismatches +
                          section.measurementMismatches +
                          section.referenceMismatches +
                          section.negationMismatches}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {sections.length === 0 && (
                <p className="p-8 text-center text-sm text-slate-500">
                  No section summary is available.
                </p>
              )}
            </div>
          </section>

          <section className="space-y-4">
            <div>
              <h2 className="text-sm font-semibold text-slate-950">
                Translation Group Results
              </h2>
              <p className="mt-1 text-xs text-slate-500">
                Long text is bounded to snippets in this table. Open a row for full
                permitted detail.
              </p>
            </div>
            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <Phase8FilterField label="Search">
                  <span className="relative block">
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
                      placeholder="Bounded text or source reference"
                      className="min-h-11 w-full rounded-xl border border-slate-300 pl-10 pr-3 text-sm"
                    />
                  </span>
                </Phase8FilterField>
                <FilterSelect
                  label="Language Pair"
                  value={pair}
                  onChange={(value) => {
                    setPair(value);
                    setPage(1);
                  }}
                  options={[
                    ['', 'All language pairs'],
                    ['id-en', 'Indonesian ↔ English'],
                    ['id-zh', 'Indonesian ↔ Chinese'],
                    ['en-zh', 'English ↔ Chinese'],
                  ]}
                />
                <FilterSelect
                  label="Section"
                  value={sectionId}
                  onChange={(value) => {
                    setSectionId(value);
                    setPage(1);
                  }}
                  options={[
                    ['', 'All sections'],
                    ...sections.map(
                      (section) =>
                        [
                          section.detectedSectionId ?? section.id,
                          section.sectionName ??
                            section.canonicalSectionCode ??
                            'Unmapped',
                        ] as const,
                    ),
                  ]}
                />
                <FilterSelect
                  label="Similarity Category"
                  value={category}
                  onChange={(value) => {
                    setCategory(value as SimilarityCategory | '');
                    setPage(1);
                  }}
                  options={[
                    ['', 'All categories'],
                    ...similarityCategories.map(
                      (candidate) =>
                        [candidate, candidate.replaceAll('_', ' ')] as const,
                    ),
                  ]}
                />
                <Phase8FilterField label="Minimum Score">
                  <input
                    type="number"
                    min="0"
                    max="1"
                    step="0.01"
                    value={minimumScore}
                    onChange={(event) => {
                      setMinimumScore(event.target.value);
                      setPage(1);
                    }}
                    className="min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
                  />
                </Phase8FilterField>
                <Phase8FilterField label="Maximum Score">
                  <input
                    type="number"
                    min="0"
                    max="1"
                    step="0.01"
                    value={maximumScore}
                    onChange={(event) => {
                      setMaximumScore(event.target.value);
                      setPage(1);
                    }}
                    className="min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
                  />
                </Phase8FilterField>
                <FilterSelect
                  label="Consistency Issue"
                  value={consistencyIssue}
                  onChange={(value) => {
                    setConsistencyIssue(value as ConsistencyFilter);
                    setPage(1);
                  }}
                  options={[
                    ['', 'All results'],
                    ['number', 'Number mismatch'],
                    ['date', 'Date mismatch'],
                    ['measurement', 'Measurement mismatch'],
                    ['reference', 'Reference mismatch'],
                    ['negation', 'Negation review signal'],
                  ]}
                />
                <FilterSelect
                  label="Finding Severity"
                  value={findingSeverity}
                  onChange={(value) => {
                    setFindingSeverity(value);
                    setPage(1);
                  }}
                  options={[
                    ['', 'All severities'],
                    ['CRITICAL', 'Critical'],
                    ['MAJOR', 'Major'],
                    ['MINOR', 'Minor'],
                    ['INFO', 'Info'],
                  ]}
                />
              </div>
            </div>

            {resultsQuery.isLoading && (
              <Phase8Loading label="Loading similarity results" />
            )}
            {resultsQuery.error && (
              <Phase8ErrorAlert
                message={getApiErrorMessage(
                  resultsQuery.error,
                  'Similarity results could not be loaded.',
                )}
                onRetry={() => void resultsQuery.refetch()}
              />
            )}
            {resultsQuery.data && (
              <>
                <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
                  <div className="overflow-x-auto">
                    <table className="min-w-[154rem] divide-y divide-slate-200">
                      <thead className="bg-slate-50">
                        <tr>
                          {[
                            'Section',
                            'Group',
                            'Source Language',
                            'Target Language',
                            'Source Text',
                            'Target Text',
                            'Similarity',
                            'Confidence',
                            'Length Ratio',
                            'Numbers',
                            'Dates',
                            'Measurements',
                            'References',
                            'Negation',
                            'Findings',
                            'Detail',
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
                        {resultsQuery.data.items.map((result) => (
                          <tr key={result.id} className="align-top hover:bg-slate-50">
                            <td className="max-w-44 px-4 py-3 text-xs text-slate-700">
                              {result.sectionCode ?? result.sectionName ?? 'Unmapped'}
                            </td>
                            <td className="max-w-40 px-4 py-3 text-xs text-slate-600">
                              {result.groupLabel ??
                                result.translationGroupId ??
                                'Ungrouped'}
                            </td>
                            <td className="px-4 py-3 text-xs text-slate-600">
                              {
                                languageNames[
                                  result.sourceLanguage ?? result.sourceLanguageCode
                                ]
                              }
                            </td>
                            <td className="px-4 py-3 text-xs text-slate-600">
                              {
                                languageNames[
                                  result.targetLanguage ?? result.targetLanguageCode
                                ]
                              }
                            </td>
                            <td className="max-w-72 px-4 py-3 text-xs leading-5 text-slate-700">
                              {boundedSnippet(result.sourceTextSnippet)}
                            </td>
                            <td className="max-w-72 px-4 py-3 text-xs leading-5 text-slate-700">
                              {boundedSnippet(result.targetTextSnippet)}
                            </td>
                            <td className="px-4 py-3">
                              <div className="space-y-1">
                                <span className="text-xs font-semibold text-slate-900">
                                  {displayPercent(result.similarityScore)}
                                </span>
                                <SimilarityCategoryBadge
                                  category={result.similarityCategory}
                                />
                              </div>
                            </td>
                            <td className="px-4 py-3 text-xs text-slate-700">
                              {displayPercent(
                                result.confidenceScore ?? result.confidence,
                              )}
                            </td>
                            <td className="px-4 py-3 text-xs text-slate-700">
                              {result.lengthRatio?.toFixed(2) ?? '—'}
                            </td>
                            {(
                              [
                                [
                                  'Numbers',
                                  result.numberStatus ?? result.numberConsistencyStatus,
                                ],
                                [
                                  'Dates',
                                  result.dateStatus ?? result.dateConsistencyStatus,
                                ],
                                [
                                  'Measurements',
                                  result.measurementStatus ??
                                    result.measurementConsistencyStatus,
                                ],
                                [
                                  'References',
                                  result.referenceStatus ??
                                    result.referenceConsistencyStatus,
                                ],
                                [
                                  'Negation',
                                  result.negationStatus ??
                                    result.negationConsistencyStatus,
                                ],
                              ] as const
                            ).map(([label, status]) => (
                              <td key={label} className="px-4 py-3">
                                <ConsistencyBadge label={label} status={status} />
                              </td>
                            ))}
                            <td className="px-4 py-3 text-xs font-semibold text-rose-700">
                              {result.findingCount ??
                                (typeof result.metrics.findingCount === 'number'
                                  ? result.metrics.findingCount
                                  : 0)}
                            </td>
                            <td className="px-4 py-3">
                              <button
                                type="button"
                                onClick={() => setSelectedResult(result)}
                                className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-violet-700 hover:bg-violet-50"
                              >
                                <Eye className="size-3.5" aria-hidden="true" />
                                Open
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {resultsQuery.data.items.length === 0 && (
                    <p className="p-10 text-center text-sm text-slate-500">
                      No translation groups match these filters.
                    </p>
                  )}
                </div>
                <Phase8Pagination
                  page={page}
                  pageSize={50}
                  totalItems={resultsQuery.data.totalItems}
                  totalPages={resultsQuery.data.totalPages}
                  label="translation groups"
                  onPageChange={setPage}
                />
              </>
            )}
          </section>

          <section className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-sm font-semibold text-slate-950">
                Consistency Issues
              </h2>
              <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
                {[
                  ['Number mismatches', mismatchCount('number')],
                  ['Date mismatches', mismatchCount('date')],
                  ['Measurement mismatches', mismatchCount('measurement')],
                  ['Reference mismatches', mismatchCount('reference')],
                  ['Negation review signals', mismatchCount('negation')],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-xl bg-slate-50 p-3">
                    <dt className="text-slate-500">{label}</dt>
                    <dd className="mt-1 text-lg font-semibold text-slate-950">
                      {value}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-sm font-semibold text-slate-950">Findings</h2>
              <p className="mt-3 text-3xl font-semibold text-slate-950">
                {summaryQuery.data?.findingCount ?? 0}
              </p>
              <p className="mt-2 text-xs leading-5 text-slate-600">
                Similarity and consistency findings use the existing review workflow.
                Missing primary language is not duplicated as a low-similarity finding.
              </p>
              <Link
                to={runId ? `/compliance/findings?similarityRunId=${runId}` : '#'}
                className="mt-4 inline-flex text-xs font-semibold text-blue-700"
              >
                Open related findings
              </Link>
            </div>
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h2 className="text-sm font-semibold text-slate-950">History</h2>
                <p className="mt-1 text-xs text-slate-500">
                  Historical runs are retained when analysis is repeated.
                </p>
              </div>
              {hasPermission('similarity:rerun') && (
                <div className="flex max-w-xl flex-1 gap-2">
                  <input
                    value={rerunReason}
                    onChange={(event) => setRerunReason(event.target.value)}
                    placeholder="Required re-run reason"
                    aria-label="Re-run reason"
                    className="min-h-10 min-w-0 flex-1 rounded-xl border border-slate-300 px-3 text-sm"
                  />
                  <button
                    type="button"
                    disabled={!rerunReason.trim() || mutations.rerun.isPending}
                    onClick={() => void rerun()}
                    className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-violet-700 px-4 text-xs font-semibold text-white disabled:opacity-50"
                  >
                    <RefreshCw className="size-3.5" aria-hidden="true" />
                    Re-run
                  </button>
                </div>
              )}
            </div>
            <div className="mt-4 divide-y divide-slate-100">
              {(historyQuery.data?.items ?? []).map((historyRun) => (
                <Link
                  key={historyRun.id}
                  to={`?fileId=${fileId ?? ''}&runId=${historyRun.id}`}
                  className="flex flex-wrap items-center justify-between gap-3 py-3 text-xs hover:bg-slate-50"
                >
                  <span className="font-semibold text-slate-900">
                    {historyRun.modelName}
                  </span>
                  <span>{displayPercent(historyRun.averageSimilarity)}</span>
                  <span>{historyRun.lowSimilarityGroups} low groups</span>
                  <span className="text-slate-500">
                    {historyRun.completedAt
                      ? formatDateTime(historyRun.completedAt)
                      : historyRun.status}
                  </span>
                </Link>
              ))}
              {historyQuery.data?.items.length === 0 && (
                <p className="py-8 text-center text-sm text-slate-500">
                  No earlier similarity runs.
                </p>
              )}
            </div>
          </section>
        </>
      )}

      <SimilarityDetailDialog
        open={selectedResult !== null}
        result={selectedResult}
        {...(routeDocumentId ? { documentId: routeDocumentId } : {})}
        {...(effectiveRevisionId ? { revisionId: effectiveRevisionId } : {})}
        onClose={() => setSelectedResult(null)}
      />
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
        {label}
      </p>
      <p className="mt-2 text-xl font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function EmptyPanel({
  action,
  message,
  title,
}: {
  title: string;
  message: string;
  action?: React.ReactNode;
}) {
  return (
    <section className="rounded-3xl border border-dashed border-slate-300 bg-white p-10 text-center">
      <Languages className="mx-auto size-8 text-slate-400" aria-hidden="true" />
      <h2 className="mt-4 text-lg font-semibold text-slate-950">{title}</h2>
      <p className="mx-auto mt-2 max-w-2xl text-sm leading-6 text-slate-600">
        {message}
      </p>
      {action}
    </section>
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
