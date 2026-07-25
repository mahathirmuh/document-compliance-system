import { Archive } from 'lucide-react';

export function ArchivedBadge() {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[10px] font-semibold text-amber-800">
      <Archive className="size-3" aria-hidden="true" />
      Archived
    </span>
  );
}
