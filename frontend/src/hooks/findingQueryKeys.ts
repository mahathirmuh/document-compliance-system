import type { FindingListParams } from '../types/finding';
import type { DocumentSessionScope } from './documentQueryKeys';

const root = (scope: DocumentSessionScope) => ['findings', scope[0], scope[1]] as const;

export const findingKeys = {
  all: root,
  lists: (scope: DocumentSessionScope) => [...root(scope), 'list'] as const,
  list: (scope: DocumentSessionScope, params: FindingListParams) =>
    [...root(scope), 'list', params] as const,
  details: (scope: DocumentSessionScope) => [...root(scope), 'detail'] as const,
  detail: (scope: DocumentSessionScope, id: string) =>
    [...root(scope), 'detail', id] as const,
  report: (scope: DocumentSessionScope, params: FindingListParams) =>
    [...root(scope), 'report', params] as const,
} as const;
