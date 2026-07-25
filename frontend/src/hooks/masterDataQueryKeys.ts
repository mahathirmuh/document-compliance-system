import type { DepartmentListParams } from '../types/department';
import type { DocumentStatusListParams } from '../types/documentStatus';
import type { DocumentTypeListParams } from '../types/documentType';
import type { SectionListParams, SectionOptionsParams } from '../types/section';
import type { ValidationRuleListParams } from '../types/validationRule';

export type SessionQueryScope = readonly [userId: string, generation: number];

const root = (scope: SessionQueryScope) => ['master-data', scope[0], scope[1]] as const;

export const masterDataKeys = {
  all: root,
  overview: (scope: SessionQueryScope) => [...root(scope), 'overview'] as const,
  departments: {
    all: (scope: SessionQueryScope) => [...root(scope), 'departments'] as const,
    lists: (scope: SessionQueryScope) =>
      [...root(scope), 'departments', 'list'] as const,
    list: (scope: SessionQueryScope, params: DepartmentListParams) =>
      [...root(scope), 'departments', 'list', params] as const,
    detail: (scope: SessionQueryScope, id: string) =>
      [...root(scope), 'departments', 'detail', id] as const,
    options: (scope: SessionQueryScope, activeOnly: boolean) =>
      [...root(scope), 'departments', 'options', activeOnly] as const,
  },
  sections: {
    all: (scope: SessionQueryScope) => [...root(scope), 'sections'] as const,
    lists: (scope: SessionQueryScope) => [...root(scope), 'sections', 'list'] as const,
    list: (scope: SessionQueryScope, params: SectionListParams) =>
      [...root(scope), 'sections', 'list', params] as const,
    detail: (scope: SessionQueryScope, id: string) =>
      [...root(scope), 'sections', 'detail', id] as const,
    options: (scope: SessionQueryScope, params: SectionOptionsParams) =>
      [...root(scope), 'sections', 'options', params] as const,
  },
  documentTypes: {
    all: (scope: SessionQueryScope) => [...root(scope), 'document-types'] as const,
    lists: (scope: SessionQueryScope) =>
      [...root(scope), 'document-types', 'list'] as const,
    list: (scope: SessionQueryScope, params: DocumentTypeListParams) =>
      [...root(scope), 'document-types', 'list', params] as const,
    detail: (scope: SessionQueryScope, id: string) =>
      [...root(scope), 'document-types', 'detail', id] as const,
    options: (scope: SessionQueryScope) =>
      [...root(scope), 'document-types', 'options'] as const,
  },
  documentStatuses: {
    all: (scope: SessionQueryScope) => [...root(scope), 'document-statuses'] as const,
    lists: (scope: SessionQueryScope) =>
      [...root(scope), 'document-statuses', 'list'] as const,
    list: (scope: SessionQueryScope, params: DocumentStatusListParams) =>
      [...root(scope), 'document-statuses', 'list', params] as const,
    detail: (scope: SessionQueryScope, id: string) =>
      [...root(scope), 'document-statuses', 'detail', id] as const,
    options: (scope: SessionQueryScope) =>
      [...root(scope), 'document-statuses', 'options'] as const,
  },
  validationRules: {
    all: (scope: SessionQueryScope) => [...root(scope), 'validation-rules'] as const,
    lists: (scope: SessionQueryScope) =>
      [...root(scope), 'validation-rules', 'list'] as const,
    list: (scope: SessionQueryScope, params: ValidationRuleListParams) =>
      [...root(scope), 'validation-rules', 'list', params] as const,
    detail: (scope: SessionQueryScope, id: string) =>
      [...root(scope), 'validation-rules', 'detail', id] as const,
    options: (scope: SessionQueryScope) =>
      [...root(scope), 'validation-rules', 'options'] as const,
  },
} as const;
