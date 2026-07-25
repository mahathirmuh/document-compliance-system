import { Download, LoaderCircle } from 'lucide-react';

import { getApiErrorMessage } from '../../api/errors';
import { useDocumentExport } from '../../hooks/useDocumentExport';
import { useToast } from '../../providers/useToast';
import type { DocumentExportParams } from '../../types/document';
import { downloadFile } from '../../utils/downloadFile';

interface DocumentExportButtonProps {
  params: DocumentExportParams;
  label?: string;
}

export function DocumentExportButton({
  label = 'Export',
  params,
}: DocumentExportButtonProps) {
  const exportMutation = useDocumentExport();
  const { showToast } = useToast();

  const exportDocuments = async (): Promise<void> => {
    try {
      const result = await exportMutation.mutateAsync(params);
      downloadFile(
        result,
        `document_register_${new Date().toISOString().slice(0, 10)}.xlsx`,
      );
      showToast({
        tone: 'success',
        title: 'Document register exported',
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Document register could not be exported',
        message: getApiErrorMessage(error, 'Review your filters and try again.'),
      });
    }
  };

  return (
    <button
      type="button"
      onClick={() => void exportDocuments()}
      disabled={exportMutation.isPending}
      className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 bg-white px-3.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
    >
      {exportMutation.isPending ? (
        <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
      ) : (
        <Download className="size-4" aria-hidden="true" />
      )}
      {exportMutation.isPending ? 'Exporting...' : label}
    </button>
  );
}
