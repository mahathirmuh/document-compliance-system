import { Database } from 'lucide-react';

interface EmptyMasterDataStateProps {
  title?: string;
  description?: string;
}

export function EmptyMasterDataState({
  description = 'Try changing the search or filters, or create the first record.',
  title = 'No records found',
}: EmptyMasterDataStateProps) {
  return (
    <div className="flex min-h-52 flex-col items-center justify-center px-6 py-10 text-center">
      <div className="grid size-12 place-items-center rounded-2xl bg-slate-100 text-slate-500">
        <Database className="size-5" aria-hidden="true" />
      </div>
      <p className="mt-4 text-sm font-semibold text-slate-900">{title}</p>
      <p className="mt-1 max-w-md text-xs leading-5 text-slate-500">{description}</p>
    </div>
  );
}
