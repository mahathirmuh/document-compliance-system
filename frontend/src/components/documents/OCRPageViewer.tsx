import { Braces, MapPin, ScanText } from 'lucide-react';

import { OCRConfidenceBadge } from './OCRConfidenceBadge';
import { OCRStatusBadge } from './OCRStatusBadge';
import { formatConfidence, ocrProfileLabels } from './ocrDisplay';
import type { OCRBlock, OCRPageResult } from '../../types/ocr';

export type OCRConfidenceFilter = 'ALL' | 'HIGH' | 'REVIEW' | 'LOW';

const matchesConfidence = (
  confidence: number,
  filter: OCRConfidenceFilter,
  lowConfidenceThreshold: number,
  reviewConfidenceThreshold: number,
): boolean => {
  if (filter === 'HIGH') {
    return confidence >= reviewConfidenceThreshold;
  }
  if (filter === 'REVIEW') {
    return (
      confidence >= lowConfidenceThreshold && confidence < reviewConfidenceThreshold
    );
  }
  if (filter === 'LOW') {
    return confidence < lowConfidenceThreshold;
  }
  return true;
};

export function OCRPageViewer({
  blocks,
  confidenceFilter,
  isLoading,
  lowConfidenceThreshold,
  onConfidenceFilterChange,
  page,
  reviewConfidenceThreshold,
}: {
  page: OCRPageResult;
  blocks: readonly OCRBlock[];
  confidenceFilter: OCRConfidenceFilter;
  isLoading?: boolean;
  lowConfidenceThreshold: number;
  onConfidenceFilterChange: (filter: OCRConfidenceFilter) => void;
  reviewConfidenceThreshold: number;
}) {
  const visibleBlocks = blocks.filter((block) =>
    matchesConfidence(
      block.confidence,
      confidenceFilter,
      lowConfidenceThreshold,
      reviewConfidenceThreshold,
    ),
  );

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-semibold text-slate-950">
            OCR Page {page.pageNumber}
          </h2>
          <OCRStatusBadge status={page.status} />
          <span className="ml-auto text-xs font-semibold text-slate-600">
            {formatConfidence(page.averageConfidence)} average
          </span>
        </div>
        <dl className="mt-4 grid gap-3 text-xs sm:grid-cols-2 xl:grid-cols-5">
          <Metadata label="Profile" value={ocrProfileLabels[page.languageProfile]} />
          <Metadata label="Render" value={`${page.renderDpi} DPI`} />
          <Metadata label="Rotation" value={`${page.rotationApplied}°`} />
          <Metadata
            label="Deskew"
            value={page.deskewAngle === null ? '—' : `${page.deskewAngle.toFixed(2)}°`}
          />
          <Metadata label="Blocks" value={page.blockCount.toLocaleString()} />
        </dl>
        {page.warningCodes.length > 0 && (
          <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
            Warnings: {page.warningCodes.join(', ')}
          </p>
        )}
        {page.error && (
          <p
            role="alert"
            className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800"
          >
            {page.error.code}: {page.error.message}
          </p>
        )}
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="flex items-center gap-2">
          <Braces className="size-4 text-slate-500" aria-hidden="true" />
          <h3 className="text-sm font-semibold text-slate-950">Raw OCR text</h3>
        </div>
        <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap rounded-xl bg-slate-50 p-4 font-mono text-xs leading-6 text-slate-700">
          {page.rawText || 'No OCR text was recognised on this page.'}
        </pre>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <ScanText className="size-4 text-slate-500" aria-hidden="true" />
            <h3 className="text-sm font-semibold text-slate-950">OCR blocks</h3>
          </div>
          <label className="text-xs font-semibold text-slate-700">
            Confidence
            <select
              aria-label="OCR confidence"
              value={confidenceFilter}
              onChange={(event) =>
                onConfidenceFilterChange(event.target.value as OCRConfidenceFilter)
              }
              className="ml-2 min-h-9 rounded-lg border border-slate-300 bg-white px-2 text-xs"
            >
              <option value="ALL">All blocks</option>
              <option value="HIGH">High confidence</option>
              <option value="REVIEW">Needs review</option>
              <option value="LOW">Low confidence</option>
            </select>
          </label>
        </div>
        {isLoading ? (
          <div className="mt-4 h-52 animate-pulse rounded-xl bg-slate-100" />
        ) : visibleBlocks.length === 0 ? (
          <p className="mt-4 rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-600">
            No OCR blocks match this confidence filter.
          </p>
        ) : (
          <ol className="mt-4 space-y-3">
            {visibleBlocks.map((block) => (
              <li key={block.id} className="rounded-xl border border-slate-200 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[10px] font-semibold text-blue-800">
                    Source: OCR
                  </span>
                  <OCRConfidenceBadge
                    confidence={block.confidence}
                    lowConfidenceThreshold={lowConfidenceThreshold}
                    reviewConfidenceThreshold={reviewConfidenceThreshold}
                  />
                  <span className="text-[10px] text-slate-500">
                    {block.providerModel} ·{' '}
                    {block.recognitionProfile in ocrProfileLabels
                      ? ocrProfileLabels[
                          block.recognitionProfile as keyof typeof ocrProfileLabels
                        ]
                      : block.recognitionProfile}
                  </span>
                  <span className="ml-auto text-[10px] text-slate-500">
                    Block {block.blockOrder}
                  </span>
                </div>
                <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-800">
                  {block.text}
                </p>
                <details className="mt-3 text-[11px] text-slate-500">
                  <summary className="inline-flex cursor-pointer items-center gap-1 font-semibold">
                    <MapPin className="size-3" aria-hidden="true" />
                    Bounding box and polygon
                  </summary>
                  <pre className="mt-2 overflow-x-auto rounded-lg bg-slate-50 p-2 font-mono">
                    {JSON.stringify(
                      {
                        bbox: block.bbox,
                        polygon: block.polygon,
                        orientation: block.orientation,
                      },
                      null,
                      2,
                    )}
                  </pre>
                </details>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}

function Metadata({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-semibold text-slate-500">{label}</dt>
      <dd className="mt-1 text-slate-800">{value}</dd>
    </div>
  );
}
