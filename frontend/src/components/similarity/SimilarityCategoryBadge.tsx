import type { ConsistencyStatus, SimilarityCategory } from '../../types/similarity';

const categoryStyles: Record<SimilarityCategory, string> = {
  HIGH: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  ACCEPTABLE: 'border-blue-200 bg-blue-50 text-blue-800',
  NEEDS_REVIEW: 'border-amber-200 bg-amber-50 text-amber-800',
  LOW: 'border-rose-200 bg-rose-50 text-rose-800',
  NOT_EVALUATED: 'border-slate-200 bg-slate-100 text-slate-600',
};

const consistencyStyles: Record<ConsistencyStatus, string> = {
  MATCH: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  MISMATCH: 'border-rose-200 bg-rose-50 text-rose-800',
  AMBIGUOUS: 'border-amber-200 bg-amber-50 text-amber-800',
  NOT_APPLICABLE: 'border-slate-200 bg-slate-100 text-slate-600',
  POTENTIALLY_EQUIVALENT: 'border-blue-200 bg-blue-50 text-blue-800',
  POSSIBLE_NEGATION_MISMATCH: 'border-amber-200 bg-amber-50 text-amber-800',
};

export function SimilarityCategoryBadge({
  category,
}: {
  category: SimilarityCategory;
}) {
  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold ${categoryStyles[category]}`}
    >
      {category.replaceAll('_', ' ')}
    </span>
  );
}

export function ConsistencyBadge({
  label,
  status,
}: {
  label?: string;
  status: ConsistencyStatus;
}) {
  return (
    <span
      title={label ? `${label}: ${status.replaceAll('_', ' ')}` : undefined}
      className={`inline-flex min-w-8 justify-center rounded-full border px-2 py-1 text-[10px] font-semibold ${consistencyStyles[status]}`}
    >
      {status === 'MATCH'
        ? 'OK'
        : status === 'NOT_APPLICABLE'
          ? 'N/A'
          : status === 'AMBIGUOUS' ||
              status === 'POTENTIALLY_EQUIVALENT' ||
              status === 'POSSIBLE_NEGATION_MISMATCH'
            ? 'CHECK'
            : 'ISSUE'}
    </span>
  );
}
