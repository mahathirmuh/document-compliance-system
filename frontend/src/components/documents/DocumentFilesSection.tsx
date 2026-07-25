import { FileUp } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import { ConfirmationDialog } from '../master-data/ConfirmationDialog';
import { DeleteDocumentFileDialog } from './DeleteDocumentFileDialog';
import { DocumentExtractionSection } from './DocumentExtractionSection';
import { DocumentFileTable } from './DocumentFileTable';
import { ReplaceDocumentFileDialog } from './ReplaceDocumentFileDialog';
import {
  useDocumentFileMutations,
  useDocumentFiles,
} from '../../hooks/useDocumentFiles';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type { DocumentDetail } from '../../types/document';
import type { DocumentFileListItem } from '../../types/documentFile';

export function DocumentFilesSection({ document }: { document: DocumentDetail }) {
  const query = useDocumentFiles(document.id);
  const mutations = useDocumentFileMutations();
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canUpload = hasPermission('documents:upload');
  const canDownload = hasPermission('documents:download');
  const canReplace = hasPermission('documents:replace_file');
  const canDelete = hasPermission('documents:delete_file');
  const canViewHistory = hasPermission('documents:view_file_history');
  const canUseExtraction =
    hasPermission('documents:extract') ||
    hasPermission('documents:view_extracted_content') ||
    hasPermission('documents:view_extraction_history');
  const [replaceTarget, setReplaceTarget] = useState<DocumentFileListItem | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<DocumentFileListItem | null>(null);
  const [restoreTarget, setRestoreTarget] = useState<DocumentFileListItem | null>(null);
  const { showToast } = useToast();

  const files = canViewHistory
    ? (query.data ?? [])
    : (query.data ?? []).filter(
        (file) => file.isCurrent && file.fileStatus === 'AVAILABLE',
      );

  const replace = async (
    file: File,
    reason: string,
    onProgress: (progress: number) => void,
  ): Promise<void> => {
    if (!replaceTarget) {
      return;
    }
    try {
      await mutations.replace.mutateAsync({
        fileId: replaceTarget.id,
        file,
        reason,
        onProgress,
      });
      showToast({ tone: 'success', title: 'Physical file replaced' });
      setReplaceTarget(null);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'File could not be replaced',
        message: getApiErrorMessage(
          error,
          'The existing file remains current and unchanged.',
        ),
      });
    }
  };

  const remove = async (reason: string): Promise<void> => {
    if (!deleteTarget) {
      return;
    }
    try {
      await mutations.delete.mutateAsync({
        fileId: deleteTarget.id,
        payload: { reason },
      });
      showToast({ tone: 'success', title: 'File moved to history' });
      setDeleteTarget(null);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'File could not be removed',
        message: getApiErrorMessage(error, 'The active file remains unchanged.'),
      });
    }
  };

  const restore = async (): Promise<void> => {
    if (!restoreTarget) {
      return;
    }
    try {
      await mutations.restore.mutateAsync({
        fileId: restoreTarget.id,
        payload: { reason: 'Restored from file history.', replaceCurrent: false },
      });
      showToast({ tone: 'success', title: 'File restored' });
      setRestoreTarget(null);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'File could not be restored',
        message: getApiErrorMessage(
          error,
          'Remove or replace the current file before restoring this version.',
        ),
      });
    }
  };

  const currentRevision = document.currentRevision;
  const revisionStatus = replaceTarget
    ? (document.revisions.find(
        (revision) => revision.id === replaceTarget.documentRevisionId,
      )?.status.code ?? null)
    : null;

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">Physical Files</h2>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            Current, replaced, and soft-deleted file metadata. Storage paths remain
            private.
          </p>
        </div>
        {canUpload && currentRevision && !document.isArchived && (
          <Link
            to={`/documents/upload?documentId=${document.id}&revisionId=${currentRevision.id}`}
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white hover:bg-blue-800"
          >
            <FileUp className="size-4" aria-hidden="true" />
            Upload to Current Revision
          </Link>
        )}
      </div>

      {document.isArchived && (
        <p className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          Archived documents are read-only. File upload, replacement, removal, and
          restore are blocked.
        </p>
      )}
      {query.isLoading && (
        <div className="h-48 animate-pulse rounded-2xl bg-slate-100" />
      )}
      {query.error && (
        <div
          role="alert"
          className="flex flex-col gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700 sm:flex-row sm:items-center sm:justify-between"
        >
          <span>
            {getApiErrorMessage(
              query.error,
              'Physical file metadata could not be loaded.',
            )}
          </span>
          <button
            type="button"
            onClick={() => void query.refetch()}
            className="min-h-9 rounded-lg border border-rose-300 px-3 text-xs font-semibold"
          >
            Retry
          </button>
        </div>
      )}
      {!query.isLoading && !query.error && (
        <DocumentFileTable
          files={files}
          canDownload={canDownload}
          canReplace={canReplace}
          canDelete={canDelete}
          canRestore={canDelete}
          documentArchived={document.isArchived}
          onReplace={setReplaceTarget}
          onDelete={setDeleteTarget}
          onRestore={setRestoreTarget}
        />
      )}
      {!canViewHistory && files.length > 0 && (
        <p className="text-xs text-slate-500">
          Replaced and deleted versions require the file-history permission.
        </p>
      )}
      {canUseExtraction && (
        <div className="border-t border-slate-200 pt-5">
          <DocumentExtractionSection
            files={files}
            documentArchived={document.isArchived}
          />
        </div>
      )}

      <ReplaceDocumentFileDialog
        file={replaceTarget}
        revisionStatus={revisionStatus}
        isPending={mutations.replace.isPending}
        onClose={() => setReplaceTarget(null)}
        onConfirm={replace}
      />
      <DeleteDocumentFileDialog
        file={deleteTarget}
        isPending={mutations.delete.isPending}
        onClose={() => setDeleteTarget(null)}
        onConfirm={remove}
      />
      <ConfirmationDialog
        isOpen={restoreTarget !== null}
        title="Restore this file?"
        message="Restore is allowed only when the revision has no other current primary file."
        confirmLabel="Restore File"
        tone="primary"
        isPending={mutations.restore.isPending}
        onCancel={() => setRestoreTarget(null)}
        onConfirm={() => void restore()}
      />
    </div>
  );
}
