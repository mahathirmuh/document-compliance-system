import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  createSharePointFolder,
  createSharePointFolderMapping,
  createSharePointMetadataMapping,
  listSharePointFolderMappings,
  listSharePointFolders,
  listSharePointMetadataMappings,
  updateSharePointFolderMapping,
  updateSharePointMetadataMapping,
} from '../api/sharepointApi';
import type {
  SharePointFolderCreate,
  SharePointFolderListParams,
  SharePointFolderMappingWrite,
  SharePointMappingListParams,
  SharePointMetadataMappingWrite,
} from '../types/sharepoint';
import { useDocumentSession } from './useDocumentSession';

export const sharePointMappingKeys = {
  root: (scope: readonly [string, number]) =>
    ['sharepoint-mappings', scope[0], scope[1]] as const,
  folders: (scope: readonly [string, number], params: object) =>
    [...sharePointMappingKeys.root(scope), 'folders', params] as const,
  folderMappings: (scope: readonly [string, number], params: object) =>
    [...sharePointMappingKeys.root(scope), 'folder-mappings', params] as const,
  metadataMappings: (scope: readonly [string, number], params: object) =>
    [...sharePointMappingKeys.root(scope), 'metadata-mappings', params] as const,
} as const;

export const useSharePointFolders = (
  params: SharePointFolderListParams,
  enabled = true,
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: sharePointMappingKeys.folders(scope, params),
    queryFn: ({ signal }) => listSharePointFolders(params, signal),
    enabled: enabled && Boolean(params.connectionId),
    placeholderData: (previous) => previous,
  });
};

export const useSharePointFolderMappings = (params: SharePointMappingListParams) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: sharePointMappingKeys.folderMappings(scope, params),
    queryFn: ({ signal }) => listSharePointFolderMappings(params, signal),
    placeholderData: (previous) => previous,
  });
};

export const useSharePointMetadataMappings = (params: SharePointMappingListParams) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: sharePointMappingKeys.metadataMappings(scope, params),
    queryFn: ({ signal }) => listSharePointMetadataMappings(params, signal),
    placeholderData: (previous) => previous,
  });
};

export const useSharePointMappingMutations = () => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();
  const invalidate = async (): Promise<void> => {
    await queryClient.invalidateQueries({
      queryKey: sharePointMappingKeys.root(scope),
    });
  };
  return {
    createFolder: useMutation({
      mutationFn: (payload: SharePointFolderCreate) => createSharePointFolder(payload),
      onSuccess: invalidate,
    }),
    createFolderMapping: useMutation({
      mutationFn: (payload: SharePointFolderMappingWrite) =>
        createSharePointFolderMapping(payload),
      onSuccess: invalidate,
    }),
    updateFolderMapping: useMutation({
      mutationFn: ({
        mappingId,
        payload,
      }: {
        mappingId: string;
        payload: SharePointFolderMappingWrite;
      }) => updateSharePointFolderMapping(mappingId, payload),
      onSuccess: invalidate,
    }),
    createMetadataMapping: useMutation({
      mutationFn: (payload: SharePointMetadataMappingWrite) =>
        createSharePointMetadataMapping(payload),
      onSuccess: invalidate,
    }),
    updateMetadataMapping: useMutation({
      mutationFn: ({
        mappingId,
        payload,
      }: {
        mappingId: string;
        payload: SharePointMetadataMappingWrite;
      }) => updateSharePointMetadataMapping(mappingId, payload),
      onSuccess: invalidate,
    }),
  } as const;
};
