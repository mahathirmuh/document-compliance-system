import { FileClock, X } from 'lucide-react';

import { DocumentCodeField } from './DocumentCodeField';
import { DocumentStatusBadge } from './DocumentStatusBadge';
import { RevisionBadge } from './RevisionBadge';
import { SharePointLink } from './SharePointLink';
import { getApiErrorMessage } from '../../api/errors';
import { useDocumentRevision } from '../../hooks/useDocumentRevisions';
import type { DocumentUserSummary } from '../../types/document';
import type { DocumentRevisionListItem } from '../../types/documentRevision';
import { formatDate, formatDateTime } from '../../utils/formatters';

interface RevisionDetailsDialogProps {
  documentId: string;
  revision: DocumentRevisionListItem | null;
  onClose: () => void;
}

export function RevisionDetailsDialog({
  documentId,
  onClose,
  revision,
}: RevisionDetailsDialogProps) {
  const query = useDocumentRevision(revision ? documentId : null, revision?.id ?? null);

  if (!revision) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-[90] grid place-items-center bg-slate-950/50 p-3 backdrop-blur-sm sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="revision-details-title"
    >
      <section className="flex max-h-[94vh] w-full max-w-4xl flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-2xl">
        <header className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-5 sm:px-7">
          <div className="flex items-start gap-3">
            <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-blue-50 text-blue-700">
              <FileClock className="size-5" aria-hidden="true" />
            </div>
            <div>
              <h2
                id="revision-details-title"
                className="text-lg font-semibold text-slate-950"
              >
                Revision Details
              </h2>
              <p className="mt-1 text-xs text-slate-500">
                Read-only controlled metadata for {revision.revisionCode}.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close revision details"
            className="grid size-9 place-items-center rounded-xl text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-6 sm:px-7">
          {query.isLoading && (
            <div className="space-y-4" aria-label="Loading revision details">
              <div className="h-20 animate-pulse rounded-2xl bg-slate-100" />
              <div className="grid gap-3 sm:grid-cols-2">
                {Array.from({ length: 8 }, (_, index) => (
                  <div
                    key={index}
                    className="h-16 animate-pulse rounded-xl bg-slate-100"
                  />
                ))}
              </div>
            </div>
          )}

          {query.error && (
            <div
              role="alert"
              className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-800"
            >
              <p className="font-semibold">Revision details could not be loaded</p>
              <p className="mt-1">
                {getApiErrorMessage(
                  query.error,
                  'The revision was not found or is outside your scope.',
                )}
              </p>
              <button
                type="button"
                onClick={() => void query.refetch()}
                className="mt-4 min-h-9 rounded-xl border border-rose-300 px-3 text-xs font-semibold hover:bg-rose-100"
              >
                Try again
              </button>
            </div>
          )}

          {query.data && (
            <div className="space-y-5">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <RevisionBadge
                    revisionCode={query.data.revisionCode}
                    isCurrent={query.data.isCurrent}
                  />
                  <DocumentStatusBadge
                    code={query.data.status.code}
                    name={query.data.status.name}
                  />
                  {query.data.isSuperseded && (
                    <span className="rounded-full bg-amber-100 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-amber-800">
                      Superseded
                    </span>
                  )}
                </div>
                <div className="mt-3">
                  <DocumentCodeField code={query.data.fullDocumentCode} />
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <DetailField
                  label="Issue Date"
                  value={formatDate(query.data.issueDate)}
                />
                <DetailField
                  label="Effective Date"
                  value={formatDate(query.data.effectiveDate)}
                />
                <DetailField
                  label="Review Date"
                  value={formatDate(query.data.reviewDate)}
                />
                <DetailField
                  label="Expiry Date"
                  value={formatDate(query.data.expiryDate)}
                />
                <DetailField
                  label="Validation Rule"
                  value={query.data.validationRule?.name ?? 'Not assigned'}
                />
                <DetailField
                  label="Revision Number"
                  value={query.data.revisionNumber?.toString() ?? 'Non-numeric'}
                />
                <DetailField
                  label="Superseded At"
                  value={
                    query.data.supersededAt
                      ? formatDateTime(query.data.supersededAt)
                      : '—'
                  }
                />
                <DetailField
                  label="Superseded By Revision"
                  value={query.data.supersededByRevisionId ?? '—'}
                />
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <TextPanel
                  label="External Reference"
                  value={query.data.externalReference}
                />
                <TextPanel label="Remarks" value={query.data.remarks} />
              </div>

              <div className="rounded-2xl border border-slate-200 p-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-500">
                  SharePoint Metadata
                </p>
                <div className="mt-2">
                  <SharePointLink url={query.data.sharepointUrl} />
                </div>
              </div>

              <div className="grid gap-4 border-t border-slate-200 pt-5 sm:grid-cols-2">
                <AuditUser
                  label="Created By"
                  user={query.data.createdBy}
                  timestamp={query.data.createdAt}
                />
                <AuditUser
                  label="Last Updated By"
                  user={query.data.updatedBy}
                  timestamp={query.data.updatedAt}
                />
              </div>
            </div>
          )}
        </div>

        <footer className="flex justify-end border-t border-slate-200 bg-slate-50 px-5 py-4 sm:px-7">
          <button
            type="button"
            onClick={onClose}
            className="min-h-10 rounded-xl border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            Close
          </button>
        </footer>
      </section>
    </div>
  );
}

function DetailField({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200 p-3">
      <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-500">
        {label}
      </p>
      <p className="mt-1 break-words text-sm font-medium text-slate-800">{value}</p>
    </div>
  );
}

function TextPanel({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="rounded-2xl border border-slate-200 p-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-500">
        {label}
      </p>
      <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-slate-700">
        {value || 'Not provided'}
      </p>
    </div>
  );
}

function AuditUser({
  label,
  timestamp,
  user,
}: {
  label: string;
  timestamp: string;
  user: DocumentUserSummary | null;
}) {
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-500">
        {label}
      </p>
      <p className="mt-1 text-sm font-semibold text-slate-800">
        {user?.name ?? 'System'}
      </p>
      {user?.email && <p className="text-xs text-slate-500">{user.email}</p>}
      <p className="mt-1 text-xs text-slate-500">{formatDateTime(timestamp)}</p>
    </div>
  );
}
