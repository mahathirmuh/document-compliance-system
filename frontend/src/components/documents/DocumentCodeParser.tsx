import { FileSearch, LoaderCircle } from 'lucide-react';
import { useState } from 'react';

import { getApiErrorMessage } from '../../api/errors';
import { useDocumentMutations } from '../../hooks/useDocumentMutations';
import type { DocumentParseResponse } from '../../types/document';

interface DocumentCodeParserProps {
  onParsed: (result: DocumentParseResponse) => void;
}

export function DocumentCodeParser({ onParsed }: DocumentCodeParserProps) {
  const [value, setValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const mutation = useDocumentMutations().parseCode;

  const identify = async (): Promise<void> => {
    if (!value.trim()) {
      setError('Enter a document code or supported filename.');
      return;
    }
    try {
      const result = await mutation.mutateAsync({ value: value.trim() });
      setError(null);
      setWarnings(result.warnings);
      onParsed(result);
    } catch (requestError: unknown) {
      setWarnings([]);
      setError(
        getApiErrorMessage(
          requestError,
          'The code could not be identified. Check its components and try again.',
        ),
      );
    }
  };

  return (
    <section className="rounded-2xl border border-blue-200 bg-blue-50/60 p-4 sm:p-5">
      <div className="flex items-start gap-3">
        <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-blue-100 text-blue-700">
          <FileSearch className="size-4" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold text-slate-950">
            Identify from Document Code or Filename
          </h2>
          <p className="mt-1 text-xs leading-5 text-slate-600">
            Supports metadata parsing for PDF, DOCX, and XLSX filenames. No physical
            file is uploaded.
          </p>
          <div className="mt-3 flex flex-col gap-2 sm:flex-row">
            <input
              value={value}
              onChange={(event) => setValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  void identify();
                }
              }}
              placeholder="MTI-HRM-IER-SOP-001_Rev.000.pdf"
              aria-label="Document code or filename"
              className="min-h-10 min-w-0 flex-1 rounded-xl border border-blue-200 bg-white px-3 text-sm text-slate-950 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
            />
            <button
              type="button"
              onClick={() => void identify()}
              disabled={mutation.isPending}
              className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white hover:bg-blue-800 disabled:opacity-60"
            >
              {mutation.isPending && (
                <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
              )}
              Identify
            </button>
          </div>
          {error && (
            <p role="alert" className="mt-2 text-xs font-medium text-rose-700">
              {error}
            </p>
          )}
          {warnings.length > 0 && (
            <ul className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-800">
              {warnings.map((warning) => (
                <li key={warning}>• {warning}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
