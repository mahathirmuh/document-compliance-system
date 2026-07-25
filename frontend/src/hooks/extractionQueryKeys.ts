import type { ExtractionJobListParams } from '../types/extraction';
import type {
  ExtractionBlockListParams,
  ExtractionContainerListParams,
  ExtractionSearchParams,
  ExtractionTableListParams,
} from '../types/extractedContent';
import type { DocumentSessionScope } from './documentQueryKeys';

const root = (scope: DocumentSessionScope) =>
  ['extractions', scope[0], scope[1]] as const;

export const extractionKeys = {
  all: root,
  jobs: (scope: DocumentSessionScope) => [...root(scope), 'jobs'] as const,
  jobLists: (scope: DocumentSessionScope) => [...root(scope), 'jobs', 'list'] as const,
  jobList: (scope: DocumentSessionScope, params: ExtractionJobListParams) =>
    [...root(scope), 'jobs', 'list', params] as const,
  job: (scope: DocumentSessionScope, jobId: string) =>
    [...root(scope), 'jobs', 'detail', jobId] as const,
  file: (scope: DocumentSessionScope, fileId: string) =>
    [...root(scope), 'files', fileId] as const,
  latest: (scope: DocumentSessionScope, fileId: string) =>
    [...root(scope), 'files', fileId, 'latest'] as const,
  history: (
    scope: DocumentSessionScope,
    fileId: string,
    page: number,
    pageSize: number,
  ) => [...root(scope), 'files', fileId, 'history', page, pageSize] as const,
  runs: (scope: DocumentSessionScope) => [...root(scope), 'runs'] as const,
  run: (scope: DocumentSessionScope, runId: string) =>
    [...root(scope), 'runs', runId] as const,
  containers: (
    scope: DocumentSessionScope,
    runId: string,
    params: ExtractionContainerListParams,
  ) => [...root(scope), 'runs', runId, 'containers', params] as const,
  blocks: (
    scope: DocumentSessionScope,
    runId: string,
    params: ExtractionBlockListParams,
  ) => [...root(scope), 'runs', runId, 'blocks', params] as const,
  tables: (
    scope: DocumentSessionScope,
    runId: string,
    params: ExtractionTableListParams,
  ) => [...root(scope), 'runs', runId, 'tables', params] as const,
  search: (
    scope: DocumentSessionScope,
    runId: string,
    params: ExtractionSearchParams,
  ) => [...root(scope), 'runs', runId, 'search', params] as const,
} as const;
