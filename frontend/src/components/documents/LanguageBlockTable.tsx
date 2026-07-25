import { ExternalLink, Eye } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';

import { LanguageBadge } from './LanguageBadge';
import type { LanguageBlockResult } from '../../types/languageDetection';

export function LanguageBlockTable({
  blocks,
  sourceContext,
}: {
  blocks: readonly LanguageBlockResult[];
  sourceContext?: {
    documentId: string;
    revisionId: string;
    extractionRunId: string;
  };
}) {
  const [detail, setDetail] = useState<LanguageBlockResult | null>(null);

  if (blocks.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-600">
        No language block results match the selected filters.
      </p>
    );
  }

  return (
    <>
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                {[
                  'Source',
                  'Container',
                  'Reference',
                  'Text',
                  'Detected Language',
                  'Confidence',
                  'Mixed',
                  'Characters',
                  'Actions',
                ].map((heading) => (
                  <th
                    key={heading}
                    className="whitespace-nowrap px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-500"
                  >
                    {heading}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {blocks.map((block) => (
                <tr key={block.id} className="align-top hover:bg-slate-50">
                  <td className="whitespace-nowrap px-4 py-3 text-xs font-semibold text-slate-700">
                    {block.sourceType === 'OCR' ? 'OCR' : 'Native'}
                  </td>
                  <td className="max-w-40 px-4 py-3 text-xs text-slate-600">
                    {block.containerId ?? '—'}
                  </td>
                  <td className="max-w-48 break-all px-4 py-3 font-mono text-[10px] text-slate-500">
                    {block.sourceReference}
                  </td>
                  <td className="max-w-xl px-4 py-3 text-xs leading-5 text-slate-800">
                    <span className="line-clamp-3">{block.text}</span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <LanguageBadge code={block.languageCode} />
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-700">
                    <span>Language {Math.round(block.confidence * 100)}%</span>
                    {block.sourceType === 'OCR' && (
                      <span className="mt-1 block text-[10px] text-slate-500">
                        OCR{' '}
                        {block.sourceConfidence === null
                          ? '—'
                          : `${Math.round(block.sourceConfidence * 100)}%`}
                      </span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-700">
                    {block.isMixed ? 'Yes' : 'No'}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-xs tabular-nums text-slate-700">
                    {block.characterCount.toLocaleString()}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      <button
                        type="button"
                        onClick={() => setDetail(block)}
                        className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-blue-700 hover:bg-blue-50"
                      >
                        <Eye className="size-3.5" aria-hidden="true" />
                        View Detail
                      </button>
                      {sourceContext && block.containerId && (
                        <Link
                          to={sourceContainerHref(block, sourceContext)}
                          className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-violet-700 hover:bg-violet-50"
                        >
                          <ExternalLink className="size-3.5" aria-hidden="true" />
                          Open Source Container
                        </Link>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {detail && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Language result detail"
          className="fixed inset-0 z-[70] grid place-items-center bg-slate-950/55 p-4"
        >
          <section className="max-h-[85vh] w-full max-w-2xl overflow-auto rounded-3xl bg-white p-6 shadow-2xl">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-lg font-semibold text-slate-950">
                Language result detail
              </h2>
              <button
                type="button"
                onClick={() => setDetail(null)}
                className="min-h-9 rounded-lg border border-slate-300 px-3 text-xs font-semibold text-slate-700"
              >
                Close
              </button>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <LanguageBadge code={detail.languageCode} />
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-semibold text-slate-700">
                {detail.sourceType}
              </span>
            </div>
            <p className="mt-4 whitespace-pre-wrap rounded-xl bg-slate-50 p-4 text-sm leading-6 text-slate-800">
              {detail.text}
            </p>
            <dl className="mt-4 grid gap-4 text-xs sm:grid-cols-2">
              <Detail label="Reference" value={detail.sourceReference} />
              <Detail
                label="Language confidence"
                value={`${Math.round(detail.confidence * 100)}%`}
              />
              <Detail
                label="OCR confidence"
                value={
                  detail.sourceConfidence === null
                    ? 'Not applicable'
                    : `${Math.round(detail.sourceConfidence * 100)}%`
                }
              />
              <Detail
                label="Characters"
                value={detail.characterCount.toLocaleString()}
              />
              <Detail
                label="Han characters"
                value={detail.hanCharacterCount.toLocaleString()}
              />
              <Detail
                label="Latin characters"
                value={detail.latinCharacterCount.toLocaleString()}
              />
            </dl>
            {detail.detectedLanguages.length > 0 && (
              <pre className="mt-4 overflow-x-auto rounded-xl bg-slate-950 p-4 font-mono text-[11px] text-slate-100">
                {JSON.stringify(detail.detectedLanguages, null, 2)}
              </pre>
            )}
          </section>
        </div>
      )}
    </>
  );
}

function sourceContainerHref(
  block: LanguageBlockResult,
  context: {
    documentId: string;
    revisionId: string;
    extractionRunId: string;
  },
): string {
  const query = new URLSearchParams({
    runId: context.extractionRunId,
    containerId: block.containerId ?? '',
  });
  if (block.extractedBlockId) {
    query.set('blockId', block.extractedBlockId);
  }
  return `/documents/${context.documentId}/revisions/${context.revisionId}/extracted-content?${query.toString()}`;
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-semibold text-slate-500">{label}</dt>
      <dd className="mt-1 break-all text-slate-800">{value}</dd>
    </div>
  );
}
