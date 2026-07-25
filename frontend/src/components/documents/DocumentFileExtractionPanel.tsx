import { Ban, Eye, History, RefreshCw } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';

import { CancelExtractionDialog } from './CancelExtractionDialog';
import { ExtractionProgress } from './ExtractionProgress';
import { ExtractionStatusBadge } from './ExtractionStatusBadge';
import { ReExtractionDialog } from './ReExtractionDialog';
import { StartExtractionButton } from './StartExtractionButton';
import { getApiErrorMessage } from '../../api/errors';
import { useExtractionMutations } from '../../hooks/useExtraction';
import { useExtractionJobs } from '../../hooks/useExtractionJobs';
import { useLatestExtraction } from '../../hooks/useExtractedContent';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type { DocumentFileListItem } from '../../types/documentFile';
import type { ExtractionJob } from '../../types/extraction';
import { isActiveExtractionStatus } from '../../types/extraction';
import { formatDateTime } from '../../utils/formatters';

export function DocumentFileExtractionPanel({
  documentArchived = false,
  file,
}: {
  file: DocumentFileListItem;
  documentArchived?: boolean;
}) {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canViewContent = hasPermission('documents:view_extracted_content');
  const canTrackJobs =
    hasPermission('documents:view_extraction_history') ||
    hasPermission('documents:extract');
  const [reextractOpen, setReextractOpen] = useState(false);
  const [cancelTarget, setCancelTarget] = useState<ExtractionJob | null>(null);
  const { showToast } = useToast();
  const mutations = useExtractionMutations();
  const jobsQuery = useExtractionJobs(
    {
      documentFileId: file.id,
      page: 1,
      pageSize: 10,
      sortBy: 'requestedAt',
      sortOrder: 'desc',
    },
    { enabled: canTrackJobs, pollActive: true },
  );
  const latestQuery = useLatestExtraction(file.id, canViewContent);
  const activeJob = jobsQuery.data?.items.find((job) =>
    isActiveExtractionStatus(job.status),
  );
  const latestRun = latestQuery.data ?? null;
  const canMutate =
    file.isCurrent &&
    file.fileStatus === 'AVAILABLE' &&
    !documentArchived &&
    !activeJob;
  const contentPath = `/documents/${file.documentId}/revisions/${file.documentRevisionId}/extracted-content`;
  const historyPath = `/documents/${file.documentId}/revisions/${file.documentRevisionId}/extraction-history`;

  const reextract = async (reason: string): Promise<void> => {
    try {
      await mutations.reextract.mutateAsync({
        fileId: file.id,
        payload: { reason },
      });
      setReextractOpen(false);
      showToast({
        tone: 'success',
        title: 'Re-extraction queued',
        message: 'The previous extraction result remains available in history.',
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Re-extraction could not be queued',
        message: getApiErrorMessage(error, 'Review the file state and try again.'),
      });
    }
  };

  const cancel = async (): Promise<void> => {
    if (!cancelTarget) {
      return;
    }
    try {
      await mutations.cancel.mutateAsync(cancelTarget.id);
      setCancelTarget(null);
      showToast({
        tone: 'success',
        title: 'Cancellation requested',
        message: 'The worker will stop at the next safe checkpoint.',
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Cancellation could not be requested',
        message: getApiErrorMessage(error, 'The job state may have changed.'),
      });
    }
  };

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <p className="break-all text-sm font-semibold text-slate-900">
            {file.originalFilename}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {file.revisionCode} · {file.fileExtension.toUpperCase()}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {activeJob && (
            <>
              <ExtractionStatusBadge status={activeJob.status} />
              {hasPermission('documents:cancel_extraction') &&
                activeJob.status !== 'CANCEL_REQUESTED' && (
                  <button
                    type="button"
                    onClick={() => setCancelTarget(activeJob)}
                    className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-amber-700 hover:bg-amber-50"
                  >
                    <Ban className="size-3.5" aria-hidden="true" />
                    Cancel
                  </button>
                )}
            </>
          )}
          {!activeJob && latestRun && (
            <ExtractionStatusBadge status={latestRun.status} />
          )}
          {!activeJob && !latestRun && !latestQuery.isLoading && (
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-semibold text-slate-600">
              Not Extracted
            </span>
          )}
        </div>
      </div>

      {activeJob && (
        <div className="mt-4">
          <ExtractionProgress
            progress={activeJob.progress}
            status={activeJob.status}
            currentStage={activeJob.currentStage}
          />
        </div>
      )}
      {latestRun && !activeJob && (
        <dl className="mt-4 grid gap-3 text-xs sm:grid-cols-2 xl:grid-cols-5">
          <div>
            <dt className="font-semibold text-slate-500">Last Extracted</dt>
            <dd className="mt-1 text-slate-800">
              {formatDateTime(latestRun.completedAt)}
            </dd>
          </div>
          <div>
            <dt className="font-semibold text-slate-500">Extractor</dt>
            <dd className="mt-1 text-slate-800">{latestRun.extractorType}</dd>
          </div>
          <div>
            <dt className="font-semibold text-slate-500">Characters</dt>
            <dd className="mt-1 text-slate-800">
              {latestRun.totalCharacters.toLocaleString()}
            </dd>
          </div>
          <div>
            <dt className="font-semibold text-slate-500">Blocks</dt>
            <dd className="mt-1 text-slate-800">
              {latestRun.totalBlocks.toLocaleString()}
            </dd>
          </div>
          <div>
            <dt className="font-semibold text-slate-500">Requires OCR</dt>
            <dd className="mt-1 text-slate-800">
              {latestRun.requiresOcr ? 'Yes' : 'No'}
            </dd>
          </div>
        </dl>
      )}
      {latestQuery.error && (
        <p role="alert" className="mt-3 text-xs text-rose-700">
          {getApiErrorMessage(
            latestQuery.error,
            'Extraction status could not be loaded.',
          )}
        </p>
      )}
      <div className="mt-4 flex flex-wrap gap-2 border-t border-slate-100 pt-4">
        {!latestRun && canMutate && <StartExtractionButton fileId={file.id} />}
        {latestRun &&
          hasPermission('documents:view_extracted_content') &&
          latestRun.status !== 'OCR_REQUIRED' && (
            <Link
              to={contentPath}
              className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-blue-50 px-3 text-xs font-semibold text-blue-700 hover:bg-blue-100"
            >
              <Eye className="size-3.5" aria-hidden="true" />
              View Content
            </Link>
          )}
        {latestRun?.status === 'OCR_REQUIRED' &&
          hasPermission('documents:view_extracted_content') && (
            <Link
              to={contentPath}
              className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-orange-50 px-3 text-xs font-semibold text-orange-800 hover:bg-orange-100"
            >
              <Eye className="size-3.5" aria-hidden="true" />
              View OCR Notice
            </Link>
          )}
        {latestRun && canMutate && hasPermission('documents:reextract') && (
          <button
            type="button"
            onClick={() => setReextractOpen(true)}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-indigo-700 hover:bg-indigo-50"
          >
            <RefreshCw className="size-3.5" aria-hidden="true" />
            Re-extract
          </button>
        )}
        {hasPermission('documents:view_extraction_history') && (
          <Link
            to={historyPath}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-slate-600 hover:bg-slate-100"
          >
            <History className="size-3.5" aria-hidden="true" />
            Extraction History
          </Link>
        )}
      </div>

      <ReExtractionDialog
        isOpen={reextractOpen}
        run={latestRun}
        isPending={mutations.reextract.isPending}
        onClose={() => setReextractOpen(false)}
        onConfirm={reextract}
      />
      <CancelExtractionDialog
        job={cancelTarget}
        isPending={mutations.cancel.isPending}
        onCancel={() => setCancelTarget(null)}
        onConfirm={cancel}
      />
    </article>
  );
}
