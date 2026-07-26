import { AlertTriangle, Check, Clipboard, Info, ShieldAlert } from 'lucide-react';

import type {
  FileIdentificationStatus,
  UploadProposedAction,
  UploadSessionItem,
} from '../../types/documentUpload';
import { formatFileSize, shortFileHash } from '../../utils/documentFiles';
import { uploadActionLabels } from '../../utils/uploadActions';

const statusLabels: Record<FileIdentificationStatus, string> = {
  IDENTIFIED: 'Identified',
  PARTIALLY_IDENTIFIED: 'Partially Identified',
  NOT_IDENTIFIED: 'Not Identified',
  DUPLICATE_FILE: 'Duplicate',
  INVALID: 'Invalid',
};

const statusClasses: Record<FileIdentificationStatus, string> = {
  IDENTIFIED: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  PARTIALLY_IDENTIFIED: 'border-amber-200 bg-amber-50 text-amber-800',
  NOT_IDENTIFIED: 'border-slate-200 bg-slate-100 text-slate-700',
  DUPLICATE_FILE: 'border-orange-200 bg-orange-50 text-orange-800',
  INVALID: 'border-rose-200 bg-rose-50 text-rose-800',
};

const actionDescriptions: Record<UploadProposedAction, string> = {
  ATTACH_TO_EXISTING_REVISION:
    'The complete document code matches an existing revision without a current file.',
  CREATE_DOCUMENT_AND_REVISION:
    'The filename contains valid master codes, but no register record exists yet.',
  ADD_NEW_REVISION: 'The base document exists and this revision code is new.',
  REPLACE_CURRENT_FILE: 'The matched revision already has a current physical file.',
  MANUAL_REVIEW: 'Review or supply metadata before this file can be committed.',
  SKIP: 'This file will remain uncommitted and its temporary copy will be cleaned up.',
};

export function IdentificationStatusBadge({
  status,
}: {
  status: FileIdentificationStatus;
}) {
  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold ${statusClasses[status]}`}
    >
      {statusLabels[status]}
    </span>
  );
}

export function FileIdentificationPreview({ item }: { item: UploadSessionItem }) {
  const parsed = item.parsedMetadata;

  const copyHash = async (): Promise<void> => {
    if (item.sha256Hash && navigator.clipboard) {
      await navigator.clipboard.writeText(item.sha256Hash);
    }
  };

  const metadata = [
    ['Company', parsed?.companyCode],
    ['Department', parsed?.departmentCode],
    ['Section', parsed?.sectionCode],
    ['Document Type', parsed?.documentTypeCode],
    ['Document Number', parsed?.documentNumber],
    ['Document Title', parsed?.title],
    ['Revision', parsed?.revisionCode],
    ['Base Document Code', parsed?.baseDocumentCode],
    ['Full Document Code', parsed?.fullDocumentCode],
  ] as const;

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <IdentificationStatusBadge status={item.identificationStatus} />
            {item.fileExtension && (
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold uppercase text-slate-600">
                {item.fileExtension}
              </span>
            )}
          </div>
          <h2 className="mt-3 break-all text-base font-semibold text-slate-950">
            {item.originalFilename}
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            {formatFileSize(item.fileSize)} · {item.detectedMimeType ?? 'Type pending'}
          </p>
        </div>
        <div className="rounded-xl bg-slate-50 px-3 py-2 text-xs text-slate-600">
          <span className="font-medium">SHA-256:</span>{' '}
          <code>{shortFileHash(item.sha256Hash)}</code>
          {item.sha256Hash && (
            <button
              type="button"
              onClick={() => void copyHash()}
              className="ml-2 inline-grid size-7 place-items-center rounded-lg text-slate-500 hover:bg-slate-200"
              aria-label="Copy full SHA-256 hash"
            >
              <Clipboard className="size-3.5" aria-hidden="true" />
            </button>
          )}
        </div>
      </div>

      <section className="rounded-2xl border border-blue-200 bg-blue-50 p-4">
        <div className="flex gap-3">
          <Info className="mt-0.5 size-5 shrink-0 text-blue-700" aria-hidden="true" />
          <div>
            <p className="text-sm font-semibold text-blue-950">
              Proposed: {uploadActionLabels[item.proposedAction]}
            </p>
            <p className="mt-1 text-xs leading-5 text-blue-800">
              {actionDescriptions[item.proposedAction]}
            </p>
          </div>
        </div>
      </section>

      <div className="grid gap-5 lg:grid-cols-2">
        <section className="rounded-2xl border border-slate-200 p-5">
          <h3 className="text-sm font-semibold text-slate-950">Parsed metadata</h3>
          <dl className="mt-4 grid gap-3 sm:grid-cols-2">
            {metadata.map(([label, value]) => (
              <div key={label}>
                <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                  {label}
                </dt>
                <dd className="mt-1 break-all text-sm text-slate-800">
                  {value || '—'}
                </dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="rounded-2xl border border-slate-200 p-5">
          <h3 className="text-sm font-semibold text-slate-950">Register match</h3>
          {item.matchedDocument ? (
            <dl className="mt-4 space-y-3">
              <div>
                <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                  Document
                </dt>
                <dd className="mt-1 text-sm font-semibold text-slate-900">
                  {item.matchedDocument.baseDocumentCode}
                </dd>
                <dd className="mt-0.5 text-xs text-slate-600">
                  {item.matchedDocument.title}
                </dd>
              </div>
              <div>
                <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                  Revision
                </dt>
                <dd className="mt-1 text-sm text-slate-800">
                  {item.matchedRevision?.revisionCode ?? 'No matching revision'}
                </dd>
              </div>
            </dl>
          ) : (
            <p className="mt-3 text-sm text-slate-500">
              No existing register record was exposed within your department scope.
            </p>
          )}
        </section>
      </div>

      {item.duplicateWarning && (
        <MessagePanel
          tone="warning"
          title="Duplicate content detected"
          messages={[item.duplicateWarning.message]}
        />
      )}
      {item.warnings.length > 0 && (
        <MessagePanel tone="warning" title="Warnings" messages={item.warnings} />
      )}
      {item.errors.length > 0 && (
        <MessagePanel tone="error" title="Validation errors" messages={item.errors} />
      )}
    </div>
  );
}

function MessagePanel({
  messages,
  title,
  tone,
}: {
  title: string;
  messages: readonly string[];
  tone: 'warning' | 'error';
}) {
  const Icon = tone === 'warning' ? AlertTriangle : ShieldAlert;
  const style =
    tone === 'warning'
      ? 'border-amber-200 bg-amber-50 text-amber-900'
      : 'border-rose-200 bg-rose-50 text-rose-900';
  return (
    <div className={`flex gap-3 rounded-2xl border p-4 ${style}`} role="alert">
      <Icon className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
      <div>
        <p className="text-sm font-semibold">{title}</p>
        <ul className="mt-1 space-y-1 text-xs leading-5">
          {messages.map((message) => (
            <li key={message} className="flex gap-2">
              <Check className="mt-1 size-3 shrink-0" aria-hidden="true" />
              {message}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
