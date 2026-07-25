import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { sectionApi } from '../api/sectionApi';
import type {
  SectionCreate,
  SectionListParams,
  SectionOptionsParams,
  SectionUpdate,
} from '../types/section';
import { masterDataKeys } from './masterDataQueryKeys';
import { useMasterDataSession } from './useMasterDataSession';

export const useSections = (params: SectionListParams) => {
  const scope = useMasterDataSession();
  return useQuery({
    queryKey: masterDataKeys.sections.list(scope, params),
    queryFn: () => sectionApi.list(params),
    placeholderData: (previous) => previous,
  });
};

export const useSection = (id: string | null) => {
  const scope = useMasterDataSession();
  return useQuery({
    queryKey: masterDataKeys.sections.detail(scope, id ?? 'none'),
    queryFn: () => sectionApi.getById(id ?? ''),
    enabled: id !== null,
  });
};

export const useSectionOptions = (params: SectionOptionsParams = {}) => {
  const scope = useMasterDataSession();
  return useQuery({
    queryKey: masterDataKeys.sections.options(scope, params),
    queryFn: () => sectionApi.getOptions(params),
    staleTime: 60_000,
  });
};

export const useSectionMutations = () => {
  const scope = useMasterDataSession();
  const queryClient = useQueryClient();
  const invalidate = async (): Promise<void> => {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: masterDataKeys.sections.all(scope),
      }),
      queryClient.invalidateQueries({ queryKey: masterDataKeys.overview(scope) }),
    ]);
  };

  return {
    create: useMutation({
      mutationFn: (payload: SectionCreate) => sectionApi.create(payload),
      onSuccess: invalidate,
    }),
    update: useMutation({
      mutationFn: ({ id, payload }: { id: string; payload: SectionUpdate }) =>
        sectionApi.update(id, payload),
      onSuccess: invalidate,
    }),
    activate: useMutation({
      mutationFn: sectionApi.activate,
      onSuccess: invalidate,
    }),
    deactivate: useMutation({
      mutationFn: sectionApi.deactivate,
      onSuccess: invalidate,
    }),
  };
};
