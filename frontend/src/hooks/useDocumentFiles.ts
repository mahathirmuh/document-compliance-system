import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  deleteDocumentFile,
  downloadCurrentRevisionFile,
  downloadDocumentFile,
  getDocumentFile,
  listDocumentFiles,
  listRevisionFiles,
  replaceDocumentFile,
  restoreDocumentFile,
  type ReplaceDocumentFileInput,
} from '../api/documentFileApi';
import type {
  DocumentFileDeleteRequest,
  DocumentFileRestoreRequest,
} from '../types/documentFile';
import { documentFileKeys } from './documentFileQueryKeys';
import { documentKeys } from './documentQueryKeys';
import { useDocumentSession } from './useDocumentSession';

interface DeleteFileVariables {
  fileId: string;
  payload: DocumentFileDeleteRequest;
}

interface RestoreFileVariables {
  fileId: string;
  payload?: DocumentFileRestoreRequest;
}

export const useDocumentFile = (fileId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: documentFileKeys.detail(scope, fileId ?? 'none'),
    queryFn: ({ signal }) => getDocumentFile(fileId ?? '', signal),
    enabled: fileId !== null,
  });
};

export const useDocumentFiles = (documentId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: documentFileKeys.document(scope, documentId ?? 'none'),
    queryFn: ({ signal }) => listDocumentFiles(documentId ?? '', signal),
    enabled: documentId !== null,
  });
};

export const useRevisionFiles = (
  documentId: string | null,
  revisionId: string | null,
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: documentFileKeys.revision(
      scope,
      documentId ?? 'none',
      revisionId ?? 'none',
    ),
    queryFn: ({ signal }) =>
      listRevisionFiles(documentId ?? '', revisionId ?? '', signal),
    enabled: documentId !== null && revisionId !== null,
  });
};

export const useDocumentFileMutations = () => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();

  const invalidate = async (): Promise<void> => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: documentFileKeys.all(scope) }),
      queryClient.invalidateQueries({ queryKey: documentKeys.all(scope) }),
    ]);
  };

  return {
    download: useMutation({ mutationFn: downloadDocumentFile }),
    downloadCurrentRevision: useMutation({
      mutationFn: ({
        documentId,
        revisionId,
      }: {
        documentId: string;
        revisionId: string;
      }) => downloadCurrentRevisionFile(documentId, revisionId),
    }),
    replace: useMutation({
      mutationFn: (input: ReplaceDocumentFileInput) => replaceDocumentFile(input),
      onSuccess: invalidate,
    }),
    delete: useMutation({
      mutationFn: ({ fileId, payload }: DeleteFileVariables) =>
        deleteDocumentFile(fileId, payload),
      onSuccess: invalidate,
    }),
    restore: useMutation({
      mutationFn: ({ fileId, payload = {} }: RestoreFileVariables) =>
        restoreDocumentFile(fileId, payload),
      onSuccess: invalidate,
    }),
  } as const;
};
