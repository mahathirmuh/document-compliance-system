import type { ExtractionJobStatus, ExtractionRunStatus } from '../../types/extraction';

import { extractionStatusLabel } from './extractionDisplay';

type DisplayStatus = ExtractionJobStatus | ExtractionRunStatus;

const statusStyles: Record<DisplayStatus, string> = {
  QUEUED: 'bg-slate-100 text-slate-700 ring-slate-200',
  INSPECTING: 'bg-sky-50 text-sky-700 ring-sky-200',
  EXTRACTING: 'bg-blue-50 text-blue-700 ring-blue-200',
  NORMALISING: 'bg-indigo-50 text-indigo-700 ring-indigo-200',
  PERSISTING: 'bg-violet-50 text-violet-700 ring-violet-200',
  COMPLETED: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  PARTIALLY_COMPLETED: 'bg-amber-50 text-amber-800 ring-amber-200',
  OCR_REQUIRED: 'bg-orange-50 text-orange-800 ring-orange-200',
  FAILED: 'bg-rose-50 text-rose-700 ring-rose-200',
  CANCEL_REQUESTED: 'bg-amber-50 text-amber-800 ring-amber-200',
  CANCELLED: 'bg-slate-100 text-slate-600 ring-slate-200',
};

export function ExtractionStatusBadge({ status }: { status: DisplayStatus }) {
  return (
    <span
      className={`inline-flex whitespace-nowrap rounded-full px-2.5 py-1 text-[10px] font-semibold ring-1 ring-inset ${statusStyles[status]}`}
    >
      {extractionStatusLabel(status)}
    </span>
  );
}
