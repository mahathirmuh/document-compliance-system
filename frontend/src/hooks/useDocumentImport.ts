import { useMutation, useQueryClient } from '@tanstack/react-query';

import {
  confirmImport,
  downloadImportTemplate,
  previewImport,
} from '../api/documentImportApi';
import type { DocumentImportMode } from '../types/documentImport';
import { documentKeys } from './documentQueryKeys';
import { useDocumentSession } from './useDocumentSession';

interface DocumentImportConfirmVariables {
  file: File;
  mode: DocumentImportMode;
}

export const useDocumentImport = () => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();

  return {
    template: useMutation({
      mutationFn: () => downloadImportTemplate(),
    }),
    preview: useMutation({
      mutationFn: (file: File) => previewImport(file),
    }),
    confirm: useMutation({
      mutationFn: ({ file, mode }: DocumentImportConfirmVariables) =>
        confirmImport(file, mode),
      onSuccess: async () => {
        await queryClient.invalidateQueries({
          queryKey: documentKeys.all(scope),
        });
      },
    }),
  };
};
