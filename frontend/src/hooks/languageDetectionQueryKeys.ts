import type {
  LanguageBlockListParams,
  LanguageContainerListParams,
  LanguageDetectionDocumentListParams,
  LanguageDetectionJobListParams,
  LanguageHistoryParams,
} from '../types/languageDetection';
import type { DocumentSessionScope } from './documentQueryKeys';

const root = (scope: DocumentSessionScope) =>
  ['language-detection', scope[0], scope[1]] as const;

export const languageDetectionKeys = {
  all: root,
  documents: (scope: DocumentSessionScope) => [...root(scope), 'documents'] as const,
  documentList: (
    scope: DocumentSessionScope,
    params: LanguageDetectionDocumentListParams,
  ) => [...root(scope), 'documents', 'list', params] as const,
  jobs: (scope: DocumentSessionScope) => [...root(scope), 'jobs'] as const,
  jobLists: (scope: DocumentSessionScope) => [...root(scope), 'jobs', 'list'] as const,
  jobList: (scope: DocumentSessionScope, params: LanguageDetectionJobListParams) =>
    [...root(scope), 'jobs', 'list', params] as const,
  job: (scope: DocumentSessionScope, jobId: string) =>
    [...root(scope), 'jobs', 'detail', jobId] as const,
  files: (scope: DocumentSessionScope) => [...root(scope), 'files'] as const,
  file: (scope: DocumentSessionScope, fileId: string) =>
    [...root(scope), 'files', fileId] as const,
  latest: (scope: DocumentSessionScope, fileId: string) =>
    [...root(scope), 'files', fileId, 'latest'] as const,
  history: (
    scope: DocumentSessionScope,
    fileId: string,
    params: LanguageHistoryParams,
  ) => [...root(scope), 'files', fileId, 'history', params] as const,
  runs: (scope: DocumentSessionScope) => [...root(scope), 'runs'] as const,
  run: (scope: DocumentSessionScope, runId: string) =>
    [...root(scope), 'runs', runId] as const,
  summary: (scope: DocumentSessionScope, runId: string) =>
    [...root(scope), 'runs', runId, 'summary'] as const,
  blocks: (
    scope: DocumentSessionScope,
    runId: string,
    params: LanguageBlockListParams,
  ) => [...root(scope), 'runs', runId, 'blocks', params] as const,
  containers: (
    scope: DocumentSessionScope,
    runId: string,
    params: LanguageContainerListParams,
  ) => [...root(scope), 'runs', runId, 'containers', params] as const,
} as const;
