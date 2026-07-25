import {
  CheckCircle2,
  Filter,
  ListChecks,
  PencilLine,
  UploadCloud,
  X,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import { FileDropzone } from '../../components/documents/FileDropzone';
import { IdentificationStatusBadge } from '../../components/documents/FileIdentificationPreview';
import { ManualIdentificationForm } from '../../components/documents/ManualIdentificationForm';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { useBatchDocumentUpload } from '../../hooks/useBatchDocumentUpload';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type {
  FileIdentificationStatus,
  UploadConfirmationItem,
  UploadConfirmationResult,
  UploadProposedAction,
  UploadSessionItem,
} from '../../types/documentUpload';
import {
  documentBatchMaxFiles,
  documentBatchMaxTotalSizeBytes,
  formatFileSize,
} from '../../utils/documentFiles';
import { formatDateTime } from '../../utils/formatters';
import { isUploadActionAllowed, uploadActionLabels } from '../../utils/uploadActions';

type ResultFilter = 'ALL' | FileIdentificationStatus;

const rowActions = [
  'ATTACH_TO_EXISTING_REVISION',
  'CREATE_DOCUMENT_AND_REVISION',
  'ADD_NEW_REVISION',
  'REPLACE_CURRENT_FILE',
  'SKIP',
] as const satisfies readonly UploadProposedAction[];

export function BatchUploadPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [selectionError, setSelectionError] = useState<string | null>(null);
  const [previewItems, setPreviewItems] = useState<UploadSessionItem[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [filter, setFilter] = useState<ResultFilter>('ALL');
  const [bulkAction, setBulkAction] = useState<UploadProposedAction | ''>('');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [confirmations, setConfirmations] = useState<
    Record<string, UploadConfirmationItem>
  >({});
  const [editingItem, setEditingItem] = useState<UploadSessionItem | null>(null);
  const [result, setResult] = useState<UploadConfirmationResult | null>(null);
  const workflow = useBatchDocumentUpload();
  const { showToast } = useToast();
  const permissions = useAuthStore((state) => state.permissions);
  const allowedRowActions = useMemo(
    () => rowActions.filter((action) => isUploadActionAllowed(action, permissions)),
    [permissions],
  );

  const visibleItems = useMemo(
    () =>
      filter === 'ALL'
        ? previewItems
        : previewItems.filter((item) => item.identificationStatus === filter),
    [filter, previewItems],
  );
  const totalSize = files.reduce((sum, file) => sum + file.size, 0);
  const expired = expiresAt ? new Date(expiresAt).getTime() <= now : false;

  useEffect(() => {
    if (!expiresAt) {
      return;
    }
    const timer = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, [expiresAt]);

  const updateFiles = (nextFiles: File[]): void => {
    const nextTotal = nextFiles.reduce((sum, file) => sum + file.size, 0);
    if (nextTotal > documentBatchMaxTotalSizeBytes) {
      setSelectionError(
        `Combined size exceeds ${formatFileSize(documentBatchMaxTotalSizeBytes)}.`,
      );
      return;
    }
    setSelectionError(null);
    setFiles(nextFiles);
  };

  const startBatch = async (): Promise<void> => {
    if (files.length === 0) {
      return;
    }
    try {
      const preview = await workflow.upload.mutateAsync(files);
      setPreviewItems(preview.items);
      setSessionId(preview.sessionId);
      setExpiresAt(preview.expiresAt);
      setNow(Date.now());
      setSelectedIds(
        new Set(
          preview.items
            .filter((item) => item.identificationStatus !== 'INVALID')
            .map((item) => item.uploadItemId),
        ),
      );
      setConfirmations(
        Object.fromEntries(
          preview.items.map((item) => [
            item.uploadItemId,
            buildDefaultConfirmation(item, allowedRowActions),
          ]),
        ),
      );
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Batch could not be uploaded',
        message: getApiErrorMessage(
          error,
          'Review the file count, total size, and supported formats.',
        ),
      });
    }
  };

  const setRowAction = (
    item: UploadSessionItem,
    action: UploadProposedAction,
  ): void => {
    setConfirmations((current) => ({
      ...current,
      [item.uploadItemId]: {
        ...(current[item.uploadItemId] ??
          buildDefaultConfirmation(item, allowedRowActions)),
        action,
      },
    }));
  };

  const saveCorrection = async (
    confirmation: UploadConfirmationItem,
  ): Promise<void> => {
    setConfirmations((current) => ({
      ...current,
      [confirmation.uploadItemId]: confirmation,
    }));
    setSelectedIds((current) => new Set(current).add(confirmation.uploadItemId));
    setEditingItem(null);
  };

  const applyBulkAction = (): void => {
    if (!bulkAction) {
      return;
    }
    setConfirmations((current) => {
      const next = { ...current };
      previewItems.forEach((item) => {
        if (
          selectedIds.has(item.uploadItemId) &&
          item.identificationStatus !== 'INVALID'
        ) {
          next[item.uploadItemId] = {
            ...(current[item.uploadItemId] ??
              buildDefaultConfirmation(item, allowedRowActions)),
            action: bulkAction,
          };
        }
      });
      return next;
    });
  };

  const confirmBatch = async (): Promise<void> => {
    if (!sessionId) {
      return;
    }
    const unresolved = previewItems.filter(
      (item) =>
        selectedIds.has(item.uploadItemId) &&
        confirmationNeedsCorrection(
          confirmations[item.uploadItemId] ??
            buildDefaultConfirmation(item, allowedRowActions),
        ),
    );
    if (unresolved.length > 0) {
      showToast({
        tone: 'error',
        title: 'Manual metadata is still required',
        message: `Correct ${unresolved.length} selected file${unresolved.length === 1 ? '' : 's'} before confirming.`,
      });
      return;
    }

    const items = previewItems.map((item): UploadConfirmationItem => {
      if (!selectedIds.has(item.uploadItemId)) {
        return {
          uploadItemId: item.uploadItemId,
          action: 'SKIP',
        };
      }
      return (
        confirmations[item.uploadItemId] ??
        buildDefaultConfirmation(item, allowedRowActions)
      );
    });
    try {
      const confirmationResult = await workflow.confirm.mutateAsync({
        sessionId,
        payload: { items },
      });
      setResult(confirmationResult);
      showToast({ tone: 'success', title: 'Batch confirmation completed' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Batch could not be confirmed',
        message: getApiErrorMessage(
          error,
          'Each item is committed independently; review the server response.',
        ),
      });
    }
  };

  const resetLocal = (): void => {
    setFiles([]);
    setSelectionError(null);
    setPreviewItems([]);
    setSessionId(null);
    setExpiresAt(null);
    setFilter('ALL');
    setBulkAction('');
    setSelectedIds(new Set());
    setConfirmations({});
    setEditingItem(null);
    setResult(null);
    workflow.reset();
  };

  const cancelAndReset = async (): Promise<void> => {
    if (sessionId && !expired) {
      try {
        await workflow.cancel.mutateAsync(sessionId);
      } catch (error: unknown) {
        showToast({
          tone: 'error',
          title: 'Temporary batch could not be cancelled',
          message: getApiErrorMessage(error, 'Try again before the session expires.'),
        });
        return;
      }
    }
    resetLocal();
  };

  if (result) {
    return <BatchResult result={result} onReset={resetLocal} />;
  }

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Documents"
        title="Batch Upload"
        description="Validate multiple physical files, review identification per item, and commit selected files independently."
      />

      {previewItems.length === 0 ? (
        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
          <FileDropzone
            files={files}
            onFilesChange={updateFiles}
            multiple
            maximumFiles={documentBatchMaxFiles}
            disabled={workflow.upload.isPending}
          />
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-600">
            <span>
              {files.length}/{documentBatchMaxFiles} files selected
            </span>
            <span>
              {formatFileSize(totalSize)} /{' '}
              {formatFileSize(documentBatchMaxTotalSizeBytes)}
            </span>
          </div>
          {selectionError && (
            <p
              role="alert"
              className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700"
            >
              {selectionError}
            </p>
          )}
          {workflow.upload.isPending && (
            <div className="mt-5" role="status">
              <div className="flex justify-between text-xs font-semibold text-slate-700">
                <span>Uploading batch</span>
                <span>{workflow.progress}%</span>
              </div>
              <div
                role="progressbar"
                aria-label="Overall batch upload"
                aria-valuenow={workflow.progress}
                aria-valuemin={0}
                aria-valuemax={100}
                className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100"
              >
                <div
                  className="h-full rounded-full bg-blue-700 transition-[width]"
                  style={{ width: `${workflow.progress}%` }}
                />
              </div>
              <p className="mt-3 text-[11px] leading-5 text-slate-500">
                Per-file percentages are estimates derived from aggregate multipart
                bytes, file size, and request order; multipart overhead can shift the
                exact boundary.
              </p>
              <ul className="mt-2 grid gap-1 text-[11px] text-slate-500 sm:grid-cols-2">
                {files.map((file, index) => (
                  <li
                    key={`${file.name}-${file.lastModified}`}
                    className="min-w-0 rounded-lg bg-slate-50 px-2 py-1.5"
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="truncate">{file.name}</span>
                      <span className="shrink-0 font-semibold text-blue-700">
                        {workflow.fileProgress[index] ?? 0}% estimated
                      </span>
                    </span>
                    <span className="mt-1 block h-1 overflow-hidden rounded-full bg-slate-200">
                      <span
                        className="block h-full rounded-full bg-blue-600"
                        style={{
                          width: `${workflow.fileProgress[index] ?? 0}%`,
                        }}
                      />
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="mt-6 flex justify-end">
            <button
              type="button"
              onClick={() => void startBatch()}
              disabled={
                files.length === 0 ||
                selectionError !== null ||
                workflow.upload.isPending
              }
              className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-blue-700 px-5 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <UploadCloud className="size-4" aria-hidden="true" />
              {workflow.upload.isPending ? 'Identifying...' : 'Upload and Identify'}
            </button>
          </div>
        </section>
      ) : (
        <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-col gap-4 border-b border-slate-200 p-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-base font-semibold text-slate-950">
                Identification results
              </h2>
              <p className="mt-1 text-xs text-slate-500">
                {selectedIds.size} of {previewItems.length} files selected
              </p>
              {expiresAt && (
                <p className="mt-1 text-xs text-slate-500">
                  Temporary session expires {formatDateTime(expiresAt)}.
                </p>
              )}
            </div>
            <div className="flex flex-col gap-3 sm:items-end">
              <label className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                <Filter className="size-4" aria-hidden="true" />
                Result
                <select
                  value={filter}
                  onChange={(event) => setFilter(event.target.value as ResultFilter)}
                  className="min-h-10 rounded-xl border border-slate-300 bg-white px-3 text-sm"
                >
                  <option value="ALL">All results</option>
                  <option value="IDENTIFIED">Identified</option>
                  <option value="PARTIALLY_IDENTIFIED">Partially identified</option>
                  <option value="NOT_IDENTIFIED">Not identified</option>
                  <option value="DUPLICATE_FILE">Duplicate</option>
                  <option value="INVALID">Invalid</option>
                </select>
              </label>
              <div className="flex flex-wrap items-center justify-end gap-2">
                <label className="text-xs font-semibold text-slate-600">
                  <span className="sr-only">Bulk action</span>
                  <select
                    aria-label="Bulk action"
                    value={bulkAction}
                    onChange={(event) =>
                      setBulkAction(event.target.value as UploadProposedAction | '')
                    }
                    className="min-h-10 rounded-xl border border-slate-300 bg-white px-3 text-sm"
                  >
                    <option value="">Choose bulk action</option>
                    {allowedRowActions.map((action) => (
                      <option key={action} value={action}>
                        {uploadActionLabels[action]}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  onClick={applyBulkAction}
                  disabled={!bulkAction || selectedIds.size === 0 || expired}
                  className="min-h-10 rounded-xl border border-blue-200 bg-blue-50 px-3 text-xs font-semibold text-blue-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Apply to Selected
                </button>
              </div>
            </div>
          </div>
          {expired && (
            <div className="p-5 pb-0">
              <BatchSessionExpired />
            </div>
          )}
          <div className="overflow-x-auto">
            <table className="min-w-[90rem] divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  {[
                    'Select',
                    'Filename',
                    'Type',
                    'Size',
                    'Identification',
                    'Base Document Code',
                    'Revision',
                    'Matched Document',
                    'Warnings',
                    'Errors',
                    'Action',
                    'Correction',
                  ].map((heading) => (
                    <th
                      key={heading}
                      className="whitespace-nowrap px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-500"
                    >
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {visibleItems.map((item) => {
                  const confirmation =
                    confirmations[item.uploadItemId] ??
                    buildDefaultConfirmation(item, allowedRowActions);
                  const selected = selectedIds.has(item.uploadItemId);
                  return (
                    <tr key={item.uploadItemId} className="align-top hover:bg-slate-50">
                      <td className="px-4 py-4">
                        <input
                          type="checkbox"
                          checked={selected}
                          disabled={item.identificationStatus === 'INVALID'}
                          aria-label={`Select ${item.originalFilename}`}
                          onChange={(event) =>
                            setSelectedIds((current) => {
                              const next = new Set(current);
                              if (event.target.checked) {
                                next.add(item.uploadItemId);
                              } else {
                                next.delete(item.uploadItemId);
                              }
                              return next;
                            })
                          }
                          className="size-4 rounded border-slate-300"
                        />
                      </td>
                      <td className="max-w-60 break-all px-4 py-4 text-xs font-semibold text-slate-900">
                        {item.originalFilename}
                      </td>
                      <td className="px-4 py-4 text-xs font-semibold uppercase text-slate-600">
                        {item.fileExtension ?? '—'}
                      </td>
                      <td className="whitespace-nowrap px-4 py-4 text-xs text-slate-600">
                        {formatFileSize(item.fileSize)}
                      </td>
                      <td className="px-4 py-4">
                        <IdentificationStatusBadge status={item.identificationStatus} />
                      </td>
                      <td className="max-w-56 break-all px-4 py-4 text-xs text-slate-700">
                        {item.parsedMetadata?.baseDocumentCode ?? '—'}
                      </td>
                      <td className="px-4 py-4 text-xs text-slate-700">
                        {item.parsedMetadata?.revisionCode ?? '—'}
                      </td>
                      <td className="max-w-56 px-4 py-4 text-xs text-slate-700">
                        {item.matchedDocument?.baseDocumentCode ?? '—'}
                      </td>
                      <td className="max-w-56 px-4 py-4 text-xs text-amber-700">
                        {[item.duplicateWarning?.message, ...item.warnings]
                          .filter(Boolean)
                          .join(' · ') || '—'}
                      </td>
                      <td className="max-w-56 px-4 py-4 text-xs text-rose-700">
                        {item.errors.join(' · ') || '—'}
                      </td>
                      <td className="px-4 py-4">
                        <select
                          value={confirmation.action}
                          disabled={item.identificationStatus === 'INVALID'}
                          aria-label={`Action for ${item.originalFilename}`}
                          onChange={(event) =>
                            setRowAction(
                              item,
                              event.target.value as UploadProposedAction,
                            )
                          }
                          className="min-h-9 max-w-64 rounded-lg border border-slate-300 bg-white px-2 text-xs"
                        >
                          {allowedRowActions.map((action) => (
                            <option key={action} value={action}>
                              {uploadActionLabels[action]}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-4 py-4">
                        {item.identificationStatus !== 'INVALID' && (
                          <button
                            type="button"
                            onClick={() => setEditingItem(item)}
                            className={`inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold ${
                              confirmationNeedsCorrection(confirmation)
                                ? 'bg-amber-100 text-amber-900'
                                : 'bg-slate-100 text-slate-700'
                            }`}
                          >
                            <PencilLine className="size-3.5" aria-hidden="true" />
                            {confirmationNeedsCorrection(confirmation)
                              ? 'Required'
                              : 'Edit'}
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {visibleItems.length === 0 && (
            <p className="p-10 text-center text-sm text-slate-500">
              No files match this result filter.
            </p>
          )}
          <div className="flex flex-col-reverse gap-3 border-t border-slate-200 p-5 sm:flex-row sm:justify-between">
            <button
              type="button"
              onClick={() => void cancelAndReset()}
              disabled={workflow.confirm.isPending || workflow.cancel.isPending}
              className="min-h-11 rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              {workflow.cancel.isPending ? 'Cancelling...' : 'Start Over'}
            </button>
            <button
              type="button"
              onClick={() => void confirmBatch()}
              disabled={workflow.confirm.isPending || selectedIds.size === 0 || expired}
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-blue-700 px-5 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <ListChecks className="size-4" aria-hidden="true" />
              {workflow.confirm.isPending
                ? 'Confirming...'
                : `Confirm ${selectedIds.size} Selected`}
            </button>
          </div>
        </section>
      )}

      {editingItem && (
        <div
          className="fixed inset-0 z-[90] overflow-y-auto bg-slate-950/45 p-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="batch-correction-title"
        >
          <div className="mx-auto my-4 w-full max-w-5xl rounded-3xl bg-slate-50 p-5 shadow-2xl sm:p-7">
            <div className="mb-5 flex items-start justify-between gap-4">
              <div>
                <h2
                  id="batch-correction-title"
                  className="text-lg font-semibold text-slate-950"
                >
                  Correct upload metadata
                </h2>
                <p className="mt-1 break-all text-xs text-slate-500">
                  {editingItem.originalFilename}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setEditingItem(null)}
                aria-label="Close metadata correction"
                className="grid size-9 place-items-center rounded-xl text-slate-500 hover:bg-slate-200"
              >
                <X className="size-4" aria-hidden="true" />
              </button>
            </div>
            <ManualIdentificationForm
              item={editingItem}
              initialAction={confirmations[editingItem.uploadItemId]?.action ?? null}
              isSubmitting={false}
              submitLabel="Save Correction"
              onBack={() => setEditingItem(null)}
              onSubmit={saveCorrection}
            />
          </div>
        </div>
      )}
    </div>
  );
}

const buildDefaultConfirmation = (
  item: UploadSessionItem,
  allowedActions: readonly UploadProposedAction[],
): UploadConfirmationItem => {
  const action =
    item.identificationStatus === 'INVALID' ||
    item.proposedAction === 'MANUAL_REVIEW' ||
    !allowedActions.includes(item.proposedAction)
      ? 'SKIP'
      : item.proposedAction;
  return {
    uploadItemId: item.uploadItemId,
    action,
    documentId: item.matchedDocument?.id ?? null,
    revisionId: item.matchedRevision?.id ?? null,
    metadata: {
      revisionCode: item.parsedMetadata?.revisionCode ?? null,
    },
  };
};

const confirmationNeedsCorrection = (confirmation: UploadConfirmationItem): boolean =>
  confirmation.action === 'CREATE_DOCUMENT_AND_REVISION' ||
  (confirmation.action === 'ADD_NEW_REVISION' &&
    (!confirmation.documentId ||
      !confirmation.metadata?.revisionCode ||
      !confirmation.metadata.documentStatusId)) ||
  (confirmation.action === 'ATTACH_TO_EXISTING_REVISION' &&
    (!confirmation.documentId || !confirmation.revisionId)) ||
  (confirmation.action === 'REPLACE_CURRENT_FILE' &&
    (!confirmation.documentId ||
      !confirmation.revisionId ||
      !confirmation.metadata?.reason));

function BatchSessionExpired() {
  return (
    <div
      role="alert"
      className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"
    >
      <p className="font-semibold">Batch upload session expired</p>
      <p className="mt-1 text-xs leading-5">
        This preview can no longer be confirmed. Start over to select and upload the
        files again.
      </p>
    </div>
  );
}

function BatchResult({
  onReset,
  result,
}: {
  result: UploadConfirmationResult;
  onReset: () => void;
}) {
  const committed =
    result.committed ??
    result.items.filter((item) => item.status === 'COMMITTED').length;
  const skipped =
    result.skipped ?? result.items.filter((item) => item.status === 'SKIPPED').length;
  const failed =
    result.failed ?? result.items.filter((item) => item.status === 'FAILED').length;

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Documents"
        title="Batch Upload Result"
        description="Each selected item was committed in its own transaction."
      />
      <section className="rounded-3xl border border-slate-200 bg-white p-7 shadow-sm">
        <div className="flex items-center gap-4">
          <span className="grid size-14 place-items-center rounded-2xl bg-emerald-50 text-emerald-700">
            <CheckCircle2 className="size-7" aria-hidden="true" />
          </span>
          <div>
            <h2 className="text-lg font-semibold text-slate-950">
              Confirmation completed
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Review any failed item before starting another batch.
            </p>
          </div>
        </div>
        <dl className="mt-6 grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {[
            ['Total', result.total ?? result.items.length],
            ['Committed', committed],
            ['Skipped', skipped],
            ['Failed', failed],
            ['Documents Created', result.documentsCreated ?? 0],
            ['Revisions Created', result.revisionsCreated ?? 0],
          ].map(([label, value]) => (
            <div key={label} className="rounded-2xl bg-slate-50 p-4">
              <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                {label}
              </dt>
              <dd className="mt-1 text-2xl font-semibold text-slate-950">{value}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-6 overflow-x-auto rounded-2xl border border-slate-200">
          <table className="min-w-[50rem] divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                {['Status', 'Action', 'Document', 'Revision', 'Error', 'Link'].map(
                  (heading) => (
                    <th
                      key={heading}
                      className="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-500"
                    >
                      {heading}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {result.items.map((item) => (
                <tr key={item.uploadItemId}>
                  <td className="px-4 py-3 text-xs font-semibold text-slate-800">
                    {item.status}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-600">
                    {uploadActionLabels[item.action]}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-600">
                    {item.baseDocumentCode ?? '—'}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-600">
                    {item.revisionCode ?? '—'}
                  </td>
                  <td className="max-w-80 px-4 py-3 text-xs text-rose-700">
                    {item.error ?? '—'}
                  </td>
                  <td className="px-4 py-3">
                    {item.documentId ? (
                      <Link
                        to={`/documents/${item.documentId}?tab=files`}
                        className="text-xs font-semibold text-blue-700 hover:text-blue-900"
                      >
                        Open
                      </Link>
                    ) : (
                      '—'
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <button
          type="button"
          onClick={onReset}
          className="mt-6 min-h-11 rounded-xl bg-blue-700 px-5 text-sm font-semibold text-white hover:bg-blue-800"
        >
          Upload Another Batch
        </button>
      </section>
    </div>
  );
}
