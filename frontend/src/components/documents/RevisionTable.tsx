import {
  CheckCircle2,
  Eye,
  FileCheck2,
  FileUp,
  FileX2,
  GitCompareArrows,
  Pencil,
  Replace,
} from 'lucide-react';
import { Link } from 'react-router';

import { DocumentCodeField } from './DocumentCodeField';
import { DocumentFileDownloadButton } from './DocumentFileDownloadButton';
import { DocumentStatusBadge } from './DocumentStatusBadge';
import { RevisionBadge } from './RevisionBadge';
import type { DocumentFileListItem } from '../../types/documentFile';
import type { DocumentRevisionListItem } from '../../types/documentRevision';
import { formatFileSize } from '../../utils/documentFiles';
import { formatDate } from '../../utils/formatters';

interface RevisionTableProps {
  revisions: readonly DocumentRevisionListItem[];
  isLoading?: boolean;
  canManage: boolean;
  onView: (revision: DocumentRevisionListItem) => void;
  onEdit: (revision: DocumentRevisionListItem) => void;
  onSetCurrent: (revision: DocumentRevisionListItem) => void;
  onSupersede: (revision: DocumentRevisionListItem) => void;
  documentId?: string;
  files?: readonly DocumentFileListItem[];
  canUploadFile?: boolean;
  canDownloadFile?: boolean;
  canReplaceFile?: boolean;
  documentArchived?: boolean;
  onReplaceFile?: (file: DocumentFileListItem) => void;
}

const actionClassName =
  'inline-flex min-h-8 items-center gap-1.5 rounded-lg px-2 text-[11px] font-semibold text-slate-600 hover:bg-slate-100 hover:text-slate-950';

export function RevisionTable({
  canDownloadFile = false,
  canManage,
  canReplaceFile = false,
  canUploadFile = false,
  documentArchived = false,
  documentId,
  files = [],
  isLoading = false,
  onEdit,
  onReplaceFile,
  onSetCurrent,
  onSupersede,
  onView,
  revisions,
}: RevisionTableProps) {
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
      <div className="overflow-x-auto">
        <table className="min-w-[96rem] divide-y divide-slate-200">
          <thead className="bg-slate-50">
            <tr>
              {[
                'Revision',
                'Full Document Code',
                'Status',
                'Validation Rule',
                'Issue Date',
                'Effective Date',
                'Review Date',
                'Expiry Date',
                'Current',
                'Superseded',
                'Has File',
                'File Type',
                'File Size',
                'Actions',
              ].map((heading) => (
                <th
                  key={heading}
                  className="whitespace-nowrap px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-500"
                >
                  {heading}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {isLoading
              ? Array.from({ length: 3 }, (_, index) => (
                  <tr key={index} aria-label="Loading revision row">
                    {Array.from({ length: 14 }, (__, cell) => (
                      <td key={cell} className="px-4 py-4">
                        <div className="h-4 w-24 animate-pulse rounded bg-slate-100" />
                      </td>
                    ))}
                  </tr>
                ))
              : revisions.map((revision) => {
                  const currentFile = files.find(
                    (file) =>
                      file.documentRevisionId === revision.id &&
                      file.isCurrent &&
                      file.fileStatus === 'AVAILABLE',
                  );
                  return (
                    <tr key={revision.id} className="hover:bg-slate-50/70">
                      <td className="px-4 py-3">
                        <RevisionBadge
                          revisionCode={revision.revisionCode}
                          isCurrent={revision.isCurrent}
                        />
                      </td>
                      <td className="max-w-64 px-4 py-3">
                        <DocumentCodeField code={revision.fullDocumentCode} />
                      </td>
                      <td className="px-4 py-3">
                        <DocumentStatusBadge
                          code={revision.status.code}
                          name={revision.status.name}
                        />
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-600">
                        {revision.validationRule?.code ?? '—'}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">
                        {formatDate(revision.issueDate)}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">
                        {formatDate(revision.effectiveDate)}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">
                        {formatDate(revision.reviewDate)}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">
                        {formatDate(revision.expiryDate)}
                      </td>
                      <td className="px-4 py-3 text-xs font-semibold text-slate-700">
                        {revision.isCurrent ? 'Current' : '—'}
                      </td>
                      <td className="px-4 py-3 text-xs font-semibold text-slate-700">
                        {revision.isSuperseded ? 'Superseded' : '—'}
                      </td>
                      <td className="px-4 py-3">
                        {currentFile ? (
                          <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-700">
                            <FileCheck2 className="size-3.5" aria-hidden="true" />
                            Yes
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 text-xs text-slate-500">
                            <FileX2 className="size-3.5" aria-hidden="true" />
                            No
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs font-semibold uppercase text-slate-600">
                        {currentFile?.fileExtension ?? '—'}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">
                        {formatFileSize(currentFile?.fileSize)}
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex min-w-max items-center gap-0.5">
                          <button
                            type="button"
                            onClick={() => onView(revision)}
                            className={actionClassName}
                          >
                            <Eye className="size-3.5" aria-hidden="true" />
                            View
                          </button>
                          {currentFile && canDownloadFile && (
                            <DocumentFileDownloadButton
                              fileId={currentFile.id}
                              fallbackFileName={currentFile.sanitizedFilename}
                              label="Download"
                              className={actionClassName}
                            />
                          )}
                          {currentFile &&
                            canReplaceFile &&
                            !documentArchived &&
                            onReplaceFile && (
                              <button
                                type="button"
                                onClick={() => onReplaceFile(currentFile)}
                                className={actionClassName}
                              >
                                <Replace className="size-3.5" aria-hidden="true" />
                                Replace
                              </button>
                            )}
                          {!currentFile &&
                            canUploadFile &&
                            !documentArchived &&
                            documentId && (
                              <Link
                                to={`/documents/upload?documentId=${documentId}&revisionId=${revision.id}`}
                                className={actionClassName}
                              >
                                <FileUp className="size-3.5" aria-hidden="true" />
                                Upload
                              </Link>
                            )}
                          {documentId && (
                            <Link
                              to={`/documents/${documentId}/revisions/${revision.id}/file`}
                              className={actionClassName}
                            >
                              Files
                            </Link>
                          )}
                          {canManage && (
                            <>
                              <button
                                type="button"
                                onClick={() => onEdit(revision)}
                                className={actionClassName}
                              >
                                <Pencil className="size-3.5" aria-hidden="true" />
                                Edit
                              </button>
                              {!revision.isCurrent && !revision.isSuperseded && (
                                <button
                                  type="button"
                                  onClick={() => onSetCurrent(revision)}
                                  className={actionClassName}
                                >
                                  <CheckCircle2
                                    className="size-3.5"
                                    aria-hidden="true"
                                  />
                                  Set Current
                                </button>
                              )}
                              {!revision.isSuperseded && revisions.length > 1 && (
                                <button
                                  type="button"
                                  onClick={() => onSupersede(revision)}
                                  className={actionClassName}
                                >
                                  <GitCompareArrows
                                    className="size-3.5"
                                    aria-hidden="true"
                                  />
                                  Supersede
                                </button>
                              )}
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
          </tbody>
        </table>
      </div>
      {!isLoading && revisions.length === 0 && (
        <div className="px-6 py-12 text-center">
          <p className="text-sm font-semibold text-slate-900">No revisions yet</p>
          <p className="mt-1 text-xs text-slate-500">
            Add the first revision to establish a current controlled record.
          </p>
        </div>
      )}
    </div>
  );
}
