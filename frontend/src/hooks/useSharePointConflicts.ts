import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  assignSyncConflict,
  getSyncConflict,
  ignoreSyncConflict,
  listSyncConflicts,
  resolveSyncConflict,
} from '../api/sharepointSyncApi';
import type {
  ConflictAssignmentRequest,
  ConflictResolutionRequest,
  SyncConflictListParams,
} from '../types/synchronisation';
import { useDocumentSession } from './useDocumentSession';

export const sharePointConflictKeys = {
  root: (scope: readonly [string, number]) =>
    ['sharepoint-conflicts', scope[0], scope[1]] as const,
  list: (scope: readonly [string, number], params: object) =>
    [...sharePointConflictKeys.root(scope), 'list', params] as const,
  detail: (scope: readonly [string, number], conflictId: string) =>
    [...sharePointConflictKeys.root(scope), 'detail', conflictId] as const,
} as const;

export const useSharePointConflicts = (params: SyncConflictListParams) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: sharePointConflictKeys.list(scope, params),
    queryFn: ({ signal }) => listSyncConflicts(params, signal),
    placeholderData: (previous) => previous,
  });
};

export const useSharePointConflict = (conflictId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: sharePointConflictKeys.detail(scope, conflictId ?? 'none'),
    queryFn: ({ signal }) => getSyncConflict(conflictId ?? '', signal),
    enabled: conflictId !== null,
  });
};

export const useSharePointConflictMutations = () => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();
  const invalidate = async (): Promise<void> => {
    await queryClient.invalidateQueries({
      queryKey: sharePointConflictKeys.root(scope),
    });
  };
  return {
    assign: useMutation({
      mutationFn: ({
        conflictId,
        payload,
      }: {
        conflictId: string;
        payload: ConflictAssignmentRequest;
      }) => assignSyncConflict(conflictId, payload),
      onSuccess: invalidate,
    }),
    resolve: useMutation({
      mutationFn: ({
        conflictId,
        payload,
      }: {
        conflictId: string;
        payload: ConflictResolutionRequest;
      }) => resolveSyncConflict(conflictId, payload),
      onSuccess: invalidate,
    }),
    ignore: useMutation({
      mutationFn: ({ comment, conflictId }: { conflictId: string; comment: string }) =>
        ignoreSyncConflict(conflictId, comment),
      onSuccess: invalidate,
    }),
  } as const;
};
