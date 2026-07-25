import { Braces, MapPin, Sigma } from 'lucide-react';

import { SafeHighlight } from './SafeHighlight';
import { LanguageBadge } from './LanguageBadge';
import type { ExtractorType } from '../../types/extraction';
import type { ExtractedBlock } from '../../types/extractedContent';

const readableMetadataValue = (value: unknown): string => {
  if (value === null || value === undefined) {
    return '—';
  }
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return JSON.stringify(value);
};

export function ExtractedBlockViewer({
  activeBlockId,
  blocks,
  extractorType,
  highlightQuery = '',
  onSelectBlock,
}: {
  blocks: readonly ExtractedBlock[];
  extractorType: ExtractorType;
  highlightQuery?: string;
  activeBlockId?: string | null;
  onSelectBlock?: (block: ExtractedBlock) => void;
}) {
  if (blocks.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-300 px-6 py-12 text-center">
        <p className="text-sm font-semibold text-slate-900">
          No extracted blocks in this container.
        </p>
      </div>
    );
  }

  if (extractorType === 'XLSX') {
    return (
      <div className="overflow-hidden rounded-2xl border border-slate-200">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                {['Coordinate', 'Value', 'Type', 'Formula / Cached Value'].map(
                  (heading) => (
                    <th
                      key={heading}
                      className="whitespace-nowrap px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-500"
                    >
                      {heading}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {blocks.map((block) => {
                const metadata = block.metadata ?? {};
                const formula = metadata.formula;
                const cachedValue = metadata.cachedValue;
                const coordinate =
                  metadata.coordinate ?? block.sourceReference.split('cell=')[1];
                return (
                  <tr
                    key={block.id}
                    id={`block-${block.id}`}
                    className={
                      activeBlockId === block.id ? 'bg-amber-50' : 'hover:bg-slate-50'
                    }
                    onClick={() => onSelectBlock?.(block)}
                  >
                    <td className="whitespace-nowrap px-4 py-3 font-mono text-xs font-semibold text-blue-700">
                      {readableMetadataValue(coordinate)}
                    </td>
                    <td className="max-w-xl whitespace-pre-wrap px-4 py-3 text-xs text-slate-800">
                      <div className="mb-2 flex flex-wrap items-center gap-1.5">
                        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[9px] font-semibold text-slate-700">
                          {block.contentSource === 'OCR' ? 'OCR' : 'Native'}
                        </span>
                        {block.languageCode && (
                          <LanguageBadge code={block.languageCode} />
                        )}
                        {block.languageConfidence !== null &&
                          block.languageConfidence !== undefined && (
                            <span className="text-[9px] text-slate-500">
                              Language {Math.round(block.languageConfidence * 100)}%
                            </span>
                          )}
                        {block.ocrConfidence !== null &&
                          block.ocrConfidence !== undefined && (
                            <span className="text-[9px] text-slate-500">
                              OCR {Math.round(block.ocrConfidence * 100)}%
                            </span>
                          )}
                      </div>
                      <SafeHighlight text={block.text} query={highlightQuery} />
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-[10px] font-semibold text-slate-600">
                      {block.blockType}
                      {Boolean(metadata.isMerged) && (
                        <span className="ml-2 rounded-full bg-violet-50 px-2 py-0.5 text-violet-700">
                          Merged
                        </span>
                      )}
                    </td>
                    <td className="max-w-sm px-4 py-3 font-mono text-[11px] text-slate-600">
                      {formula !== undefined && formula !== null
                        ? readableMetadataValue(formula)
                        : '—'}
                      {cachedValue !== undefined && (
                        <p className="mt-1 text-slate-500">
                          Cached: {readableMetadataValue(cachedValue)}
                        </p>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {blocks.map((block) => (
        <article
          key={block.id}
          id={`block-${block.id}`}
          onClick={() => onSelectBlock?.(block)}
          className={`scroll-mt-24 rounded-2xl border p-4 transition ${
            activeBlockId === block.id
              ? 'border-amber-300 bg-amber-50 shadow-sm'
              : 'border-slate-200 bg-white hover:border-slate-300'
          }`}
        >
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[10px] font-semibold text-blue-700">
              {block.blockType}
            </span>
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-semibold text-slate-700">
              {block.contentSource === 'OCR' ? 'OCR' : 'Native'}
            </span>
            {block.languageCode && <LanguageBadge code={block.languageCode} />}
            {block.languageConfidence !== null &&
              block.languageConfidence !== undefined && (
                <span className="text-[10px] text-slate-500">
                  Language {Math.round(block.languageConfidence * 100)}%
                </span>
              )}
            {block.ocrConfidence !== null && block.ocrConfidence !== undefined && (
              <span className="text-[10px] text-slate-500">
                OCR {Math.round(block.ocrConfidence * 100)}%
              </span>
            )}
            {block.styleName && (
              <span className="rounded-full bg-violet-50 px-2.5 py-1 text-[10px] font-semibold text-violet-700">
                {block.styleName}
              </span>
            )}
            {block.headingLevel && (
              <span className="text-[10px] font-semibold text-slate-500">
                Heading {block.headingLevel}
              </span>
            )}
            <code className="ml-auto text-[10px] text-slate-500">
              {block.sourceReference}
            </code>
          </div>
          <p
            className={`mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-800 ${
              block.blockType === 'HEADING' ? 'font-semibold text-slate-950' : ''
            }`}
          >
            <SafeHighlight text={block.text} query={highlightQuery} />
          </p>
          {block.location && Object.keys(block.location).length > 0 && (
            <details className="mt-3 text-[11px] text-slate-500">
              <summary className="inline-flex cursor-pointer items-center gap-1 font-semibold">
                <MapPin className="size-3" aria-hidden="true" />
                Source location
              </summary>
              <pre className="mt-2 overflow-x-auto rounded-lg bg-slate-50 p-2 font-mono">
                {JSON.stringify(block.location, null, 2)}
              </pre>
            </details>
          )}
          {block.blockType === 'FORMULA' && (
            <div className="mt-3 flex items-start gap-2 rounded-xl bg-indigo-50 p-3 text-xs text-indigo-800">
              <Sigma className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              Formula retained as metadata and was not executed.
            </div>
          )}
          {block.metadata && Object.keys(block.metadata).length > 0 && (
            <details className="mt-2 text-[11px] text-slate-500">
              <summary className="inline-flex cursor-pointer items-center gap-1 font-semibold">
                <Braces className="size-3" aria-hidden="true" />
                Block metadata
              </summary>
              <pre className="mt-2 overflow-x-auto rounded-lg bg-slate-50 p-2 font-mono">
                {JSON.stringify(block.metadata, null, 2)}
              </pre>
            </details>
          )}
        </article>
      ))}
    </div>
  );
}
