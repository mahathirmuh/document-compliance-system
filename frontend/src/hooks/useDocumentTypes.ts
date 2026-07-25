import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { documentTypeApi } from '../api/documentTypeApi';
import type {
  DocumentTypeCreate,
  DocumentTypeListParams,
  DocumentTypeUpdate,
} from '../types/documentType';
import { masterDataKeys } from './masterDataQueryKeys';
import { useMasterDataSession } from './useMasterDataSession';

export const useDocumentTypes = (params: DocumentTypeListParams) => {
  const scope = useMasterDataSession();
  return useQuery({
    queryKey: masterDataKeys.documentTypes.list(scope, params),
    queryFn: () => documentTypeApi.list(params),
    placeholderData: (previous) => previous,
  });
};

export const useDocumentType = (id: string | null) => {
  const scope = useMasterDataSession();
  return useQuery({
    queryKey: masterDataKeys.documentTypes.detail(scope, id ?? 'none'),
    queryFn: () => documentTypeApi.getById(id ?? ''),
    enabled: id !== null,
  });
};

export const useDocumentTypeOptions = () => {
  const scope = useMasterDataSession();
  return useQuery({
    queryKey: masterDataKeys.documentTypes.options(scope),
    queryFn: documentTypeApi.getOptions,
    staleTime: 60_000,
  });
};

export const useDocumentTypeMutations = () => {
  const scope = useMasterDataSession();
  const queryClient = useQueryClient();
  const invalidate = async (): Promise<void> => {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: masterDataKeys.documentTypes.all(scope),
      }),
      queryClient.invalidateQueries({
        queryKey: masterDataKeys.validationRules.all(scope),
      }),
      queryClient.invalidateQueries({ queryKey: masterDataKeys.overview(scope) }),
    ]);
  };

  return {
    create: useMutation({
      mutationFn: (payload: DocumentTypeCreate) => documentTypeApi.create(payload),
      onSuccess: invalidate,
    }),
    update: useMutation({
      mutationFn: ({ id, payload }: { id: string; payload: DocumentTypeUpdate }) =>
        documentTypeApi.update(id, payload),
      onSuccess: invalidate,
    }),
    activate: useMutation({
      mutationFn: documentTypeApi.activate,
      onSuccess: invalidate,
    }),
    deactivate: useMutation({
      mutationFn: documentTypeApi.deactivate,
      onSuccess: invalidate,
    }),
  };
};
