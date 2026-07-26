import { ArrowLeft, CheckCircle2, CircleSlash, UserRound } from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { Link, useParams } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import {
  Phase8ErrorAlert,
  Phase8Loading,
} from '../../components/compliance/Phase8TableUtilities';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import {
  Phase10StatusBadge,
  phase10InputClass,
  phase10TextareaClass,
} from '../../components/phase10/Phase10Ui';
import {
  useSharePointConflict,
  useSharePointConflictMutations,
} from '../../hooks/useSharePointConflicts';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type {
  ConflictVersionSnapshot,
  SharePointConflictResolution,
} from '../../types/synchronisation';
import { formatDateTime } from '../../utils/formatters';

export function SharePointConflictDetailPage() {
  const { conflictId } = useParams<{ conflictId: string }>();
  const query = useSharePointConflict(conflictId ?? null);
  const mutations = useSharePointConflictMutations();
  const canResolve = useAuthStore((state) =>
    state.hasPermission('sharepoint:resolve_conflicts'),
  );
  const [resolution, setResolution] =
    useState<SharePointConflictResolution>('KEEP_LOCAL');
  const [comment, setComment] = useState('');
  const [assignee, setAssignee] = useState('');
  const { showToast } = useToast();
  const conflict = query.data;
  const actionable =
    canResolve && conflict && ['OPEN', 'IN_REVIEW'].includes(conflict.status);

  const resolve = async (): Promise<void> => {
    if (!conflict || comment.trim().length < 5) return;
    try {
      await mutations.resolve.mutateAsync({
        conflictId: conflict.id,
        payload: { resolution, comment: comment.trim() },
      });
      setComment('');
      showToast({ tone: 'success', title: 'Conflict resolved' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Conflict could not be resolved',
        message: getApiErrorMessage(error, 'Refresh and try again.'),
      });
    }
  };

  const ignore = async (): Promise<void> => {
    if (!conflict || comment.trim().length < 5) return;
    try {
      await mutations.ignore.mutateAsync({
        conflictId: conflict.id,
        comment: comment.trim(),
      });
      setComment('');
      showToast({ tone: 'success', title: 'Conflict ignored with audit comment' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Conflict could not be ignored',
        message: getApiErrorMessage(error, 'Try again.'),
      });
    }
  };

  const assign = async (): Promise<void> => {
    if (!conflict || !assignee.trim()) return;
    try {
      await mutations.assign.mutateAsync({
        conflictId: conflict.id,
        payload: {
          userId: assignee.trim(),
          ...(comment.trim() ? { comment: comment.trim() } : {}),
        },
      });
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
      <Link
        to="/documents/sharepoint-conflicts"
        className="inline-flex items-center gap-2 text-xs font-semibold text-blue-700"
      >
        <ArrowLeft className="size-4" aria-hidden="true" /> Back to conflicts
      </Link>
      <MasterDataPageHeader
        eyebrow="Documents"
        title="SharePoint Conflict Detail"
        description="Compare local and remote state before choosing an audited resolution. Existing business revision history is preserved."
      />
      {query.isLoading && <Phase8Loading label="Loading SharePoint conflict" />}
      {query.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(query.error, 'Conflict could not be loaded.')}
          onRetry={() => void query.refetch()}
        />
      )}
      {conflict && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label="Document" value={conflict.documentCode ?? '—'} />
            <Metric label="Revision" value={conflict.revisionCode ?? '—'} />
            <Metric label="Type" value={conflict.conflictType.replaceAll('_', ' ')} />
            <Metric
              label="Status"
              value={<Phase10StatusBadge status={conflict.status} />}
            />
            <Metric label="Detected" value={formatDateTime(conflict.detectedAt)} />
            <Metric label="Assigned To" value={conflict.assignedTo ?? 'Unassigned'} />
            <Metric
              label="Resolution"
              value={conflict.resolution?.replaceAll('_', ' ') ?? 'Pending'}
            />
            <Metric
              label="Resolved At"
              value={conflict.resolvedAt ? formatDateTime(conflict.resolvedAt) : '—'}
            />
          </div>
          <div className="grid gap-5 lg:grid-cols-2">
            <VersionPanel
              title="Local version"
              snapshot={conflict.localVersion}
              tone="blue"
            />
            <VersionPanel
              title="Remote SharePoint version"
              snapshot={conflict.remoteVersion}
              tone="violet"
            />
          </div>
          <section className="rounded-3xl border border-slate-200 bg-white p-6">
            <h2 className="text-sm font-semibold text-slate-950">Conflict History</h2>
            <ol className="mt-4 space-y-3 text-xs text-slate-600">
              <li>
                {formatDateTime(conflict.detectedAt)} · Conflict detected by sync job{' '}
                {conflict.syncJobId}.
              </li>
              {conflict.assignedTo && <li>Assigned to {conflict.assignedTo}.</li>}
              {conflict.resolvedAt && (
                <li>
                  {formatDateTime(conflict.resolvedAt)} ·{' '}
                  {conflict.resolution?.replaceAll('_', ' ')} by{' '}
                  {conflict.resolvedBy ?? 'system'}.
                </li>
              )}
              {conflict.resolutionComment && (
                <li>Comment: {conflict.resolutionComment}</li>
              )}
            </ol>
          </section>
          {actionable && (
            <section className="rounded-3xl border border-amber-200 bg-amber-50 p-6">
              <h2 className="text-sm font-semibold text-amber-950">Resolution</h2>
              <p className="mt-1 text-xs leading-5 text-amber-800">
                KEEP_REMOTE creates local file history; KEEP_LOCAL uploads a new remote
                version; KEEP_BOTH creates a safe copy. A comment is mandatory.
              </p>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <label className="text-xs font-semibold text-slate-700">
                  Resolution option
                  <select
                    value={resolution}
                    onChange={(event) =>
                      setResolution(event.target.value as SharePointConflictResolution)
                    }
                    className={`mt-1.5 ${phase10InputClass}`}
                  >
                    {[
                      'KEEP_LOCAL',
                      'KEEP_REMOTE',
                      'KEEP_BOTH',
                      'MERGE_METADATA',
                      'IGNORE_REMOTE_CHANGE',
                      'IGNORE_LOCAL_CHANGE',
                    ].map((value) => (
                      <option key={value} value={value}>
                        {value.replaceAll('_', ' ')}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-xs font-semibold text-slate-700">
                  Assign to user ID
                  <div className="mt-1.5 flex gap-2">
                    <input
                      value={assignee}
                      onChange={(event) => setAssignee(event.target.value)}
                      className={phase10InputClass}
                    />
                    <button
                      type="button"
                      disabled={!assignee.trim() || mutations.assign.isPending}
                      onClick={() => void assign()}
                      className="inline-flex min-h-10 shrink-0 items-center gap-2 rounded-xl border border-slate-300 px-3 text-xs font-semibold disabled:opacity-50"
                    >
                      <UserRound className="size-4" aria-hidden="true" /> Assign
                    </button>
                  </div>
                </label>
                <label className="text-xs font-semibold text-slate-700 sm:col-span-2">
                  Resolution comment
                  <textarea
                    value={comment}
                    onChange={(event) => setComment(event.target.value)}
                    rows={4}
                    className={`mt-1.5 ${phase10TextareaClass}`}
                  />
                </label>
                {comment.trim().length > 0 && comment.trim().length < 5 && (
                  <p role="alert" className="text-xs text-rose-700 sm:col-span-2">
                    Enter at least 5 characters.
                  </p>
                )}
              </div>
              <div className="mt-5 flex flex-wrap justify-end gap-2">
                <button
                  type="button"
                  disabled={comment.trim().length < 5 || mutations.ignore.isPending}
                  onClick={() => void ignore()}
                  className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-amber-300 bg-white px-4 text-xs font-semibold text-amber-800 disabled:opacity-50"
                >
                  <CircleSlash className="size-4" aria-hidden="true" /> Ignore
                </button>
                <button
                  type="button"
                  disabled={comment.trim().length < 5 || mutations.resolve.isPending}
                  onClick={() => void resolve()}
                  className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-blue-700 px-4 text-xs font-semibold text-white disabled:opacity-50"
                >
                  <CheckCircle2 className="size-4" aria-hidden="true" /> Resolve
                  Conflict
                </button>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function VersionPanel({
  snapshot,
  title,
  tone,
}: {
  title: string;
  snapshot: ConflictVersionSnapshot;
  tone: 'blue' | 'violet';
}) {
  const fields: [string, ReactNode][] = [
    ['Filename', snapshot.filename ?? '—'],
    ['Path', snapshot.path ?? '—'],
    ['SHA-256 / eTag', snapshot.sha256Hash ?? snapshot.etag ?? '—'],
    ['File size', snapshot.size?.toLocaleString() ?? '—'],
    ['Modified at', snapshot.modifiedAt ? formatDateTime(snapshot.modifiedAt) : '—'],
    ['Modified by', snapshot.modifiedBy ?? '—'],
  ];
  return (
    <section
      className={`rounded-3xl border p-6 ${tone === 'blue' ? 'border-blue-200 bg-blue-50' : 'border-violet-200 bg-violet-50'}`}
    >
      <h2 className="text-sm font-semibold text-slate-950">{title}</h2>
      <dl className="mt-4 grid gap-4 sm:grid-cols-2">
        {fields.map(([label, value]) => (
          <div key={label}>
            <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              {label}
            </dt>
            <dd className="mt-1 break-all text-xs font-medium text-slate-800">
              {value}
            </dd>
          </div>
        ))}
      </dl>
      <div className="mt-5">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
          Metadata
        </p>
        <pre className="mt-2 max-h-56 overflow-auto rounded-xl bg-white/80 p-3 text-[11px] text-slate-700">
          {JSON.stringify(snapshot.metadata ?? {}, null, 2)}
        </pre>
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
        {label}
      </p>
      <div className="mt-2 text-sm font-semibold text-slate-900">{value}</div>
    </div>
  );
}
