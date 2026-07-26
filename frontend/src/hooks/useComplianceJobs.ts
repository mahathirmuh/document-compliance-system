import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  cancelComplianceJob,
  getComplianceJob,
  listComplianceJobs,
} from '../api/complianceApi';
import type { ComplianceJobListParams } from '../types/compliance';
import {
  isActiveComplianceJobStatus,
  isTerminalComplianceJobStatus,
} from '../types/compliance';
import { complianceKeys } from './complianceQueryKeys';
import { documentFileKeys } from './documentFileQueryKeys';
import { documentKeys } from './documentQueryKeys';
import { findingKeys } from './findingQueryKeys';
import { useDocumentSession } from './useDocumentSession';

const pollIntervalMs = 3_000;

export const useComplianceJob = (
  jobId: string | null,
  options: { enabled?: boolean; poll?: boolean } = {},
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: complianceKeys.job(scope, jobId ?? 'none'),
    queryFn: ({ signal }) => getComplianceJob(jobId ?? '', signal),
    enabled: (options.enabled ?? true) && jobId !== null,
    refetchInterval: (query) => {
      if (!options.poll || !query.state.data) {
        return false;
      }
      return isTerminalComplianceJobStatus(query.state.data.status)
        ? false
        : pollIntervalMs;
    },
  });
};

export const useComplianceJobs = (
  params: ComplianceJobListParams,
  options: { enabled?: boolean; pollActive?: boolean } = {},
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: complianceKeys.jobList(scope, params),
    queryFn: ({ signal }) => listComplianceJobs(params, signal),
    enabled: options.enabled ?? true,
    placeholderData: (previous) => previous,
    refetchInterval: (query) => {
      if (!options.pollActive) {
        return false;
      }
      return query.state.data?.items.some((job) =>
        isActiveComplianceJobStatus(job.status),
      )
        ? pollIntervalMs
        : false;
    },
  });
};

export const useCancelComplianceJob = () => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cancelComplianceJob,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: complianceKeys.all(scope) }),
        queryClient.invalidateQueries({ queryKey: findingKeys.all(scope) }),
        queryClient.invalidateQueries({ queryKey: documentFileKeys.all(scope) }),
        queryClient.invalidateQueries({ queryKey: documentKeys.all(scope) }),
      ]);
    },
  });
};
