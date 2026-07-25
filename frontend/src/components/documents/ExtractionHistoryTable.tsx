import { Download, Eye, RefreshCw } from 'lucide-react';
import { Link } from 'react-router';

import { ExtractionStatusBadge } from './ExtractionStatusBadge';
import type { ExtractionRunHistoryItem } from '../../types/extractedContent';
import { formatDateTime } from '../../utils/formatters';

export function ExtractionHistoryTable({
  canExport,
  canReextract,
  documentId,
  isExporting = false,
  onExport,
  onReextract,
  revisionId,
  runs,
}: {
  runs: readonly ExtractionRunHistoryItem[];
  documentId: string;
  revisionId: string;
  canExport: boolean;
  canReextract: boolean;
  isExporting?: boolean;
  onExport: (run: ExtractionRunHistoryItem, format: 'json' | 'txt') => void;
  onReextract: (run: ExtractionRunHistoryItem) => void;
}) {
  if (runs.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-300 px-6 py-12 text-center">
        <p className="text-sm font-semibold text-slate-900">No extraction history.</p>
        <p className="mt-1 text-xs text-slate-500">
          Start extraction from the current available physical file.
        </p>
      </div>
    );
  }
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200">
      <div className="overflow-x-auto">
        <table className="min-w-[72rem] divide-y divide-slate-200">
          <thead className="bg-slate-50">
            <tr>
              {[
                'Completed At',
                'Extractor',
                'Status',
                'Source Hash',
                'Content Hash',
                'Pages / Sheets',
                'Blocks',
                'Characters',
                'Requested By',
                'Latest',
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
          <tbody className="divide-y divide-slate-100 bg-white">
            {runs.map((run) => (
              <tr key={run.id} className="hover:bg-slate-50">
                <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">
                  {formatDateTime(run.completedAt)}
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-xs font-semibold text-slate-700">
                  {run.extractorType} {run.extractorVersion}
                </td>
                <td className="px-4 py-3">
                  <ExtractionStatusBadge status={run.status} />
                </td>
                <td className="px-4 py-3 font-mono text-[10px] text-slate-500">
                  {run.sourceSha256Hash.slice(0, 12)}…
                </td>
                <td className="px-4 py-3 font-mono text-[10px] text-slate-500">
                  {run.contentHash ? `${run.contentHash.slice(0, 12)}…` : '—'}
                </td>
                <td className="px-4 py-3 text-xs text-slate-600">
                  {run.summary.totalPages || run.summary.totalSheets || '—'}
                </td>
                <td className="px-4 py-3 text-xs text-slate-600">
                  {run.summary.totalBlocks.toLocaleString()}
                </td>
                <td className="px-4 py-3 text-xs text-slate-600">
                  {run.summary.totalCharacters.toLocaleString()}
                </td>
                <td className="px-4 py-3 text-xs text-slate-600">
                  {run.requestedBy?.name ?? 'Unknown user'}
                </td>
                <td className="px-4 py-3 text-xs font-semibold text-slate-700">
                  {run.isLatest ? 'Latest' : '—'}
                </td>
                <td className="px-4 py-3">
                  <div className="flex min-w-max gap-1">
                    <Link
                      to={`/documents/${documentId}/revisions/${revisionId}/extracted-content?runId=${run.id}`}
                      className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-blue-700 hover:bg-blue-50"
                    >
                      <Eye className="size-3.5" aria-hidden="true" />
                      View
                    </Link>
                    {canExport &&
                      (['json', 'txt'] as const).map((format) => (
                        <button
                          key={format}
                          type="button"
                          onClick={() => onExport(run, format)}
                          disabled={isExporting}
                          className="inline-flex min-h-9 items-center gap-1 rounded-lg px-2.5 text-[11px] font-semibold uppercase text-slate-600 hover:bg-slate-100 disabled:opacity-50"
                        >
                          <Download className="size-3" aria-hidden="true" />
                          {format}
                        </button>
                      ))}
                    {canReextract && run.isLatest && (
                      <button
                        type="button"
                        onClick={() => onReextract(run)}
                        className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-indigo-700 hover:bg-indigo-50"
                      >
                        <RefreshCw className="size-3.5" aria-hidden="true" />
                        Re-extract
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
