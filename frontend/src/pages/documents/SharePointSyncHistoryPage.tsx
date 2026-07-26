import { Download, Eye, Play } from 'lucide-react';
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
import { downloadFile } from '../../utils/downloadFile';
import { formatDateTime } from '../../utils/formatters';

const duration = (job: SharePointSyncJob): string => {
  if (!job.startedAt || !job.completedAt) return '—';
  const seconds = Math.max(
    0,
    Math.round(
      (new Date(job.completedAt).getTime() - new Date(job.startedAt).getTime()) / 1_000,
    ),
  );
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
};

export function SharePointSyncHistoryPage() {
  const [page, setPage] = useState(1);
  const [detail, setDetail] = useState<SharePointSyncJob | null>(null);
  const user = useAuthStore((state) => state.user);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const viewAll = hasPermission('sharepoint:view_all_departments');
  const canSync = hasPermission('sharepoint:sync');
  const query = useSharePointSyncJobs({
    page,
    pageSize: 20,
    status: ['COMPLETED', 'PARTIALLY_COMPLETED', 'FAILED', 'CANCELLED', 'DEAD_LETTER'],
  });
  const mutations = useSharePointSyncMutations();
  const { showToast } = useToast();

  const exportJob = async (
    job: SharePointSyncJob,
    format: 'json' | 'xlsx',
  ): Promise<void> => {
    try {
      const result = await mutations.exportJob.mutateAsync({ jobId: job.id, format });
      downloadFile(result, `sharepoint_sync_${job.id}.${format}`);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Sync export failed',
        message: getApiErrorMessage(error, 'Try again.'),
      });
    }
  };

  const rerun = async (job: SharePointSyncJob): Promise<void> => {
    if (!job.syncProfileId) return;
    try {
      await mutations.runProfile.mutateAsync({
        profileId: job.syncProfileId,
        jobType: job.jobType === 'MANUAL_FULL' ? 'MANUAL_FULL' : 'MANUAL_INCREMENTAL',
      });
      showToast({ tone: 'success', title: 'Sync re-run queued' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Sync could not be re-run',
        message: getApiErrorMessage(error, 'Check the profile status.'),
      });
    }
  };

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Documents"
        title="SharePoint Sync History"
        description="Review completed, partial, failed, and cancelled synchronisation attempts with item-level audit history."
      />
      {!viewAll && user?.departmentId && (
        <p className="rounded-2xl border border-blue-200 bg-blue-50 p-4 text-xs text-blue-800">
          Department scope is enforced by the backend for your assigned department.
        </p>
      )}
      {query.isLoading && <Phase8Loading label="Loading SharePoint sync history" />}
      {query.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(query.error, 'Sync history could not be loaded.')}
          onRetry={() => void query.refetch()}
        />
      )}
      {query.data && query.data.items.length === 0 && (
        <Phase10Empty>No SharePoint sync history.</Phase10Empty>
      )}
      {query.data && query.data.items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
            <table className="min-w-[86rem] divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  {[
                    'Completed At',
                    'Profile',
                    'Direction',
                    'Discovered',
                    'Created',
                    'Updated',
                    'Skipped',
                    'Conflicted',
                    'Failed',
                    'Status',
                    'Duration',
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
                    <Phase10Cell>
                      {job.completedAt
                        ? formatDateTime(job.completedAt)
                        : job.failedAt
                          ? formatDateTime(job.failedAt)
                          : '—'}
                    </Phase10Cell>
                    <Phase10Cell strong>{job.syncProfileId}</Phase10Cell>
                    <Phase10Cell>{job.direction}</Phase10Cell>
                    <Phase10Cell>{job.itemsDiscovered}</Phase10Cell>
                    <Phase10Cell>{job.itemsCreated}</Phase10Cell>
                    <Phase10Cell>{job.itemsUpdated}</Phase10Cell>
                    <Phase10Cell>{job.itemsSkipped}</Phase10Cell>
                    <Phase10Cell>{job.itemsConflicted}</Phase10Cell>
                    <Phase10Cell>{job.itemsFailed}</Phase10Cell>
                    <Phase10Cell>
                      <Phase10StatusBadge status={job.status} />
                    </Phase10Cell>
                    <Phase10Cell>{duration(job)}</Phase10Cell>
                    <td className="px-4 py-3">
                      <div className="flex min-w-max gap-1.5">
                        <Phase10Action
                          label="View Details"
                          icon={Eye}
                          onClick={() => setDetail(job)}
                        />
                        <Phase10Action
                          label="Export XLSX"
                          icon={Download}
                          onClick={() => void exportJob(job, 'xlsx')}
                        />
                        <Phase10Action
                          label="Export JSON"
                          icon={Download}
                          onClick={() => void exportJob(job, 'json')}
                        />
                        {canSync && job.syncProfileId && (
                          <Phase10Action
                            label="Re-run"
                            icon={Play}
                            tone="primary"
                            onClick={() => void rerun(job)}
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
    </div>
  );
}
