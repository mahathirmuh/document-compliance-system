interface DocumentStatusBadgeProps {
  code?: string | null;
  name?: string | null;
}

const getTone = (code: string): string => {
  const normalized = code.toUpperCase();
  if (['EFFECTIVE', 'APPROVED', 'ACTIVE'].includes(normalized)) {
    return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  }
  if (['OBSOLETE', 'SUPERSEDED', 'REJECTED'].includes(normalized)) {
    return 'border-rose-200 bg-rose-50 text-rose-700';
  }
  if (['DRAFT', 'INITIAL'].includes(normalized)) {
    return 'border-slate-200 bg-slate-100 text-slate-700';
  }
  return 'border-blue-200 bg-blue-50 text-blue-700';
};

export function DocumentStatusBadge({ code, name }: DocumentStatusBadgeProps) {
  if (!code && !name) {
    return <span className="text-xs text-slate-400">No status</span>;
  }

  return (
    <span
      className={`inline-flex max-w-40 items-center truncate rounded-full border px-2.5 py-1 text-[10px] font-semibold ${getTone(code ?? name ?? '')}`}
      title={name ?? code ?? undefined}
    >
      {name || code}
    </span>
  );
}
