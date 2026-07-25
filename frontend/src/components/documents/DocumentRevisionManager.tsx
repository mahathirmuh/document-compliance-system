import { GitBranchPlus } from 'lucide-react';
import { useState } from 'react';

import { RevisionDetailsDialog } from './RevisionDetailsDialog';
import { RevisionFormDialog } from './RevisionFormDialog';
import { RevisionTable } from './RevisionTable';
import { ReplaceDocumentFileDialog } from './ReplaceDocumentFileDialog';
import { SetCurrentRevisionDialog } from './SetCurrentRevisionDialog';
import { SupersedeRevisionDialog } from './SupersedeRevisionDialog';
import { getApiErrorMessage } from '../../api/errors';
import { useDocumentFormOptions } from '../../hooks/useDocumentFormOptions';
import {
  useDocumentFileMutations,
  useDocumentFiles,
} from '../../hooks/useDocumentFiles';
import {
  useDocumentRevisionMutations,
  useDocumentRevisions,
} from '../../hooks/useDocumentRevisions';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type { DocumentDetail } from '../../types/document';
import type { DocumentFileListItem } from '../../types/documentFile';
import type {
  DocumentRevisionCreate,
  DocumentRevisionListItem,
  DocumentRevisionUpdate,
} from '../../types/documentRevision';

interface DocumentRevisionManagerProps {
  document: DocumentDetail;
  compact?: boolean;
}

type RevisionDialogMode = 'create' | 'edit' | null;

export function DocumentRevisionManager({
  compact = false,
  document,
}: DocumentRevisionManagerProps) {
  const [dialogMode, setDialogMode] = useState<RevisionDialogMode>(null);
  const [selectedRevision, setSelectedRevision] =
    useState<DocumentRevisionListItem | null>(null);
  const [detailsTarget, setDetailsTarget] = useState<DocumentRevisionListItem | null>(
    null,
  );
  const [currentTarget, setCurrentTarget] = useState<DocumentRevisionListItem | null>(
    null,
  );
  const [supersedeTarget, setSupersedeTarget] =
    useState<DocumentRevisionListItem | null>(null);
  const [replaceFileTarget, setReplaceFileTarget] =
    useState<DocumentFileListItem | null>(null);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canManage = hasPermission('documents:manage_revisions') && !document.isArchived;
  const canUploadFile = hasPermission('documents:upload') && !document.isArchived;
  const canDownloadFile = hasPermission('documents:download');
  const canReplaceFile =
    hasPermission('documents:replace_file') && !document.isArchived;
  const query = useDocumentRevisions(document.id);
  const filesQuery = useDocumentFiles(document.id);
  const mutations = useDocumentRevisionMutations(document.id);
  const fileMutations = useDocumentFileMutations();
  const formOptions = useDocumentFormOptions(canManage);
  const { showToast } = useToast();
  const revisions = query.data ?? document.revisions;
  const statuses = formOptions.data?.documentStatuses ?? [];
  const validationRules = (formOptions.data?.validationRules ?? []).filter(
    (rule) =>
      rule.documentTypeId === null || rule.documentTypeId === document.documentTypeId,
  );

  const saveRevision = async (
    payload: DocumentRevisionCreate | DocumentRevisionUpdate,
  ): Promise<void> => {
    try {
      if (dialogMode === 'edit' && selectedRevision) {
        await mutations.update.mutateAsync({
          revisionId: selectedRevision.id,
          payload: payload as DocumentRevisionUpdate,
        });
      } else {
        await mutations.create.mutateAsync(payload as DocumentRevisionCreate);
      }
      showToast({
        tone: 'success',
        title: dialogMode === 'edit' ? 'Revision updated' : 'Revision added',
      });
      setDialogMode(null);
      setSelectedRevision(null);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Revision could not be saved',
        message: getApiErrorMessage(error, 'Review the revision code and dates.'),
      });
    }
  };

  const setCurrent = async (reason: string | null): Promise<void> => {
    if (!currentTarget) {
      return;
    }
    try {
      await mutations.setCurrent.mutateAsync({
        revisionId: currentTarget.id,
        payload: { reason },
      });
      showToast({ tone: 'success', title: 'Current revision updated' });
      setCurrentTarget(null);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Current revision could not be updated',
        message: getApiErrorMessage(error, 'Try again.'),
      });
    }
  };

  const supersede = async ({
    reason,
    supersededByRevisionId,
  }: {
    supersededByRevisionId: string;
    reason: string;
  }): Promise<void> => {
    if (!supersedeTarget) {
      return;
    }
    try {
      await mutations.supersede.mutateAsync({
        revisionId: supersedeTarget.id,
        payload: { supersededByRevisionId, reason },
      });
      showToast({ tone: 'success', title: 'Revision superseded' });
      setSupersedeTarget(null);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Revision could not be superseded',
        message: getApiErrorMessage(error, 'Select a valid replacing revision.'),
      });
    }
  };

  const replaceFile = async (
    file: File,
    reason: string,
    onProgress: (progress: number) => void,
  ): Promise<void> => {
    if (!replaceFileTarget) {
      return;
    }
    try {
      await fileMutations.replace.mutateAsync({
        fileId: replaceFileTarget.id,
        file,
        reason,
        onProgress,
      });
      showToast({ tone: 'success', title: 'Physical file replaced' });
      setReplaceFileTarget(null);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'File could not be replaced',
        message: getApiErrorMessage(error, 'The previous file remains current.'),
      });
    }
  };

  return (
    <section className={compact ? 'space-y-4' : 'space-y-5'}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">Revision History</h2>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            Exactly one revision can be current. Superseding remains an explicit action.
          </p>
        </div>
        {canManage && (
          <button
            type="button"
            onClick={() => {
              setSelectedRevision(null);
              setDialogMode('create');
            }}
            disabled={formOptions.isLoading || formOptions.isError}
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <GitBranchPlus className="size-4" aria-hidden="true" />
            Add Revision
          </button>
        )}
      </div>
      {query.error && (
        <p
          role="alert"
          className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700"
        >
          {getApiErrorMessage(query.error, 'Revisions could not be loaded.')}
        </p>
      )}
      {filesQuery.error && (
        <p
          role="alert"
          className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800"
        >
          File indicators could not be loaded. Revision metadata remains available.
        </p>
      )}
      {canManage && formOptions.error && (
        <div
          role="alert"
          className="flex flex-col gap-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 sm:flex-row sm:items-center sm:justify-between"
        >
          <span>
            {getApiErrorMessage(
              formOptions.error,
              'Revision form options could not be loaded.',
            )}
          </span>
          <button
            type="button"
            onClick={() => void formOptions.refetch()}
            className="min-h-9 rounded-lg border border-rose-300 px-3 text-xs font-semibold hover:bg-rose-100"
          >
            Retry options
          </button>
        </div>
      )}
      <RevisionTable
        revisions={revisions}
        isLoading={query.isLoading}
        canManage={canManage}
        onView={setDetailsTarget}
        onEdit={(revision) => {
          setSelectedRevision(revision);
          setDialogMode('edit');
        }}
        onSetCurrent={setCurrentTarget}
        onSupersede={setSupersedeTarget}
        documentId={document.id}
        files={filesQuery.data ?? []}
        canUploadFile={canUploadFile}
        canDownloadFile={canDownloadFile}
        canReplaceFile={canReplaceFile}
        documentArchived={document.isArchived}
        onReplaceFile={setReplaceFileTarget}
      />
      <RevisionDetailsDialog
        documentId={document.id}
        revision={detailsTarget}
        onClose={() => setDetailsTarget(null)}
      />
      <RevisionFormDialog
        isOpen={dialogMode !== null}
        revision={dialogMode === 'edit' ? selectedRevision : null}
        statuses={statuses}
        validationRules={validationRules}
        isPending={mutations.create.isPending || mutations.update.isPending}
        onClose={() => {
          setDialogMode(null);
          setSelectedRevision(null);
        }}
        onSubmit={saveRevision}
      />
      <SetCurrentRevisionDialog
        revision={currentTarget}
        isPending={mutations.setCurrent.isPending}
        onClose={() => setCurrentTarget(null)}
        onConfirm={setCurrent}
      />
      <SupersedeRevisionDialog
        revision={supersedeTarget}
        revisions={revisions}
        isPending={mutations.supersede.isPending}
        onClose={() => setSupersedeTarget(null)}
        onConfirm={supersede}
      />
      <ReplaceDocumentFileDialog
        file={replaceFileTarget}
        revisionStatus={
          replaceFileTarget
            ? (revisions.find(
                (revision) => revision.id === replaceFileTarget.documentRevisionId,
              )?.status.code ?? null)
            : null
        }
        isPending={fileMutations.replace.isPending}
        onClose={() => setReplaceFileTarget(null)}
        onConfirm={replaceFile}
      />
    </section>
  );
}
