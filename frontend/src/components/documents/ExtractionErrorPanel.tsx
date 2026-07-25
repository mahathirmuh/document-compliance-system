import { AlertCircle } from 'lucide-react';

import type { ExtractionError } from '../../types/extraction';

const friendlyErrorMessages: Record<string, string> = {
  PDF_PASSWORD_REQUIRED: 'This PDF is password-protected and cannot be extracted.',
  PDF_CORRUPT: 'This PDF is corrupt or cannot be read safely.',
  PDF_EMPTY: 'This PDF does not contain extractable pages.',
  DOCX_CORRUPT: 'This DOCX file is corrupt or cannot be read safely.',
  DOCX_EMPTY: 'This DOCX file does not contain extractable content.',
  XLSX_CORRUPT: 'This XLSX workbook is corrupt or cannot be read safely.',
  XLSX_EMPTY: 'This XLSX workbook does not contain extractable cells.',
  XLSX_TOO_MANY_SHEETS: 'This workbook exceeds the worksheet safety limit.',
  XLSX_TOO_MANY_CELLS: 'This workbook exceeds the extracted-cell safety limit.',
  XLSX_WORKBOOK_TOO_LARGE: 'This workbook exceeds the extraction size limit.',
  EXTRACTION_TIMEOUT: 'Extraction exceeded its allowed processing time.',
  EXTRACTION_WORKER_FAILED:
    'The extraction worker could not complete this job. Try again later.',
};

export function ExtractionErrorPanel({
  error,
  fallbackMessage = 'Document content could not be extracted.',
}: {
  error?: ExtractionError | null;
  fallbackMessage?: string;
}) {
  const message = error
    ? (friendlyErrorMessages[error.code] ?? error.message)
    : fallbackMessage;
  return (
    <div
      role="alert"
      className="flex gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-rose-800"
    >
      <AlertCircle className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
      <div>
        <p className="text-sm font-semibold">Extraction failed</p>
        <p className="mt-1 text-xs leading-5">{message}</p>
        {error?.code && (
          <p className="mt-2 font-mono text-[10px] text-rose-700">{error.code}</p>
        )}
      </div>
    </div>
  );
}
