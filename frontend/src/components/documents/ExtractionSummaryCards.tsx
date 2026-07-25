import {
  BookOpenText,
  FileStack,
  Grid3X3,
  Layers3,
  ScanText,
  Sheet,
  Table2,
  TextCursorInput,
  WholeWord,
} from 'lucide-react';

import type { ExtractionResultSummary } from '../../types/extraction';

export function ExtractionSummaryCards({
  summary,
}: {
  summary: ExtractionResultSummary;
}) {
  const cards = [
    ...(summary.totalPages > 0
      ? [{ label: 'Pages', value: summary.totalPages, icon: FileStack }]
      : []),
    ...(summary.totalSheets > 0
      ? [{ label: 'Worksheets', value: summary.totalSheets, icon: Sheet }]
      : []),
    ...(summary.totalParagraphs > 0
      ? [
          {
            label: 'Paragraphs',
            value: summary.totalParagraphs,
            icon: BookOpenText,
          },
        ]
      : []),
    ...(summary.totalTables > 0
      ? [{ label: 'Tables', value: summary.totalTables, icon: Table2 }]
      : []),
    ...(summary.totalCells > 0
      ? [{ label: 'Cells', value: summary.totalCells, icon: Grid3X3 }]
      : []),
    { label: 'Blocks', value: summary.totalBlocks, icon: Layers3 },
    {
      label: 'Characters',
      value: summary.totalCharacters,
      icon: TextCursorInput,
    },
    { label: 'Words', value: summary.totalWords, icon: WholeWord },
    {
      label: 'OCR Required',
      value: summary.requiresOcr ? 'Yes' : 'No',
      icon: ScanText,
    },
  ];

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5">
      {cards.map(({ icon: Icon, label, value }) => (
        <div
          key={label}
          className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                {label}
              </p>
              <p className="mt-2 text-xl font-semibold text-slate-950">
                {typeof value === 'number' ? value.toLocaleString() : value}
              </p>
            </div>
            <span className="grid size-9 place-items-center rounded-xl bg-blue-50 text-blue-700">
              <Icon className="size-4" aria-hidden="true" />
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
