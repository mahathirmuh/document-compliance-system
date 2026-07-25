import { Download, Eye, Languages, RefreshCw, Search } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import { ExtractionStatusBadge } from '../../components/documents/ExtractionStatusBadge';
import {
  getPresenceClass,
  presenceLabels,
} from '../../components/documents/languageDisplay';
import { LanguageProgress } from '../../components/documents/LanguageProgress';
import { OCRStatusBadge } from '../../components/documents/OCRStatusBadge';
import { RedetectLanguageDialog } from '../../components/documents/RedetectLanguageDialog';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { useDocumentFormOptions } from '../../hooks/useDocumentFormOptions';
import {
  useLanguageDetectionJob,
  useLanguageDetectionMutations,
} from '../../hooks/useLanguageDetection';
import { useLanguageDetectionDocuments } from '../../hooks/useLanguageDetectionDocuments';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import {
  languageDetectionJobStatuses,
  type LanguageDetectionDocumentListItem,
  type LanguageDetectionDocumentStatus,
  type LanguagePresenceStatus,
} from '../../types/languageDetection';
import { downloadFile } from '../../utils/downloadFile';
import { formatDateTime } from '../../utils/formatters';

const documentStatuses: readonly LanguageDetectionDocumentStatus[] = [
  'NOT_STARTED',
  ...languageDetectionJobStatuses,
];

export function LanguageDetectionPage() {
  const user = useAuthStore((state) => state.user);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const departmentLocked = !hasPermission('documents:view_all_departments');
  const [searchInput, setSearchInput] = useState('');
  const search = useDebouncedValue(searchInput.trim(), 400);
  const [departmentId, setDepartmentId] = useState(
    departmentLocked ? (user?.departmentId ?? '') : '',
  );
  const [status, setStatus] = useState<LanguageDetectionDocumentStatus | ''>('');
  const [page, setPage] = useState(1);
  const [trackedJobId, setTrackedJobId] = useState<string | null>(null);
  const [redetectTarget, setRedetectTarget] =
    useState<LanguageDetectionDocumentListItem | null>(null);
  const optionsQuery = useDocumentFormOptions();
  const documentsQuery = useLanguageDetectionDocuments(
    {
      page,
      pageSize: 20,
      sortBy: 'documentCode',
      sortOrder: 'asc',
      ...(search ? { search } : {}),
      ...(departmentId ? { departmentId } : {}),
      ...(status ? { status } : {}),
    },
    { pollActive: true },
  );
  const mutations = useLanguageDetectionMutations();
  useLanguageDetectionJob(trackedJobId, { poll: true });
  const { showToast } = useToast();

  const detect = async (item: LanguageDetectionDocumentListItem): Promise<void> => {
    if (!item.extractionRunId || !item.sourceReady) {
      return;
    }
    try {
      const queued = await mutations.start.mutateAsync({
        documentFileId: item.file.id,
        extractionRunId: item.extractionRunId,
        ocrRunId: item.ocrRunId,
        force: false,
      });
      setTrackedJobId(queued.jobId);
      showToast({
        tone: 'success',
        title: 'Language detection queued',
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Language detection could not be queued',
        message: getApiErrorMessage(error, 'The current source may have changed.'),
      });
    }
  };

  const redetect = async (reason: string): Promise<void> => {
    if (!redetectTarget?.languageDetectionRunId) {
      return;
    }
    try {
      const queued = await mutations.redetect.mutateAsync({
        runId: redetectTarget.languageDetectionRunId,
        payload: { reason },
      });
      setTrackedJobId(queued.jobId);
      setRedetectTarget(null);
      showToast({
        tone: 'success',
        title: 'Language re-detection queued',
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Language re-detection could not be queued',
        message: getApiErrorMessage(error, 'The current source may have changed.'),
      });
    }
  };

  const exportRun = async (
    item: LanguageDetectionDocumentListItem,
    format: 'json' | 'xlsx',
  ): Promise<void> => {
    if (!item.languageDetectionRunId) {
      return;
    }
    try {
      const result = await mutations.export.mutateAsync({
        runId: item.languageDetectionRunId,
        format,
      });
      downloadFile(
        result,
        `${item.document.baseDocumentCode}_${item.revision.revisionCode}_languages.${format}`,
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

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Documents"
        title="Language Detection"
        description="Review every current document file and its preliminary Indonesian, English, and Chinese language evidence."
      />
      <section className="rounded-3xl border border-blue-200 bg-blue-50 p-4 text-xs leading-5 text-blue-800">
        Coverage shown here is preliminary language detection and does not represent
        translation equivalence or final compliance. Detection becomes available when a
        current extraction or OCR text source is ready.
      </section>
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
                onChange={(event) => {
                  setSearchInput(event.target.value);
                  setPage(1);
                }}
                placeholder="Document code, title, revision, or filename"
                className="min-h-11 w-full rounded-xl border border-slate-300 pl-10 pr-3 text-sm outline-none focus:border-violet-600"
              />
            </span>
          </label>
          <label className="text-xs font-semibold text-slate-700">
            Department
            <select
              aria-label="Department"
              value={departmentId}
              disabled={departmentLocked}
              onChange={(event) => {
                setDepartmentId(event.target.value);
                setPage(1);
              }}
              className="mt-1.5 min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm disabled:bg-slate-100"
            >
              {!departmentLocked && <option value="">All departments</option>}
              {(optionsQuery.data?.departments ?? []).map((department) => (
                <option key={department.id} value={department.id}>
                  {department.code} · {department.name}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs font-semibold text-slate-700">
            Language Detection Status
            <select
              aria-label="Language Detection Status"
              value={status}
              onChange={(event) => {
                setStatus(event.target.value as LanguageDetectionDocumentStatus | '');
                setPage(1);
              }}
              className="mt-1.5 min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
            >
              <option value="">All statuses</option>
              {documentStatuses.map((value) => (
                <option key={value} value={value}>
                  {formatStatus(value)}
                </option>
              ))}
            </select>
          </label>
        </div>
        {departmentLocked && (
          <p className="mt-3 text-[11px] text-slate-500">
            Documents and actions are locked to your department.
          </p>
        )}
      </section>

      {documentsQuery.isLoading && (
        <div
          aria-label="Loading language detection documents"
          className="h-72 animate-pulse rounded-3xl bg-slate-100"
        />
      )}
      {documentsQuery.error && (
        <p
          role="alert"
          className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700"
        >
          {getApiErrorMessage(
            documentsQuery.error,
            'Language-detection documents could not be loaded.',
          )}
        </p>
      )}
      {documentsQuery.data && (
        <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="min-w-[1300px] divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  {[
                    'Document Code',
                    'Revision',
                    'Filename',
                    'Extraction Status',
                    'OCR Status',
                    'Language Detection Status',
                    'Indonesian',
                    'English',
                    'Chinese',
                    'Last Detected',
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
                {documentsQuery.data.items.map((item) => (
                  <tr key={item.file.id} className="align-top hover:bg-slate-50">
                    <td className="px-4 py-4 text-xs font-semibold text-slate-800">
                      {item.document.baseDocumentCode}
                    </td>
                    <td className="whitespace-nowrap px-4 py-4 text-xs text-slate-700">
                      {item.revision.revisionCode}
                    </td>
                    <td className="max-w-52 break-all px-4 py-4 text-xs text-slate-700">
                      {item.file.filename}
                    </td>
                    <td className="whitespace-nowrap px-4 py-4">
                      {item.extractionStatus ? (
                        <ExtractionStatusBadge status={item.extractionStatus} />
                      ) : (
                        <EmptyStatus>Not Started</EmptyStatus>
                      )}
                    </td>
                    <td className="whitespace-nowrap px-4 py-4">
                      {item.ocrStatus ? (
                        <OCRStatusBadge status={item.ocrStatus} />
                      ) : (
                        <EmptyStatus>
                          {item.file.extension === 'pdf'
                            ? 'Not Started'
                            : 'Not Applicable'}
                        </EmptyStatus>
                      )}
                    </td>
                    <td className="min-w-52 px-4 py-4">
                      {item.languageDetectionStatus ? (
                        <LanguageProgress
                          status={item.languageDetectionStatus}
                          progress={item.languageProgress ?? 0}
                          currentStage={item.languageCurrentStage}
                        />
                      ) : (
                        <EmptyStatus>Not Detected</EmptyStatus>
                      )}
                    </td>
                    {(['id', 'en', 'zh'] as const).map((code) => (
                      <td key={code} className="whitespace-nowrap px-4 py-4">
                        <Presence value={item.languagePresence?.[code] ?? null} />
                      </td>
                    ))}
                    <td className="whitespace-nowrap px-4 py-4 text-xs text-slate-600">
                      {item.lastDetected ? formatDateTime(item.lastDetected) : '—'}
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex min-w-56 flex-wrap gap-1">
                        {!item.languageDetectionRunId &&
                          item.sourceReady &&
                          hasPermission('documents:detect_language') && (
                            <button
                              type="button"
                              onClick={() => void detect(item)}
                              disabled={mutations.start.isPending}
                              className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-violet-700 hover:bg-violet-50 disabled:opacity-50"
                            >
                              <Languages className="size-3.5" aria-hidden="true" />
                              Detect Languages
                            </button>
                          )}
                        {item.languageDetectionRunId &&
                          hasPermission('documents:view_language_results') && (
                            <Link
                              to={`/documents/${item.document.id}/revisions/${item.revision.id}/language-results?runId=${item.languageDetectionRunId}`}
                              className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-violet-700 hover:bg-violet-50"
                            >
                              <Eye className="size-3.5" aria-hidden="true" />
                              View Results
                            </Link>
                          )}
                        {item.languageDetectionRunId &&
                          item.sourceReady &&
                          hasPermission('documents:redetect_language') && (
                            <button
                              type="button"
                              onClick={() => setRedetectTarget(item)}
                              className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-blue-700 hover:bg-blue-50"
                            >
                              <RefreshCw className="size-3.5" aria-hidden="true" />
                              Re-detect
                            </button>
                          )}
                        {item.languageDetectionRunId &&
                          hasPermission('documents:export_language_results') &&
                          (['json', 'xlsx'] as const).map((format) => (
                            <button
                              key={format}
                              type="button"
                              onClick={() => void exportRun(item, format)}
                              disabled={mutations.export.isPending}
                              className="inline-flex min-h-9 items-center gap-1 rounded-lg px-2 text-[10px] font-semibold uppercase text-slate-600 hover:bg-slate-100 disabled:opacity-50"
                            >
                              <Download className="size-3" aria-hidden="true" />
                              {format}
                            </button>
                          ))}
                      </div>
                      {!item.sourceReady && !item.languageDetectionRunId && (
                        <p className="mt-1 text-[10px] text-slate-500">
                          Waiting for usable extraction or OCR text.
                        </p>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {documentsQuery.data.items.length === 0 && (
            <p className="p-12 text-center text-sm text-slate-600">
              No current document files match the selected filters.
            </p>
          )}
          {documentsQuery.data.totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-slate-200 px-5 py-4 text-xs text-slate-600">
              <span>
                Page {page} of {documentsQuery.data.totalPages}
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
                  disabled={page >= documentsQuery.data.totalPages}
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
      <RedetectLanguageDialog
        isOpen={redetectTarget !== null}
        isPending={mutations.redetect.isPending}
        onClose={() => setRedetectTarget(null)}
        onConfirm={(reason) => void redetect(reason)}
      />
    </div>
  );
}

function EmptyStatus({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-semibold text-slate-600 ring-1 ring-inset ring-slate-200">
      {children}
    </span>
  );
}

function Presence({ value }: { value: LanguagePresenceStatus | null }) {
  if (!value) {
    return <span className="text-xs text-slate-400">Not Detected</span>;
  }
  return (
    <span
      className={`rounded-full px-2.5 py-1 text-[10px] font-semibold ${getPresenceClass(
        value,
      )}`}
    >
      {presenceLabels[value]}
    </span>
  );
}

function formatStatus(status: LanguageDetectionDocumentStatus): string {
  return status
    .toLowerCase()
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}
