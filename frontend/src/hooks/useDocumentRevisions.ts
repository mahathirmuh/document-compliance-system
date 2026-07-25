import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  createRevision,
  getRevision,
  listRevisions,
  setCurrentRevision,
  supersedeRevision,
  updateRevision,
} from '../api/documentRevisionApi';
import type {
  DocumentRevisionCreate,
  DocumentRevisionSetCurrentRequest,
  DocumentRevisionSupersedeRequest,
  DocumentRevisionUpdate,
} from '../types/documentRevision';
import { documentKeys } from './documentQueryKeys';
import { useDocumentSession } from './useDocumentSession';

interface RevisionUpdateVariables {
  revisionId: string;
  payload: DocumentRevisionUpdate;
}

interface SetCurrentRevisionVariables {
  revisionId: string;
  payload?: DocumentRevisionSetCurrentRequest;
}

interface SupersedeRevisionVariables {
  revisionId: string;
  payload: DocumentRevisionSupersedeRequest;
}

export const useDocumentRevisions = (documentId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: documentKeys.revisions.list(scope, documentId ?? 'none'),
    queryFn: ({ signal }) => listRevisions(documentId ?? '', signal),
    enabled: documentId !== null,
  });
};

export const useDocumentRevision = (
  documentId: string | null,
  revisionId: string | null,
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: documentKeys.revisions.detail(
      scope,
      documentId ?? 'none',
      revisionId ?? 'none',
    ),
    queryFn: ({ signal }) => getRevision(documentId ?? '', revisionId ?? '', signal),
    enabled: documentId !== null && revisionId !== null,
  });
};

export const useDocumentRevisionMutations = (documentId: string) => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();

  const invalidateRevisions = async (): Promise<void> => {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: documentKeys.revisions.all(scope, documentId),
      }),
      queryClient.invalidateQueries({
        queryKey: documentKeys.detail(scope, documentId),
      }),
      queryClient.invalidateQueries({
        queryKey: documentKeys.lists(scope),
      }),
    ]);
  };

  return {
    create: useMutation({
      mutationFn: (payload: DocumentRevisionCreate) =>
        createRevision(documentId, payload),
      onSuccess: invalidateRevisions,
    }),
    update: useMutation({
      mutationFn: ({ payload, revisionId }: RevisionUpdateVariables) =>
        updateRevision(documentId, revisionId, payload),
      onSuccess: invalidateRevisions,
    }),
    setCurrent: useMutation({
      mutationFn: ({ payload, revisionId }: SetCurrentRevisionVariables) =>
        setCurrentRevision(documentId, revisionId, payload ?? {}),
      onSuccess: invalidateRevisions,
    }),
    supersede: useMutation({
      mutationFn: ({ payload, revisionId }: SupersedeRevisionVariables) =>
        supersedeRevision(documentId, revisionId, payload),
      onSuccess: invalidateRevisions,
    }),
  };
};
