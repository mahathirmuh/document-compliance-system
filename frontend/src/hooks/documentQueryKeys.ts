import type { DocumentListParams } from '../types/document';

export type DocumentSessionScope = readonly [userId: string, generation: number];

const root = (scope: DocumentSessionScope) =>
  ['documents', scope[0], scope[1]] as const;

export const documentKeys = {
  all: root,
  formOptions: (scope: DocumentSessionScope) =>
    [...root(scope), 'form-options'] as const,
  lists: (scope: DocumentSessionScope) => [...root(scope), 'list'] as const,
  list: (scope: DocumentSessionScope, params: DocumentListParams) =>
    [...root(scope), 'list', params] as const,
  details: (scope: DocumentSessionScope) => [...root(scope), 'detail'] as const,
  detail: (scope: DocumentSessionScope, documentId: string) =>
    [...root(scope), 'detail', documentId] as const,
  revisions: {
    all: (scope: DocumentSessionScope, documentId: string) =>
      [...root(scope), 'detail', documentId, 'revisions'] as const,
    list: (scope: DocumentSessionScope, documentId: string) =>
      [...root(scope), 'detail', documentId, 'revisions', 'list'] as const,
    detail: (scope: DocumentSessionScope, documentId: string, revisionId: string) =>
      [
        ...root(scope),
        'detail',
        documentId,
        'revisions',
        'detail',
        revisionId,
      ] as const,
  },
} as const;
