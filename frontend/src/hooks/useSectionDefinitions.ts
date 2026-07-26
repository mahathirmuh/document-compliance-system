import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { sectionDefinitionApi } from '../api/sectionDefinitionApi';
import type {
  SectionAliasCreate,
  SectionAliasListParams,
  SectionAliasProfileCreate,
  SectionAliasProfileListParams,
  SectionAliasProfileUpdate,
  SectionAliasUpdate,
  SectionDefinitionCreate,
  SectionDefinitionImportConfirmRequest,
  SectionDefinitionListParams,
  SectionDefinitionUpdate,
  SectionHeadingMatchRequest,
} from '../types/sectionDefinition';
import { sectionDefinitionKeys } from './sectionDefinitionQueryKeys';
import { useDocumentSession } from './useDocumentSession';

export const useSectionAliasProfiles = (params: SectionAliasProfileListParams) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: sectionDefinitionKeys.profileList(scope, params),
    queryFn: ({ signal }) => sectionDefinitionApi.listProfiles(params, signal),
    placeholderData: (previous) => previous,
  });
};

export const useSectionDefinitions = (params: SectionDefinitionListParams) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: sectionDefinitionKeys.definitionList(scope, params),
    queryFn: ({ signal }) => sectionDefinitionApi.listDefinitions(params, signal),
    placeholderData: (previous) => previous,
  });
};

export const useSectionAliases = (params: SectionAliasListParams) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: sectionDefinitionKeys.aliasList(scope, params),
    queryFn: ({ signal }) => sectionDefinitionApi.listAliases(params, signal),
    placeholderData: (previous) => previous,
  });
};

export const useSectionDefinitionMutations = () => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();
  const invalidate = async (): Promise<void> => {
    await queryClient.invalidateQueries({
      queryKey: sectionDefinitionKeys.all(scope),
    });
  };

  return {
    createProfile: useMutation({
      mutationFn: (payload: SectionAliasProfileCreate) =>
        sectionDefinitionApi.createProfile(payload),
      onSuccess: invalidate,
    }),
    updateProfile: useMutation({
      mutationFn: ({
        id,
        payload,
      }: {
        id: string;
        payload: SectionAliasProfileUpdate;
      }) => sectionDefinitionApi.updateProfile(id, payload),
      onSuccess: invalidate,
    }),
    activateProfile: useMutation({
      mutationFn: sectionDefinitionApi.activateProfile,
      onSuccess: invalidate,
    }),
    deactivateProfile: useMutation({
      mutationFn: sectionDefinitionApi.deactivateProfile,
      onSuccess: invalidate,
    }),
    createDefinition: useMutation({
      mutationFn: (payload: SectionDefinitionCreate) =>
        sectionDefinitionApi.createDefinition(payload),
      onSuccess: invalidate,
    }),
    updateDefinition: useMutation({
      mutationFn: ({ id, payload }: { id: string; payload: SectionDefinitionUpdate }) =>
        sectionDefinitionApi.updateDefinition(id, payload),
      onSuccess: invalidate,
    }),
    activateDefinition: useMutation({
      mutationFn: sectionDefinitionApi.activateDefinition,
      onSuccess: invalidate,
    }),
    deactivateDefinition: useMutation({
      mutationFn: sectionDefinitionApi.deactivateDefinition,
      onSuccess: invalidate,
    }),
    createAlias: useMutation({
      mutationFn: (payload: SectionAliasCreate) =>
        sectionDefinitionApi.createAlias(payload),
      onSuccess: invalidate,
    }),
    updateAlias: useMutation({
      mutationFn: ({ id, payload }: { id: string; payload: SectionAliasUpdate }) =>
        sectionDefinitionApi.updateAlias(id, payload),
      onSuccess: invalidate,
    }),
    activateAlias: useMutation({
      mutationFn: sectionDefinitionApi.activateAlias,
      onSuccess: invalidate,
    }),
    deactivateAlias: useMutation({
      mutationFn: sectionDefinitionApi.deactivateAlias,
      onSuccess: invalidate,
    }),
    testMatch: useMutation({
      mutationFn: (payload: SectionHeadingMatchRequest) =>
        sectionDefinitionApi.testMatch(payload),
    }),
    previewImport: useMutation({
      mutationFn: ({ file, profileId }: { file: File; profileId?: string }) =>
        sectionDefinitionApi.previewImport(file, profileId),
    }),
    confirmImport: useMutation({
      mutationFn: (payload: SectionDefinitionImportConfirmRequest) =>
        sectionDefinitionApi.confirmImport(payload),
      onSuccess: invalidate,
    }),
    export: useMutation({
      mutationFn: (profileId?: string) => sectionDefinitionApi.exportXlsx(profileId),
    }),
  } as const;
};
