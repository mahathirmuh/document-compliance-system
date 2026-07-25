import type { ExtractionJobStatus } from '../../types/extraction';
import { extractionStatusLabel } from './extractionDisplay';

export function ExtractionProgress({
  currentStage,
  progress,
  status,
}: {
  progress: number;
  status: ExtractionJobStatus;
  currentStage?: string | null;
}) {
  const safeProgress = Math.min(100, Math.max(0, Math.round(progress)));
  return (
    <div className="min-w-40">
      <div className="mb-1.5 flex items-center justify-between gap-3 text-[10px] font-medium text-slate-600">
        <span className="truncate">
          {currentStage || extractionStatusLabel(status)}
        </span>
        <span>{safeProgress}%</span>
      </div>
      <div
        role="progressbar"
        aria-label="Extraction progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={safeProgress}
        className="h-2 overflow-hidden rounded-full bg-slate-100"
      >
        <div
          className="h-full rounded-full bg-blue-600 transition-[width] duration-500"
          style={{ width: `${safeProgress}%` }}
        />
      </div>
    </div>
  );
}
