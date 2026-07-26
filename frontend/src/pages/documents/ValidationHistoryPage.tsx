import { ArrowRightLeft, Download, Eye, RefreshCw, Search } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import { ComplianceStatusBadge } from '../../components/compliance/ComplianceStatusBadge';
import {
  Phase8ErrorAlert,
  Phase8FilterField,
  Phase8Loading,
  Phase8Pagination,
} from '../../components/compliance/Phase8TableUtilities';
import { RevalidateComplianceDialog } from '../../components/compliance/RevalidateComplianceDialog';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { useComplianceMutations } from '../../hooks/useCompliance';
import { useComplianceJobs } from '../../hooks/useComplianceJobs';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { useDocumentFormOptions } from '../../hooks/useDocumentFormOptions';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import {
  terminalComplianceJobStatuses,
  type ComplianceJob,
  type ComplianceStatus,
} from '../../types/compliance';
import { downloadFile } from '../../utils/downloadFile';
import { formatDateTime } from '../../utils/formatters';

export function ValidationHistoryPage() {
  const user = useAuthStore((state) => state.user);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const departmentLocked = !hasPermission('compliance:view_all_departments');
  const [searchInput, setSearchInput] = useState('');
  const search = useDebouncedValue(searchInput.trim(), 350);
  const [departmentId, setDepartmentId] = useState(
    departmentLocked ? (user?.departmentId ?? '') : '',
  );
  const [validationRuleId, setValidationRuleId] = useState('');
  const [complianceStatus, setComplianceStatus] = useState<ComplianceStatus | ''>('');
  const [page, setPage] = useState(1);
  const [revalidateTarget, setRevalidateTarget] = useState<ComplianceJob | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const optionsQuery = useDocumentFormOptions();
  const query = useComplianceJobs({
    page,
    pageSize: 20,
    sortBy: 'completedAt',
    sortOrder: 'desc',
    status: terminalComplianceJobStatuses,
    ...(search ? { search } : {}),
    ...(departmentId ? { departmentId } : {}),
    ...(validationRuleId ? { validationRuleId } : {}),
    ...(complianceStatus ? { complianceStatus } : {}),
  });
  const mutations = useComplianceMutations();
  const { showToast } = useToast();

  const exportRun = async (
    job: ComplianceJob,
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
        `${job.document?.baseDocumentCode ?? 'document'}_compliance.${format}`,
      );
      showToast({
        tone: 'success',
        title: `Compliance ${format.toUpperCase()} downloaded`,
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Compliance export failed',
        message: getApiErrorMessage(error, 'The result could not be downloaded.'),
      });
    }
  };

  const revalidate = async (reason: string): Promise<void> => {
    const runId = revalidateTarget?.resultSummary?.runId;
    if (!runId) {
      return;
    }
    setActionError(null);
    try {
      await mutations.revalidate.mutateAsync({ runId, payload: { reason } });
      setRevalidateTarget(null);
      showToast({
        tone: 'success',
        title: 'Revalidation queued',
        message: 'The previous run remains available for comparison.',
      });
    } catch (error: unknown) {
      setActionError(
        getApiErrorMessage(error, 'The revalidation could not be queued.'),
      );
    }
  };

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Documents"
        title="Validation History"
        description="Review immutable compliance runs, compare changes, revalidate, and export results within your department scope."
      />
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
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
                placeholder="Document code or title"
                className="min-h-11 w-full rounded-xl border border-slate-300 pl-10 pr-3 text-sm"
              />
            </span>
          </Phase8FilterField>
          <Phase8FilterField label="Department">
            <select
              value={departmentId}
              disabled={departmentLocked}
              onChange={(event) => {
                setDepartmentId(event.target.value);
                setPage(1);
              }}
              className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm disabled:bg-slate-100"
            >
              <option value="">
                {departmentLocked ? 'Assigned department only' : 'All departments'}
              </option>
              {(optionsQuery.data?.departments ?? []).map((department) => (
                <option key={department.id} value={department.id}>
                  {department.code} — {department.name}
                </option>
              ))}
            </select>
          </Phase8FilterField>
          <Phase8FilterField label="Validation Rule">
            <select
              value={validationRuleId}
              onChange={(event) => {
                setValidationRuleId(event.target.value);
                setPage(1);
              }}
              className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
            >
              <option value="">All rules</option>
              {(optionsQuery.data?.validationRules ?? []).map((rule) => (
                <option key={rule.id} value={rule.id}>
                  {rule.code} — {rule.name}
                </option>
              ))}
            </select>
          </Phase8FilterField>
          <Phase8FilterField label="Compliance Status">
            <select
              value={complianceStatus}
              onChange={(event) => {
                setComplianceStatus(event.target.value as ComplianceStatus | '');
                setPage(1);
              }}
              className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
            >
              <option value="">All statuses</option>
              {(
                [
                  'COMPLIANT',
                  'PARTIALLY_COMPLIANT',
                  'NON_COMPLIANT',
                  'NEEDS_REVIEW',
                  'NOT_EVALUATED',
                ] as const
              ).map((candidate) => (
                <option key={candidate} value={candidate}>
                  {candidate.replaceAll('_', ' ')}
                </option>
              ))}
            </select>
          </Phase8FilterField>
        </div>
      </section>

      {query.isLoading && <Phase8Loading label="Loading validation history" />}
      {query.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            query.error,
            'Validation history could not be loaded.',
          )}
          onRetry={() => void query.refetch()}
        />
      )}
      {query.data && (
        <>
          <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
            <div className="overflow-x-auto">
              <table className="min-w-[94rem] divide-y divide-slate-200">
                <thead className="bg-slate-50">
                  <tr>
                    {[
                      'Validated At',
                      'Document Code',
                      'Revision',
                      'Validation Rule',
                      'Compliance Status',
                      'Score',
                      'Critical',
                      'Major',
                      'Minor',
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
                  {query.data.items.map((job) => {
                    const result = job.resultSummary;
                    const runId = result?.runId;
                    const compliancePath = `/documents/${job.documentId}/revisions/${job.documentRevisionId}/compliance?fileId=${job.documentFileId}&runId=${runId ?? ''}`;
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
                        <td className="px-4 py-3 text-xs text-slate-600">
                          {job.validationRule?.name ?? '—'}
                        </td>
                        <td className="px-4 py-3">
                          {result?.complianceStatus ? (
                            <ComplianceStatusBadge status={result.complianceStatus} />
                          ) : (
                            <span className="text-xs text-slate-500">
                              No official result
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm font-semibold text-slate-900">
                          {result?.complianceScore?.toFixed(1) ?? '—'}
                        </td>
                        <td className="px-4 py-3 text-xs text-rose-700">
                          {result?.criticalFindings ?? '—'}
                        </td>
                        <td className="px-4 py-3 text-xs text-orange-700">
                          {result?.majorFindings ?? '—'}
                        </td>
                        <td className="px-4 py-3 text-xs text-amber-700">
                          {result?.minorFindings ?? '—'}
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-600">
                          {job.requestedBy?.name ?? 'Unknown user'}
                        </td>
                        <td className="px-4 py-3">
                          {runId && (
                            <div className="flex min-w-max gap-1">
                              <Link
                                to={compliancePath}
                                className="inline-flex min-h-9 items-center gap-1 rounded-lg px-2.5 text-xs font-semibold text-blue-700 hover:bg-blue-50"
                              >
                                <Eye className="size-3.5" aria-hidden="true" />
                                View Compliance
                              </Link>
                              <Link
                                to={`${compliancePath}&compare=previous`}
                                className="inline-flex min-h-9 items-center gap-1 rounded-lg px-2.5 text-xs font-semibold text-indigo-700 hover:bg-indigo-50"
                              >
                                <ArrowRightLeft
                                  className="size-3.5"
                                  aria-hidden="true"
                                />
                                Compare
                              </Link>
                              {hasPermission('compliance:revalidate') && (
                                <button
                                  type="button"
                                  onClick={() => {
                                    setActionError(null);
                                    setRevalidateTarget(job);
                                  }}
                                  className="inline-flex min-h-9 items-center gap-1 rounded-lg px-2.5 text-xs font-semibold text-violet-700 hover:bg-violet-50"
                                >
                                  <RefreshCw className="size-3.5" aria-hidden="true" />
                                  Revalidate
                                </button>
                              )}
                              {hasPermission('compliance:export') &&
                                (['xlsx', 'json'] as const).map((format) => (
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
                No validation history matches these filters.
              </p>
            )}
          </div>
          <Phase8Pagination
            page={page}
            totalItems={query.data.totalItems}
            totalPages={query.data.totalPages}
            label="validation jobs"
            onPageChange={setPage}
          />
        </>
      )}
      <RevalidateComplianceDialog
        isOpen={revalidateTarget !== null}
        isPending={mutations.revalidate.isPending}
        errorMessage={actionError}
        onClose={() => setRevalidateTarget(null)}
        onConfirm={(reason) => void revalidate(reason)}
      />
    </div>
  );
}
