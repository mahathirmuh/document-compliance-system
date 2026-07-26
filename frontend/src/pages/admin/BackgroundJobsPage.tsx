import { ArchiveX, RotateCcw } from 'lucide-react';
import { useState } from 'react';

import { getApiErrorMessage } from '../../api/errors';
import {
  Phase8ErrorAlert,
  Phase8FilterField,
  Phase8Loading,
  Phase8Pagination,
} from '../../components/compliance/Phase8TableUtilities';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import {
  Phase10Action,
  Phase10Cell,
  Phase10Empty,
  Phase10StatusBadge,
  ReasonDialog,
  phase10InputClass,
} from '../../components/phase10/Phase10Ui';
import {
  useDeadLetterJobs,
  useDeadLetterMutations,
} from '../../hooks/useSystemHealth';
import { useToast } from '../../providers/useToast';
import type {
  DeadLetterJob,
  DeadLetterStatus,
} from '../../types/systemHealth';
import { formatDateTime } from '../../utils/formatters';

export function BackgroundJobsPage() {
  const [page, setPage] = useState(1);
  const [taskName, setTaskName] = useState('');
  const [status, setStatus] = useState<DeadLetterStatus | ''>('ACTIVE');
  const [dismissTarget, setDismissTarget] = useState<DeadLetterJob | null>(null);
  const params = {
    page,
    pageSize: 20,
    ...(taskName.trim() ? { taskName: taskName.trim() } : {}),
    ...(status ? { status } : {}),
  };
  const query = useDeadLetterJobs(params);
  const mutations = useDeadLetterMutations();
  const { showToast } = useToast();

  const retry = async (job: DeadLetterJob): Promise<void> => {
    try {
      await mutations.retry.mutateAsync(job.id);
      showToast({ tone: 'success', title: 'Dead-letter retry queued' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Dead-letter retry failed',
        message: getApiErrorMessage(error, 'Try again.'),
      });
    }
  };

  const dismiss = async (reason: string): Promise<void> => {
    if (!dismissTarget) return;
    try {
      await mutations.dismiss.mutateAsync({
        jobId: dismissTarget.id,
        payload: { reason },
      });
      setDismissTarget(null);
      showToast({ tone: 'success', title: 'Dead-letter job dismissed' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Dead-letter dismissal failed',
        message: getApiErrorMessage(error, 'Try again.'),
      });
    }
  };

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Administration"
        title="Background Jobs"
        description="Inspect sanitized dead-letter failures and recover retryable tasks without exposing serialized secrets."
      />
      <div className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 sm:grid-cols-2">
        <Phase8FilterField label="Task name">
          <input
            value={taskName}
            onChange={(event) => {
              setTaskName(event.target.value);
              setPage(1);
            }}
            placeholder="Filter by task name"
            className={phase10InputClass}
          />
        </Phase8FilterField>
        <Phase8FilterField label="Status">
          <select
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as DeadLetterStatus | '');
              setPage(1);
            }}
            className={phase10InputClass}
          >
            <option value="">All statuses</option>
            {['ACTIVE', 'RETRY_QUEUED', 'RETRIED', 'DISMISSED'].map((value) => (
              <option key={value} value={value}>
                {value.replaceAll('_', ' ')}
              </option>
            ))}
          </select>
        </Phase8FilterField>
      </div>
      {query.isLoading && <Phase8Loading label="Loading dead-letter jobs" />}
      {query.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            query.error,
            'Dead-letter jobs could not be loaded.',
          )}
          onRetry={() => void query.refetch()}
        />
      )}
      {query.data && query.data.items.length === 0 && (
        <Phase10Empty>No dead-letter jobs match these filters.</Phase10Empty>
      )}
      {query.data && query.data.items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
            <table className="min-w-[76rem] divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  {[
                    'Last Failed',
                    'Task',
                    'Entity',
                    'Status',
                    'Attempts',
                    'Error Code',
                    'Safe Error',
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
                {query.data.items.map((job) => (
                  <tr key={job.id}>
                    <Phase10Cell>{formatDateTime(job.lastFailedAt)}</Phase10Cell>
                    <Phase10Cell strong>{job.taskName}</Phase10Cell>
                    <Phase10Cell>
                      {job.entityType} · {job.entityId ?? '—'}
                    </Phase10Cell>
                    <Phase10Cell>
                      <Phase10StatusBadge status={job.status} />
                    </Phase10Cell>
                    <Phase10Cell>
                      {job.attempts} / {job.maximumAttempts}
                    </Phase10Cell>
                    <Phase10Cell>{job.errorCode}</Phase10Cell>
                    <Phase10Cell>{job.lastError}</Phase10Cell>
                    <td className="px-4 py-3">
                      <div className="flex min-w-max gap-1.5">
                        <Phase10Action
                          label="Retry"
                          icon={RotateCcw}
                          disabled={
                            !['ACTIVE', 'RETRIED'].includes(job.status) ||
                            mutations.retry.isPending
                          }
                          onClick={() => void retry(job)}
                        />
                        <Phase10Action
                          label="Dismiss"
                          icon={ArchiveX}
                          tone="danger"
                          disabled={
                            job.status === 'DISMISSED' ||
                            mutations.dismiss.isPending
                          }
                          onClick={() => setDismissTarget(job)}
                        />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Phase8Pagination
            page={page}
            totalItems={query.data.totalItems}
            totalPages={query.data.totalPages}
            label="dead-letter jobs"
            onPageChange={setPage}
          />
        </>
      )}
      <ReasonDialog
        open={dismissTarget !== null}
        title="Dismiss dead-letter job?"
        description="Dismissal preserves failure history but removes the job from the active recovery queue."
        confirmLabel="Dismiss Job"
        isPending={mutations.dismiss.isPending}
        onClose={() => setDismissTarget(null)}
        onConfirm={dismiss}
      />
    </div>
  );
}
