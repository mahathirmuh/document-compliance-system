import { FileText, Gauge, ScanText, TriangleAlert } from 'lucide-react';

import { formatConfidence } from './ocrDisplay';
import type { OCRSummary } from '../../types/ocr';

export function OCRSummaryCards({ summary }: { summary: OCRSummary }) {
  const items = [
    {
      label: 'Pages Requested',
      value: summary.pageCountRequested.toLocaleString(),
      icon: FileText,
    },
    {
      label: 'Pages Processed',
      value: summary.pageCountProcessed.toLocaleString(),
      icon: ScanText,
    },
    {
      label: 'Pages Failed',
      value: summary.pageCountFailed.toLocaleString(),
      icon: TriangleAlert,
    },
    {
      label: 'OCR Blocks',
      value: summary.totalBlocks.toLocaleString(),
      icon: ScanText,
    },
    {
      label: 'Characters',
      value: summary.totalCharacters.toLocaleString(),
      icon: FileText,
    },
    {
      label: 'Average OCR Confidence',
      value: formatConfidence(summary.averageConfidence),
      icon: Gauge,
    },
    {
      label: 'Low-Confidence Blocks',
      value: summary.lowConfidenceBlocks.toLocaleString(),
      icon: TriangleAlert,
    },
  ] as const;

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <article
            key={item.label}
            className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
          >
            <div className="flex items-center gap-2 text-slate-500">
              <Icon className="size-4" aria-hidden="true" />
              <p className="text-[10px] font-semibold uppercase tracking-wide">
                {item.label}
              </p>
            </div>
            <p className="mt-3 text-xl font-semibold text-slate-950">{item.value}</p>
          </article>
        );
      })}
    </div>
  );
}
