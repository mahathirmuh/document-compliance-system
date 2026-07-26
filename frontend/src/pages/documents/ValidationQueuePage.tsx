import { Ban, Eye, FileText, Search } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import { ComplianceJobStatusBadge } from '../../components/compliance/ComplianceJobStatusBadge';
import { ComplianceProgress } from '../../components/compliance/ComplianceProgress';
import {
  Phase8ErrorAlert,
  Phase8FilterField,
  Phase8Loading,
  Phase8Pagination,
} from '../../components/compliance/Phase8TableUtilities';
import { ConfirmationDialog } from '../../components/master-data/ConfirmationDialog';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import {
  useComplianceJobs,
  useCancelComplianceJob,
} from '../../hooks/useComplianceJobs';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { useDocumentFormOptions } from '../../hooks/useDocumentFormOptions';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import {
  activeComplianceJobStatuses,
  complianceJobStatuses,
  isActiveComplianceJobStatus,
  type ComplianceJob,
  type ComplianceJobStatus,
} from '../../types/compliance';
import { formatDateTime } from '../../utils/formatters';

export function ValidationQueuePage() {
  const user = useAuthStore((state) => state.user);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const departmentLocked = !hasPermission('compliance:view_all_departments');
  const [searchInput, setSearchInput] = useState('');
  const search = useDebouncedValue(searchInput.trim(), 350);
  const [departmentId, setDepartmentId] = useState(
    departmentLocked ? (user?.departmentId ?? '') : '',
  );
  const [status, setStatus] = useState<ComplianceJobStatus | ''>('');
  const [validationRuleId, setValidationRuleId] = useState('');
  const [requestedBy, setRequestedBy] = useState('');
  const [requestedFrom, setRequestedFrom] = useState('');
  const [requestedTo, setRequestedTo] = useState('');
  const [page, setPage] = useState(1);
  const [cancelTarget, setCancelTarget] = useState<ComplianceJob | null>(null);
  const optionsQuery = useDocumentFormOptions();
  const cancelMutation = useCancelComplianceJob();
  const { showToast } = useToast();
  const query = useComplianceJobs(
    {
      page,
      pageSize: 20,
      sortBy: 'requestedAt',
      sortOrder: 'desc',
      ...(search ? { search } : {}),
      ...(departmentId ? { departmentId } : {}),
      ...(status ? { status } : { status: activeComplianceJobStatuses }),
      ...(validationRuleId ? { validationRuleId } : {}),
      ...(requestedBy.trim() ? { requestedBy: requestedBy.trim() } : {}),
      ...(requestedFrom ? { requestedFrom } : {}),
      ...(requestedTo ? { requestedTo } : {}),
    },
    { pollActive: true },
  );

  const cancel = async (): Promise<void> => {
    if (!cancelTarget) {
      return;
    }
    try {
      await cancelMutation.mutateAsync(cancelTarget.id);
      setCancelTarget(null);
      showToast({
        tone: 'success',
        title: 'Validation cancellation requested',
        message: 'The worker will stop safely between validation stages.',
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Validation could not be cancelled',
        message: getApiErrorMessage(error, 'Refresh the queue and try again.'),
      });
    }
  };

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Documents"
        title="Validation Queue"
        description="Monitor multilingual compliance jobs. Active jobs refresh every three seconds and stop polling at a terminal state."
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
                placeholder="Document code, title, or filename"
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
          <Phase8FilterField label="Status">
            <select
              value={status}
              onChange={(event) => {
                setStatus(event.target.value as ComplianceJobStatus | '');
                setPage(1);
              }}
              className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
            >
              <option value="">Active statuses</option>
              {complianceJobStatuses.map((candidate) => (
                <option key={candidate} value={candidate}>
                  {candidate.replaceAll('_', ' ')}
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
          <Phase8FilterField label="Requested By">
            <input
              value={requestedBy}
              onChange={(event) => {
                setRequestedBy(event.target.value);
                setPage(1);
              }}
              placeholder="User ID"
              className="min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
            />
          </Phase8FilterField>
          <Phase8FilterField label="Requested From">
            <input
              type="date"
              value={requestedFrom}
              onChange={(event) => {
                setRequestedFrom(event.target.value);
                setPage(1);
              }}
              className="min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
            />
          </Phase8FilterField>
          <Phase8FilterField label="Requested To">
            <input
              type="date"
              min={requestedFrom || undefined}
              value={requestedTo}
              onChange={(event) => {
                setRequestedTo(event.target.value);
                setPage(1);
              }}
              className="min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
            />
          </Phase8FilterField>
        </div>
        {departmentLocked && (
          <p className="mt-3 text-xs text-slate-500">
            Department scope is enforced by your compliance permissions.
          </p>
        )}
      </section>

      {query.isLoading && <Phase8Loading label="Loading validation queue" />}
      {query.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            query.error,
            'The validation queue could not be loaded.',
          )}
          onRetry={() => void query.refetch()}
        />
      )}
      {query.data && (
        <>
          <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
            <div className="overflow-x-auto">
              <table className="min-w-[88rem] divide-y divide-slate-200">
                <thead className="bg-slate-50">
                  <tr>
                    {[
                      'Requested At',
                      'Document Code',
                      'Revision',
                      'Validation Rule',
                      'Status',
                      'Progress',
                      'Current Stage',
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
                    const runId = job.resultSummary?.runId;
                    const documentPath = `/documents/${job.documentId}`;
                    return (
                      <tr key={job.id} className="hover:bg-slate-50">
                        <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">
                          {formatDateTime(job.requestedAt)}
                        </td>
                        <td className="px-4 py-3 text-xs font-semibold text-blue-700">
                          {job.document?.baseDocumentCode ?? job.documentId}
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-600">
                          {job.revision?.revisionCode ?? '—'}
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-600">
                          {job.validationRule?.name ?? 'Resolved by backend'}
                        </td>
                        <td className="px-4 py-3">
                          <ComplianceJobStatusBadge status={job.status} />
                        </td>
                        <td className="px-4 py-3">
                          <ComplianceProgress
                            status={job.status}
                            progress={job.progress}
                            currentStage={job.currentStage}
                          />
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-600">
                          {job.currentStage?.replaceAll('_', ' ') ?? '—'}
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-600">
                          {job.requestedBy?.name ?? 'Unknown user'}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex min-w-max gap-1">
                            {runId && (
                              <Link
                                to={`/documents/${job.documentId}/revisions/${job.documentRevisionId}/compliance?fileId=${job.documentFileId}&runId=${runId}`}
                                className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-blue-700 hover:bg-blue-50"
                              >
                                <Eye className="size-3.5" aria-hidden="true" />
                                View
                              </Link>
                            )}
                            <Link
                              to={documentPath}
                              className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-slate-600 hover:bg-slate-100"
                            >
                              <FileText className="size-3.5" aria-hidden="true" />
                              Open Document
                            </Link>
                            {hasPermission('compliance:validate') &&
                              isActiveComplianceJobStatus(job.status) &&
                              job.status !== 'CANCEL_REQUESTED' && (
                                <button
                                  type="button"
                                  onClick={() => setCancelTarget(job)}
                                  className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-amber-700 hover:bg-amber-50"
                                >
                                  <Ban className="size-3.5" aria-hidden="true" />
                                  Cancel
                                </button>
                              )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {query.data.items.length === 0 && (
              <p className="px-6 py-12 text-center text-sm text-slate-500">
                No validation jobs match these filters.
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
      <ConfirmationDialog
        isOpen={cancelTarget !== null}
        title="Cancel compliance validation?"
        message="The worker will stop at a safe stage. No partial result will be published as an official compliance run."
        confirmLabel="Request Cancellation"
        tone="danger"
        isPending={cancelMutation.isPending}
        onCancel={() => setCancelTarget(null)}
        onConfirm={() => void cancel()}
      />
    </div>
  );
}
