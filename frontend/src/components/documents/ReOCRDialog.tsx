import { X } from 'lucide-react';
import { useEffect, useState } from 'react';

import {
  ocrLanguageProfiles,
  ocrPreprocessingProfiles,
  type OCRLanguageProfile,
  type OCRPreprocessingProfile,
  type OCRReprocessRequest,
  type OCRRun,
} from '../../types/ocr';
import { ocrPreprocessingLabels, ocrProfileLabels } from './ocrDisplay';

const parsePages = (value: string): number[] | null => {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const pages = trimmed
    .split(',')
    .map((page) => Number(page.trim()))
    .filter((page) => Number.isInteger(page) && page > 0);
  return pages.length > 0 ? [...new Set(pages)].sort((a, b) => a - b) : [];
};

export function ReOCRDialog({
  isOpen,
  isPending,
  onClose,
  onConfirm,
  run,
}: {
  isOpen: boolean;
  isPending: boolean;
  run: OCRRun | null;
  onClose: () => void;
  onConfirm: (payload: OCRReprocessRequest) => void;
}) {
  const [reason, setReason] = useState('');
  const [pagesInput, setPagesInput] = useState('');
  const [languageProfile, setLanguageProfile] =
    useState<OCRLanguageProfile>('AUTO_MULTILINGUAL');
  const [preprocessingProfile, setPreprocessingProfile] =
    useState<OCRPreprocessingProfile>('STANDARD');
  const parsedPages = parsePages(pagesInput);
  const reasonError =
    reason.trim().length === 0
      ? 'A reason is required.'
      : reason.trim().length > 1_000
        ? 'Reason must be 1,000 characters or fewer.'
        : null;
  const pageError =
    pagesInput.trim() && parsedPages?.length === 0
      ? 'Use positive page numbers separated by commas.'
      : null;

  useEffect(() => {
    if (isOpen && run) {
      setReason('');
      setPagesInput('');
      setLanguageProfile(run.languageProfile);
      setPreprocessingProfile(run.preprocessingProfile);
    }
  }, [isOpen, run]);

  if (!isOpen || !run) {
    return null;
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Re-run OCR"
      className="fixed inset-0 z-[70] grid place-items-center bg-slate-950/55 p-4"
    >
      <form
        className="w-full max-w-xl rounded-3xl bg-white p-6 shadow-2xl"
        onSubmit={(event) => {
          event.preventDefault();
          if (reasonError || pageError) {
            return;
          }
          onConfirm({
            reason: reason.trim(),
            pageNumbers: parsedPages,
            languageProfile,
            preprocessingProfile,
          });
        }}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">Re-run OCR</h2>
            <p className="mt-1 text-sm text-slate-600">
              The existing OCR result remains available in history.
            </p>
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
          htmlFor="reocr-pages"
          className="mt-4 block text-xs font-semibold text-slate-700"
        >
          Pages (optional)
        </label>
        <input
          id="reocr-pages"
          value={pagesInput}
          onChange={(event) => setPagesInput(event.target.value)}
          placeholder="For example: 4, 5"
          aria-describedby={
            pageError ? 'reocr-pages-help reocr-pages-error' : 'reocr-pages-help'
          }
          className="mt-1.5 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
        />
        <p id="reocr-pages-help" className="mt-1 text-xs text-slate-500">
          Leave blank to let the server select pages requiring OCR.
        </p>
        {pageError && (
          <p id="reocr-pages-error" className="mt-1 text-xs text-rose-700">
            {pageError}
          </p>
        )}
        <label
          htmlFor="reocr-reason"
          className="mt-4 block text-xs font-semibold text-slate-700"
        >
          Reason
        </label>
        <textarea
          id="reocr-reason"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          maxLength={1_000}
          rows={3}
          aria-describedby={reasonError ? 'reocr-reason-error' : undefined}
          className="mt-1.5 w-full rounded-xl border border-slate-300 p-3 text-sm"
        />
        {reasonError && (
          <p id="reocr-reason-error" className="mt-1 text-xs text-rose-700">
            {reasonError}
          </p>
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
            disabled={isPending || Boolean(reasonError) || Boolean(pageError)}
            className="min-h-10 rounded-xl bg-indigo-700 px-4 text-sm font-semibold text-white disabled:opacity-50"
          >
            {isPending ? 'Queueing…' : 'Queue Re-OCR'}
          </button>
        </div>
      </form>
    </div>
  );
}
