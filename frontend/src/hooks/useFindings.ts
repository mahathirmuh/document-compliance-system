import { useMutation, useQuery } from '@tanstack/react-query';

import {
  exportFindings,
  getFinding,
  getFindingsReport,
  listFindings,
} from '../api/findingApi';
import type { FindingExportFormat, FindingListParams } from '../types/finding';
import { findingKeys } from './findingQueryKeys';
import { useDocumentSession } from './useDocumentSession';

export const useFindings = (
  params: FindingListParams,
  options: { enabled?: boolean } = {},
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: findingKeys.list(scope, params),
    queryFn: ({ signal }) => listFindings(params, signal),
    placeholderData: (previous) => previous,
    enabled: options.enabled ?? true,
  });
};

export const useFinding = (findingId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: findingKeys.detail(scope, findingId ?? 'none'),
    queryFn: ({ signal }) => getFinding(findingId ?? '', signal),
    enabled: findingId !== null,
  });
};

export const useFindingsReport = (params: FindingListParams) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: findingKeys.report(scope, params),
    queryFn: ({ signal }) => getFindingsReport(params, signal),
    placeholderData: (previous) => previous,
  });
};

export const useFindingsExport = () =>
  useMutation({
    mutationFn: ({
      format,
      params,
    }: {
      format: FindingExportFormat;
      params: Omit<FindingListParams, 'page' | 'pageSize'>;
    }) => exportFindings(format, params),
  });
