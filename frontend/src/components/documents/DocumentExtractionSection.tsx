import { DocumentFileExtractionPanel } from './DocumentFileExtractionPanel';
import type { DocumentFileListItem } from '../../types/documentFile';

export function DocumentExtractionSection({
  documentArchived = false,
  files,
}: {
  files: readonly DocumentFileListItem[];
  documentArchived?: boolean;
}) {
  const extractableFiles = files.filter(
    (file) => file.isCurrent && file.fileStatus === 'AVAILABLE',
  );

  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold text-slate-950">Content Extraction</h3>
        <p className="mt-1 text-xs leading-5 text-slate-500">
          Extraction reads selectable content from the current PDF, DOCX, or XLSX file.
          Scanned PDF pages are retained as OCR required.
        </p>
      </div>
      {extractableFiles.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-slate-300 p-5 text-center text-xs text-slate-500">
          Upload a current available physical file before starting extraction.
        </p>
      ) : (
        extractableFiles.map((file) => (
          <DocumentFileExtractionPanel
            key={file.id}
            file={file}
            documentArchived={documentArchived}
          />
        ))
      )}
    </section>
  );
}
