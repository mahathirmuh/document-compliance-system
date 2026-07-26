import type { ComplianceStatus } from '../../types/compliance';

const statusStyles: Record<ComplianceStatus, string> = {
  COMPLIANT: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  PARTIALLY_COMPLIANT: 'border-amber-200 bg-amber-50 text-amber-800',
  NON_COMPLIANT: 'border-rose-200 bg-rose-50 text-rose-800',
  NEEDS_REVIEW: 'border-violet-200 bg-violet-50 text-violet-800',
  NOT_EVALUATED: 'border-slate-200 bg-slate-100 text-slate-700',
};

const complianceStatusLabels: Record<ComplianceStatus, string> = {
  COMPLIANT: 'Compliant',
  PARTIALLY_COMPLIANT: 'Partially Compliant',
  NON_COMPLIANT: 'Non-Compliant',
  NEEDS_REVIEW: 'Needs Review',
  NOT_EVALUATED: 'Not Evaluated',
};

export function ComplianceStatusBadge({ status }: { status: ComplianceStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${statusStyles[status]}`}
    >
      {complianceStatusLabels[status]}
    </span>
  );
}
