import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { validationRuleApi } from '../api/validationRuleApi';
import type {
  ValidationRuleCreate,
  ValidationRuleListParams,
  ValidationRuleUpdate,
} from '../types/validationRule';
import { masterDataKeys } from './masterDataQueryKeys';
import { useMasterDataSession } from './useMasterDataSession';

export const useValidationRules = (params: ValidationRuleListParams) => {
  const scope = useMasterDataSession();
  return useQuery({
    queryKey: masterDataKeys.validationRules.list(scope, params),
    queryFn: () => validationRuleApi.list(params),
    placeholderData: (previous) => previous,
  });
};

export const useValidationRule = (id: string | null) => {
  const scope = useMasterDataSession();
  return useQuery({
    queryKey: masterDataKeys.validationRules.detail(scope, id ?? 'none'),
    queryFn: () => validationRuleApi.getById(id ?? ''),
    enabled: id !== null,
  });
};

export const useValidationRuleOptions = () => {
  const scope = useMasterDataSession();
  return useQuery({
    queryKey: masterDataKeys.validationRules.options(scope),
    queryFn: validationRuleApi.getOptions,
    staleTime: 60_000,
  });
};

export const useValidationRuleMutations = () => {
  const scope = useMasterDataSession();
  const queryClient = useQueryClient();
  const invalidate = async (): Promise<void> => {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: masterDataKeys.validationRules.all(scope),
      }),
      queryClient.invalidateQueries({
        queryKey: masterDataKeys.documentTypes.all(scope),
      }),
      queryClient.invalidateQueries({ queryKey: masterDataKeys.overview(scope) }),
    ]);
  };

  return {
    create: useMutation({
      mutationFn: (payload: ValidationRuleCreate) => validationRuleApi.create(payload),
      onSuccess: invalidate,
    }),
    update: useMutation({
      mutationFn: ({ id, payload }: { id: string; payload: ValidationRuleUpdate }) =>
        validationRuleApi.update(id, payload),
      onSuccess: invalidate,
    }),
    activate: useMutation({
      mutationFn: validationRuleApi.activate,
      onSuccess: invalidate,
    }),
    deactivate: useMutation({
      mutationFn: validationRuleApi.deactivate,
      onSuccess: invalidate,
    }),
    setDefault: useMutation({
      mutationFn: validationRuleApi.setDefault,
      onSuccess: invalidate,
    }),
  };
};
