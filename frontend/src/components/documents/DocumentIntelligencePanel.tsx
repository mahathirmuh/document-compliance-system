import { Eye, Languages, RefreshCw, ScanText } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';

import { LanguageProgress } from './LanguageProgress';
import { LanguageStatusBadge } from './LanguageStatusBadge';
import { OCRProgress } from './OCRProgress';
import { OCRStatusBadge } from './OCRStatusBadge';
import { RedetectLanguageDialog } from './RedetectLanguageDialog';
import { ReOCRDialog } from './ReOCRDialog';
import { StartOCRDialog } from './StartOCRDialog';
import { getPresenceClass, presenceLabels } from './languageDisplay';
import { formatConfidence } from './ocrDisplay';
import { getApiErrorMessage } from '../../api/errors';
import { useLatestExtraction } from '../../hooks/useExtractedContent';
import { useLanguageDetectionMutations } from '../../hooks/useLanguageDetection';
import { useLanguageDetectionJobs } from '../../hooks/useLanguageDetectionJobs';
import {
  useLanguageSummary,
  useLatestLanguageDetection,
} from '../../hooks/useLanguageResults';
import { useLatestOCR, useOCRMutations } from '../../hooks/useOCR';
import { useOCRJobs } from '../../hooks/useOCRJobs';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type { DocumentFileListItem } from '../../types/documentFile';
import { isActiveLanguageDetectionStatus } from '../../types/languageDetection';
import type { OCRReprocessRequest, OCRStartRequest } from '../../types/ocr';
import { isActiveOCRStatus } from '../../types/ocr';

export function DocumentIntelligencePanel({
  documentArchived = false,
  file,
}: {
  file: DocumentFileListItem;
  documentArchived?: boolean;
}) {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canViewOCR = hasPermission('documents:view_ocr_results');
  const canViewLanguage = hasPermission('documents:view_language_results');
  const canTrackOCR =
    hasPermission('documents:ocr') || hasPermission('documents:view_ocr_history');
  const canTrackLanguage = canViewLanguage;
  const canLoadExtraction =
    hasPermission('documents:view_extracted_content') ||
    hasPermission('documents:ocr') ||
    hasPermission('documents:detect_language');
  const extractionQuery = useLatestExtraction(file.id, canLoadExtraction);
  const ocrQuery = useLatestOCR(file.id, canViewOCR || hasPermission('documents:ocr'));
  const languageQuery = useLatestLanguageDetection(file.id, canViewLanguage);
  const ocrJobsQuery = useOCRJobs(
    {
      documentFileId: file.id,
      page: 1,
      pageSize: 10,
      sortBy: 'requestedAt',
      sortOrder: 'desc',
    },
    { enabled: canTrackOCR, pollActive: true },
  );
  const languageJobsQuery = useLanguageDetectionJobs(
    {
      documentFileId: file.id,
      page: 1,
      pageSize: 10,
      sortBy: 'requestedAt',
      sortOrder: 'desc',
    },
    { enabled: canTrackLanguage, pollActive: true },
  );
  const latestOCR = ocrQuery.data ?? null;
  const latestLanguage = languageQuery.data ?? null;
  const summaryQuery = useLanguageSummary(
    latestLanguage?.runId ?? null,
    latestLanguage !== null && canViewLanguage,
  );
  const activeOCR = ocrJobsQuery.data?.items.find((job) =>
    isActiveOCRStatus(job.status),
  );
  const activeLanguage = languageJobsQuery.data?.items.find((job) =>
    isActiveLanguageDetectionStatus(job.status),
  );
  const extraction = extractionQuery.data ?? null;
  const canMutate =
    file.isCurrent && file.fileStatus === 'AVAILABLE' && !documentArchived;
  const canForceOCR = hasPermission('documents:reocr');
  const canStartOCR =
    file.fileExtension === 'pdf' &&
    canMutate &&
    extraction !== null &&
    !activeOCR &&
    hasPermission('documents:ocr') &&
    (extraction.requiresOcr || canForceOCR);
  const hasLanguageSource =
    extraction !== null && (extraction.status !== 'OCR_REQUIRED' || latestOCR !== null);
  const canStartLanguage =
    canMutate &&
    hasLanguageSource &&
    !activeLanguage &&
    hasPermission('documents:detect_language') &&
    latestLanguage === null;
  const [startOCROpen, setStartOCROpen] = useState(false);
  const [reocrOpen, setReocrOpen] = useState(false);
  const [redetectOpen, setRedetectOpen] = useState(false);
  const ocrMutations = useOCRMutations();
  const languageMutations = useLanguageDetectionMutations();
  const { showToast } = useToast();
  const ocrPath = `/documents/${file.documentId}/revisions/${file.documentRevisionId}/ocr-results`;
  const languagePath = `/documents/${file.documentId}/revisions/${file.documentRevisionId}/language-results`;

  const startOCR = async (payload: OCRStartRequest): Promise<void> => {
    try {
      await ocrMutations.start.mutateAsync(payload);
      setStartOCROpen(false);
      showToast({
        tone: 'success',
        title: 'OCR queued',
        message: 'Only pages selected by the server or user will be rendered.',
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'OCR could not be queued',
        message: getApiErrorMessage(
          error,
          'This PDF may not require OCR or another job may be active.',
        ),
      });
    }
  };

  const reocr = async (payload: OCRReprocessRequest): Promise<void> => {
    if (!latestOCR) {
      return;
    }
    try {
      await ocrMutations.reocr.mutateAsync({
        runId: latestOCR.runId,
        payload,
      });
      setReocrOpen(false);
      showToast({ tone: 'success', title: 'Re-OCR queued' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Re-OCR could not be queued',
        message: getApiErrorMessage(error, 'Review the page selection and reason.'),
      });
    }
  };

  const startLanguage = async (): Promise<void> => {
    if (!extraction) {
      return;
    }
    try {
      const result = await languageMutations.start.mutateAsync({
        documentFileId: file.id,
        extractionRunId: extraction.runId,
        ocrRunId: latestOCR?.runId ?? null,
        force: false,
      });
      showToast({
        tone: 'success',
        title: result.reusedExistingResult
          ? 'Existing language result loaded'
          : 'Language detection queued',
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Language detection could not be started',
        message: getApiErrorMessage(error, 'Review the extracted content state.'),
      });
    }
  };

  const redetect = async (reason: string): Promise<void> => {
    if (!latestLanguage) {
      return;
    }
    try {
      await languageMutations.redetect.mutateAsync({
        runId: latestLanguage.runId,
        payload: { reason },
      });
      setRedetectOpen(false);
      showToast({ tone: 'success', title: 'Language re-detection queued' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Language re-detection could not be queued',
        message: getApiErrorMessage(error, 'Review the current source content.'),
      });
    }
  };

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <p className="break-all text-sm font-semibold text-slate-900">
            {file.originalFilename}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {file.revisionCode} · {file.fileExtension.toUpperCase()} ·{' '}
            {file.isCurrent ? 'Current file' : 'Historical file'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {activeOCR ? (
            <OCRStatusBadge status={activeOCR.status} />
          ) : latestOCR ? (
            <OCRStatusBadge status={latestOCR.status} />
          ) : (
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-semibold text-slate-600">
              OCR Not Run
            </span>
          )}
          {activeLanguage ? (
            <LanguageStatusBadge status={activeLanguage.status} />
          ) : latestLanguage ? (
            <LanguageStatusBadge status={latestLanguage.status} />
          ) : (
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-semibold text-slate-600">
              Language Not Detected
            </span>
          )}
        </div>
      </div>

      {(activeOCR || activeLanguage) && (
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          {activeOCR && (
            <OCRProgress
              status={activeOCR.status}
              progress={activeOCR.progress}
              currentStage={activeOCR.currentStage}
            />
          )}
          {activeLanguage && (
            <LanguageProgress
              status={activeLanguage.status}
              progress={activeLanguage.progress}
              currentStage={activeLanguage.currentStage}
            />
          )}
        </div>
      )}

      <dl className="mt-4 grid gap-3 text-xs sm:grid-cols-2 xl:grid-cols-6">
        <Metric
          label="Extraction Status"
          value={
            !canLoadExtraction
              ? 'Unavailable'
              : (extraction?.status ??
                (extractionQuery.isLoading ? 'Loading…' : 'Not Run'))
          }
        />
        <Metric
          label="OCR Status"
          value={activeOCR?.status ?? latestOCR?.status ?? 'Not Run'}
        />
        <Metric
          label="OCR Confidence"
          value={formatConfidence(latestOCR?.averageConfidence ?? null)}
        />
        {(['id', 'en', 'zh'] as const).map((code) => {
          const presence = summaryQuery.data?.languagePresence[code];
          return (
            <div key={code}>
              <dt className="font-semibold text-slate-500">
                {code === 'id' ? 'Indonesian' : code === 'en' ? 'English' : 'Chinese'}
              </dt>
              <dd className="mt-1">
                {presence ? (
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${getPresenceClass(
                      presence,
                    )}`}
                  >
                    {presenceLabels[presence]}
                  </span>
                ) : (
                  <span className="text-slate-700">Not detected</span>
                )}
              </dd>
            </div>
          );
        })}
      </dl>

      {(extractionQuery.error || ocrQuery.error || languageQuery.error) && (
        <p role="alert" className="mt-3 text-xs text-rose-700">
          {getApiErrorMessage(
            extractionQuery.error || ocrQuery.error || languageQuery.error,
            'Content intelligence status could not be loaded.',
          )}
        </p>
      )}

      <div className="mt-4 flex flex-wrap gap-2 border-t border-slate-100 pt-4">
        {canStartOCR && (
          <button
            type="button"
            onClick={() => setStartOCROpen(true)}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-blue-50 px-3 text-xs font-semibold text-blue-700 hover:bg-blue-100"
          >
            <ScanText className="size-3.5" aria-hidden="true" />
            Run OCR
          </button>
        )}
        {latestOCR && canViewOCR && (
          <Link
            to={ocrPath}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-blue-700 hover:bg-blue-50"
          >
            <Eye className="size-3.5" aria-hidden="true" />
            View OCR
          </Link>
        )}
        {latestOCR && canMutate && !activeOCR && hasPermission('documents:reocr') && (
          <button
            type="button"
            onClick={() => setReocrOpen(true)}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-indigo-700 hover:bg-indigo-50"
          >
            <RefreshCw className="size-3.5" aria-hidden="true" />
            Re-run OCR
          </button>
        )}
        {canStartLanguage && (
          <button
            type="button"
            onClick={() => void startLanguage()}
            disabled={languageMutations.start.isPending}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-violet-50 px-3 text-xs font-semibold text-violet-700 hover:bg-violet-100 disabled:opacity-50"
          >
            <Languages className="size-3.5" aria-hidden="true" />
            Detect Languages
          </button>
        )}
        {latestLanguage && canViewLanguage && (
          <Link
            to={languagePath}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-violet-700 hover:bg-violet-50"
          >
            <Eye className="size-3.5" aria-hidden="true" />
            View Language Results
          </Link>
        )}
        {latestLanguage &&
          canMutate &&
          !activeLanguage &&
          hasPermission('documents:redetect_language') && (
            <button
              type="button"
              onClick={() => setRedetectOpen(true)}
              className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-violet-700 hover:bg-violet-50"
            >
              <RefreshCw className="size-3.5" aria-hidden="true" />
              Re-detect Languages
            </button>
          )}
      </div>

      {extraction && (
        <StartOCRDialog
          isOpen={startOCROpen}
          filename={file.originalFilename}
          documentFileId={file.id}
          extractionRunId={extraction.runId}
          allowForce={canForceOCR}
          isPending={ocrMutations.start.isPending}
          onClose={() => setStartOCROpen(false)}
          onConfirm={(payload) => void startOCR(payload)}
        />
      )}
      <ReOCRDialog
        isOpen={reocrOpen}
        run={latestOCR}
        isPending={ocrMutations.reocr.isPending}
        onClose={() => setReocrOpen(false)}
        onConfirm={(payload) => void reocr(payload)}
      />
      <RedetectLanguageDialog
        isOpen={redetectOpen}
        isPending={languageMutations.redetect.isPending}
        onClose={() => setRedetectOpen(false)}
        onConfirm={(reason) => void redetect(reason)}
      />
    </article>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-semibold text-slate-500">{label}</dt>
      <dd className="mt-1 text-slate-800">{value}</dd>
    </div>
  );
}
