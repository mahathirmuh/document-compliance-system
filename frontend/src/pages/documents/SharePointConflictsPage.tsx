import { Eye, UserRound } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';

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
  phase10InputClass,
} from '../../components/phase10/Phase10Ui';
import {
  useSharePointConflictMutations,
  useSharePointConflicts,
} from '../../hooks/useSharePointConflicts';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type {
  SharePointConflictStatus,
  SharePointConflictType,
  SharePointSyncConflict,
} from '../../types/synchronisation';
import { formatDateTime } from '../../utils/formatters';

export function SharePointConflictsPage() {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<SharePointConflictStatus | ''>('OPEN');
  const [type, setType] = useState<SharePointConflictType | ''>('');
  const [assignTarget, setAssignTarget] = useState<SharePointSyncConflict | null>(null);
  const [assignee, setAssignee] = useState('');
  const user = useAuthStore((state) => state.user);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const viewAll = hasPermission('sharepoint:view_all_departments');
  const canResolve = hasPermission('sharepoint:resolve_conflicts');
  const query = useSharePointConflicts({
    page,
    pageSize: 20,
    ...(status ? { status } : {}),
    ...(type ? { conflictType: type } : {}),
    ...(!viewAll && user?.departmentId ? { departmentId: user.departmentId } : {}),
  });
  const mutations = useSharePointConflictMutations();
  const { showToast } = useToast();

  const assign = async (): Promise<void> => {
    if (!assignTarget || !assignee.trim()) return;
    try {
      await mutations.assign.mutateAsync({
        conflictId: assignTarget.id,
        payload: { userId: assignee.trim() },
      });
      setAssignTarget(null);
      setAssignee('');
      showToast({ tone: 'success', title: 'Conflict assigned' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Conflict could not be assigned',
        message: getApiErrorMessage(error, 'Select a valid user.'),
      });
    }
  };

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Documents"
        title="SharePoint Conflicts"
        description="Review changes that cannot be reconciled automatically. Manual policy never overwrites either side before an audited decision."
      />
      <div className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-4">
        <Phase8FilterField label="Status">
          <select
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as SharePointConflictStatus | '');
              setPage(1);
            }}
            className={phase10InputClass}
          >
            <option value="">All statuses</option>
            {['OPEN', 'IN_REVIEW', 'RESOLVED', 'IGNORED'].map((value) => (
              <option key={value} value={value}>
                {value.replaceAll('_', ' ')}
              </option>
            ))}
          </select>
        </Phase8FilterField>
        <Phase8FilterField label="Conflict type">
          <select
            value={type}
            onChange={(event) => {
              setType(event.target.value as SharePointConflictType | '');
              setPage(1);
            }}
            className={phase10InputClass}
          >
            <option value="">All conflict types</option>
            {[
              'BOTH_MODIFIED',
              'LOCAL_DELETED_REMOTE_MODIFIED',
              'REMOTE_DELETED_LOCAL_MODIFIED',
              'METADATA_CONFLICT',
              'PATH_CONFLICT',
              'DUPLICATE_REMOTE_ITEM',
              'HASH_MISMATCH',
              'VERSION_MISMATCH',
            ].map((value) => (
              <option key={value} value={value}>
                {value.replaceAll('_', ' ')}
              </option>
            ))}
          </select>
        </Phase8FilterField>
        <div className="self-end rounded-xl bg-slate-50 p-3 text-xs text-slate-600 lg:col-span-2">
          Scope: {viewAll ? 'All permitted departments' : 'Assigned department only'}
        </div>
      </div>
      {query.isLoading && <Phase8Loading label="Loading SharePoint conflicts" />}
      {query.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            query.error,
            'SharePoint conflicts could not be loaded.',
          )}
          onRetry={() => void query.refetch()}
        />
      )}
      {query.data && query.data.items.length === 0 && (
        <Phase10Empty>No conflicts match these filters.</Phase10Empty>
      )}
      {query.data && query.data.items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
            <table className="min-w-[76rem] divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  {[
                    'Detected At',
                    'Document Code',
                    'Revision',
                    'Conflict Type',
                    'Local Modified',
                    'Remote Modified',
                    'Status',
                    'Assigned To',
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
                {query.data.items.map((conflict) => (
                  <tr key={conflict.id}>
                    <Phase10Cell>{formatDateTime(conflict.detectedAt)}</Phase10Cell>
                    <Phase10Cell strong>{conflict.documentCode ?? '—'}</Phase10Cell>
                    <Phase10Cell>{conflict.revisionCode ?? '—'}</Phase10Cell>
                    <Phase10Cell>
                      {conflict.conflictType.replaceAll('_', ' ')}
                    </Phase10Cell>
                    <Phase10Cell>
                      {conflict.localVersion.modifiedAt
                        ? formatDateTime(conflict.localVersion.modifiedAt)
                        : '—'}
                    </Phase10Cell>
                    <Phase10Cell>
                      {conflict.remoteVersion.modifiedAt
                        ? formatDateTime(conflict.remoteVersion.modifiedAt)
                        : '—'}
                    </Phase10Cell>
                    <Phase10Cell>
                      <Phase10StatusBadge status={conflict.status} />
                    </Phase10Cell>
                    <Phase10Cell>{conflict.assignedTo ?? 'Unassigned'}</Phase10Cell>
                    <td className="px-4 py-3">
                      <div className="flex min-w-max gap-1.5">
                        <Link
                          to={`/documents/sharepoint-conflicts/${conflict.id}`}
                          className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-blue-200 px-2.5 text-[11px] font-semibold text-blue-700 hover:bg-blue-50"
                        >
                          <Eye className="size-3.5" aria-hidden="true" /> View
                        </Link>
                        {canResolve &&
                          ['OPEN', 'IN_REVIEW'].includes(conflict.status) && (
                            <Phase10Action
                              label="Assign"
                              icon={UserRound}
                              onClick={() => {
                                setAssignTarget(conflict);
                                setAssignee(conflict.assignedTo ?? '');
                              }}
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
            label="conflicts"
            onPageChange={setPage}
          />
        </>
      )}
      {assignTarget && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Assign SharePoint conflict"
          className="fixed inset-0 z-50 grid place-items-center bg-slate-950/50 p-4"
        >
          <form
            className="w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl"
            onSubmit={(event) => {
              event.preventDefault();
              void assign();
            }}
          >
            <h2 className="text-lg font-semibold text-slate-950">Assign Conflict</h2>
            <label className="mt-4 block text-xs font-semibold text-slate-700">
              User ID
              <input
                aria-label="User ID"
                value={assignee}
                onChange={(event) => setAssignee(event.target.value)}
                className={`mt-2 ${phase10InputClass}`}
              />
            </label>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setAssignTarget(null)}
                className="min-h-10 rounded-xl border border-slate-300 px-4 text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={!assignee.trim() || mutations.assign.isPending}
                className="min-h-10 rounded-xl bg-blue-700 px-4 text-xs font-semibold text-white disabled:opacity-50"
              >
                Assign
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
