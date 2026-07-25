import { ArrowLeft, FileUp } from 'lucide-react';
import { useState } from 'react';
import { Link, useParams } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import { DeleteDocumentFileDialog } from '../../components/documents/DeleteDocumentFileDialog';
import { DocumentCodeField } from '../../components/documents/DocumentCodeField';
import { DocumentFileTable } from '../../components/documents/DocumentFileTable';
import { ReplaceDocumentFileDialog } from '../../components/documents/ReplaceDocumentFileDialog';
import { RevisionBadge } from '../../components/documents/RevisionBadge';
import { ConfirmationDialog } from '../../components/master-data/ConfirmationDialog';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { useDocument } from '../../hooks/useDocument';
import {
  useDocumentFileMutations,
  useRevisionFiles,
} from '../../hooks/useDocumentFiles';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type { DocumentFileListItem } from '../../types/documentFile';

export function DocumentRevisionFilePage() {
  const { documentId = '', revisionId = '' } = useParams();
  const documentQuery = useDocument(documentId || null);
  const filesQuery = useRevisionFiles(documentId || null, revisionId || null);
  const mutations = useDocumentFileMutations();
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const [replaceTarget, setReplaceTarget] = useState<DocumentFileListItem | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<DocumentFileListItem | null>(null);
  const [restoreTarget, setRestoreTarget] = useState<DocumentFileListItem | null>(null);
  const { showToast } = useToast();
  const revision = documentQuery.data?.revisions.find(
    (candidate) => candidate.id === revisionId,
  );
  const canHistory = hasPermission('documents:view_file_history');
  const files = canHistory
    ? (filesQuery.data ?? [])
    : (filesQuery.data ?? []).filter(
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
      setReplaceTarget(null);
      showToast({ tone: 'success', title: 'Physical file replaced' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'File could not be replaced',
        message: getApiErrorMessage(error, 'The previous file remains current.'),
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
      setDeleteTarget(null);
      showToast({ tone: 'success', title: 'File moved to history' });
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
        payload: { reason: 'Restored from revision file history.' },
      });
      setRestoreTarget(null);
      showToast({ tone: 'success', title: 'File restored' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'File could not be restored',
        message: getApiErrorMessage(error, 'A current file may already exist.'),
      });
    }
  };

  if (documentQuery.isLoading || filesQuery.isLoading) {
    return (
      <div className="space-y-5" aria-label="Loading revision files">
        <div className="h-28 animate-pulse rounded-3xl bg-slate-100" />
        <div className="h-64 animate-pulse rounded-3xl bg-slate-100" />
      </div>
    );
  }

  if (documentQuery.error || !documentQuery.data || !revision) {
    return (
      <p
        role="alert"
        className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700"
      >
        {getApiErrorMessage(
          documentQuery.error,
          'The document or revision was not found within your scope.',
        )}
      </p>
    );
  }

  const document = documentQuery.data;
  const archived = document.isArchived;
  const canUpload = hasPermission('documents:upload') && !archived;
  const canReplace = hasPermission('documents:replace_file') && !archived;
  const canDelete = hasPermission('documents:delete_file') && !archived;

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Documents"
        title="Revision Physical File"
        description={document.title}
        actions={
          <div className="flex flex-wrap gap-2">
            <Link
              to={`/documents/${document.id}?tab=files`}
              className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 bg-white px-3.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              <ArrowLeft className="size-4" aria-hidden="true" />
              Document Files
            </Link>
            {canUpload && files.every((file) => !file.isCurrent) && (
              <Link
                to={`/documents/upload?documentId=${document.id}&revisionId=${revision.id}`}
                className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white hover:bg-blue-800"
              >
                <FileUp className="size-4" aria-hidden="true" />
                Upload File
              </Link>
            )}
          </div>
        }
      />
      <section className="flex flex-wrap items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <DocumentCodeField code={document.baseDocumentCode} />
        <RevisionBadge
          revisionCode={revision.revisionCode}
          isCurrent={revision.isCurrent}
        />
        <span className="text-xs text-slate-500">{revision.status.name}</span>
      </section>
      {archived && (
        <p className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          Archived documents are read-only. Existing files may only be viewed or
          downloaded according to permission.
        </p>
      )}
      {filesQuery.error ? (
        <p
          role="alert"
          className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700"
        >
          {getApiErrorMessage(
            filesQuery.error,
            'Revision file metadata could not be loaded.',
          )}
        </p>
      ) : (
        <DocumentFileTable
          files={files}
          canDownload={hasPermission('documents:download')}
          canReplace={canReplace}
          canDelete={canDelete}
          canRestore={canDelete}
          documentArchived={archived}
          onReplace={setReplaceTarget}
          onDelete={setDeleteTarget}
          onRestore={setRestoreTarget}
        />
      )}
      <ReplaceDocumentFileDialog
        file={replaceTarget}
        revisionStatus={revision.status.code}
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
        message="Restore is allowed only when this revision has no other current file."
        confirmLabel="Restore File"
        tone="primary"
        isPending={mutations.restore.isPending}
        onCancel={() => setRestoreTarget(null)}
        onConfirm={() => void restore()}
      />
    </div>
  );
}
