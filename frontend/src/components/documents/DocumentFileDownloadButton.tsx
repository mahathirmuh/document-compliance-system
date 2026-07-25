import { Download } from 'lucide-react';

import { getApiErrorMessage } from '../../api/errors';
import { useDocumentFileMutations } from '../../hooks/useDocumentFiles';
import { useToast } from '../../providers/useToast';
import { downloadFile } from '../../utils/downloadFile';

interface DocumentFileDownloadButtonProps {
  fileId: string;
  fallbackFileName: string;
  label?: string;
  className?: string;
}

export function DocumentFileDownloadButton({
  className,
  fallbackFileName,
  fileId,
  label = 'Download',
}: DocumentFileDownloadButtonProps) {
  const mutations = useDocumentFileMutations();
  const { showToast } = useToast();

  const startDownload = async (): Promise<void> => {
    try {
      const response = await mutations.download.mutateAsync(fileId);
      downloadFile(response, fallbackFileName);
      showToast({ tone: 'success', title: 'Download started' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'File could not be downloaded',
        message: getApiErrorMessage(
          error,
          'Check file status, permission, and department scope.',
        ),
      });
    }
  };

  return (
    <button
      type="button"
      onClick={() => void startDownload()}
      disabled={mutations.download.isPending}
      className={
        className ??
        'inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-blue-50 px-3 text-xs font-semibold text-blue-700 hover:bg-blue-100 disabled:opacity-60'
      }
    >
      <Download className="size-3.5" aria-hidden="true" />
      {mutations.download.isPending ? 'Downloading...' : label}
    </button>
  );
}
