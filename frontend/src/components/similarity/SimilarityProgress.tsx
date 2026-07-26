import type { SimilarityJobStatus } from '../../types/similarity';

export function SimilarityProgress({
  currentStage,
  progress,
  status,
}: {
  currentStage: string | null;
  progress: number;
  status: SimilarityJobStatus;
}) {
  const bounded = Math.max(0, Math.min(100, progress));
  return (
    <div className="w-36" aria-label={`Similarity progress ${bounded}%`}>
      <div className="flex items-center justify-between text-[10px] font-semibold text-slate-600">
        <span>{bounded}%</span>
        <span>{status.replaceAll('_', ' ')}</span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-200">
        <span
          className="block h-full rounded-full bg-violet-600 transition-[width]"
          style={{ width: `${bounded}%` }}
        />
      </div>
      <p className="mt-1 truncate text-[9px] text-slate-500">
        {currentStage?.replaceAll('_', ' ') ?? 'Waiting'}
      </p>
    </div>
  );
}
