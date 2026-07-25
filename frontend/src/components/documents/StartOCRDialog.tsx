import { X } from 'lucide-react';
import { useEffect, useState } from 'react';

import {
  ocrLanguageProfiles,
  ocrPreprocessingProfiles,
  type OCRLanguageProfile,
  type OCRPreprocessingProfile,
  type OCRStartRequest,
} from '../../types/ocr';
import { ocrPreprocessingLabels, ocrProfileLabels } from './ocrDisplay';

const parsePages = (value: string): number[] | null => {
  if (!value.trim()) {
    return null;
  }
  const pages = value
    .split(',')
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isInteger(item) && item > 0);
  return pages.length > 0 ? [...new Set(pages)].sort((a, b) => a - b) : [];
};

export function StartOCRDialog({
  allowForce,
  documentFileId,
  extractionRunId,
  filename,
  isOpen,
  isPending,
  onClose,
  onConfirm,
}: {
  isOpen: boolean;
  filename: string;
  documentFileId: string;
  extractionRunId: string;
  allowForce: boolean;
  isPending: boolean;
  onClose: () => void;
  onConfirm: (payload: OCRStartRequest) => void;
}) {
  const [languageProfile, setLanguageProfile] =
    useState<OCRLanguageProfile>('AUTO_MULTILINGUAL');
  const [preprocessingProfile, setPreprocessingProfile] =
    useState<OCRPreprocessingProfile>('STANDARD');
  const [pagesInput, setPagesInput] = useState('');
  const [force, setForce] = useState(false);
  const pages = parsePages(pagesInput);
  const pageError =
    pagesInput.trim() && pages?.length === 0
      ? 'Use positive page numbers separated by commas.'
      : null;

  useEffect(() => {
    if (isOpen) {
      setLanguageProfile('AUTO_MULTILINGUAL');
      setPreprocessingProfile('STANDARD');
      setPagesInput('');
      setForce(false);
    }
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Start OCR"
      className="fixed inset-0 z-[70] grid place-items-center bg-slate-950/55 p-4"
    >
      <form
        className="w-full max-w-xl rounded-3xl bg-white p-6 shadow-2xl"
        onSubmit={(event) => {
          event.preventDefault();
          if (pageError) {
            return;
          }
          onConfirm({
            documentFileId,
            extractionRunId,
            languageProfile,
            pageNumbers: pages,
            preprocessingProfile,
            force,
          });
        }}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">Start PDF OCR</h2>
            <p className="mt-1 break-all text-sm text-slate-600">{filename}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="grid size-9 place-items-center rounded-xl text-slate-500 hover:bg-slate-100"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>
        <p className="mt-4 rounded-xl border border-blue-200 bg-blue-50 p-3 text-xs leading-5 text-blue-800">
          By default the server processes only PDF pages with no or very little
          selectable text. OCR runs locally and preserves native text.
        </p>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <label className="text-xs font-semibold text-slate-700">
            Language profile
            <select
              value={languageProfile}
              onChange={(event) =>
                setLanguageProfile(event.target.value as OCRLanguageProfile)
              }
              className="mt-1.5 min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
            >
              {ocrLanguageProfiles.map((profile) => (
                <option key={profile} value={profile}>
                  {ocrProfileLabels[profile]}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs font-semibold text-slate-700">
            Preprocessing
            <select
              value={preprocessingProfile}
              onChange={(event) =>
                setPreprocessingProfile(event.target.value as OCRPreprocessingProfile)
              }
              className="mt-1.5 min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
            >
              {ocrPreprocessingProfiles.map((profile) => (
                <option key={profile} value={profile}>
                  {ocrPreprocessingLabels[profile]}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label
          htmlFor="start-ocr-pages"
          className="mt-4 block text-xs font-semibold text-slate-700"
        >
          Manual pages (optional)
        </label>
        <input
          id="start-ocr-pages"
          value={pagesInput}
          onChange={(event) => setPagesInput(event.target.value)}
          placeholder="For example: 2, 5, 6"
          aria-describedby={
            pageError
              ? 'start-ocr-pages-help start-ocr-pages-error'
              : 'start-ocr-pages-help'
          }
          className="mt-1.5 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
        />
        <p id="start-ocr-pages-help" className="mt-1 text-xs text-slate-500">
          Leave blank for automatic page selection.
        </p>
        {pageError && (
          <p id="start-ocr-pages-error" className="mt-1 text-xs text-rose-700">
            {pageError}
          </p>
        )}
        {allowForce && (
          <label className="mt-4 flex items-start gap-2 rounded-xl bg-slate-50 p-3 text-xs text-slate-700">
            <input
              type="checkbox"
              checked={force}
              onChange={(event) => setForce(event.target.checked)}
              className="mt-0.5 size-4 rounded border-slate-300"
            />
            <span>
              <strong className="block text-slate-900">Force selected pages</strong>
              Use only when a page needs reprocessing despite sufficient native text.
            </span>
          </label>
        )}
        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            className="min-h-10 rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isPending || Boolean(pageError)}
            className="min-h-10 rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white disabled:opacity-50"
          >
            {isPending ? 'Queueing…' : 'Queue OCR'}
          </button>
        </div>
      </form>
    </div>
  );
}
