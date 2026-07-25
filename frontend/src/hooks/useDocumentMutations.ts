import { useMutation, useQueryClient } from '@tanstack/react-query';

import {
  archiveDocument,
  bulkArchive,
  bulkRestore,
  bulkUpdateStatus,
  createDocument,
  parseDocumentCode,
  restoreDocument,
  updateDocument,
} from '../api/documentApi';
import type {
  DocumentArchiveRequest,
  DocumentBulkArchiveRequest,
  DocumentBulkRestoreRequest,
  DocumentBulkUpdateStatusRequest,
  DocumentCreate,
  DocumentParseRequest,
  DocumentUpdate,
} from '../types/document';
import { documentKeys } from './documentQueryKeys';
import { useDocumentSession } from './useDocumentSession';

interface DocumentUpdateVariables {
  documentId: string;
  payload: DocumentUpdate;
}

interface DocumentArchiveVariables {
  documentId: string;
  payload: DocumentArchiveRequest;
}

export const useDocumentMutations = () => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();

  const invalidateDocuments = async (): Promise<void> => {
    await queryClient.invalidateQueries({
      queryKey: documentKeys.all(scope),
    });
  };

  return {
    create: useMutation({
      mutationFn: (payload: DocumentCreate) => createDocument(payload),
      onSuccess: invalidateDocuments,
    }),
    update: useMutation({
      mutationFn: ({ documentId, payload }: DocumentUpdateVariables) =>
        updateDocument(documentId, payload),
      onSuccess: invalidateDocuments,
    }),
    archive: useMutation({
      mutationFn: ({ documentId, payload }: DocumentArchiveVariables) =>
        archiveDocument(documentId, payload),
      onSuccess: invalidateDocuments,
    }),
    restore: useMutation({
      mutationFn: (documentId: string) => restoreDocument(documentId),
      onSuccess: invalidateDocuments,
    }),
    parseCode: useMutation({
      mutationFn: (payload: DocumentParseRequest) => parseDocumentCode(payload),
    }),
    bulkArchive: useMutation({
      mutationFn: (payload: DocumentBulkArchiveRequest) => bulkArchive(payload),
      onSuccess: invalidateDocuments,
    }),
    bulkRestore: useMutation({
      mutationFn: (payload: DocumentBulkRestoreRequest) => bulkRestore(payload),
      onSuccess: invalidateDocuments,
    }),
    bulkUpdateStatus: useMutation({
      mutationFn: (payload: DocumentBulkUpdateStatusRequest) =>
        bulkUpdateStatus(payload),
      onSuccess: invalidateDocuments,
    }),
  };
};
