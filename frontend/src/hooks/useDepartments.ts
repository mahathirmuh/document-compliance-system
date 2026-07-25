import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { departmentApi } from '../api/departmentApi';
import type {
  DepartmentCreate,
  DepartmentListParams,
  DepartmentUpdate,
} from '../types/department';
import { masterDataKeys } from './masterDataQueryKeys';
import { useMasterDataSession } from './useMasterDataSession';

export const useDepartments = (params: DepartmentListParams) => {
  const scope = useMasterDataSession();
  return useQuery({
    queryKey: masterDataKeys.departments.list(scope, params),
    queryFn: () => departmentApi.list(params),
    placeholderData: (previous) => previous,
  });
};

export const useDepartment = (id: string | null) => {
  const scope = useMasterDataSession();
  return useQuery({
    queryKey: masterDataKeys.departments.detail(scope, id ?? 'none'),
    queryFn: () => departmentApi.getById(id ?? ''),
    enabled: id !== null,
  });
};

export const useDepartmentOptions = (activeOnly = true) => {
  const scope = useMasterDataSession();
  return useQuery({
    queryKey: masterDataKeys.departments.options(scope, activeOnly),
    queryFn: () => departmentApi.getOptions(activeOnly),
    staleTime: 60_000,
  });
};

export const useDepartmentMutations = () => {
  const scope = useMasterDataSession();
  const queryClient = useQueryClient();
  const invalidate = async (): Promise<void> => {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: masterDataKeys.departments.all(scope),
      }),
      queryClient.invalidateQueries({ queryKey: masterDataKeys.overview(scope) }),
    ]);
  };

  return {
    create: useMutation({
      mutationFn: (payload: DepartmentCreate) => departmentApi.create(payload),
      onSuccess: invalidate,
    }),
    update: useMutation({
      mutationFn: ({ id, payload }: { id: string; payload: DepartmentUpdate }) =>
        departmentApi.update(id, payload),
      onSuccess: invalidate,
    }),
    activate: useMutation({
      mutationFn: departmentApi.activate,
      onSuccess: invalidate,
    }),
    deactivate: useMutation({
      mutationFn: departmentApi.deactivate,
      onSuccess: invalidate,
    }),
  };
};
