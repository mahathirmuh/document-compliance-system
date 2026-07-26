import { AlertTriangle, Gauge } from 'lucide-react';

import { ComplianceStatusBadge } from './ComplianceStatusBadge';
import type {
  ComplianceScoreBreakdown,
  ComplianceStatus,
} from '../../types/compliance';

const componentLabels: Record<
  Exclude<
    keyof ComplianceScoreBreakdown,
    'penalties' | 'scoreCap' | 'scoreCapReason' | 'finalScore'
  >,
  string
> = {
  documentCode: 'Document code',
  languagePresence: 'Language presence',
  languageCoverage: 'Language coverage',
  sectionCompleteness: 'Section completeness',
  languageOrder: 'Language order',
  translationGroups: 'Translation groups',
  tableCompleteness: 'Table completeness',
};

const scoreKeys = Object.keys(componentLabels) as Array<keyof typeof componentLabels>;

export function ComplianceScorePanel({
  breakdown,
  reasons = [],
  score,
  status,
}: {
  breakdown: ComplianceScoreBreakdown | null;
  reasons?: readonly string[];
  score: number | null;
  status: ComplianceStatus;
}) {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
            Compliance score
          </p>
          <div className="mt-3 flex items-end gap-3">
            <Gauge className="mb-1 size-7 text-blue-700" aria-hidden="true" />
            <span className="text-4xl font-semibold tracking-tight text-slate-950">
              {score === null ? '—' : score.toFixed(1)}
            </span>
            <span className="mb-1 text-sm font-medium text-slate-500">/ 100</span>
          </div>
          <div className="mt-3">
            <ComplianceStatusBadge status={status} />
          </div>
        </div>
        {breakdown && (
          <div className="grid flex-1 gap-3 sm:grid-cols-2 xl:max-w-4xl xl:grid-cols-4">
            {scoreKeys.map((key) => {
              const component = breakdown[key];
              const percentage =
                component.maximum > 0
                  ? Math.round((component.earned / component.maximum) * 100)
                  : 0;
              return (
                <div key={key} className="rounded-2xl bg-slate-50 p-3">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                    {componentLabels[key]}
                  </p>
                  <p className="mt-2 text-sm font-semibold text-slate-900">
                    {component.earned.toFixed(1)} / {component.maximum.toFixed(1)}
                  </p>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200">
                    <div
                      className="h-full rounded-full bg-blue-600"
                      style={{ width: `${Math.max(0, Math.min(100, percentage))}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
      {breakdown && (
        <div className="mt-5 flex flex-wrap gap-2 border-t border-slate-100 pt-4 text-xs text-slate-600">
          <span className="rounded-lg bg-slate-50 px-2.5 py-1.5">
            Major penalties: {breakdown.penalties.major}
          </span>
          <span className="rounded-lg bg-slate-50 px-2.5 py-1.5">
            Minor penalties: {breakdown.penalties.minor}
          </span>
          {breakdown.scoreCap !== undefined && breakdown.scoreCap !== null && (
            <span className="rounded-lg bg-rose-50 px-2.5 py-1.5 font-semibold text-rose-700">
              Score cap: {breakdown.scoreCap}
              {breakdown.scoreCapReason ? ` — ${breakdown.scoreCapReason}` : ''}
            </span>
          )}
        </div>
      )}
      {(status === 'NEEDS_REVIEW' || status === 'NOT_EVALUATED') &&
        reasons.length > 0 && (
          <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-4">
            <p className="flex items-center gap-2 text-xs font-semibold text-amber-900">
              <AlertTriangle className="size-4" aria-hidden="true" />
              {status === 'NOT_EVALUATED'
                ? 'Validation prerequisites are incomplete'
                : 'Manual review is required'}
            </p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-xs leading-5 text-amber-800">
              {reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </div>
        )}
    </section>
  );
}
