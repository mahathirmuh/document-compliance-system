import { useQuery } from '@tanstack/react-query';

import { listDocuments } from '../api/documentApi';
import type { DocumentListParams } from '../types/document';
import { documentKeys } from './documentQueryKeys';
import { useDocumentSession } from './useDocumentSession';

export const useDocuments = (params: DocumentListParams) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: documentKeys.list(scope, params),
    queryFn: ({ signal }) => listDocuments(params, signal),
    placeholderData: (previous) => previous,
  });
};
