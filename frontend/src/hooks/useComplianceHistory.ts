import { useQuery } from '@tanstack/react-query';

import { getComplianceHistory } from '../api/complianceApi';
import type { ComplianceHistoryParams } from '../types/compliance';
import { complianceKeys } from './complianceQueryKeys';
import { useDocumentSession } from './useDocumentSession';

export const useComplianceHistory = (
  fileId: string | null,
  params: ComplianceHistoryParams,
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: complianceKeys.history(scope, fileId ?? 'none', params),
    queryFn: ({ signal }) => getComplianceHistory(fileId ?? '', params, signal),
    enabled: fileId !== null,
    placeholderData: (previous) => previous,
  });
};
