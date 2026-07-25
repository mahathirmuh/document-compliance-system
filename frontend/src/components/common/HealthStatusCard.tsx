import { Check, CircleAlert, Clock3, RefreshCw, Server, Wifi } from 'lucide-react';

import { useHealthCheck } from '../../hooks/useHealthCheck';

const formatCheckTime = (timestamp: number): string =>
  new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(timestamp);

export function HealthStatusCard() {
  const { data, dataUpdatedAt, error, isError, isFetching, isPending, refetch } =
    useHealthCheck();

  const lastChecked =
    dataUpdatedAt > 0 ? formatCheckTime(dataUpdatedAt) : 'Waiting for first response';

  return (
    <section
      className="overflow-hidden rounded-3xl border border-white/70 bg-white/90 shadow-panel backdrop-blur-xl"
      aria-labelledby="backend-status-title"
    >
      <div className="border-b border-slate-100 px-6 py-5 sm:px-7">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="grid size-10 place-items-center rounded-xl bg-slate-950 text-white">
              <Server className="size-5" strokeWidth={1.8} />
            </div>
            <div>
              <h2
                id="backend-status-title"
                className="text-sm font-semibold text-slate-950"
              >
                Backend connection
              </h2>
              <p className="mt-0.5 text-xs text-slate-500">GET /api/v1/health</p>
            </div>
          </div>

          <StatusBadge
            isError={isError}
            isLoading={isPending}
            isRefreshing={isFetching && !isPending}
          />
        </div>
      </div>

      <div className="p-6 sm:p-7" aria-live="polite">
        {isPending ? (
          <LoadingState />
        ) : isError ? (
          <ErrorState
            message={
              error instanceof Error
                ? error.message
                : 'The backend could not be reached.'
            }
          />
        ) : (
          <ConnectedState service={data.service} />
        )}

        <div className="mt-6 grid gap-3 border-t border-slate-100 pt-5 sm:grid-cols-[1fr_auto] sm:items-center">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <Clock3 className="size-3.5" aria-hidden="true" />
            <span>Last checked: {lastChecked}</span>
          </div>
          <button
            type="button"
            onClick={() => void refetch()}
            disabled={isFetching}
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 text-xs font-semibold text-slate-700 shadow-sm transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <RefreshCw
              className={`size-3.5 ${isFetching ? 'animate-spin' : ''}`}
              aria-hidden="true"
            />
            {isFetching ? 'Checking...' : 'Check again'}
          </button>
        </div>
      </div>
    </section>
  );
}

interface StatusBadgeProps {
  isError: boolean;
  isLoading: boolean;
  isRefreshing: boolean;
}

function StatusBadge({ isError, isLoading, isRefreshing }: StatusBadgeProps) {
  if (isLoading) {
    return (
      <span className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-600">
        <span className="size-1.5 animate-pulse rounded-full bg-slate-400" />
        Connecting
      </span>
    );
  }

  if (isError) {
    return (
      <span className="inline-flex items-center gap-2 rounded-full bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-700">
        <span className="size-1.5 rounded-full bg-rose-500" />
        Unavailable
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700">
      <span
        className={`size-1.5 rounded-full bg-emerald-500 ${
          isRefreshing ? 'animate-pulse' : ''
        }`}
      />
      {isRefreshing ? 'Refreshing' : 'Connected'}
    </span>
  );
}

function LoadingState() {
  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3">
        <div className="size-10 animate-pulse rounded-full bg-slate-100" />
        <div className="flex-1 space-y-2 pt-1">
          <div className="h-4 w-40 animate-pulse rounded bg-slate-100" />
          <div className="h-3 w-full max-w-xs animate-pulse rounded bg-slate-100" />
        </div>
      </div>
      <p className="sr-only">Checking backend connection</p>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-3">
      <div className="grid size-10 shrink-0 place-items-center rounded-full bg-rose-50 text-rose-600">
        <CircleAlert className="size-5" aria-hidden="true" />
      </div>
      <div>
        <p className="text-sm font-semibold text-slate-950">Backend unavailable</p>
        <p className="mt-1 text-sm leading-6 text-slate-600">
          {message || 'Check that the API service is running, then try again.'}
        </p>
      </div>
    </div>
  );
}

function ConnectedState({ service }: { service: string }) {
  return (
    <div className="flex items-start gap-3">
      <div className="grid size-10 shrink-0 place-items-center rounded-full bg-emerald-50 text-emerald-600">
        <Check className="size-5" strokeWidth={2.4} aria-hidden="true" />
      </div>
      <div className="min-w-0">
        <p className="text-sm font-semibold text-slate-950">Backend connected</p>
        <p className="mt-1 flex items-center gap-1.5 text-sm leading-6 text-slate-600">
          <Wifi className="size-3.5 shrink-0 text-emerald-600" aria-hidden="true" />
          <span className="truncate">{service}</span>
        </p>
      </div>
    </div>
  );
}
