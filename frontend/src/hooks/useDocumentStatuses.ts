import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { documentStatusApi } from '../api/documentStatusApi';
import type {
  DocumentStatusCreate,
  DocumentStatusListParams,
  DocumentStatusUpdate,
} from '../types/documentStatus';
import { masterDataKeys } from './masterDataQueryKeys';
import { useMasterDataSession } from './useMasterDataSession';

export const useDocumentStatuses = (params: DocumentStatusListParams) => {
  const scope = useMasterDataSession();
  return useQuery({
    queryKey: masterDataKeys.documentStatuses.list(scope, params),
    queryFn: () => documentStatusApi.list(params),
    placeholderData: (previous) => previous,
  });
};

export const useDocumentStatus = (id: string | null) => {
  const scope = useMasterDataSession();
  return useQuery({
    queryKey: masterDataKeys.documentStatuses.detail(scope, id ?? 'none'),
    queryFn: () => documentStatusApi.getById(id ?? ''),
    enabled: id !== null,
  });
};

export const useDocumentStatusOptions = () => {
  const scope = useMasterDataSession();
  return useQuery({
    queryKey: masterDataKeys.documentStatuses.options(scope),
    queryFn: documentStatusApi.getOptions,
    staleTime: 60_000,
  });
};

export const useDocumentStatusMutations = () => {
  const scope = useMasterDataSession();
  const queryClient = useQueryClient();
  const invalidate = async (): Promise<void> => {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: masterDataKeys.documentStatuses.all(scope),
      }),
      queryClient.invalidateQueries({ queryKey: masterDataKeys.overview(scope) }),
    ]);
  };

  return {
    create: useMutation({
      mutationFn: (payload: DocumentStatusCreate) => documentStatusApi.create(payload),
      onSuccess: invalidate,
    }),
    update: useMutation({
      mutationFn: ({ id, payload }: { id: string; payload: DocumentStatusUpdate }) =>
        documentStatusApi.update(id, payload),
      onSuccess: invalidate,
    }),
    activate: useMutation({
      mutationFn: documentStatusApi.activate,
      onSuccess: invalidate,
    }),
    deactivate: useMutation({
      mutationFn: documentStatusApi.deactivate,
      onSuccess: invalidate,
    }),
  };
};
