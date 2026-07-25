import { History, Replace, RotateCcw, Trash2 } from 'lucide-react';
import { Link } from 'react-router';

import { DocumentFileDownloadButton } from './DocumentFileDownloadButton';
import type {
  DocumentFileListItem,
  DocumentFileStatus,
} from '../../types/documentFile';
import { formatFileSize, shortFileHash } from '../../utils/documentFiles';
import { formatDateTime } from '../../utils/formatters';

interface DocumentFileTableProps {
  files: readonly DocumentFileListItem[];
  canDownload: boolean;
  canReplace: boolean;
  canDelete: boolean;
  canRestore: boolean;
  documentArchived?: boolean;
  showDocument?: boolean;
  onReplace: (file: DocumentFileListItem) => void;
  onDelete: (file: DocumentFileListItem) => void;
  onRestore: (file: DocumentFileListItem) => void;
}

const statusStyles: Record<DocumentFileStatus, string> = {
  AVAILABLE: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  UPLOADING: 'bg-blue-50 text-blue-700 ring-blue-200',
  QUARANTINED: 'bg-orange-50 text-orange-700 ring-orange-200',
  REPLACED: 'bg-slate-100 text-slate-700 ring-slate-200',
  DELETED: 'bg-rose-50 text-rose-700 ring-rose-200',
  FAILED: 'bg-rose-50 text-rose-700 ring-rose-200',
};

export function DocumentFileStatusBadge({ status }: { status: DocumentFileStatus }) {
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-[10px] font-semibold ring-1 ring-inset ${statusStyles[status]}`}
    >
      {status.charAt(0) + status.slice(1).toLowerCase()}
    </span>
  );
}

export function DocumentFileTable({
  canDelete,
  canDownload,
  canReplace,
  canRestore,
  documentArchived = false,
  files,
  onDelete,
  onReplace,
  onRestore,
  showDocument = false,
}: DocumentFileTableProps) {
  if (files.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-300 px-6 py-12 text-center">
        <p className="text-sm font-semibold text-slate-900">
          No physical file uploaded.
        </p>
        <p className="mt-1 text-xs text-slate-500">
          Upload a validated PDF, DOCX, or XLSX to a document revision.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200">
      <div className="overflow-x-auto">
        <table className="min-w-[76rem] divide-y divide-slate-200">
          <thead className="bg-slate-50">
            <tr>
              {[
                'Current',
                'Filename',
                ...(showDocument ? ['Document'] : []),
                'Revision',
                'Type',
                'Size',
                'Uploaded By',
                'Uploaded At',
                'Hash',
                'Status',
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
            {files.map((file) => {
              const downloadable =
                canDownload &&
                (file.fileStatus === 'AVAILABLE' || file.fileStatus === 'REPLACED');
              return (
                <tr key={file.id} className="hover:bg-slate-50/70">
                  <td className="px-4 py-3 text-xs font-semibold text-slate-700">
                    {file.isCurrent ? 'Current' : '—'}
                  </td>
                  <td className="max-w-64 break-all px-4 py-3 text-xs font-semibold text-slate-900">
                    {file.originalFilename}
                  </td>
                  {showDocument && (
                    <td className="max-w-56 px-4 py-3 text-xs text-slate-700">
                      <Link
                        to={`/documents/${file.documentId}?tab=files`}
                        className="font-semibold text-blue-700 hover:text-blue-900"
                      >
                        {file.baseDocumentCode}
                      </Link>
                      <p className="mt-0.5 truncate text-[11px] text-slate-500">
                        {file.documentTitle}
                      </p>
                    </td>
                  )}
                  <td className="px-4 py-3 text-xs text-slate-700">
                    {file.revisionCode}
                  </td>
                  <td className="px-4 py-3 text-xs font-semibold uppercase text-slate-600">
                    {file.fileExtension}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">
                    {formatFileSize(file.fileSize)}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-600">
                    {file.uploadedBy?.name ?? 'Unknown user'}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">
                    {formatDateTime(file.uploadedAt)}
                  </td>
                  <td className="px-4 py-3">
                    <code className="text-[11px] text-slate-600">
                      {shortFileHash(file.sha256Hash)}
                    </code>
                  </td>
                  <td className="px-4 py-3">
                    <DocumentFileStatusBadge status={file.fileStatus} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex min-w-max items-center gap-1">
                      {downloadable && (
                        <DocumentFileDownloadButton
                          fileId={file.id}
                          fallbackFileName={file.sanitizedFilename}
                        />
                      )}
                      {canReplace &&
                        file.isCurrent &&
                        file.fileStatus === 'AVAILABLE' &&
                        !documentArchived && (
                          <button
                            type="button"
                            onClick={() => onReplace(file)}
                            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-amber-50 px-3 text-xs font-semibold text-amber-800 hover:bg-amber-100"
                          >
                            <Replace className="size-3.5" aria-hidden="true" />
                            Replace
                          </button>
                        )}
                      {canDelete &&
                        file.fileStatus === 'AVAILABLE' &&
                        !documentArchived && (
                          <button
                            type="button"
                            onClick={() => onDelete(file)}
                            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-rose-50 px-3 text-xs font-semibold text-rose-700 hover:bg-rose-100"
                          >
                            <Trash2 className="size-3.5" aria-hidden="true" />
                            Remove
                          </button>
                        )}
                      {canRestore &&
                        file.fileStatus === 'DELETED' &&
                        !documentArchived && (
                          <button
                            type="button"
                            onClick={() => onRestore(file)}
                            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-emerald-50 px-3 text-xs font-semibold text-emerald-700 hover:bg-emerald-100"
                          >
                            <RotateCcw className="size-3.5" aria-hidden="true" />
                            Restore
                          </button>
                        )}
                      <Link
                        to={`/documents/${file.documentId}/revisions/${file.documentRevisionId}/file`}
                        className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-slate-600 hover:bg-slate-100"
                      >
                        <History className="size-3.5" aria-hidden="true" />
                        Revision Files
                      </Link>
                    </div>
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
