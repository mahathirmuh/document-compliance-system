import { useQuery } from '@tanstack/react-query';

import { getOCRHistory } from '../api/ocrApi';
import type { OCRHistoryParams } from '../types/ocr';
import { ocrKeys } from './ocrQueryKeys';
import { useDocumentSession } from './useDocumentSession';

export const useOCRHistory = (
  fileId: string | null,
  params: OCRHistoryParams,
  enabled = true,
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: ocrKeys.history(scope, fileId ?? 'none', params),
    queryFn: ({ signal }) => getOCRHistory(fileId ?? '', params, signal),
    enabled: enabled && fileId !== null,
    placeholderData: (previous) => previous,
  });
};
