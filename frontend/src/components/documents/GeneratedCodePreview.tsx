import { FileCode2 } from 'lucide-react';

import { DocumentCodeField } from './DocumentCodeField';

interface GeneratedCodePreviewProps {
  baseDocumentCode: string;
  fullDocumentCode?: string;
}

export function GeneratedCodePreview({
  baseDocumentCode,
  fullDocumentCode,
}: GeneratedCodePreviewProps) {
  return (
    <div
      className="rounded-2xl border border-blue-200 bg-blue-50/70 p-4"
      aria-live="polite"
    >
      <div className="flex items-start gap-3">
        <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-blue-100 text-blue-700">
          <FileCode2 className="size-4.5" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-blue-700">
            Generated code preview
          </p>
          {baseDocumentCode ? (
            <div className="mt-2 space-y-2">
              <DocumentCodeField code={baseDocumentCode} />
              {fullDocumentCode && (
                <DocumentCodeField code={fullDocumentCode} label="Copy full code" />
              )}
            </div>
          ) : (
            <p className="mt-2 text-xs leading-5 text-slate-500">
              Select the identity fields to preview the document code.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
