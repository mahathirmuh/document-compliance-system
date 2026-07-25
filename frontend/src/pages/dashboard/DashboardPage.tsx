import {
  ArrowUpRight,
  BadgeCheck,
  Boxes,
  CircleUserRound,
  LockKeyhole,
  ShieldCheck,
} from 'lucide-react';
import { Link } from 'react-router';

import { HealthStatusCard } from '../../components/common/HealthStatusCard';
import { appConfig } from '../../config/app';
import { useAuthStore } from '../../store/authStore';
import { formatRole } from '../../utils/formatters';

export function DashboardPage() {
  const user = useAuthStore((state) => state.user);

  if (!user) {
    return null;
  }

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-3xl border border-blue-200/60 bg-gradient-to-br from-blue-700 via-blue-800 to-slate-950 px-6 py-8 text-white shadow-panel sm:px-8 sm:py-10">
        <div
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_82%_18%,rgba(125,211,252,0.26),transparent_28%)]"
          aria-hidden="true"
        />
        <div className="relative max-w-3xl">
          <span className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-1.5 text-xs font-semibold text-blue-100">
            <BadgeCheck className="size-3.5" aria-hidden="true" />
            Authentication active
          </span>
          <h1 className="mt-5 text-balance text-3xl font-semibold tracking-[-0.035em] sm:text-4xl">
            Welcome, {user.name}
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-blue-100/80 sm:text-base">
            Your secure Document Compliance workspace is ready. Access is controlled by
            the permissions assigned to your account.
          </p>
        </div>
      </section>

      <section aria-labelledby="session-overview-title">
        <div className="mb-4 flex items-end justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-700">
              Current session
            </p>
            <h2
              id="session-overview-title"
              className="mt-1 text-xl font-semibold tracking-tight text-slate-950"
            >
              Access overview
            </h2>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <OverviewCard
            icon={LockKeyhole}
            label="Authentication"
            value="Active"
            detail="Your identity has been verified"
            tone="emerald"
          />
          <OverviewCard
            icon={CircleUserRound}
            label="Assigned role"
            value={formatRole(user.role)}
            detail={user.email}
            tone="blue"
          />
          <OverviewCard
            icon={ShieldCheck}
            label="Application version"
            value={`v${appConfig.version}`}
            detail="Phase 4 document register release"
            tone="slate"
          />
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,0.9fr)_minmax(24rem,0.65fr)]">
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-7">
          <div className="flex items-start gap-4">
            <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-blue-50 text-blue-700">
              <Boxes className="size-5" aria-hidden="true" />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.15em] text-slate-500">
                Workspace readiness
              </p>
              <h2 className="mt-2 text-lg font-semibold text-slate-950">
                Document Register is ready
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
                Authorized users can maintain document metadata, revisions, archive
                records, and spreadsheet-based register imports while Master Data
                remains available as the source of controlled options.
              </p>
            </div>
          </div>
        </div>

        <div>
          <HealthStatusCard />
          <Link
            to="/system-status"
            className="mt-3 inline-flex items-center gap-1.5 rounded-lg px-1 py-1 text-xs font-semibold text-blue-700 transition hover:text-blue-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
          >
            Open full system status
            <ArrowUpRight className="size-3.5" aria-hidden="true" />
          </Link>
        </div>
      </section>
    </div>
  );
}

interface OverviewCardProps {
  icon: typeof LockKeyhole;
  label: string;
  value: string;
  detail: string;
  tone: 'blue' | 'emerald' | 'slate';
}

const cardTones = {
  blue: 'bg-blue-50 text-blue-700',
  emerald: 'bg-emerald-50 text-emerald-700',
  slate: 'bg-slate-100 text-slate-700',
} as const;

function OverviewCard({ detail, icon: Icon, label, tone, value }: OverviewCardProps) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className={`grid size-10 place-items-center rounded-xl ${cardTones[tone]}`}>
        <Icon className="size-4.5" strokeWidth={1.9} aria-hidden="true" />
      </div>
      <p className="mt-4 text-xs font-medium text-slate-500">{label}</p>
      <p className="mt-1 truncate text-base font-semibold text-slate-950">{value}</p>
      <p className="mt-1 truncate text-xs text-slate-500">{detail}</p>
    </article>
  );
}
