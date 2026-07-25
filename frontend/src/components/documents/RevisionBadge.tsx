import { GitBranch } from 'lucide-react';

interface RevisionBadgeProps {
  revisionCode?: string | null;
  isCurrent?: boolean;
}

export function RevisionBadge({ isCurrent = false, revisionCode }: RevisionBadgeProps) {
  if (!revisionCode) {
    return <span className="text-xs font-medium text-slate-400">No Revision</span>;
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[10px] font-semibold ${
        isCurrent
          ? 'border-blue-200 bg-blue-50 text-blue-700'
          : 'border-slate-200 bg-slate-50 text-slate-700'
      }`}
    >
      <GitBranch className="size-3" aria-hidden="true" />
      {revisionCode}
    </span>
  );
}
