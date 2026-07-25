import type { DocumentFileListItem } from '../../types/documentFile';

import { DocumentIntelligencePanel } from './DocumentIntelligencePanel';

export function DocumentIntelligenceSection({
  documentArchived = false,
  files,
}: {
  files: readonly DocumentFileListItem[];
  documentArchived?: boolean;
}) {
  if (files.length === 0) {
    return null;
  }
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold text-slate-950">
          OCR &amp; Language Detection
        </h2>
        <p className="mt-1 text-xs leading-5 text-slate-500">
          OCR is available only for eligible PDF pages. Language detection uses merged
          native and OCR content and reports preliminary coverage.
        </p>
      </div>
      {files.map((file) => (
        <DocumentIntelligencePanel
          key={file.id}
          file={file}
          documentArchived={documentArchived}
        />
      ))}
    </section>
  );
}
