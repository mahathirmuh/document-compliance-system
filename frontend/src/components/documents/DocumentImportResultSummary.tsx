import type {
  DocumentImportPreview,
  DocumentImportResult,
} from '../../types/documentImport';

interface DocumentImportResultSummaryProps {
  preview?: DocumentImportPreview;
  result?: DocumentImportResult;
}

const toneClasses = {
  slate: 'bg-slate-50 text-slate-700',
  emerald: 'bg-emerald-50 text-emerald-700',
  blue: 'bg-blue-50 text-blue-700',
  amber: 'bg-amber-50 text-amber-700',
  rose: 'bg-rose-50 text-rose-700',
} as const;

export function DocumentImportResultSummary({
  preview,
  result,
}: DocumentImportResultSummaryProps) {
  const metrics = result
    ? [
        ['Total Rows', result.totalRows, 'slate'],
        ['Documents Created', result.documentsCreated, 'emerald'],
        ['Revisions Added', result.revisionsAdded, 'blue'],
        ['Metadata Updated', result.metadataUpdated, 'blue'],
        ['Duplicates Skipped', result.duplicatesSkipped, 'amber'],
        ['Invalid Skipped', result.invalidSkipped, 'amber'],
        ['Failed', result.failed, 'rose'],
      ]
    : preview
      ? [
          ['Total Rows', preview.totalRows, 'slate'],
          ['Valid Create', preview.validCreateRows, 'emerald'],
          ['Valid Add Revision', preview.validAddRevisionRows, 'blue'],
          ['Warnings', preview.warningRows, 'amber'],
          ['Duplicates', preview.duplicateRows, 'amber'],
          ['Invalid', preview.invalidRows, 'rose'],
        ]
      : [];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-7">
      {metrics.map(([label, value, tone]) => (
        <div
          key={String(label)}
          className={`rounded-xl p-3 ${toneClasses[tone as keyof typeof toneClasses]}`}
        >
          <p className="text-[10px] font-semibold uppercase tracking-wide opacity-70">
            {label}
          </p>
          <p className="mt-1 text-xl font-semibold">{value}</p>
        </div>
      ))}
    </div>
  );
}
