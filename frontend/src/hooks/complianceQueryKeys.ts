import type {
  ComplianceHistoryParams,
  ComplianceJobListParams,
  ComplianceOverviewParams,
  ComplianceReportParams,
  ComplianceResultListParams,
  TranslationGroupListParams,
} from '../types/compliance';
import type { DocumentSessionScope } from './documentQueryKeys';

const root = (scope: DocumentSessionScope) =>
  ['compliance', scope[0], scope[1]] as const;

export const complianceKeys = {
  all: root,
  jobs: (scope: DocumentSessionScope) => [...root(scope), 'jobs'] as const,
  jobLists: (scope: DocumentSessionScope) => [...root(scope), 'jobs', 'list'] as const,
  jobList: (scope: DocumentSessionScope, params: ComplianceJobListParams) =>
    [...root(scope), 'jobs', 'list', params] as const,
  job: (scope: DocumentSessionScope, id: string) =>
    [...root(scope), 'jobs', 'detail', id] as const,
  runs: (scope: DocumentSessionScope) => [...root(scope), 'runs'] as const,
  run: (scope: DocumentSessionScope, id: string) =>
    [...root(scope), 'runs', 'detail', id] as const,
  summary: (scope: DocumentSessionScope, id: string) =>
    [...root(scope), 'runs', id, 'summary'] as const,
  score: (scope: DocumentSessionScope, id: string) =>
    [...root(scope), 'runs', id, 'score'] as const,
  sections: (
    scope: DocumentSessionScope,
    id: string,
    params: ComplianceResultListParams,
  ) => [...root(scope), 'runs', id, 'sections', params] as const,
  groups: (
    scope: DocumentSessionScope,
    id: string,
    params: TranslationGroupListParams,
  ) => [...root(scope), 'runs', id, 'groups', params] as const,
  comparison: (scope: DocumentSessionScope, id: string, otherId: string) =>
    [...root(scope), 'runs', id, 'compare', otherId] as const,
  files: (scope: DocumentSessionScope) => [...root(scope), 'files'] as const,
  latest: (scope: DocumentSessionScope, fileId: string) =>
    [...root(scope), 'files', fileId, 'latest'] as const,
  history: (
    scope: DocumentSessionScope,
    fileId: string,
    params: ComplianceHistoryParams,
  ) => [...root(scope), 'files', fileId, 'history', params] as const,
  overview: (scope: DocumentSessionScope, params: ComplianceOverviewParams) =>
    [...root(scope), 'overview', params] as const,
  report: (scope: DocumentSessionScope, params: ComplianceReportParams) =>
    [...root(scope), 'report', params] as const,
} as const;
