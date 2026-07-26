import {
  AlertTriangle,
  CheckCircle2,
  CircleOff,
  RefreshCw,
  XCircle,
} from 'lucide-react';

import { getApiErrorMessage } from '../../api/errors';
import {
  Phase8ErrorAlert,
  Phase8Loading,
} from '../../components/compliance/Phase8TableUtilities';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { Phase10StatusBadge } from '../../components/phase10/Phase10Ui';
import { useSystemHealth } from '../../hooks/useSystemHealth';
import type {
  DependencyHealth,
  HealthState,
  WorkerHealth,
} from '../../types/systemHealth';
import { formatDateTime } from '../../utils/formatters';

const iconFor = (state: HealthState) => {
  if (state === 'healthy') return CheckCircle2;
  if (state === 'degraded') return AlertTriangle;
  if (state === 'disabled') return CircleOff;
  return XCircle;
};

const iconTone = (state: HealthState): string => {
  if (state === 'healthy') return 'text-emerald-600';
  if (state === 'degraded') return 'text-amber-600';
  if (state === 'unhealthy') return 'text-rose-600';
  return 'text-slate-500';
};

export function SystemHealthPage() {
  const query = useSystemHealth();
  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <MasterDataPageHeader
          eyebrow="Administration"
          title="System Health"
          description="Cached dependency checks and worker heartbeats without exposing credentials, tokens, connection strings, or stack traces."
        />
        <button
          type="button"
          onClick={() => void query.refetch()}
          disabled={query.isFetching}
          className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 px-4 text-xs font-semibold text-slate-700 disabled:opacity-50"
        >
          <RefreshCw
            className={`size-4 ${query.isFetching ? 'animate-spin' : ''}`}
            aria-hidden="true"
          />
          Refresh
        </button>
      </div>
      {query.isLoading && <Phase8Loading label="Loading system health" />}
      {query.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            query.error,
            'System health could not be loaded.',
          )}
          onRetry={() => void query.refetch()}
        />
      )}
      {query.data && (
        <>
          <section className="flex flex-col gap-4 rounded-3xl border border-slate-200 bg-white p-6 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Overall status
              </p>
              <div className="mt-2">
                <Phase10StatusBadge status={query.data.status} />
              </div>
            </div>
            <div className="text-xs">
              <p className="text-slate-500">Checked</p>
              <p className="mt-1 font-semibold text-slate-900">
                {formatDateTime(query.data.checkedAt)}
              </p>
            </div>
          </section>

          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-slate-950">Dependencies</h2>
            {query.data.dependencies.length === 0 ? (
              <p className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-500">
                No dependency checks are registered.
              </p>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {query.data.dependencies.map((dependency) => (
                  <DependencyCard key={dependency.name} dependency={dependency} />
                ))}
              </div>
            )}
          </section>

          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-slate-950">Worker Heartbeats</h2>
            {query.data.workers.length === 0 ? (
              <p className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-500">
                No worker heartbeats are registered.
              </p>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {query.data.workers.map((worker) => (
                  <WorkerCard
                    key={`${worker.workerName}:${worker.queueName}`}
                    worker={worker}
                  />
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}

function DependencyCard({ dependency }: { dependency: DependencyHealth }) {
  const Icon = iconFor(dependency.status);
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="grid size-9 place-items-center rounded-xl bg-slate-50">
            <Icon
              className={`size-5 ${iconTone(dependency.status)}`}
              aria-hidden="true"
            />
          </span>
          <h3 className="text-sm font-semibold capitalize text-slate-950">
            {dependency.name.replaceAll('_', ' ')}
          </h3>
        </div>
        <Phase10StatusBadge status={dependency.status} />
      </div>
      <p className="mt-4 min-h-10 text-xs leading-5 text-slate-600">
        {dependency.message ??
          (dependency.status === 'disabled'
            ? 'Integration is disabled; this is not a failure.'
            : 'No additional health message.')}
      </p>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-[11px]">
        <div>
          <dt className="text-slate-400">Latency</dt>
          <dd className="mt-1 font-semibold text-slate-700">
            {dependency.latencyMs === null
              ? '—'
              : `${Math.round(dependency.latencyMs)} ms`}
          </dd>
        </div>
        <div>
          <dt className="text-slate-400">Checked</dt>
          <dd className="mt-1 font-semibold text-slate-700">
            {formatDateTime(dependency.checkedAt)}
          </dd>
        </div>
      </dl>
    </article>
  );
}

function WorkerCard({ worker }: { worker: WorkerHealth }) {
  const Icon = iconFor(worker.status);
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="grid size-9 place-items-center rounded-xl bg-slate-50">
            <Icon className={`size-5 ${iconTone(worker.status)}`} aria-hidden="true" />
          </span>
          <div>
            <h3 className="text-sm font-semibold capitalize text-slate-950">
              {worker.workerName.replaceAll('_', ' ')}
            </h3>
            <p className="text-[11px] text-slate-500">{worker.queueName}</p>
          </div>
        </div>
        <Phase10StatusBadge status={worker.status} />
      </div>
      <dl className="mt-5 grid grid-cols-2 gap-3 text-[11px]">
        <div>
          <dt className="text-slate-400">Last heartbeat</dt>
          <dd className="mt-1 font-semibold text-slate-700">
            {worker.lastHeartbeatAt
              ? formatDateTime(worker.lastHeartbeatAt)
              : 'Not reported'}
          </dd>
        </div>
        <div>
          <dt className="text-slate-400">Heartbeat age</dt>
          <dd className="mt-1 font-semibold text-slate-700">
            {worker.ageSeconds === null
              ? '—'
              : `${Math.round(worker.ageSeconds)} seconds`}
          </dd>
        </div>
      </dl>
    </article>
  );
}
