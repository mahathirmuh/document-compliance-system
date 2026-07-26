import {
  ArrowDownToLine,
  ArrowUpFromLine,
  ExternalLink,
  History,
  RefreshCw,
} from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import {
  useDocumentRemoteStatus,
  useDocumentRemoteVersions,
  useSharePointSyncMutations,
} from '../../hooks/useSharePointSync';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type { DocumentFileListItem } from '../../types/documentFile';
import { formatDateTime } from '../../utils/formatters';
import {
  Phase10Action,
  Phase10Dialog,
  Phase10StatusBadge,
  ReasonDialog,
} from '../phase10/Phase10Ui';

export function DocumentRemotePanel({
  documentFile,
}: {
  documentFile: DocumentFileListItem | null;
}) {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canPush = hasPermission('sharepoint:push');
  const canPull = hasPermission('sharepoint:pull');
  const canViewHistory = hasPermission('sharepoint:view_history');
  const query = useDocumentRemoteStatus(documentFile?.id ?? null);
  const versionsQuery = useDocumentRemoteVersions(
    documentFile?.id && canViewHistory ? documentFile.id : null,
  );
  const mutations = useSharePointSyncMutations();
  const [action, setAction] = useState<'push' | 'pull' | 'reconcile' | null>(null);
  const [versionsOpen, setVersionsOpen] = useState(false);
  const { showToast } = useToast();

  if (!documentFile) {
    return (
      <p className="rounded-2xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">
        Upload a current physical file before configuring SharePoint synchronisation.
      </p>
    );
  }
  if (
    ['QUARANTINED', 'PENDING_SCAN', 'SCAN_FAILED'].includes(documentFile.fileStatus)
  ) {
    return (
      <div
        role="alert"
        className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-800"
      >
        This file is {documentFile.fileStatus.replaceAll('_', ' ').toLowerCase()} and
        cannot be pushed, pulled, downloaded, or reconciled until the malware-scanning
        policy marks it available.
      </div>
    );
  }
  if (query.isLoading) {
    return (
      <div
        aria-label="Loading SharePoint remote status"
        className="h-56 animate-pulse rounded-2xl bg-slate-100"
      />
    );
  }
  if (query.error || !query.data) {
    return (
      <div
        role="alert"
        className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700"
      >
        {getApiErrorMessage(
          query.error,
          'SharePoint remote status could not be loaded.',
        )}
        <button
          type="button"
          onClick={() => void query.refetch()}
          className="ml-3 font-semibold underline"
        >
          Retry
        </button>
      </div>
    );
  }
  const remote = query.data;
  const active = Boolean(remote.activeJobId) || remote.remoteSyncStatus === 'SYNCING';
  const safeWebUrl =
    remote.remoteWebUrl?.startsWith('https://') && !remote.remoteWebUrl.includes('@')
      ? remote.remoteWebUrl
      : null;

  const run = async (reason: string): Promise<void> => {
    if (!action) return;
    try {
      if (action === 'push') {
        await mutations.pushFile.mutateAsync({
          fileId: documentFile.id,
          payload: { reason },
        });
      } else if (action === 'pull') {
        await mutations.pullFile.mutateAsync({
          fileId: documentFile.id,
          payload: { reason },
        });
      } else {
        await mutations.reconcileFile.mutateAsync({
          fileId: documentFile.id,
          payload: { reason },
        });
      }
      setAction(null);
      showToast({
        tone: 'success',
        title:
          action === 'push'
            ? 'SharePoint push queued'
            : action === 'pull'
              ? 'SharePoint pull queued'
              : 'SharePoint reconciliation queued',
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'SharePoint action failed',
        message: getApiErrorMessage(error, 'Check active jobs and file status.'),
      });
    }
  };

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Storage Provider" value={remote.storageProvider} />
        <Metric
          label="Remote Sync Status"
          value={<Phase10StatusBadge status={remote.remoteSyncStatus} />}
        />
        <Metric label="Connection" value={remote.connectionName ?? 'Not mapped'} />
        <Metric label="Remote Path" value={remote.remotePath ?? 'Not synced'} />
        <Metric label="Remote Version" value={remote.remoteVersionId ?? '—'} />
        <Metric
          label="Last Synced"
          value={remote.lastSyncedAt ? formatDateTime(remote.lastSyncedAt) : 'Never'}
        />
        <Metric
          label="Remote Last Modified"
          value={
            remote.remoteLastModifiedAt
              ? formatDateTime(remote.remoteLastModifiedAt)
              : '—'
          }
        />
        <Metric
          label="Remote Size"
          value={remote.remoteSize?.toLocaleString() ?? '—'}
        />
      </div>
      {remote.syncErrorMessage && (
        <div
          role="alert"
          className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-700"
        >
          <p className="font-semibold">{remote.syncErrorCode ?? 'SYNC_ERROR'}</p>
          <p className="mt-1">{remote.syncErrorMessage}</p>
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {canPush && (
          <Phase10Action
            label="Push to SharePoint"
            icon={ArrowUpFromLine}
            tone="primary"
            disabled={active}
            onClick={() => setAction('push')}
          />
        )}
        {canPull && remote.remoteItemId && (
          <Phase10Action
            label="Pull from SharePoint"
            icon={ArrowDownToLine}
            disabled={active}
            onClick={() => setAction('pull')}
          />
        )}
        {(canPush || canPull) && remote.remoteItemId && (
          <Phase10Action
            label="Reconcile"
            icon={RefreshCw}
            disabled={active}
            onClick={() => setAction('reconcile')}
          />
        )}
        {safeWebUrl && (
          <a
            href={safeWebUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 text-[11px] font-semibold text-slate-700 hover:bg-slate-50"
          >
            <ExternalLink className="size-3.5" aria-hidden="true" />
            Open in SharePoint
          </a>
        )}
        {canViewHistory && (
          <>
            <Phase10Action
              label="View Remote Versions"
              icon={History}
              disabled={!remote.remoteItemId}
              onClick={() => setVersionsOpen(true)}
            />
            <Link
              to={`/documents/sharepoint-sync-history?fileId=${documentFile.id}`}
              className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 text-[11px] font-semibold text-slate-700 hover:bg-slate-50"
            >
              <History className="size-3.5" aria-hidden="true" />
              View Sync History
            </Link>
          </>
        )}
      </div>
      {active && (
        <p className="rounded-2xl border border-blue-200 bg-blue-50 p-4 text-xs text-blue-800">
          A SharePoint job is active for this file. Status refreshes every three
          seconds; conflicting actions are disabled.
        </p>
      )}
      <ReasonDialog
        open={action !== null}
        title={
          action === 'push'
            ? 'Push file to SharePoint?'
            : action === 'pull'
              ? 'Pull file from SharePoint?'
              : 'Reconcile local and remote file?'
        }
        description="The backend rechecks permissions, department scope, active jobs, malware status, and conflict policy before transfer."
        confirmLabel={
          action === 'push'
            ? 'Queue Push'
            : action === 'pull'
              ? 'Queue Pull'
              : 'Reconcile'
        }
        isPending={
          mutations.pushFile.isPending ||
          mutations.pullFile.isPending ||
          mutations.reconcileFile.isPending
        }
        onClose={() => setAction(null)}
        onConfirm={run}
      />
      <Phase10Dialog
        open={versionsOpen}
        label="SharePoint remote versions"
        title="Remote SharePoint Versions"
        description="Storage versions are tracked separately from business document revisions."
        onClose={() => setVersionsOpen(false)}
      >
        {versionsQuery.isLoading && (
          <div
            aria-label="Loading remote versions"
            className="h-40 animate-pulse rounded-2xl bg-slate-100"
          />
        )}
        {versionsQuery.error && (
          <p role="alert" className="text-sm text-rose-700">
            {getApiErrorMessage(
              versionsQuery.error,
              'Remote versions could not be loaded.',
            )}
          </p>
        )}
        {versionsQuery.data?.length === 0 && (
          <p className="text-sm text-slate-500">No remote versions recorded.</p>
        )}
        <ol className="space-y-3">
          {versionsQuery.data?.map((version) => (
            <li
              key={version.id}
              className="rounded-xl border border-slate-200 p-4 text-xs text-slate-600"
            >
              <p className="font-semibold text-slate-900">
                Version {version.remoteVersionId}
              </p>
              <p className="mt-1">
                {version.remoteLastModifiedAt
                  ? formatDateTime(version.remoteLastModifiedAt)
                  : 'Unknown time'}{' '}
                · {version.remoteLastModifiedBy ?? 'Unknown user'} ·{' '}
                {version.remoteSize?.toLocaleString() ?? '—'} bytes
              </p>
            </li>
          ))}
        </ol>
      </Phase10Dialog>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-2xl bg-slate-50 p-4">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
        {label}
      </p>
      <div className="mt-2 break-words text-sm font-semibold text-slate-900">
        {value}
      </div>
    </div>
  );
}
