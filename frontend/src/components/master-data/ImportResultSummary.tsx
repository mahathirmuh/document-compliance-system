import type { ImportPreview, ImportResult } from '../../types/masterData';

interface ImportResultSummaryProps {
  preview?: ImportPreview;
  result?: ImportResult;
}

export function ImportResultSummary({ preview, result }: ImportResultSummaryProps) {
  const metrics = result
    ? [
        ['Total', result.totalRows, 'slate'],
        ['Created', result.created, 'emerald'],
        ['Updated', result.updated, 'blue'],
        ['Skipped', result.skipped, 'amber'],
        ['Failed', result.failed, 'rose'],
      ]
    : preview
      ? [
          ['Total', preview.totalRows, 'slate'],
          ['Valid', preview.validRows, 'emerald'],
          ['Invalid', preview.invalidRows, 'rose'],
          ['Duplicate', preview.duplicateRows, 'amber'],
        ]
      : [];

  const tones: Record<string, string> = {
    slate: 'bg-slate-50 text-slate-700',
    emerald: 'bg-emerald-50 text-emerald-700',
    blue: 'bg-blue-50 text-blue-700',
    amber: 'bg-amber-50 text-amber-700',
    rose: 'bg-rose-50 text-rose-700',
  };

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {metrics.map(([label, value, tone]) => (
        <div key={String(label)} className={`rounded-xl p-3 ${tones[String(tone)]}`}>
          <p className="text-[10px] font-semibold uppercase tracking-wide opacity-70">
            {label}
          </p>
          <p className="mt-1 text-xl font-semibold">{value}</p>
        </div>
      ))}
    </div>
  );
}
