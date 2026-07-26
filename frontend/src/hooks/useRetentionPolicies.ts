import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  createRetentionPolicy,
  listRetentionPolicies,
  runRetentionPolicies,
  updateRetentionPolicy,
} from '../api/retentionApi';
import type {
  RetentionPolicyCreate,
  RetentionPolicyListParams,
  RetentionPolicyUpdate,
  RetentionRunRequest,
} from '../types/retention';
import { useDocumentSession } from './useDocumentSession';

export const retentionKeys = {
  root: (scope: readonly [string, number]) =>
    ['retention-policies', scope[0], scope[1]] as const,
  list: (scope: readonly [string, number], params: object) =>
    [...retentionKeys.root(scope), 'list', params] as const,
} as const;

export const useRetentionPolicies = (params: RetentionPolicyListParams) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: retentionKeys.list(scope, params),
    queryFn: ({ signal }) => listRetentionPolicies(params, signal),
    placeholderData: (previous) => previous,
  });
};

export const useRetentionPolicyMutations = () => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();
  const invalidate = async (): Promise<void> => {
    await queryClient.invalidateQueries({ queryKey: retentionKeys.root(scope) });
  };
  return {
    create: useMutation({
      mutationFn: (payload: RetentionPolicyCreate) =>
        createRetentionPolicy(payload),
      onSuccess: invalidate,
    }),
    update: useMutation({
      mutationFn: ({
        payload,
        policyId,
      }: {
        policyId: string;
        payload: RetentionPolicyUpdate;
      }) => updateRetentionPolicy(policyId, payload),
      onSuccess: invalidate,
    }),
    run: useMutation({
      mutationFn: (payload: RetentionRunRequest) => runRetentionPolicies(payload),
      onSuccess: invalidate,
    }),
  } as const;
};
