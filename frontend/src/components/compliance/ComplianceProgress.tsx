import type { ComplianceJobStatus } from '../../types/compliance';

export function ComplianceProgress({
  currentStage,
  progress,
  status,
}: {
  status: ComplianceJobStatus;
  progress: number;
  currentStage: string | null;
}) {
  const safeProgress = Math.max(0, Math.min(100, progress));
  return (
    <div className="min-w-44" aria-label={`Validation progress ${safeProgress}%`}>
      <div className="flex items-center justify-between gap-3 text-[10px] font-semibold text-slate-600">
        <span className="truncate">
          {currentStage?.replaceAll('_', ' ') ?? status.replaceAll('_', ' ')}
        </span>
        <span>{safeProgress}%</span>
      </div>
      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full rounded-full bg-blue-600 transition-[width] duration-500"
          style={{ width: `${safeProgress}%` }}
        />
      </div>
    </div>
  );
}
