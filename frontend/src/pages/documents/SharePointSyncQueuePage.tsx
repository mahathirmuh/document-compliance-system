import { Eye, RotateCcw, XCircle } from 'lucide-react';
import { useState } from 'react';

import { getApiErrorMessage } from '../../api/errors';
import {
  Phase8ErrorAlert,
  Phase8Loading,
  Phase8Pagination,
} from '../../components/compliance/Phase8TableUtilities';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import {
  Phase10Action,
  Phase10Cell,
  Phase10Dialog,
  Phase10Empty,
  Phase10StatusBadge,
} from '../../components/phase10/Phase10Ui';
import { SharePointSyncJobDialog } from '../../components/sharepoint/SharePointSyncJobDialog';
import {
  useSharePointSyncJobs,
  useSharePointSyncMutations,
} from '../../hooks/useSharePointSync';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type { SharePointSyncJob } from '../../types/synchronisation';
import { isTerminalSyncStatus } from '../../types/synchronisation';
import { formatDateTime } from '../../utils/formatters';

export function SharePointSyncQueuePage() {
  const [page, setPage] = useState(1);
  const [detail, setDetail] = useState<SharePointSyncJob | null>(null);
  const [action, setAction] = useState<{
    type: 'cancel' | 'retry';
    job: SharePointSyncJob;
  } | null>(null);
  const user = useAuthStore((state) => state.user);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const viewAll = hasPermission('sharepoint:view_all_departments');
  const canCancel = hasPermission('sharepoint:cancel_sync');
  const canSync = hasPermission('sharepoint:sync');
  const query = useSharePointSyncJobs({
    page,
    pageSize: 20,
    status: [
      'QUEUED',
      'AUTHENTICATING',
      'DISCOVERING',
      'COMPARING',
      'TRANSFERRING',
      'UPDATING_METADATA',
      'RESOLVING_CONFLICTS',
      'PERSISTING',
      'CANCEL_REQUESTED',
    ],
  });
  const mutations = useSharePointSyncMutations();
  const { showToast } = useToast();

  const submitAction = async (): Promise<void> => {
    if (!action) return;
    try {
      if (action.type === 'cancel') {
        await mutations.cancelJob.mutateAsync(action.job.id);
      } else {
        await mutations.retryJob.mutateAsync(action.job.id);
      }
      showToast({
        tone: 'success',
        title:
          action.type === 'cancel' ? 'Cancellation requested' : 'Sync retry queued',
      });
      setAction(null);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Sync action failed',
        message: getApiErrorMessage(error, 'Refresh the job and try again.'),
      });
    }
  };

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Documents"
        title="SharePoint Sync Queue"
        description="Live SharePoint transfer progress. Active jobs poll every three seconds and stop polling after a terminal state."
      />
      {!viewAll && user?.departmentId && (
        <p className="rounded-2xl border border-blue-200 bg-blue-50 p-4 text-xs text-blue-800">
          Department scope is locked to your assigned department.
        </p>
      )}
      {query.isLoading && <Phase8Loading label="Loading SharePoint sync queue" />}
      {query.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(query.error, 'Sync queue could not be loaded.')}
          onRetry={() => void query.refetch()}
        />
      )}
      {query.data && query.data.items.length === 0 && (
        <Phase10Empty>No active SharePoint sync jobs.</Phase10Empty>
      )}
      {query.data && query.data.items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
            <table className="min-w-[84rem] divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  {[
                    'Requested At',
                    'Profile',
                    'Direction',
                    'Job Type',
                    'Status',
                    'Progress',
                    'Items',
                    'Conflicts',
                    'Failed',
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
                {query.data.items.map((job) => (
                  <tr key={job.id}>
                    <Phase10Cell>{formatDateTime(job.requestedAt)}</Phase10Cell>
                    <Phase10Cell strong>{job.syncProfileId}</Phase10Cell>
                    <Phase10Cell>{job.direction}</Phase10Cell>
                    <Phase10Cell>{job.jobType.replaceAll('_', ' ')}</Phase10Cell>
                    <Phase10Cell>
                      <Phase10StatusBadge status={job.status} />
                    </Phase10Cell>
                    <Phase10Cell>
                      <div className="w-32">
                        <div className="mb-1 text-[10px]">
                          {Math.round(job.progress)}%
                        </div>
                        <div className="h-1.5 rounded-full bg-slate-100">
                          <div
                            className="h-full rounded-full bg-blue-600"
                            style={{
                              width: `${Math.min(100, Math.max(0, job.progress))}%`,
                            }}
                          />
                        </div>
                      </div>
                    </Phase10Cell>
                    <Phase10Cell>
                      {job.itemsProcessed} / {job.itemsDiscovered}
                    </Phase10Cell>
                    <Phase10Cell>{job.itemsConflicted}</Phase10Cell>
                    <Phase10Cell>{job.itemsFailed}</Phase10Cell>
                    <Phase10Cell>{job.requestedBy ?? 'System'}</Phase10Cell>
                    <td className="px-4 py-3">
                      <div className="flex min-w-max gap-1.5">
                        <Phase10Action
                          label="View"
                          icon={Eye}
                          onClick={() => setDetail(job)}
                        />
                        {canCancel &&
                          !isTerminalSyncStatus(job.status) &&
                          job.status !== 'CANCEL_REQUESTED' && (
                            <Phase10Action
                              label="Cancel"
                              icon={XCircle}
                              tone="danger"
                              onClick={() => setAction({ type: 'cancel', job })}
                            />
                          )}
                        {canSync &&
                          ['FAILED', 'PARTIALLY_COMPLETED', 'CANCELLED'].includes(
                            job.status,
                          ) && (
                            <Phase10Action
                              label="Retry"
                              icon={RotateCcw}
                              onClick={() => setAction({ type: 'retry', job })}
                            />
                          )}
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
            label="sync jobs"
            onPageChange={setPage}
          />
        </>
      )}
      {detail && (
        <SharePointSyncJobDialog
          jobId={detail.id}
          fallbackJob={detail}
          onClose={() => setDetail(null)}
        />
      )}
      <Phase10Dialog
        open={action !== null}
        label="Confirm SharePoint sync action"
        title={action?.type === 'cancel' ? 'Cancel sync job?' : 'Retry sync job?'}
        description={
          action?.type === 'cancel'
            ? 'Cancellation is cooperative and preserves item history.'
            : 'Retry creates an audited attempt and does not bypass conflict policy.'
        }
        onClose={() => setAction(null)}
        width="max-w-lg"
      >
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={() => setAction(null)}
            className="min-h-10 rounded-xl border border-slate-300 px-4 text-xs font-semibold"
          >
            Back
          </button>
          <button
            type="button"
            disabled={mutations.cancelJob.isPending || mutations.retryJob.isPending}
            onClick={() => void submitAction()}
            className="min-h-10 rounded-xl bg-blue-700 px-4 text-xs font-semibold text-white disabled:opacity-50"
          >
            {action?.type === 'cancel' ? 'Request Cancellation' : 'Retry Sync'}
          </button>
        </div>
      </Phase10Dialog>
    </div>
  );
}
