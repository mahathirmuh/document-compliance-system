import { useQuery } from '@tanstack/react-query';

import { getExtractionHistory } from '../api/extractionApi';
import { extractionKeys } from './extractionQueryKeys';
import { useDocumentSession } from './useDocumentSession';

export const useExtractionHistory = (
  fileId: string | null,
  page: number,
  pageSize: number,
  enabled = true,
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: extractionKeys.history(scope, fileId ?? 'none', page, pageSize),
    queryFn: ({ signal }) =>
      getExtractionHistory(fileId ?? '', { page, pageSize }, signal),
    enabled: enabled && fileId !== null,
    placeholderData: (previous) => previous,
  });
};
