import type { OCRJobStatus } from '../../types/ocr';

import { OCRStatusBadge } from './OCRStatusBadge';

export function OCRProgress({
  currentStage,
  progress,
  status,
}: {
  currentStage: string | null;
  progress: number;
  status: OCRJobStatus;
}) {
  const safeProgress = Math.max(0, Math.min(100, progress));
  return (
    <div className="space-y-2" aria-label={`OCR progress ${safeProgress}%`}>
      <div className="flex items-center justify-between gap-3">
        <OCRStatusBadge status={status} />
        <span className="text-xs font-semibold tabular-nums text-slate-700">
          {safeProgress}%
        </span>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-slate-100"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={safeProgress}
      >
        <div
          className="h-full rounded-full bg-blue-600 transition-[width] duration-300"
          style={{ width: `${safeProgress}%` }}
        />
      </div>
      {currentStage && <p className="text-[11px] text-slate-500">{currentStage}</p>}
    </div>
  );
}
