import { ArrowLeft } from 'lucide-react';
import { useState } from 'react';
import { Link, useParams } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import { ExtractionHistoryTable } from '../../components/documents/ExtractionHistoryTable';
import { ReExtractionDialog } from '../../components/documents/ReExtractionDialog';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { useDocument } from '../../hooks/useDocument';
import { useRevisionFiles } from '../../hooks/useDocumentFiles';
import { useExtractionMutations } from '../../hooks/useExtraction';
import { useExtractionHistory } from '../../hooks/useExtractionHistory';
import { useExtractionExport } from '../../hooks/useExtractedContent';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type { ExtractionRunHistoryItem } from '../../types/extractedContent';
import { downloadFile } from '../../utils/downloadFile';

export function DocumentExtractionHistoryPage() {
  const { documentId = '', revisionId = '' } = useParams();
  const documentQuery = useDocument(documentId || null);
  const filesQuery = useRevisionFiles(documentId || null, revisionId || null);
  const file =
    (filesQuery.data ?? []).find(
      (candidate) => candidate.isCurrent && candidate.fileStatus === 'AVAILABLE',
    ) ?? null;
  const [page, setPage] = useState(1);
  const historyQuery = useExtractionHistory(file?.id ?? null, page, 20, file !== null);
  const [reextractRun, setReextractRun] = useState<ExtractionRunHistoryItem | null>(
    null,
  );
  const exportMutation = useExtractionExport();
  const mutations = useExtractionMutations();
  const { showToast } = useToast();
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const revision = documentQuery.data?.revisions.find(
    (candidate) => candidate.id === revisionId,
  );

  const exportRun = async (
    run: ExtractionRunHistoryItem,
    format: 'json' | 'txt',
  ): Promise<void> => {
    try {
      const result = await exportMutation.mutateAsync({ runId: run.id, format });
      downloadFile(
        result,
        `${documentQuery.data?.baseDocumentCode ?? 'document'}_${
          revision?.revisionCode ?? 'revision'
        }_extraction.${format}`,
      );
      showToast({
        tone: 'success',
        title: `Extraction ${format.toUpperCase()} downloaded`,
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Extraction export failed',
        message: getApiErrorMessage(error, 'The export could not be downloaded.'),
      });
    }
  };

  const reextract = async (reason: string): Promise<void> => {
    if (!file) {
      return;
    }
    try {
      await mutations.reextract.mutateAsync({
        fileId: file.id,
        payload: { reason },
      });
      setReextractRun(null);
      showToast({
        tone: 'success',
        title: 'Re-extraction queued',
        message: 'Every existing run remains available in this history.',
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Re-extraction could not be queued',
        message: getApiErrorMessage(error, 'Review the current file state.'),
      });
    }
  };

  if (documentQuery.isLoading || filesQuery.isLoading) {
    return (
      <div className="space-y-5" aria-label="Loading extraction history">
        <div className="h-28 animate-pulse rounded-3xl bg-slate-100" />
        <div className="h-72 animate-pulse rounded-3xl bg-slate-100" />
      </div>
    );
  }

  if (documentQuery.error || filesQuery.error || !documentQuery.data || !revision) {
    return (
      <p
        role="alert"
        className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700"
      >
        {getApiErrorMessage(
          documentQuery.error || filesQuery.error,
          'The document or revision was not found within your scope.',
        )}
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Documents"
        title="Revision Extraction History"
        description={`${documentQuery.data.baseDocumentCode} · ${revision.revisionCode}`}
        actions={
          <Link
            to={`/documents/${documentId}/revisions/${revisionId}/file`}
            className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 bg-white px-3.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            <ArrowLeft className="size-4" aria-hidden="true" />
            Revision File
          </Link>
        }
      />
      {!file ? (
        <div className="rounded-2xl border border-dashed border-slate-300 px-6 py-12 text-center">
          <p className="text-sm font-semibold text-slate-900">
            No current available physical file.
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Extraction history is associated with a specific physical file.
          </p>
        </div>
      ) : historyQuery.isLoading ? (
        <div className="h-72 animate-pulse rounded-3xl bg-slate-100" />
      ) : historyQuery.error ? (
        <p
          role="alert"
          className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700"
        >
          {getApiErrorMessage(
            historyQuery.error,
            'Extraction history could not be loaded.',
          )}
        </p>
      ) : (
        <>
          <ExtractionHistoryTable
            runs={historyQuery.data?.items ?? []}
            documentId={documentId}
            revisionId={revisionId}
            canExport={hasPermission('documents:export_extracted_content')}
            canReextract={
              hasPermission('documents:reextract') &&
              !documentQuery.data.isArchived &&
              file.isCurrent &&
              file.fileStatus === 'AVAILABLE'
            }
            isExporting={exportMutation.isPending}
            onExport={(run, format) => void exportRun(run, format)}
            onReextract={setReextractRun}
          />
          {historyQuery.data && historyQuery.data.totalPages > 1 && (
            <div className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white p-4 text-xs text-slate-600">
              <span>
                Page {page} of {historyQuery.data.totalPages} ·{' '}
                {historyQuery.data.totalItems.toLocaleString()} runs
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                  disabled={page <= 1}
                  className="min-h-9 rounded-lg border border-slate-300 px-3 font-semibold disabled:opacity-50"
                >
                  Previous
                </button>
                <button
                  type="button"
                  onClick={() => setPage((current) => current + 1)}
                  disabled={page >= historyQuery.data.totalPages}
                  className="min-h-9 rounded-lg border border-slate-300 px-3 font-semibold disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}
      <ReExtractionDialog
        isOpen={reextractRun !== null}
        run={reextractRun}
        isPending={mutations.reextract.isPending}
        onClose={() => setReextractRun(null)}
        onConfirm={reextract}
      />
    </div>
  );
}
