import { Download, FileSpreadsheet, Upload } from 'lucide-react';
import { useState } from 'react';

import type { GlossaryImportPreview } from '../../types/glossary';

export function GlossaryImportPanel({
  confirmPending,
  onConfirm,
  onDownloadTemplate,
  onPreview,
  preview,
  previewPending,
}: {
  preview: GlossaryImportPreview | null;
  previewPending: boolean;
  confirmPending: boolean;
  onPreview: (file: File) => Promise<void>;
  onConfirm: (file: File, mode: 'CREATE_ONLY' | 'UPSERT') => Promise<void>;
  onDownloadTemplate: () => Promise<void>;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [previewedFile, setPreviewedFile] = useState<File | null>(null);
  const [mode, setMode] = useState<'CREATE_ONLY' | 'UPSERT'>('CREATE_ONLY');
  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <FileSpreadsheet className="size-6 text-emerald-700" aria-hidden="true" />
        <h2 className="mt-3 text-sm font-semibold text-slate-950">
          Glossary XLSX Import
        </h2>
        <p className="mt-2 text-xs leading-5 text-slate-600">
          Use the Profiles, Terms, Translations, Variants, and Exceptions sheets.
          Preview validates duplicates, language codes, regex, required fields, and
          scope before any write.
        </p>
        <button
          type="button"
          onClick={() => void onDownloadTemplate()}
          className="mt-4 inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 px-4 text-xs font-semibold text-slate-700"
        >
          <Download className="size-4" aria-hidden="true" />
          Download Template
        </button>
        <label className="mt-5 block text-xs font-semibold text-slate-700">
          Import workbook
          <input
            type="file"
            accept=".xlsx"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              setPreviewedFile(null);
            }}
            className="mt-1.5 block w-full rounded-xl border border-slate-300 p-3 text-xs"
          />
        </label>
        <button
          type="button"
          disabled={!file || previewPending}
          onClick={() => {
            if (file) {
              void onPreview(file)
                .then(() => setPreviewedFile(file))
                .catch(() => setPreviewedFile(null));
            }
          }}
          className="mt-3 inline-flex min-h-10 items-center gap-2 rounded-xl bg-blue-700 px-4 text-xs font-semibold text-white disabled:opacity-50"
        >
          <Upload className="size-4" aria-hidden="true" />
          {previewPending ? 'Validating…' : 'Preview Import'}
        </button>
      </section>
      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <h2 className="text-sm font-semibold text-slate-950">Import Preview</h2>
        {!preview && (
          <p className="mt-5 rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">
            Select a workbook and run preview. No glossary data is changed during
            preview.
          </p>
        )}
        {preview && (
          <>
            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
              {['Profiles', 'Terms', 'Translations', 'Variants', 'Exceptions'].map(
                (label) => (
                  <div key={label} className="rounded-xl bg-slate-50 p-3">
                    <p className="text-[10px] uppercase text-slate-500">{label}</p>
                    <p className="mt-1 font-semibold text-slate-950">
                      {preview.sheets.find((sheet) => sheet.sheet === label)
                        ?.validRows ?? 0}
                    </p>
                  </div>
                ),
              )}
            </div>
            {preview.issues.length > 0 && (
              <IssueList title="Issues" tone="error" issues={preview.issues} />
            )}
            {preview.warnings.length > 0 && (
              <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-800">
                <h3 className="font-semibold">Warnings ({preview.warnings.length})</h3>
                <ul className="mt-2 space-y-1">
                  {preview.warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              </div>
            )}
            <label className="mt-5 block max-w-xs text-xs font-semibold text-slate-700">
              Import mode
              <select
                value={mode}
                onChange={(event) =>
                  setMode(event.target.value as 'CREATE_ONLY' | 'UPSERT')
                }
                className="mt-1.5 min-h-10 w-full rounded-xl border border-slate-300 bg-white px-3"
              >
                <option value="CREATE_ONLY">Create only</option>
                <option value="UPSERT">Create or update</option>
              </select>
            </label>
            <button
              type="button"
              disabled={
                !preview.valid || !file || previewedFile !== file || confirmPending
              }
              onClick={() => {
                if (file && previewedFile === file) {
                  void onConfirm(file, mode);
                }
              }}
              className="mt-5 min-h-10 rounded-xl bg-emerald-700 px-4 text-xs font-semibold text-white disabled:opacity-50"
            >
              {confirmPending ? 'Importing…' : 'Confirm Import'}
            </button>
          </>
        )}
      </section>
    </div>
  );
}

function IssueList({
  issues,
  title,
  tone,
}: {
  title: string;
  tone: 'error' | 'warning';
  issues: GlossaryImportPreview['issues'];
}) {
  return (
    <div
      className={`mt-4 rounded-xl border p-4 text-xs ${
        tone === 'error'
          ? 'border-rose-200 bg-rose-50 text-rose-800'
          : 'border-amber-200 bg-amber-50 text-amber-800'
      }`}
    >
      <h3 className="font-semibold">
        {title} ({issues.length})
      </h3>
      <ul className="mt-2 max-h-40 space-y-1 overflow-y-auto">
        {issues.map((issue, index) => (
          <li key={`${issue.sheet}-${issue.rowNumber}-${issue.code}-${index}`}>
            {issue.sheet}
            {` row ${issue.rowNumber}`}: {issue.message}
          </li>
        ))}
      </ul>
    </div>
  );
}
