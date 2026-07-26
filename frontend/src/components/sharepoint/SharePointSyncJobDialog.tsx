import { useState } from 'react';

import { getApiErrorMessage } from '../../api/errors';
import {
  Phase8ErrorAlert,
  Phase8Loading,
  Phase8Pagination,
} from '../compliance/Phase8TableUtilities';
import {
  Phase10Cell,
  Phase10Dialog,
  Phase10Empty,
  Phase10StatusBadge,
} from '../phase10/Phase10Ui';
import {
  useSharePointSyncItems,
  useSharePointSyncJob,
} from '../../hooks/useSharePointSync';
import type { SharePointSyncJob } from '../../types/synchronisation';
import { formatDateTime } from '../../utils/formatters';

export function SharePointSyncJobDialog({
  fallbackJob,
  jobId,
  onClose,
}: {
  jobId: string;
  fallbackJob?: SharePointSyncJob;
  onClose: () => void;
}) {
  const [itemPage, setItemPage] = useState(1);
  const jobQuery = useSharePointSyncJob(jobId);
  const itemQuery = useSharePointSyncItems(jobId, { page: itemPage, pageSize: 20 });
  const job = jobQuery.data ?? fallbackJob;

  return (
    <Phase10Dialog
      open
      label="SharePoint sync job details"
      title="SharePoint Sync Job"
      {...(job
        ? {
            description: `${job.profileName ?? 'Direct file operation'} · ${job.jobType.replaceAll('_', ' ')}`,
          }
        : {})}
      onClose={onClose}
      width="max-w-6xl"
    >
      {jobQuery.isLoading && !job && <Phase8Loading label="Loading sync job" />}
      {jobQuery.error && !job && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(jobQuery.error, 'Sync job could not be loaded.')}
          onRetry={() => void jobQuery.refetch()}
        />
      )}
      {job && (
        <div className="space-y-6">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label="Status" value={<Phase10StatusBadge status={job.status} />} />
            <Metric label="Progress" value={`${Math.round(job.progress)}%`} />
            <Metric
              label="Stage"
              value={job.currentStage?.replaceAll('_', ' ') ?? '—'}
            />
            <Metric label="Direction" value={job.direction} />
            <Metric label="Requested" value={formatDateTime(job.requestedAt)} />
            <Metric
              label="Started"
              value={job.startedAt ? formatDateTime(job.startedAt) : '—'}
            />
            <Metric
              label="Completed"
              value={job.completedAt ? formatDateTime(job.completedAt) : '—'}
            />
            <Metric
              label="Attempt"
              value={`${job.attemptNumber} / ${job.maximumAttempts}`}
            />
          </div>
          <div>
            <div className="mb-2 flex items-center justify-between text-xs text-slate-600">
              <span>{job.itemsProcessed.toLocaleString()} processed</span>
              <span>{Math.round(job.progress)}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full bg-blue-600 transition-[width]"
                style={{ width: `${Math.min(100, Math.max(0, job.progress))}%` }}
              />
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <Metric label="Discovered" value={job.itemsDiscovered} />
            <Metric label="Created" value={job.itemsCreated} />
            <Metric label="Updated" value={job.itemsUpdated} />
            <Metric label="Skipped" value={job.itemsSkipped} />
            <Metric label="Conflicts" value={job.itemsConflicted} />
            <Metric label="Failed" value={job.itemsFailed} />
          </div>
          {job.errorMessage && (
            <div
              role="alert"
              className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-700"
            >
              <p className="font-semibold">{job.errorCode ?? 'SYNC_ERROR'}</p>
              <p className="mt-1">{job.errorMessage}</p>
            </div>
          )}
          <section>
            <h3 className="text-sm font-semibold text-slate-950">Sync Items</h3>
            <div className="mt-3">
              {itemQuery.isLoading && <Phase8Loading label="Loading sync items" />}
              {itemQuery.error && (
                <Phase8ErrorAlert
                  message={getApiErrorMessage(
                    itemQuery.error,
                    'Sync items could not be loaded.',
                  )}
                  onRetry={() => void itemQuery.refetch()}
                />
              )}
              {itemQuery.data && itemQuery.data.items.length === 0 && (
                <Phase10Empty>No sync items have been persisted yet.</Phase10Empty>
              )}
              {itemQuery.data && itemQuery.data.items.length > 0 && (
                <>
                  <div className="overflow-x-auto rounded-2xl border border-slate-200">
                    <table className="min-w-[64rem] divide-y divide-slate-200">
                      <thead className="bg-slate-50">
                        <tr>
                          {[
                            'Document',
                            'Revision',
                            'Remote Path',
                            'Operation',
                            'Status',
                            'Size',
                            'Started',
                            'Completed',
                            'Error',
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
                        {itemQuery.data.items.map((item) => (
                          <tr key={item.id}>
                            <Phase10Cell strong>{item.documentCode ?? '—'}</Phase10Cell>
                            <Phase10Cell>{item.revisionCode ?? '—'}</Phase10Cell>
                            <Phase10Cell>{item.remotePath ?? '—'}</Phase10Cell>
                            <Phase10Cell>
                              {item.operation.replaceAll('_', ' ')}
                            </Phase10Cell>
                            <Phase10Cell>
                              <Phase10StatusBadge status={item.status} />
                            </Phase10Cell>
                            <Phase10Cell>
                              {item.remoteSize?.toLocaleString() ?? '—'}
                            </Phase10Cell>
                            <Phase10Cell>
                              {item.startedAt ? formatDateTime(item.startedAt) : '—'}
                            </Phase10Cell>
                            <Phase10Cell>
                              {item.completedAt
                                ? formatDateTime(item.completedAt)
                                : '—'}
                            </Phase10Cell>
                            <Phase10Cell>{item.errorMessage ?? '—'}</Phase10Cell>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="mt-3">
                    <Phase8Pagination
                      page={itemPage}
                      totalItems={itemQuery.data.totalItems}
                      totalPages={itemQuery.data.totalPages}
                      label="sync items"
                      onPageChange={setItemPage}
                    />
                  </div>
                </>
              )}
            </div>
          </section>
        </div>
      )}
    </Phase10Dialog>
  );
}

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-2xl bg-slate-50 p-4">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
        {label}
      </p>
      <div className="mt-2 text-sm font-semibold text-slate-900">{value}</div>
    </div>
  );
}
