import { useQuery } from '@tanstack/react-query';

import { getDocument } from '../api/documentApi';
import { documentKeys } from './documentQueryKeys';
import { useDocumentSession } from './useDocumentSession';

export const useDocument = (documentId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: documentKeys.detail(scope, documentId ?? 'none'),
    queryFn: ({ signal }) => getDocument(documentId ?? '', signal),
    enabled: documentId !== null,
  });
};
