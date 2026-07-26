import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  cancelSimilarity,
  getSimilarityJob,
  listSimilarityJobs,
} from '../api/similarityApi';
import type { SimilarityJobListParams } from '../types/similarity';
import {
  isActiveSimilarityJobStatus,
  isTerminalSimilarityJobStatus,
} from '../types/similarity';
import { similarityKeys } from './useSimilarity';
import { useDocumentSession } from './useDocumentSession';

const pollingIntervalMs = 3_000;

export const useSimilarityJob = (
  jobId: string | null,
  options: { enabled?: boolean; poll?: boolean } = {},
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: similarityKeys.job(scope, jobId ?? 'none'),
    queryFn: ({ signal }) => getSimilarityJob(jobId ?? '', signal),
    enabled: (options.enabled ?? true) && jobId !== null,
    refetchInterval: (query) => {
      if (!(options.poll ?? true) || !query.state.data) {
        return false;
      }
      return isTerminalSimilarityJobStatus(query.state.data.status)
        ? false
        : pollingIntervalMs;
    },
  });
};

export const useSimilarityJobs = (
  params: SimilarityJobListParams,
  options: { pollActive?: boolean } = {},
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: similarityKeys.jobList(scope, params),
    queryFn: ({ signal }) => listSimilarityJobs(params, signal),
    placeholderData: (previous) => previous,
    refetchInterval: (query) =>
      options.pollActive &&
      query.state.data?.items.some((job) => isActiveSimilarityJobStatus(job.status))
        ? pollingIntervalMs
        : false,
  });
};

export const useCancelSimilarity = () => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cancelSimilarity,
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: similarityKeys.root(scope),
      });
    },
  });
};
