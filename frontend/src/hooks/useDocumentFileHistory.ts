import { useQuery } from '@tanstack/react-query';

import { listFileHistory } from '../api/documentFileApi';
import type { DocumentFileHistoryParams } from '../types/documentFile';
import { documentFileKeys } from './documentFileQueryKeys';
import { useDocumentSession } from './useDocumentSession';

export const useDocumentFileHistory = (
  params: DocumentFileHistoryParams,
  enabled = true,
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: documentFileKeys.history(scope, params),
    queryFn: ({ signal }) => listFileHistory(params, signal),
    enabled,
    placeholderData: (previous) => previous,
  });
};
