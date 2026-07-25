import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  FileCheck2,
  RefreshCw,
  UploadCloud,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import { FileDropzone } from '../../components/documents/FileDropzone';
import { FileIdentificationPreview } from '../../components/documents/FileIdentificationPreview';
import { ManualIdentificationForm } from '../../components/documents/ManualIdentificationForm';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { useDocument } from '../../hooks/useDocument';
import { useDocumentUpload } from '../../hooks/useDocumentUpload';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type {
  UploadConfirmationItem,
  UploadConfirmationResult,
  UploadPreviewResponse,
  UploadProposedAction,
} from '../../types/documentUpload';
import { formatDateTime } from '../../utils/formatters';
import { isUploadActionAllowed, uploadActionLabels } from '../../utils/uploadActions';

const steps = [
  'Select File',
  'Identification',
  'Confirm Action',
  'Metadata',
  'Result',
] as const;

const actionChoices = [
  'ATTACH_TO_EXISTING_REVISION',
  'CREATE_DOCUMENT_AND_REVISION',
  'ADD_NEW_REVISION',
  'REPLACE_CURRENT_FILE',
  'SKIP',
] as const satisfies readonly UploadProposedAction[];

export function UploadDocumentPage() {
  const [searchParams] = useSearchParams();
  const [files, setFiles] = useState<File[]>([]);
  const [step, setStep] = useState(0);
  const [preview, setPreview] = useState<UploadPreviewResponse | null>(null);
  const [result, setResult] = useState<UploadConfirmationResult | null>(null);
  const [selectedAction, setSelectedAction] = useState<UploadProposedAction | ''>('');
  const [now, setNow] = useState(() => Date.now());
  const workflow = useDocumentUpload();
  const { showToast } = useToast();
  const permissions = useAuthStore((state) => state.permissions);
  const availableActionChoices = actionChoices.filter((action) =>
    isUploadActionAllowed(action, permissions),
  );
  const documentId = searchParams.get('documentId') ?? undefined;
  const revisionId = searchParams.get('revisionId') ?? undefined;
  const contextDocumentQuery = useDocument(documentId ?? null);
  const targetArchived = contextDocumentQuery.data?.isArchived ?? false;
  const targetVerificationBlocked =
    Boolean(documentId) &&
    (contextDocumentQuery.isLoading ||
      Boolean(contextDocumentQuery.error) ||
      targetArchived);
  const item = preview?.items[0] ?? null;
  const expired = preview ? new Date(preview.expiresAt).getTime() <= now : false;

  useEffect(() => {
    if (!preview) {
      return;
    }
    const timer = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, [preview]);

  const startUpload = async (): Promise<void> => {
    const file = files[0];
    if (!file || targetVerificationBlocked) {
      return;
    }
    try {
      const nextPreview = await workflow.upload.mutateAsync({
        file,
        ...(documentId ? { documentId } : {}),
        ...(revisionId ? { revisionId } : {}),
      });
      setPreview(nextPreview);
      const nextItem = nextPreview.items[0];
      setSelectedAction(
        nextItem &&
          nextItem.proposedAction !== 'MANUAL_REVIEW' &&
          availableActionChoices.includes(
            nextItem.proposedAction as (typeof actionChoices)[number],
          )
          ? nextItem.proposedAction
          : '',
      );
      setNow(Date.now());
      setStep(1);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'File could not be uploaded',
        message: getApiErrorMessage(
          error,
          'The server rejected the file or could not validate it.',
        ),
      });
    }
  };

  const confirm = async (confirmation: UploadConfirmationItem): Promise<void> => {
    if (!preview || expired) {
      return;
    }
    try {
      const confirmationResult = await workflow.confirm.mutateAsync({
        sessionId: preview.sessionId,
        payload: { items: [confirmation] },
      });
      setResult(confirmationResult);
      setStep(4);
      showToast({ tone: 'success', title: 'Upload confirmation completed' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Upload could not be confirmed',
        message: getApiErrorMessage(
          error,
          'The session, permission, department scope, and target were revalidated.',
        ),
      });
    }
  };

  const cancelSession = async (): Promise<void> => {
    if (preview && !['COMMITTED', 'CANCELLED', 'EXPIRED'].includes(preview.status)) {
      try {
        await workflow.cancel.mutateAsync(preview.sessionId);
      } catch (error: unknown) {
        showToast({
          tone: 'error',
          title: 'Temporary upload could not be cancelled',
          message: getApiErrorMessage(error, 'Try again before the session expires.'),
        });
        return;
      }
    }
    resetWorkflow();
  };

  const resetWorkflow = (): void => {
    setFiles([]);
    setPreview(null);
    setResult(null);
    setSelectedAction('');
    setStep(0);
    workflow.reset();
  };

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Documents"
        title="Upload Document"
        description="Validate and identify a physical PDF, DOCX, or XLSX before it is committed to the document register."
      />

      {documentId && (
        <UploadTargetStatus
          isLoading={contextDocumentQuery.isLoading}
          hasError={Boolean(contextDocumentQuery.error)}
          isArchived={targetArchived}
          code={contextDocumentQuery.data?.baseDocumentCode ?? null}
        />
      )}

      <UploadStepper step={step} />

      {step === 0 && (
        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
          <FileDropzone
            files={files}
            onFilesChange={setFiles}
            disabled={workflow.upload.isPending || targetVerificationBlocked}
          />
          {workflow.upload.isPending && (
            <UploadProgress
              progress={workflow.progress}
              label="Uploading and validating"
            />
          )}
          <div className="mt-6 flex justify-end">
            <button
              type="button"
              onClick={() => void startUpload()}
              disabled={
                files.length !== 1 ||
                workflow.upload.isPending ||
                targetVerificationBlocked
              }
              className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-blue-700 px-5 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <UploadCloud className="size-4" aria-hidden="true" />
              {workflow.upload.isPending ? 'Identifying...' : 'Upload and Identify'}
            </button>
          </div>
        </section>
      )}

      {step === 1 && item && preview && (
        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
          <div className="mb-5 flex flex-col gap-2 border-b border-slate-200 pb-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">
                Identification result
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Temporary session expires {formatDateTime(preview.expiresAt)}.
              </p>
            </div>
            <button
              type="button"
              onClick={() => void cancelSession()}
              disabled={workflow.cancel.isPending}
              className="text-xs font-semibold text-slate-600 hover:text-slate-950"
            >
              Cancel temporary upload
            </button>
          </div>
          {expired && <SessionExpired />}
          <FileIdentificationPreview item={item} />
          <div className="mt-6 flex justify-end">
            <button
              type="button"
              onClick={() => setStep(2)}
              disabled={expired || item.identificationStatus === 'INVALID'}
              className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-blue-700 px-5 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Review Action
              <ChevronRight className="size-4" aria-hidden="true" />
            </button>
          </div>
        </section>
      )}

      {step === 2 && item && (
        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
          <h2 className="text-lg font-semibold text-slate-950">
            Confirm the intended action
          </h2>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            The proposed action is a preview only. The backend revalidates the target,
            permission, and department scope at commit time.
          </p>
          <fieldset className="mt-5 grid gap-3 lg:grid-cols-2">
            <legend className="sr-only">Upload action</legend>
            {availableActionChoices.map((action) => (
              <label
                key={action}
                className={`flex cursor-pointer items-start gap-3 rounded-2xl border p-4 ${
                  selectedAction === action
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-slate-200 hover:border-blue-300'
                }`}
              >
                <input
                  type="radio"
                  name="upload-action"
                  value={action}
                  checked={selectedAction === action}
                  onChange={() => setSelectedAction(action)}
                  className="mt-0.5 size-4 border-slate-300 text-blue-700"
                />
                <span>
                  <span className="block text-sm font-semibold text-slate-900">
                    {uploadActionLabels[action]}
                  </span>
                  {action === item.proposedAction && (
                    <span className="mt-1 block text-xs font-semibold text-blue-700">
                      Automatically proposed
                    </span>
                  )}
                </span>
              </label>
            ))}
          </fieldset>
          <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-between">
            <button
              type="button"
              onClick={() => setStep(1)}
              className="min-h-11 rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700"
            >
              Back
            </button>
            <button
              type="button"
              onClick={() => setStep(3)}
              disabled={!selectedAction}
              className="min-h-11 rounded-xl bg-blue-700 px-5 text-sm font-semibold text-white disabled:opacity-60"
            >
              Continue to Metadata
            </button>
          </div>
        </section>
      )}

      {step === 3 && item && (
        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
          {expired ? (
            <div className="space-y-5">
              <SessionExpired />
              <button
                type="button"
                onClick={resetWorkflow}
                className="min-h-11 rounded-xl bg-blue-700 px-5 text-sm font-semibold text-white"
              >
                Start another upload
              </button>
            </div>
          ) : (
            <ManualIdentificationForm
              item={item}
              initialAction={selectedAction || null}
              isSubmitting={workflow.confirm.isPending}
              onBack={() => setStep(2)}
              onSubmit={confirm}
            />
          )}
        </section>
      )}

      {step === 4 && result && <UploadResult result={result} onReset={resetWorkflow} />}
    </div>
  );
}

function UploadTargetStatus({
  code,
  hasError,
  isArchived,
  isLoading,
}: {
  code: string | null;
  hasError: boolean;
  isArchived: boolean;
  isLoading: boolean;
}) {
  if (isLoading) {
    return (
      <div
        role="status"
        className="rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-600"
      >
        Checking the target document before upload...
      </div>
    );
  }
  if (hasError) {
    return (
      <div
        role="alert"
        className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"
      >
        The target document could not be verified. Upload is disabled.
      </div>
    );
  }
  if (isArchived) {
    return (
      <div
        role="alert"
        className="flex gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"
      >
        <AlertTriangle className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
        <div>
          <p className="font-semibold">Archived document upload blocked</p>
          <p className="mt-1 text-xs leading-5 text-amber-800">
            {code ? `${code} is archived. ` : ''}
            Restore the document before uploading or replacing a physical file.
          </p>
        </div>
      </div>
    );
  }
  return (
    <div className="rounded-2xl border border-blue-200 bg-blue-50 p-4 text-xs text-blue-800">
      Target document {code ?? 'verified'} is active and available for upload.
    </div>
  );
}

function UploadStepper({ step }: { step: number }) {
  return (
    <ol
      aria-label="Upload progress"
      className="grid overflow-hidden rounded-2xl border border-slate-200 bg-white sm:grid-cols-5"
    >
      {steps.map((label, index) => (
        <li
          key={label}
          aria-current={step === index ? 'step' : undefined}
          className={`flex items-center gap-3 border-b border-slate-200 px-4 py-3 last:border-b-0 sm:border-b-0 sm:border-r sm:last:border-r-0 ${
            step === index ? 'bg-blue-50 text-blue-800' : 'text-slate-500'
          }`}
        >
          <span
            className={`grid size-7 shrink-0 place-items-center rounded-full text-xs font-bold ${
              index < step
                ? 'bg-emerald-600 text-white'
                : step === index
                  ? 'bg-blue-700 text-white'
                  : 'bg-slate-100 text-slate-500'
            }`}
          >
            {index < step ? <CheckCircle2 className="size-4" /> : index + 1}
          </span>
          <span className="text-xs font-semibold">{label}</span>
        </li>
      ))}
    </ol>
  );
}

function UploadProgress({ label, progress }: { label: string; progress: number }) {
  return (
    <div className="mt-5" role="status" aria-live="polite">
      <div className="flex items-center justify-between text-xs font-semibold text-slate-700">
        <span>{label}</span>
        <span>{progress}%</span>
      </div>
      <div
        className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100"
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progress}
      >
        <div
          className="h-full rounded-full bg-blue-700 transition-[width]"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}

function SessionExpired() {
  return (
    <div
      role="alert"
      className="mb-5 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"
    >
      <p className="font-semibold">Upload session expired</p>
      <p className="mt-1 text-xs leading-5">
        Confirmation is no longer allowed. Start a new upload; temporary files are
        removed by the cleanup process.
      </p>
    </div>
  );
}

function UploadResult({
  onReset,
  result,
}: {
  result: UploadConfirmationResult;
  onReset: () => void;
}) {
  const item = result.items[0];
  const succeeded = item?.status === 'COMMITTED' || item?.fileStatus === 'AVAILABLE';
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-7 text-center shadow-sm">
      <span
        className={`mx-auto grid size-16 place-items-center rounded-3xl ${
          succeeded ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'
        }`}
      >
        {succeeded ? (
          <FileCheck2 className="size-8" aria-hidden="true" />
        ) : (
          <RefreshCw className="size-8" aria-hidden="true" />
        )}
      </span>
      <h2 className="mt-5 text-xl font-semibold text-slate-950">
        {succeeded ? 'Physical file committed' : 'Upload confirmation completed'}
      </h2>
      <dl className="mx-auto mt-5 grid max-w-2xl gap-3 rounded-2xl bg-slate-50 p-5 text-left sm:grid-cols-3">
        <ResultField label="Document Code" value={item?.baseDocumentCode ?? '—'} />
        <ResultField label="Revision" value={item?.revisionCode ?? '—'} />
        <ResultField
          label="File Status"
          value={item?.fileStatus ?? item?.status ?? '—'}
        />
      </dl>
      {item?.error && (
        <p role="alert" className="mx-auto mt-4 max-w-xl text-sm text-rose-700">
          {item.error}
        </p>
      )}
      <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
        {item?.documentId && (
          <Link
            to={`/documents/${item.documentId}?tab=files`}
            className="inline-flex min-h-11 items-center justify-center rounded-xl bg-blue-700 px-5 text-sm font-semibold text-white hover:bg-blue-800"
          >
            Open Document
          </Link>
        )}
        <button
          type="button"
          onClick={onReset}
          className="min-h-11 rounded-xl border border-slate-300 px-5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
        >
          Upload Another
        </button>
      </div>
    </section>
  );
}

function ResultField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className="mt-1 break-all text-sm font-semibold text-slate-900">{value}</dd>
    </div>
  );
}
