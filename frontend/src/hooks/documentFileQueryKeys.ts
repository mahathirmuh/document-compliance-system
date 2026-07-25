import type { DocumentFileHistoryParams } from '../types/documentFile';
import type { DocumentSessionScope } from './documentQueryKeys';

const root = (scope: DocumentSessionScope) =>
  ['document-files', scope[0], scope[1]] as const;

export const documentFileKeys = {
  all: root,
  histories: (scope: DocumentSessionScope) => [...root(scope), 'history'] as const,
  history: (scope: DocumentSessionScope, params: DocumentFileHistoryParams) =>
    [...root(scope), 'history', params] as const,
  details: (scope: DocumentSessionScope) => [...root(scope), 'detail'] as const,
  detail: (scope: DocumentSessionScope, fileId: string) =>
    [...root(scope), 'detail', fileId] as const,
  document: (scope: DocumentSessionScope, documentId: string) =>
    [...root(scope), 'document', documentId] as const,
  revision: (scope: DocumentSessionScope, documentId: string, revisionId: string) =>
    [...root(scope), 'document', documentId, 'revision', revisionId] as const,
} as const;
