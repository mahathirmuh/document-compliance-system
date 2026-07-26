import { Download, Play, RefreshCw, Search } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import {
  Phase8ErrorAlert,
  Phase8Loading,
  Phase8Pagination,
} from '../../components/compliance/Phase8TableUtilities';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { useDocument } from '../../hooks/useDocument';
import { useRevisionFiles } from '../../hooks/useDocumentFiles';
import {
  useGlossaryHistory,
  useGlossaryMatches,
  useGlossaryValidationFindings,
  useGlossaryValidationJob,
  useGlossaryValidationMutations,
  useGlossaryValidationRun,
  useGlossaryValidationSummary,
  useLatestGlossaryValidation,
} from '../../hooks/useGlossaryValidation';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type { GlossaryMatch } from '../../types/glossaryValidation';
import { downloadFile } from '../../utils/downloadFile';
import { formatDateTime } from '../../utils/formatters';

type GlossaryComplianceTab =
  'summary' | 'matches' | 'violations' | 'exceptions' | 'history';

export function GlossaryCompliancePage() {
  const { documentId: routeDocumentId, revisionId: routeRevisionId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const documentQuery = useDocument(routeDocumentId ?? null);
  const revisionId = routeRevisionId ?? documentQuery.data?.currentRevision?.id ?? null;
  const filesQuery = useRevisionFiles(routeDocumentId ?? null, revisionId);
  const currentFile =
    (filesQuery.data ?? []).find(
      (file) => file.isCurrent && file.fileStatus === 'AVAILABLE',
    ) ?? null;
  const fileId = searchParams.get('fileId') ?? currentFile?.id ?? null;
  const requestedRunId = searchParams.get('runId');
  const latestQuery = useLatestGlossaryValidation(fileId);
  const [queuedJobId, setQueuedJobId] = useState<string | null>(
    searchParams.get('jobId'),
  );
  const jobQuery = useGlossaryValidationJob(queuedJobId);
  const completedJobRunId =
    jobQuery.data?.status === 'COMPLETED' ||
    jobQuery.data?.status === 'PARTIALLY_COMPLETED'
      ? jobQuery.data.id
      : null;
  const runId = requestedRunId ?? completedJobRunId ?? latestQuery.data?.id ?? null;
  const runQuery = useGlossaryValidationRun(runId);
  const summaryQuery = useGlossaryValidationSummary(runId);
  const [tab, setTab] = useState<GlossaryComplianceTab>('summary');
  const [searchInput, setSearchInput] = useState('');
  const search = useDebouncedValue(searchInput.trim(), 350);
  const [page, setPage] = useState(1);
  const matchesQuery = useGlossaryMatches(runId, {
    page,
    pageSize: 50,
    ...(search ? { search } : {}),
  });
  const findingsQuery = useGlossaryValidationFindings(runId, {
    page: 1,
    pageSize: 100,
  });
  const historyQuery = useGlossaryHistory(fileId, { page: 1, pageSize: 20 });
  const mutations = useGlossaryValidationMutations();
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const { showToast } = useToast();
  const [rerunReason, setRerunReason] = useState('');
  const visibleMatches = filterMatches(matchesQuery.data?.items ?? [], search);

  useEffect(() => {
    if (completedJobRunId && fileId) {
      navigate(`?fileId=${fileId}&runId=${completedJobRunId}`, { replace: true });
    }
  }, [completedJobRunId, fileId, navigate]);

  const startValidation = async (): Promise<void> => {
    if (!fileId) {
      return;
    }
    try {
      const job = await mutations.start.mutateAsync({
        documentFileId: fileId,
        force: false,
      });
      setQueuedJobId(job.jobId);
      showToast({
        tone: 'success',
        title: 'Glossary validation queued',
        message:
          'Applicable profiles will be resolved by department and document type.',
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Glossary validation could not be queued',
        message: getApiErrorMessage(error, 'Check extraction and compliance context.'),
      });
    }
  };

  const revalidate = async (): Promise<void> => {
    if (!runId || !rerunReason.trim()) {
      return;
    }
    try {
      const job = await mutations.revalidate.mutateAsync({
        runId,
        reason: rerunReason.trim(),
      });
      setQueuedJobId(job.jobId);
      setRerunReason('');
      showToast({ tone: 'success', title: 'Glossary revalidation queued' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Glossary revalidation failed',
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
      downloadFile(result, `glossary_validation.${format}`);
      showToast({
        tone: 'success',
        title: `Glossary ${format.toUpperCase()} ready`,
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Glossary validation export failed',
        message: getApiErrorMessage(error, 'Try again.'),
      });
    }
  };

  const contextError =
    documentQuery.error ?? filesQuery.error ?? latestQuery.error ?? runQuery.error;
  const isContextLoading =
    (routeDocumentId && documentQuery.isLoading) ||
    (routeDocumentId && filesQuery.isLoading) ||
    latestQuery.isLoading;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <MasterDataPageHeader
          eyebrow="Compliance"
          title="Glossary Compliance"
          description="Validate preferred, forbidden, required, and consistent terminology against scoped multilingual glossary profiles."
        />
        <div className="flex flex-wrap gap-2">
          {runId &&
            hasPermission('glossary:export') &&
            (['json', 'xlsx'] as const).map((format) => (
              <button
                key={format}
                type="button"
                onClick={() => void exportRun(format)}
                disabled={mutations.export.isPending}
                className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 px-3 text-xs font-semibold uppercase text-slate-700 disabled:opacity-50"
              >
                <Download className="size-4" aria-hidden="true" />
                {format}
              </button>
            ))}
          {fileId && hasPermission('glossary:validate') && !runId && (
            <button
              type="button"
              onClick={() => void startValidation()}
              disabled={mutations.start.isPending}
              className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-emerald-700 px-4 text-sm font-semibold text-white disabled:opacity-50"
            >
              <Play className="size-4" aria-hidden="true" />
              Validate Glossary
            </button>
          )}
        </div>
      </div>

      {queuedJobId && jobQuery.data && !completedJobRunId && (
        <section className="rounded-2xl border border-blue-200 bg-blue-50 p-5">
          <div className="flex items-center justify-between text-xs font-semibold text-blue-900">
            <span>{jobQuery.data.currentStage?.replaceAll('_', ' ') ?? 'Queued'}</span>
            <span>{jobQuery.data.progress}%</span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-blue-100">
            <span
              className="block h-full bg-blue-700 transition-[width]"
              style={{
                width: `${Math.max(0, Math.min(100, jobQuery.data.progress))}%`,
              }}
            />
          </div>
          <p className="mt-2 text-xs text-blue-800">
            Status: {jobQuery.data.status.replaceAll('_', ' ')} · refreshes every three
            seconds
          </p>
          {jobQuery.data.errorMessage && (
            <p role="alert" className="mt-2 text-xs text-rose-800">
              {jobQuery.data.errorMessage}
            </p>
          )}
        </section>
      )}

      {isContextLoading && <Phase8Loading label="Loading glossary compliance" />}
      {contextError && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            contextError,
            'Glossary validation context could not be loaded.',
          )}
        />
      )}
      {!isContextLoading && !contextError && !fileId && (
        <EmptyPanel
          title="Select a processed document file"
          message="Open glossary compliance from a document revision or provide an authorized fileId."
        />
      )}
      {!isContextLoading && !contextError && fileId && !runId && !queuedJobId && (
        <EmptyPanel
          title="Glossary is not validated"
          message="Validation uses extracted and compliance-grouped content; the source binary is never modified."
        />
      )}

      {runId && runQuery.data && (
        <>
          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
            {[
              ['Terms Evaluated', summaryQuery.data?.totalTerms ?? '—'],
              ['Preferred Matches', summaryQuery.data?.preferredTermMatches ?? '—'],
              ['Forbidden Matches', summaryQuery.data?.forbiddenTermMatches ?? '—'],
              [
                'Missing Translations',
                summaryQuery.data?.missingRequiredTranslations ?? '—',
              ],
              ['Inconsistent Terms', summaryQuery.data?.inconsistentTerms ?? '—'],
              ['Exceptions Applied', summaryQuery.data?.exceptionAppliedCount ?? '—'],
              ['Findings', summaryQuery.data?.totalFindings ?? '—'],
            ].map(([label, value]) => (
              <div
                key={label}
                className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
              >
                <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                  {label}
                </p>
                <p className="mt-2 text-xl font-semibold text-slate-950">{value}</p>
              </div>
            ))}
          </section>

          <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
            <div className="flex overflow-x-auto border-b border-slate-200 px-3">
              {(
                [
                  ['summary', 'Summary'],
                  ['matches', 'Matches'],
                  ['violations', 'Violations'],
                  ['exceptions', 'Exceptions'],
                  ['history', 'History'],
                ] as const
              ).map(([candidate, label]) => (
                <button
                  key={candidate}
                  type="button"
                  onClick={() => {
                    setTab(candidate);
                    setPage(1);
                  }}
                  className={`min-h-12 border-b-2 px-4 text-xs font-semibold ${
                    tab === candidate
                      ? 'border-emerald-700 text-emerald-700'
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
                  <div>
                    <h2 className="text-sm font-semibold text-slate-950">
                      Resolved Profiles
                    </h2>
                    <ul className="mt-3 space-y-2">
                      {runQuery.data.profileSnapshots.map((profile, index) => (
                        <li
                          key={String(profile.id ?? index)}
                          className="rounded-xl bg-slate-50 px-4 py-3 text-xs text-slate-700"
                        >
                          <span className="font-semibold">
                            {String(profile.code ?? 'Profile')}
                          </span>{' '}
                          — {String(profile.name ?? profile.id ?? 'Resolved profile')}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <h2 className="text-sm font-semibold text-slate-950">
                      Run Information
                    </h2>
                    <dl className="mt-3 space-y-2 text-xs">
                      <InfoRow label="Status" value={runQuery.data.status} />
                      <InfoRow
                        label="Completed"
                        value={
                          runQuery.data.completedAt
                            ? formatDateTime(runQuery.data.completedAt)
                            : '—'
                        }
                      />
                      <InfoRow
                        label="Findings"
                        value={String(runQuery.data.totalFindings)}
                      />
                    </dl>
                    {hasPermission('glossary:validate') && (
                      <div className="mt-4 flex gap-2">
                        <input
                          aria-label="Glossary revalidation reason"
                          value={rerunReason}
                          onChange={(event) => setRerunReason(event.target.value)}
                          placeholder="Required revalidation reason"
                          className="min-h-10 min-w-0 flex-1 rounded-xl border border-slate-300 px-3 text-xs"
                        />
                        <button
                          type="button"
                          onClick={() => void revalidate()}
                          disabled={
                            !rerunReason.trim() || mutations.revalidate.isPending
                          }
                          className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-emerald-700 px-4 text-xs font-semibold text-white disabled:opacity-50"
                        >
                          <RefreshCw className="size-3.5" aria-hidden="true" />
                          Revalidate
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )}
              {tab === 'matches' && (
                <MatchesView
                  matches={visibleMatches}
                  searchInput={searchInput}
                  onSearch={setSearchInput}
                />
              )}
              {tab === 'violations' && (
                <div className="overflow-x-auto">
                  <table className="min-w-[65rem] divide-y divide-slate-200">
                    <thead className="bg-slate-50">
                      <tr>
                        {[
                          'Finding Code',
                          'Severity',
                          'Status',
                          'Title',
                          'Section',
                          'Language',
                          'Location',
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
                      {(findingsQuery.data?.items ?? []).map((finding) => (
                        <tr key={finding.id}>
                          <DataCell strong>{finding.findingCode}</DataCell>
                          <DataCell>{finding.severity}</DataCell>
                          <DataCell>{finding.status}</DataCell>
                          <DataCell>{finding.title}</DataCell>
                          <DataCell>—</DataCell>
                          <DataCell>
                            {finding.languageCode?.toUpperCase() ?? '—'}
                          </DataCell>
                          <DataCell>{finding.sourceReference ?? '—'}</DataCell>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {(findingsQuery.data?.items.length ?? 0) === 0 && (
                    <p className="p-8 text-center text-sm text-slate-500">
                      No glossary violations were returned.
                    </p>
                  )}
                </div>
              )}
              {tab === 'exceptions' && (
                <MatchesTable
                  matches={(matchesQuery.data?.items ?? []).filter(
                    (match) =>
                      match.exceptionId !== null &&
                      filterMatches([match], search).length > 0,
                  )}
                />
              )}
              {tab === 'history' && (
                <div className="divide-y divide-slate-100">
                  {(historyQuery.data?.items ?? []).map((historyRun) => (
                    <Link
                      key={historyRun.id}
                      to={`?fileId=${fileId ?? ''}&runId=${historyRun.id}`}
                      className="flex flex-wrap items-center justify-between gap-3 py-3 text-xs hover:bg-slate-50"
                    >
                      <span className="font-semibold text-slate-900">
                        {historyRun.status.replaceAll('_', ' ')}
                      </span>
                      <span>{historyRun.matchedTerms} matched terms</span>
                      <span className="text-rose-700">
                        {historyRun.totalFindings} findings
                      </span>
                      <span className="text-slate-500">
                        {historyRun.completedAt
                          ? formatDateTime(historyRun.completedAt)
                          : '—'}
                      </span>
                    </Link>
                  ))}
                  {(historyQuery.data?.items.length ?? 0) === 0 && (
                    <p className="py-8 text-center text-sm text-slate-500">
                      No previous glossary validation runs.
                    </p>
                  )}
                </div>
              )}
            </div>
          </section>
          {tab === 'matches' && matchesQuery.data && (
            <Phase8Pagination
              page={page}
              pageSize={50}
              totalItems={matchesQuery.data.totalItems}
              totalPages={matchesQuery.data.totalPages}
              label="glossary matches"
              onPageChange={setPage}
            />
          )}
        </>
      )}
    </div>
  );
}

function MatchesView({
  matches,
  onSearch,
  searchInput,
}: {
  matches: readonly GlossaryMatch[];
  searchInput: string;
  onSearch: (value: string) => void;
}) {
  return (
    <div className="space-y-4">
      <label className="relative block max-w-lg">
        <Search
          className="pointer-events-none absolute left-3 top-3.5 size-4 text-slate-400"
          aria-hidden="true"
        />
        <input
          aria-label="Search glossary matches"
          value={searchInput}
          onChange={(event) => onSearch(event.target.value)}
          placeholder="Search concept, term, or bounded context"
          className="min-h-11 w-full rounded-xl border border-slate-300 pl-10 pr-3 text-sm"
        />
      </label>
      <MatchesTable matches={matches} />
    </div>
  );
}

function MatchesTable({ matches }: { matches: readonly GlossaryMatch[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-[82rem] divide-y divide-slate-200">
        <thead className="bg-slate-50">
          <tr>
            {[
              'Concept',
              'Matched Text',
              'Language',
              'Match Type',
              'Preferred',
              'Forbidden',
              'Exception',
              'Section',
              'Location',
              'Context Snippet',
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
          {matches.map((match) => (
            <tr key={match.id} className="align-top">
              <DataCell strong>{match.conceptName ?? match.termCode ?? '—'}</DataCell>
              <DataCell>{match.matchedText}</DataCell>
              <DataCell>{match.languageCode.toUpperCase()}</DataCell>
              <DataCell>{match.matchType}</DataCell>
              <DataCell>{match.isPreferred ? 'Yes' : 'No'}</DataCell>
              <DataCell>{match.isForbidden ? 'Yes' : 'No'}</DataCell>
              <DataCell>{match.exceptionId ? 'Applied' : 'None'}</DataCell>
              <DataCell>{match.sectionName ?? '—'}</DataCell>
              <DataCell>{match.sourceReference ?? '—'}</DataCell>
              <DataCell>{bounded(match.contextSnippet ?? match.matchedText)}</DataCell>
            </tr>
          ))}
        </tbody>
      </table>
      {matches.length === 0 && (
        <p className="p-8 text-center text-sm text-slate-500">
          No glossary matches were returned.
        </p>
      )}
    </div>
  );
}

const bounded = (value: string, maximum = 240): string =>
  value.length > maximum ? `${value.slice(0, maximum).trimEnd()}…` : value;

const filterMatches = (
  matches: readonly GlossaryMatch[],
  search: string,
): readonly GlossaryMatch[] => {
  if (!search) {
    return matches;
  }
  const needle = search.toLocaleLowerCase();
  return matches.filter((match) =>
    [match.conceptName, match.termCode, match.matchedText, match.sourceReference].some(
      (value) => value?.toLocaleLowerCase().includes(needle),
    ),
  );
};

function DataCell({
  children,
  strong = false,
}: {
  children: React.ReactNode;
  strong?: boolean;
}) {
  return (
    <td
      className={`max-w-72 px-4 py-3 text-xs ${
        strong ? 'font-semibold text-slate-900' : 'text-slate-600'
      }`}
    >
      {children}
    </td>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 rounded-xl bg-slate-50 px-4 py-3">
      <dt className="text-slate-500">{label}</dt>
      <dd className="font-semibold text-slate-900">{value}</dd>
    </div>
  );
}

function EmptyPanel({ message, title }: { title: string; message: string }) {
  return (
    <section className="rounded-3xl border border-dashed border-slate-300 bg-white p-10 text-center">
      <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
      <p className="mx-auto mt-2 max-w-2xl text-sm leading-6 text-slate-600">
        {message}
      </p>
    </section>
  );
}
