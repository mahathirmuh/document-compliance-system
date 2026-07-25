import { Download, FileSpreadsheet, LoaderCircle, Upload, X } from 'lucide-react';
import { useCallback, useEffect, useId, useMemo, useState } from 'react';

import { DocumentImportResultSummary } from './DocumentImportResultSummary';
import { getApiErrorMessage } from '../../api/errors';
import { useDocumentImport } from '../../hooks/useDocumentImport';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import {
  documentImportModes,
  documentImportRowStatuses,
  type DocumentImportMode,
  type DocumentImportRowStatus,
} from '../../types/documentImport';
import { downloadFile } from '../../utils/downloadFile';
import { isXlsxFile } from '../../utils/xlsxFile';

interface DocumentImportDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

const modeDescriptions: Record<DocumentImportMode, [string, string]> = {
  CREATE_ONLY: [
    'Create only',
    'Create new documents and skip every existing document code.',
  ],
  CREATE_AND_ADD_REVISION: [
    'Create and add revisions',
    'Create new documents and add new revisions to matching documents.',
  ],
  UPSERT_METADATA: [
    'Upsert metadata',
    'Also update metadata for matching documents without replacing revisions.',
  ],
};

const previewStatusTones: Record<DocumentImportRowStatus, string> = {
  VALID_CREATE: 'bg-emerald-50 text-emerald-700',
  VALID_ADD_REVISION: 'bg-blue-50 text-blue-700',
  WARNING: 'bg-amber-50 text-amber-800',
  DUPLICATE: 'bg-slate-100 text-slate-700',
  INVALID: 'bg-rose-50 text-rose-700',
};

const previewPageSize = 50;

const getRowDataText = (
  data: Record<string, unknown>,
  snakeCaseKey: string,
  camelCaseKey: string,
): string => {
  const value = data[snakeCaseKey] ?? data[camelCaseKey];
  return typeof value === 'string' && value.trim() ? value : '—';
};

export function DocumentImportDialog({ isOpen, onClose }: DocumentImportDialogProps) {
  const inputId = useId();
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [mode, setMode] = useState<DocumentImportMode>('CREATE_AND_ADD_REVISION');
  const [statusFilter, setStatusFilter] = useState<DocumentImportRowStatus | 'ALL'>(
    'ALL',
  );
  const [previewPage, setPreviewPage] = useState(1);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canImport = hasPermission('documents:import');
  const canUpdate = hasPermission('documents:update');
  const canManageRevisions = hasPermission('documents:manage_revisions');
  const mutations = useDocumentImport();
  const { showToast } = useToast();

  const availableModes = useMemo(
    () =>
      documentImportModes.filter(
        (candidate) =>
          (candidate !== 'UPSERT_METADATA' || canUpdate) &&
          (candidate !== 'CREATE_AND_ADD_REVISION' || canManageRevisions),
      ),
    [canManageRevisions, canUpdate],
  );

  const reset = useCallback((): void => {
    setFile(null);
    setFileError(null);
    setStatusFilter('ALL');
    setPreviewPage(1);
    mutations.preview.reset();
    mutations.confirm.reset();
  }, [mutations.confirm, mutations.preview]);

  const close = useCallback((): void => {
    reset();
    onClose();
  }, [onClose, reset]);

  useEffect(() => {
    if (isOpen && !availableModes.includes(mode)) {
      setMode(availableModes[0] ?? 'CREATE_ONLY');
    }
  }, [availableModes, isOpen, mode]);

  useEffect(() => {
    if (!isOpen || !canImport) {
      return;
    }
    const closeOnEscape = (event: KeyboardEvent): void => {
      if (
        event.key === 'Escape' &&
        !mutations.preview.isPending &&
        !mutations.confirm.isPending
      ) {
        close();
      }
    };
    document.addEventListener('keydown', closeOnEscape);
    return () => document.removeEventListener('keydown', closeOnEscape);
  }, [
    canImport,
    close,
    isOpen,
    mutations.confirm.isPending,
    mutations.preview.isPending,
  ]);

  if (!isOpen || !canImport) {
    return null;
  }

  const chooseFile = (nextFile: File | null): void => {
    mutations.preview.reset();
    mutations.confirm.reset();
    setStatusFilter('ALL');
    setPreviewPage(1);
    if (!nextFile) {
      setFile(null);
      setFileError(null);
      return;
    }
    if (!isXlsxFile(nextFile)) {
      setFile(null);
      setFileError('Choose a valid .xlsx workbook.');
      return;
    }
    setFile(nextFile);
    setFileError(null);
  };

  const downloadTemplate = async (): Promise<void> => {
    try {
      const result = await mutations.template.mutateAsync();
      downloadFile(result, 'document_register_template.xlsx');
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Template download failed',
        message: getApiErrorMessage(error, 'The template could not be downloaded.'),
      });
    }
  };

  const previewWorkbook = async (): Promise<void> => {
    if (!file) {
      setFileError('Choose an XLSX workbook first.');
      return;
    }
    try {
      setPreviewPage(1);
      await mutations.preview.mutateAsync(file);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Import preview failed',
        message: getApiErrorMessage(error, 'The workbook could not be validated.'),
      });
    }
  };

  const confirmImport = async (): Promise<void> => {
    if (!file || !mutations.preview.data) {
      return;
    }
    try {
      const result = await mutations.confirm.mutateAsync({ file, mode });
      showToast({
        tone: 'success',
        title: 'Document register imported',
        message: `${result.documentsCreated} documents created and ${result.revisionsAdded} revisions added.`,
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Import failed',
        message: getApiErrorMessage(error, 'No unconfirmed rows were retained.'),
      });
    }
  };

  const previewRows =
    mutations.preview.data?.rows.filter(
      (row) => statusFilter === 'ALL' || row.status === statusFilter,
    ) ?? [];
  const previewPageCount = Math.max(1, Math.ceil(previewRows.length / previewPageSize));
  const visiblePreviewPage = Math.min(previewPage, previewPageCount);
  const previewStartIndex = (visiblePreviewPage - 1) * previewPageSize;
  const visiblePreviewRows = previewRows.slice(
    previewStartIndex,
    previewStartIndex + previewPageSize,
  );
  const previewRangeStart = visiblePreviewRows.length > 0 ? previewStartIndex + 1 : 0;
  const previewRangeEnd = previewStartIndex + visiblePreviewRows.length;
  const actionableRows = mutations.preview.data
    ? mutations.preview.data.validCreateRows +
      mutations.preview.data.validAddRevisionRows +
      mutations.preview.data.warningRows
    : 0;

  return (
    <div
      className="fixed inset-0 z-[90] grid place-items-center bg-slate-950/50 p-3 backdrop-blur-sm sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="document-import-title"
    >
      <section className="flex max-h-[94vh] w-full max-w-6xl flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-2xl">
        <header className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-5 sm:px-7">
          <div>
            <h2
              id="document-import-title"
              className="text-lg font-semibold text-slate-950"
            >
              Import Document Register
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Preview validates all metadata again before confirmation.
            </p>
          </div>
          <button
            type="button"
            onClick={close}
            disabled={mutations.preview.isPending || mutations.confirm.isPending}
            aria-label="Close document import"
            className="grid size-9 place-items-center rounded-xl text-slate-500 hover:bg-slate-100 disabled:opacity-50"
          >
            <X className="size-5" aria-hidden="true" />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-6 sm:px-7">
          {mutations.confirm.data ? (
            <>
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
                <p className="text-sm font-semibold text-emerald-900">
                  Import completed
                </p>
                <p className="mt-1 text-xs leading-5 text-emerald-800">
                  The register cache has been refreshed. Review skipped and failed rows
                  in the result summary.
                </p>
              </div>
              <div className="mt-5">
                <DocumentImportResultSummary result={mutations.confirm.data} />
              </div>
              <button
                type="button"
                onClick={reset}
                className="mt-6 min-h-10 rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                Import another workbook
              </button>
            </>
          ) : (
            <>
              <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <p className="text-sm font-semibold text-slate-900">
                    Use the controlled template
                  </p>
                  <p className="mt-1 text-xs leading-5 text-slate-500">
                    The server enforces the configured workbook size limit.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => void downloadTemplate()}
                  disabled={mutations.template.isPending}
                  className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-4 text-sm font-semibold text-blue-700 hover:bg-blue-100 disabled:opacity-60"
                >
                  <Download className="size-4" aria-hidden="true" />
                  {mutations.template.isPending
                    ? 'Downloading...'
                    : 'Download template'}
                </button>
              </div>

              <label
                htmlFor={inputId}
                className="mt-5 flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 px-6 py-8 text-center transition hover:border-blue-400 hover:bg-blue-50/40"
              >
                <FileSpreadsheet className="size-8 text-blue-700" aria-hidden="true" />
                <span className="mt-3 text-sm font-semibold text-slate-800">
                  {file?.name ?? 'Choose an XLSX workbook'}
                </span>
                <span className="mt-1 text-xs text-slate-500">
                  Only Office Open XML .xlsx workbooks are accepted
                </span>
              </label>
              <input
                id={inputId}
                type="file"
                accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                onChange={(event) => {
                  chooseFile(event.target.files?.[0] ?? null);
                  if (event.target.files?.[0] && !isXlsxFile(event.target.files[0])) {
                    event.target.value = '';
                  }
                }}
                className="sr-only"
              />
              {fileError && (
                <p role="alert" className="mt-2 text-xs font-medium text-rose-600">
                  {fileError}
                </p>
              )}
              <button
                type="button"
                onClick={() => void previewWorkbook()}
                disabled={!file || mutations.preview.isPending}
                className="mt-5 inline-flex min-h-11 items-center gap-2 rounded-xl bg-blue-700 px-5 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {mutations.preview.isPending ? (
                  <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Upload className="size-4" aria-hidden="true" />
                )}
                {mutations.preview.isPending
                  ? 'Validating workbook...'
                  : 'Generate preview'}
              </button>

              {mutations.preview.data && (
                <div className="mt-7">
                  <DocumentImportResultSummary preview={mutations.preview.data} />
                  {mutations.preview.data.warnings.length > 0 && (
                    <ul className="mt-4 rounded-xl border border-blue-200 bg-blue-50 p-3 text-xs leading-5 text-blue-800">
                      {mutations.preview.data.warnings.map((warning) => (
                        <li key={warning}>• {warning}</li>
                      ))}
                    </ul>
                  )}
                  <div className="mt-5 flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-slate-900">Preview rows</p>
                    <select
                      value={statusFilter}
                      onChange={(event) => {
                        setStatusFilter(
                          event.target.value as DocumentImportRowStatus | 'ALL',
                        );
                        setPreviewPage(1);
                      }}
                      aria-label="Filter import preview status"
                      className="min-h-9 rounded-xl border border-slate-300 bg-white px-3 text-xs font-semibold text-slate-700"
                    >
                      <option value="ALL">All results</option>
                      {documentImportRowStatuses.map((status) => (
                        <option key={status} value={status}>
                          {status.replaceAll('_', ' ')}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="mt-3 max-h-80 overflow-auto rounded-2xl border border-slate-200">
                    <table className="min-w-[68rem] divide-y divide-slate-200 text-left">
                      <thead className="sticky top-0 bg-slate-50">
                        <tr>
                          {[
                            'Row',
                            'Base Document Code',
                            'Revision',
                            'Title',
                            'Department',
                            'Document Type',
                            'Status',
                            'Result',
                            'Errors',
                          ].map((label) => (
                            <th
                              key={label}
                              className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wide text-slate-600"
                            >
                              {label}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {visiblePreviewRows.map((row) => (
                          <tr key={row.rowNumber}>
                            <td className="px-3 py-2 text-xs text-slate-600">
                              {row.rowNumber}
                            </td>
                            <td className="max-w-48 truncate px-3 py-2 font-mono text-[10px] text-slate-700">
                              {row.baseDocumentCode || '—'}
                            </td>
                            <td className="px-3 py-2 text-xs text-slate-600">
                              {row.revisionCode || '—'}
                            </td>
                            <td className="max-w-52 truncate px-3 py-2 text-xs text-slate-700">
                              {row.title || '—'}
                            </td>
                            <td className="px-3 py-2 text-xs text-slate-600">
                              {row.departmentCode || '—'}
                            </td>
                            <td className="px-3 py-2 text-xs text-slate-600">
                              {row.documentTypeCode || '—'}
                            </td>
                            <td className="px-3 py-2 text-xs text-slate-600">
                              {getRowDataText(
                                row.data,
                                'document_status_code',
                                'documentStatusCode',
                              )}
                            </td>
                            <td className="px-3 py-2">
                              <span
                                className={`rounded-full px-2 py-1 text-[10px] font-semibold ${previewStatusTones[row.status]}`}
                              >
                                {row.status.replaceAll('_', ' ')}
                              </span>
                            </td>
                            <td className="max-w-sm px-3 py-2 text-xs text-rose-700">
                              {[...row.errors, ...row.warnings].join('; ') || '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="mt-3 flex flex-col gap-2 text-xs text-slate-600 sm:flex-row sm:items-center sm:justify-between">
                    <p aria-live="polite">
                      Showing {previewRangeStart}–{previewRangeEnd} of{' '}
                      {previewRows.length} matching rows
                    </p>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() =>
                          setPreviewPage(Math.max(1, visiblePreviewPage - 1))
                        }
                        disabled={visiblePreviewPage <= 1}
                        className="min-h-9 rounded-lg border border-slate-300 px-3 font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Previous
                      </button>
                      <span className="min-w-20 text-center font-medium">
                        Page {visiblePreviewPage} of {previewPageCount}
                      </span>
                      <button
                        type="button"
                        onClick={() =>
                          setPreviewPage(
                            Math.min(previewPageCount, visiblePreviewPage + 1),
                          )
                        }
                        disabled={visiblePreviewPage >= previewPageCount}
                        className="min-h-9 rounded-lg border border-slate-300 px-3 font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Next
                      </button>
                    </div>
                  </div>

                  <fieldset className="mt-5">
                    <legend className="text-xs font-semibold text-slate-700">
                      Import mode
                    </legend>
                    <div className="mt-2 grid gap-3 md:grid-cols-3">
                      {availableModes.map((candidate) => {
                        const [label, description] = modeDescriptions[candidate];
                        return (
                          <label
                            key={candidate}
                            className={`cursor-pointer rounded-xl border p-3 ${
                              mode === candidate
                                ? 'border-blue-500 bg-blue-50'
                                : 'border-slate-200'
                            }`}
                          >
                            <input
                              type="radio"
                              name="documentImportMode"
                              value={candidate}
                              checked={mode === candidate}
                              onChange={() => setMode(candidate)}
                              className="mr-2"
                            />
                            <span className="text-sm font-semibold text-slate-800">
                              {label}
                            </span>
                            <span className="mt-1 block text-xs leading-5 text-slate-500">
                              {description}
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  </fieldset>

                  <button
                    type="button"
                    onClick={() => void confirmImport()}
                    disabled={actionableRows === 0 || mutations.confirm.isPending}
                    className="mt-5 min-h-11 rounded-xl bg-blue-700 px-5 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {mutations.confirm.isPending ? 'Importing...' : 'Confirm import'}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </section>
    </div>
  );
}
