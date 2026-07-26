import type { ComplianceJobStatus } from '../../types/compliance';
import { isActiveComplianceJobStatus } from '../../types/compliance';

export function ComplianceJobStatusBadge({ status }: { status: ComplianceJobStatus }) {
  const classes =
    status === 'COMPLETED'
      ? 'bg-emerald-50 text-emerald-700'
      : status === 'PARTIALLY_COMPLETED'
        ? 'bg-amber-50 text-amber-700'
        : status === 'FAILED'
          ? 'bg-rose-50 text-rose-700'
          : status === 'CANCELLED'
            ? 'bg-slate-100 text-slate-600'
            : 'bg-blue-50 text-blue-700';
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${classes}`}
    >
      {isActiveComplianceJobStatus(status) && (
        <span
          className="mr-1.5 mt-0.5 size-1.5 animate-pulse rounded-full bg-current"
          aria-hidden="true"
        />
      )}
      {status.replaceAll('_', ' ')}
    </span>
  );
}
