import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';

interface DocumentSummaryCardProps {
  icon: LucideIcon;
  label: string;
  value: ReactNode;
}

export function DocumentSummaryCard({
  icon: Icon,
  label,
  value,
}: DocumentSummaryCardProps) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-slate-100 text-slate-700">
          <Icon className="size-4" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-500">
            {label}
          </p>
          <div className="mt-1 truncate text-sm font-semibold text-slate-950">
            {value}
          </div>
        </div>
      </div>
    </article>
  );
}
