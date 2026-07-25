import { ScanText } from 'lucide-react';

import { getApiErrorMessage } from '../../api/errors';
import { useExtractionMutations } from '../../hooks/useExtraction';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type { ExtractionQueuedResult } from '../../types/extraction';

export function StartExtractionButton({
  className,
  disabled = false,
  fileId,
  label = 'Extract Content',
  onQueued,
}: {
  fileId: string;
  disabled?: boolean;
  label?: string;
  className?: string;
  onQueued?: (result: ExtractionQueuedResult) => void;
}) {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const mutation = useExtractionMutations().start;
  const { showToast } = useToast();

  if (!hasPermission('documents:extract')) {
    return null;
  }

  const start = async (): Promise<void> => {
    try {
      const result = await mutation.mutateAsync({ documentFileId: fileId });
      showToast({
        tone: 'success',
        title: result.reusedExistingResult
          ? 'Existing extraction opened'
          : 'Extraction queued',
        message: result.reusedExistingResult
          ? 'The current file already has a valid extraction result.'
          : 'Progress is available in the Extraction Queue.',
      });
      onQueued?.(result);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Extraction could not be started',
        message: getApiErrorMessage(
          error,
          'Verify that the file is current and available.',
        ),
      });
    }
  };

  return (
    <button
      type="button"
      onClick={() => void start()}
      disabled={disabled || mutation.isPending}
      className={
        className ??
        'inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-blue-50 px-3 text-xs font-semibold text-blue-700 hover:bg-blue-100 disabled:opacity-60'
      }
    >
      <ScanText className="size-3.5" aria-hidden="true" />
      {mutation.isPending ? 'Queueing...' : label}
    </button>
  );
}
