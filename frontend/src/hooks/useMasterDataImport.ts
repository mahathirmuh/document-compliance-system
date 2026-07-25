import { useMutation, useQueryClient } from '@tanstack/react-query';

import { masterDataApi } from '../api/masterDataApi';
import type { ImportMode, MasterDataEntityType } from '../types/masterData';
import { masterDataKeys } from './masterDataQueryKeys';
import { useMasterDataSession } from './useMasterDataSession';

interface ImportFileVariables {
  entityType: MasterDataEntityType;
  file: File;
}

interface ImportConfirmVariables extends ImportFileVariables {
  mode: ImportMode;
}

export const useMasterDataImport = () => {
  const scope = useMasterDataSession();
  const queryClient = useQueryClient();

  return {
    preview: useMutation({
      mutationFn: ({ entityType, file }: ImportFileVariables) =>
        masterDataApi.previewImport(entityType, file),
    }),
    confirm: useMutation({
      mutationFn: ({ entityType, file, mode }: ImportConfirmVariables) =>
        masterDataApi.confirmImport(entityType, file, mode),
      onSuccess: async () => {
        await queryClient.invalidateQueries({
          queryKey: masterDataKeys.all(scope),
        });
      },
    }),
    template: useMutation({
      mutationFn: masterDataApi.downloadTemplate,
    }),
    exportXlsx: useMutation({
      mutationFn: ({
        entityType,
        params,
      }: {
        entityType: MasterDataEntityType;
        params?: Record<string, string | number | boolean>;
      }) => masterDataApi.exportXlsx(entityType, params),
    }),
  };
};
