import { Download, FileSpreadsheet, Upload, X } from 'lucide-react';
import { useCallback, useEffect, useId, useState, type ChangeEvent } from 'react';

import { ImportResultSummary } from './ImportResultSummary';
import { getApiErrorMessage } from '../../api/errors';
import { useMasterDataImport } from '../../hooks/useMasterDataImport';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import {
  importModes,
  masterDataEntityTypes,
  type ImportMode,
  type MasterDataEntityType,
} from '../../types/masterData';
import { downloadFile } from '../../utils/downloadFile';
import { isXlsxFile } from '../../utils/xlsxFile';

interface MasterDataImportDialogProps {
  isOpen: boolean;
  onClose: () => void;
  initialEntityType?: MasterDataEntityType;
}

const entityLabels: Record<MasterDataEntityType, string> = {
  departments: 'Departments',
  sections: 'Sections',
  'document-types': 'Document Types',
  'document-statuses': 'Document Statuses',
  'validation-rules': 'Validation Rules',
};

export function MasterDataImportDialog({
  initialEntityType = 'departments',
  isOpen,
  onClose,
}: MasterDataImportDialogProps) {
  const inputId = useId();
  const [entityType, setEntityType] = useState<MasterDataEntityType>(initialEntityType);
  const [mode, setMode] = useState<ImportMode>('CREATE_ONLY');
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const canImport = useAuthStore((state) => state.hasPermission('master_data:create'));
  const canUpsert = useAuthStore((state) => state.hasPermission('master_data:update'));
  const { confirm, preview, template } = useMasterDataImport();
  const { showToast } = useToast();

  const resetImport = useCallback((): void => {
    setFile(null);
    setFileError(null);
    preview.reset();
    confirm.reset();
  }, [confirm, preview]);

  const closeDialog = useCallback((): void => {
    resetImport();
    setMode('CREATE_ONLY');
    onClose();
  }, [onClose, resetImport]);

  useEffect(() => {
    if (!isOpen || !canImport) {
      return;
    }
    const closeOnEscape = (event: KeyboardEvent): void => {
      if (event.key === 'Escape' && !preview.isPending && !confirm.isPending) {
        closeDialog();
      }
    };
    document.addEventListener('keydown', closeOnEscape);
    return () => document.removeEventListener('keydown', closeOnEscape);
  }, [canImport, closeDialog, confirm.isPending, isOpen, preview.isPending]);

  useEffect(() => {
    if (isOpen) {
      setEntityType(initialEntityType);
    }
  }, [initialEntityType, isOpen]);

  useEffect(() => {
    if (!canUpsert) {
      setMode('CREATE_ONLY');
    }
  }, [canUpsert]);

  if (!isOpen || !canImport) {
    return null;
  }

  const changeFile = (event: ChangeEvent<HTMLInputElement>): void => {
    const nextFile = event.target.files?.[0] ?? null;
    preview.reset();
    confirm.reset();

    if (nextFile && !isXlsxFile(nextFile)) {
      setFile(null);
      setFileError('Choose a valid .xlsx workbook.');
      event.target.value = '';
      return;
    }

    setFile(nextFile);
    setFileError(null);
  };

  const generatePreview = async (): Promise<void> => {
    if (!file) {
      setFileError('Choose an XLSX file before generating a preview.');
      return;
    }
    try {
      await preview.mutateAsync({ entityType, file });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Import preview failed',
        message: getApiErrorMessage(error, 'The workbook could not be validated.'),
      });
    }
  };

  const confirmImport = async (): Promise<void> => {
    if (!file || !preview.data) {
      return;
    }
    try {
      const result = await confirm.mutateAsync({ entityType, file, mode });
      showToast({
        tone: 'success',
        title: 'Master data imported',
        message: `${result.created} created, ${result.updated} updated, ${result.skipped} skipped.`,
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Import failed',
        message: getApiErrorMessage(error, 'No master data was imported.'),
      });
    }
  };

  const getTemplate = async (): Promise<void> => {
    try {
      const result = await template.mutateAsync(entityType);
      downloadFile(result, `${entityType}_template.xlsx`);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Template download failed',
        message: getApiErrorMessage(error, 'The template could not be downloaded.'),
      });
    }
  };

  const previewError = preview.error
    ? getApiErrorMessage(preview.error, 'Preview could not be generated.')
    : null;

  return (
    <div
      className="fixed inset-0 z-[90] grid place-items-center bg-slate-950/50 p-3 backdrop-blur-sm sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="import-title"
    >
      <section className="flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-2xl">
        <header className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-5 sm:px-7">
          <div>
            <h2 id="import-title" className="text-lg font-semibold text-slate-950">
              Import Master Data
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Validate the workbook before any rows are stored.
            </p>
          </div>
          <button
            type="button"
            onClick={closeDialog}
            disabled={preview.isPending || confirm.isPending}
            aria-label="Close import dialog"
            className="grid size-9 place-items-center rounded-xl text-slate-500 hover:bg-slate-100 disabled:opacity-50"
          >
            <X className="size-5" aria-hidden="true" />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-6 sm:px-7">
          {confirm.data ? (
            <div>
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
                <p className="text-sm font-semibold text-emerald-900">
                  Import completed
                </p>
                <p className="mt-1 text-xs leading-5 text-emerald-800">
                  Review the result summary below. List queries were refreshed
                  automatically.
                </p>
              </div>
              <div className="mt-5">
                <ImportResultSummary result={confirm.data} />
              </div>
              <button
                type="button"
                onClick={resetImport}
                className="mt-6 min-h-10 rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                Import another workbook
              </button>
            </div>
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-[1fr_auto]">
                <label className="text-xs font-semibold text-slate-700">
                  Entity type
                  <select
                    value={entityType}
                    onChange={(event) => {
                      setEntityType(event.target.value as MasterDataEntityType);
                      resetImport();
                    }}
                    className="mt-1.5 min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3.5 text-sm text-slate-800 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
                  >
                    {masterDataEntityTypes.map((entity) => (
                      <option key={entity} value={entity}>
                        {entityLabels[entity]}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  onClick={() => void getTemplate()}
                  disabled={template.isPending}
                  className="mt-auto inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-4 text-sm font-semibold text-blue-700 transition hover:bg-blue-100 disabled:opacity-60"
                >
                  <Download className="size-4" aria-hidden="true" />
                  {template.isPending ? 'Downloading...' : 'Download template'}
                </button>
              </div>

              <div className="mt-5">
                <label
                  htmlFor={inputId}
                  className="flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 px-6 py-8 text-center transition hover:border-blue-400 hover:bg-blue-50/40"
                >
                  <FileSpreadsheet
                    className="size-8 text-blue-700"
                    aria-hidden="true"
                  />
                  <span className="mt-3 text-sm font-semibold text-slate-800">
                    {file?.name ?? 'Choose an XLSX workbook'}
                  </span>
                  <span className="mt-1 text-xs text-slate-500">
                    Only Office Open XML .xlsx files are accepted
                  </span>
                </label>
                <input
                  id={inputId}
                  type="file"
                  accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                  onChange={changeFile}
                  className="sr-only"
                />
                {fileError && (
                  <p className="mt-2 text-xs font-medium text-rose-600">{fileError}</p>
                )}
              </div>

              <button
                type="button"
                onClick={() => void generatePreview()}
                disabled={!file || preview.isPending}
                className="mt-5 inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-blue-700 px-5 text-sm font-semibold text-white transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Upload className="size-4" aria-hidden="true" />
                {preview.isPending ? 'Validating workbook...' : 'Generate preview'}
              </button>

              {previewError && (
                <p role="alert" className="mt-4 text-sm font-medium text-rose-700">
                  {previewError}
                </p>
              )}

              {preview.data && (
                <div className="mt-7">
                  <ImportResultSummary preview={preview.data} />
                  {preview.data.invalidRows > 0 && (
                    <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-800">
                      Invalid rows will be skipped. Only valid rows are submitted for
                      import; review errors below before continuing.
                    </p>
                  )}
                  {preview.data.warnings && preview.data.warnings.length > 0 && (
                    <ul className="mt-3 rounded-xl border border-blue-200 bg-blue-50 p-3 text-xs leading-5 text-blue-800">
                      {preview.data.warnings.map((warning) => (
                        <li key={warning}>• {warning}</li>
                      ))}
                    </ul>
                  )}
                  <div className="mt-4 max-h-72 overflow-auto rounded-2xl border border-slate-200">
                    <table className="min-w-full divide-y divide-slate-200 text-left">
                      <thead className="sticky top-0 bg-slate-50">
                        <tr>
                          <th className="px-3 py-2 text-xs font-semibold text-slate-600">
                            Row
                          </th>
                          <th className="px-3 py-2 text-xs font-semibold text-slate-600">
                            Status
                          </th>
                          <th className="px-3 py-2 text-xs font-semibold text-slate-600">
                            Data
                          </th>
                          <th className="px-3 py-2 text-xs font-semibold text-slate-600">
                            Errors
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {preview.data.rows.slice(0, 100).map((row) => (
                          <tr key={row.rowNumber}>
                            <td className="px-3 py-2 text-xs text-slate-600">
                              {row.rowNumber}
                            </td>
                            <td className="px-3 py-2">
                              <span
                                className={`rounded-full px-2 py-1 text-[10px] font-semibold ${
                                  row.status === 'VALID'
                                    ? 'bg-emerald-50 text-emerald-700'
                                    : row.status === 'DUPLICATE'
                                      ? 'bg-amber-50 text-amber-700'
                                      : 'bg-rose-50 text-rose-700'
                                }`}
                              >
                                {row.status}
                              </span>
                            </td>
                            <td className="max-w-sm px-3 py-2 font-mono text-[10px] text-slate-600">
                              {JSON.stringify(row.data)}
                            </td>
                            <td className="px-3 py-2 text-xs text-rose-700">
                              {row.errors.join('; ') || '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <fieldset className="mt-5">
                    <legend className="text-xs font-semibold text-slate-700">
                      Import mode
                    </legend>
                    <div className="mt-2 grid gap-3 sm:grid-cols-2">
                      {importModes
                        .filter((importMode) => importMode !== 'UPSERT' || canUpsert)
                        .map((importMode) => (
                          <label
                            key={importMode}
                            className={`cursor-pointer rounded-xl border p-3 ${
                              mode === importMode
                                ? 'border-blue-500 bg-blue-50'
                                : 'border-slate-200'
                            }`}
                          >
                            <input
                              type="radio"
                              name="importMode"
                              value={importMode}
                              checked={mode === importMode}
                              onChange={() => setMode(importMode)}
                              className="mr-2"
                            />
                            <span className="text-sm font-semibold text-slate-800">
                              {importMode === 'CREATE_ONLY' ? 'Create Only' : 'Upsert'}
                            </span>
                            <span className="mt-1 block text-xs leading-5 text-slate-500">
                              {importMode === 'CREATE_ONLY'
                                ? 'Existing codes are skipped.'
                                : 'Existing codes are updated and new codes are created.'}
                            </span>
                          </label>
                        ))}
                    </div>
                  </fieldset>

                  <button
                    type="button"
                    onClick={() => void confirmImport()}
                    disabled={preview.data.validRows === 0 || confirm.isPending}
                    className="mt-5 min-h-11 rounded-xl bg-blue-700 px-5 text-sm font-semibold text-white transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {confirm.isPending ? 'Importing...' : 'Confirm import'}
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
