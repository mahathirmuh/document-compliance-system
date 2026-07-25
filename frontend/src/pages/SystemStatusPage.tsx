import { Activity, ArrowLeft, ShieldCheck } from 'lucide-react';
import { Link } from 'react-router';

import { HealthStatusCard } from '../components/common/HealthStatusCard';
import { appConfig } from '../config/app';

export function SystemStatusPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div className="relative overflow-hidden bg-slate-950 px-6 py-8 text-white sm:px-8">
          <div
            className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_90%_10%,rgba(59,130,246,.35),transparent_32%)]"
            aria-hidden="true"
          />
          <div className="relative">
            <span className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1.5 text-xs font-semibold text-blue-100">
              <Activity className="size-3.5" aria-hidden="true" />
              Foundation health monitor
            </span>
            <h1 className="mt-5 text-3xl font-semibold tracking-tight">
              System status
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300">
              Live connectivity for the {appConfig.name}. This preserves the Phase 1
              health check and refresh behavior.
            </p>
          </div>
        </div>
        <div className="grid gap-4 p-6 sm:grid-cols-2 sm:p-8">
          <div className="rounded-2xl border border-slate-200 p-5">
            <ShieldCheck className="size-5 text-blue-700" aria-hidden="true" />
            <p className="mt-3 text-xs font-medium text-slate-500">
              Application release
            </p>
            <p className="mt-1 font-semibold text-slate-950">
              Version {appConfig.version}
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 p-5">
            <Activity className="size-5 text-emerald-600" aria-hidden="true" />
            <p className="mt-3 text-xs font-medium text-slate-500">
              Monitoring cadence
            </p>
            <p className="mt-1 font-semibold text-slate-950">Every 30 seconds</p>
          </div>
        </div>
      </section>

      <HealthStatusCard />

      <Link
        to="/dashboard"
        className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-blue-200 hover:text-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
      >
        <ArrowLeft className="size-4" aria-hidden="true" />
        Back to dashboard
      </Link>
    </div>
  );
}
