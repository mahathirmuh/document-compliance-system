import { ArrowLeft, RotateCcw } from 'lucide-react';
import { Link, useNavigate, useParams } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import { DocumentForm } from '../../components/documents/forms/DocumentForm';
import { ConfirmationDialog } from '../../components/master-data/ConfirmationDialog';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { useDocument } from '../../hooks/useDocument';
import { useDocumentMutations } from '../../hooks/useDocumentMutations';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type { DocumentCreate, DocumentUpdate } from '../../types/document';
import { useState } from 'react';

export function EditDocumentPage() {
  const { documentId = '' } = useParams();
  const navigate = useNavigate();
  const [restoreOpen, setRestoreOpen] = useState(false);
  const query = useDocument(documentId || null);
  const mutations = useDocumentMutations();
  const canRestore = useAuthStore((state) => state.hasPermission('documents:restore'));
  const { showToast } = useToast();

  const update = async (payload: DocumentCreate | DocumentUpdate): Promise<void> => {
    try {
      const document = await mutations.update.mutateAsync({
        documentId,
        payload: payload as DocumentUpdate,
      });
      showToast({
        tone: 'success',
        title: 'Document updated',
        message: document.baseDocumentCode,
      });
      await navigate(`/documents/${document.id}`, { replace: true });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Document could not be updated',
        message: getApiErrorMessage(
          error,
          'Review controlled code changes and try again.',
        ),
      });
    }
  };

  const restore = async (): Promise<void> => {
    try {
      await mutations.restore.mutateAsync(documentId);
      showToast({ tone: 'success', title: 'Document restored' });
      setRestoreOpen(false);
      await query.refetch();
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Document could not be restored',
        message: getApiErrorMessage(error, 'Check for a conflicting document code.'),
      });
    }
  };

  if (query.isLoading) {
    return <DocumentPageSkeleton />;
  }
  if (query.error || !query.data) {
    return (
      <div className="rounded-3xl border border-rose-200 bg-white p-8 text-center shadow-sm">
        <h1 className="text-lg font-semibold text-slate-950">
          Document could not be loaded
        </h1>
        <p className="mt-2 text-sm text-rose-700">
          {getApiErrorMessage(
            query.error,
            'The document was not found or is inaccessible.',
          )}
        </p>
        <Link
          to="/documents"
          className="mt-5 inline-flex min-h-10 items-center rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white"
        >
          Back to Register
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <MasterDataPageHeader
        eyebrow="Documents"
        title="Edit Document"
        description={`Maintain metadata for ${query.data.baseDocumentCode}. Controlled identity changes require an audit reason.`}
        actions={
          <>
            {query.data.isArchived && canRestore && (
              <button
                type="button"
                onClick={() => setRestoreOpen(true)}
                className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-emerald-600 px-4 text-sm font-semibold text-white hover:bg-emerald-700"
              >
                <RotateCcw className="size-4" aria-hidden="true" />
                Restore Document
              </button>
            )}
            <Link
              to={`/documents/${documentId}`}
              className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 bg-white px-3.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              <ArrowLeft className="size-4" aria-hidden="true" />
              Cancel
            </Link>
          </>
        }
      />
      <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
        <DocumentForm
          mode="edit"
          document={query.data}
          isPending={mutations.update.isPending}
          onCancel={() => void navigate(`/documents/${documentId}`)}
          onSubmit={update}
        />
      </div>
      <ConfirmationDialog
        isOpen={restoreOpen}
        title="Restore document?"
        message="The backend will recheck code uniqueness before returning this record to the active register."
        confirmLabel="Restore"
        tone="primary"
        isPending={mutations.restore.isPending}
        onCancel={() => setRestoreOpen(false)}
        onConfirm={() => void restore()}
      />
    </div>
  );
}

function DocumentPageSkeleton() {
  return (
    <div className="space-y-5" aria-label="Loading document">
      <div className="h-24 animate-pulse rounded-3xl bg-slate-100" />
      <div className="h-[34rem] animate-pulse rounded-3xl bg-slate-100" />
    </div>
  );
}
