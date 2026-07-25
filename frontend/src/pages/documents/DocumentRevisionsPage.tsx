import { ArrowLeft } from 'lucide-react';
import { Link, useParams } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import { ArchivedBadge } from '../../components/documents/ArchivedBadge';
import { DocumentCodeField } from '../../components/documents/DocumentCodeField';
import { DocumentRevisionManager } from '../../components/documents/DocumentRevisionManager';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { useDocument } from '../../hooks/useDocument';

export function DocumentRevisionsPage() {
  const { documentId = '' } = useParams();
  const query = useDocument(documentId || null);

  if (query.isLoading) {
    return (
      <div className="space-y-5" aria-label="Loading revisions">
        <div className="h-24 animate-pulse rounded-3xl bg-slate-100" />
        <div className="h-80 animate-pulse rounded-3xl bg-slate-100" />
      </div>
    );
  }
  if (query.error || !query.data) {
    return (
      <p
        role="alert"
        className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700"
      >
        {getApiErrorMessage(query.error, 'The document could not be loaded.')}
      </p>
    );
  }

  return (
    <div className="space-y-5">
      <MasterDataPageHeader
        eyebrow="Documents"
        title="Revision Management"
        description={query.data.title}
        actions={
          <Link
            to={`/documents/${documentId}`}
            className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 bg-white px-3.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            <ArrowLeft className="size-4" aria-hidden="true" />
            Document Details
          </Link>
        }
      />
      <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <DocumentCodeField code={query.data.baseDocumentCode} />
        {query.data.isArchived && <ArchivedBadge />}
      </div>
      <DocumentRevisionManager document={query.data} />
    </div>
  );
}
