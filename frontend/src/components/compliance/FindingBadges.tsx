import type { FindingSeverity, FindingStatus } from '../../types/finding';

const severityStyles: Record<FindingSeverity, string> = {
  CRITICAL: 'border-rose-300 bg-rose-100 text-rose-900',
  MAJOR: 'border-orange-200 bg-orange-50 text-orange-800',
  MINOR: 'border-amber-200 bg-amber-50 text-amber-800',
  INFORMATION: 'border-blue-200 bg-blue-50 text-blue-800',
};

const statusStyles: Record<FindingStatus, string> = {
  OPEN: 'bg-rose-50 text-rose-700',
  IN_REVIEW: 'bg-violet-50 text-violet-700',
  RESOLVED: 'bg-emerald-50 text-emerald-700',
  CLOSED: 'bg-slate-100 text-slate-700',
  FALSE_POSITIVE: 'bg-cyan-50 text-cyan-700',
  ACCEPTED_RISK: 'bg-amber-50 text-amber-700',
  REOPENED: 'bg-orange-50 text-orange-700',
};

export function FindingSeverityBadge({ severity }: { severity: FindingSeverity }) {
  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide ${severityStyles[severity]}`}
    >
      {severity}
    </span>
  );
}

export function FindingStatusBadge({ status }: { status: FindingStatus }) {
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${statusStyles[status]}`}
    >
      {status.replaceAll('_', ' ')}
    </span>
  );
}
