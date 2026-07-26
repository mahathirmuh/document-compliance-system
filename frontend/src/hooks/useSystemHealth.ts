import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  dismissDeadLetterJob,
  getSystemHealth,
  listDeadLetterJobs,
  retryDeadLetterJob,
} from '../api/systemHealthApi';
import type {
  DeadLetterActionRequest,
  DeadLetterListParams,
} from '../types/systemHealth';
import { useDocumentSession } from './useDocumentSession';

export const systemHealthKeys = {
  root: (scope: readonly [string, number]) =>
    ['system-health', scope[0], scope[1]] as const,
  summary: (scope: readonly [string, number]) =>
    [...systemHealthKeys.root(scope), 'summary'] as const,
  deadLetters: (scope: readonly [string, number], params: object) =>
    [...systemHealthKeys.root(scope), 'dead-letters', params] as const,
} as const;

export const useSystemHealth = () => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: systemHealthKeys.summary(scope),
    queryFn: ({ signal }) => getSystemHealth(signal),
    refetchInterval: 30_000,
  });
};

export const useDeadLetterJobs = (params: DeadLetterListParams) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: systemHealthKeys.deadLetters(scope, params),
    queryFn: ({ signal }) => listDeadLetterJobs(params, signal),
    placeholderData: (previous) => previous,
  });
};

export const useDeadLetterMutations = () => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();
  const invalidate = async (): Promise<void> => {
    await queryClient.invalidateQueries({ queryKey: systemHealthKeys.root(scope) });
  };
  return {
    retry: useMutation({
      mutationFn: (jobId: string) => retryDeadLetterJob(jobId),
      onSuccess: invalidate,
    }),
    dismiss: useMutation({
      mutationFn: ({
        jobId,
        payload,
      }: {
        jobId: string;
        payload: DeadLetterActionRequest;
      }) => dismissDeadLetterJob(jobId, payload),
      onSuccess: invalidate,
    }),
  } as const;
};
