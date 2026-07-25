import { useQuery } from '@tanstack/react-query';

import { getDocumentFormOptions } from '../api/documentApi';
import { documentKeys } from './documentQueryKeys';
import { useDocumentSession } from './useDocumentSession';

export const useDocumentFormOptions = (enabled = true) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: documentKeys.formOptions(scope),
    queryFn: ({ signal }) => getDocumentFormOptions(signal),
    enabled,
  });
};
