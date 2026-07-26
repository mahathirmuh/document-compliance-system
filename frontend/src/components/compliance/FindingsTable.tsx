import { Eye, MapPin } from 'lucide-react';
import { Link } from 'react-router';

import { FindingSeverityBadge, FindingStatusBadge } from './FindingBadges';
import type { FindingListItem } from '../../types/finding';
import { formatDateTime } from '../../utils/formatters';

const getLocation = (finding: FindingListItem): string =>
  finding.sourceReference ??
  (finding.pageNumber ? `PDF page ${finding.pageNumber}` : null) ??
  (finding.worksheetName
    ? `${finding.worksheetName}${finding.cellCoordinate ? `!${finding.cellCoordinate}` : ''}`
    : null) ??
  finding.containerId ??
  '—';

export function FindingsTable({
  findings,
  onSelectionChange,
  selectedIds = [],
  showSelection = false,
}: {
  findings: readonly FindingListItem[];
  showSelection?: boolean;
  selectedIds?: readonly string[];
  onSelectionChange?: (ids: string[]) => void;
}) {
  const selected = new Set(selectedIds);
  const toggle = (id: string): void => {
    if (!onSelectionChange) {
      return;
    }
    const next = new Set(selected);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    onSelectionChange([...next]);
  };

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
      <div className="overflow-x-auto">
        <table className="min-w-[96rem] divide-y divide-slate-200">
          <thead className="bg-slate-50">
            <tr>
              {showSelection && (
                <th className="px-4 py-3 text-left">
                  <span className="sr-only">Select</span>
                </th>
              )}
              {[
                'Severity',
                'Status',
                'Finding Code',
                'Document Code',
                'Revision',
                'Title',
                'Language',
                'Section',
                'Location',
                'Assigned To',
                'Created At',
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
            {findings.map((finding) => (
              <tr key={finding.id} className="hover:bg-slate-50">
                {showSelection && (
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      aria-label={`Select ${finding.title}`}
                      checked={selected.has(finding.id)}
                      onChange={() => toggle(finding.id)}
                      className="size-4 rounded border-slate-300"
                    />
                  </td>
                )}
                <td className="px-4 py-3">
                  <FindingSeverityBadge severity={finding.severity} />
                </td>
                <td className="px-4 py-3">
                  <FindingStatusBadge status={finding.status} />
                </td>
                <td className="px-4 py-3 font-mono text-[11px] font-semibold text-slate-700">
                  {finding.findingCode}
                </td>
                <td className="px-4 py-3 text-xs font-semibold text-blue-700">
                  {finding.document?.baseDocumentCode ?? finding.documentId}
                </td>
                <td className="px-4 py-3 text-xs text-slate-600">
                  {finding.revision?.revisionCode ?? '—'}
                </td>
                <td className="max-w-xs px-4 py-3 text-xs font-medium text-slate-800">
                  {finding.title}
                  {!finding.isSystemGenerated && (
                    <span className="ml-2 rounded bg-violet-50 px-1.5 py-0.5 text-[9px] font-semibold text-violet-700">
                      Manual
                    </span>
                  )}
                  {finding.isRepeat && (
                    <span className="ml-2 rounded bg-amber-50 px-1.5 py-0.5 text-[9px] font-semibold text-amber-700">
                      Repeat
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-xs uppercase text-slate-600">
                  {finding.languageCode ?? '—'}
                </td>
                <td className="px-4 py-3 font-mono text-xs text-slate-600">
                  {finding.sectionCode ?? '—'}
                </td>
                <td className="max-w-xs px-4 py-3 text-xs text-slate-600">
                  <span className="inline-flex items-start gap-1">
                    <MapPin className="mt-0.5 size-3 shrink-0" aria-hidden="true" />
                    <span className="break-all">{getLocation(finding)}</span>
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-slate-600">
                  {finding.assignedTo?.name ?? 'Unassigned'}
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">
                  {formatDateTime(finding.createdAt)}
                </td>
                <td className="px-4 py-3">
                  <Link
                    to={`/compliance/findings/${finding.id}`}
                    className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-blue-700 hover:bg-blue-50"
                  >
                    <Eye className="size-3.5" aria-hidden="true" />
                    View
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {findings.length === 0 && (
        <p className="px-6 py-12 text-center text-sm text-slate-500">
          No findings match these filters.
        </p>
      )}
    </div>
  );
}
