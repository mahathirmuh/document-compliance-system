import { AlertTriangle } from 'lucide-react';

export function ExtractionWarningList({ warnings }: { warnings: readonly string[] }) {
  if (warnings.length === 0) {
    return null;
  }
  return (
    <section className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-amber-950">
        <AlertTriangle className="size-4" aria-hidden="true" />
        Extraction warnings
      </div>
      <ul className="mt-3 space-y-2 text-xs leading-5 text-amber-900">
        {warnings.map((warning, index) => (
          <li key={`${index}-${warning}`} className="flex gap-2">
            <span aria-hidden="true">•</span>
            <span>{warning}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
