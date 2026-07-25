import { ArrowLeft } from 'lucide-react';
import { Link, useNavigate } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import { DocumentForm } from '../../components/documents/forms/DocumentForm';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { useDocumentMutations } from '../../hooks/useDocumentMutations';
import { useToast } from '../../providers/useToast';
import type { DocumentCreate, DocumentUpdate } from '../../types/document';

export function CreateDocumentPage() {
  const mutations = useDocumentMutations();
  const navigate = useNavigate();
  const { showToast } = useToast();

  const create = async (payload: DocumentCreate | DocumentUpdate): Promise<void> => {
    try {
      const document = await mutations.create.mutateAsync(payload as DocumentCreate);
      showToast({
        tone: 'success',
        title: 'Document created',
        message: document.baseDocumentCode,
      });
      await navigate(`/documents/${document.id}`, { replace: true });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Document could not be created',
        message: getApiErrorMessage(
          error,
          'Review duplicate codes, master data, and revision fields.',
        ),
      });
    }
  };

  return (
    <div className="space-y-5">
      <MasterDataPageHeader
        eyebrow="Documents"
        title="Add Document"
        description="Register a controlled document identity and, optionally, its initial revision in one transaction."
        actions={
          <Link
            to="/documents"
            className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 bg-white px-3.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            <ArrowLeft className="size-4" aria-hidden="true" />
            Back to Register
          </Link>
        }
      />
      <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
        <DocumentForm
          mode="create"
          isPending={mutations.create.isPending}
          onCancel={() => void navigate('/documents')}
          onSubmit={create}
        />
      </div>
    </div>
  );
}
