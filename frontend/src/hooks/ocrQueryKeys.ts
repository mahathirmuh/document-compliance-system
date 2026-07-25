import type {
  OCRBlockListParams,
  OCRHistoryParams,
  OCRJobListParams,
  OCRPageListParams,
} from '../types/ocr';
import type { DocumentSessionScope } from './documentQueryKeys';

const root = (scope: DocumentSessionScope) => ['ocr', scope[0], scope[1]] as const;

export const ocrKeys = {
  all: root,
  jobs: (scope: DocumentSessionScope) => [...root(scope), 'jobs'] as const,
  jobLists: (scope: DocumentSessionScope) => [...root(scope), 'jobs', 'list'] as const,
  jobList: (scope: DocumentSessionScope, params: OCRJobListParams) =>
    [...root(scope), 'jobs', 'list', params] as const,
  job: (scope: DocumentSessionScope, jobId: string) =>
    [...root(scope), 'jobs', 'detail', jobId] as const,
  files: (scope: DocumentSessionScope) => [...root(scope), 'files'] as const,
  file: (scope: DocumentSessionScope, fileId: string) =>
    [...root(scope), 'files', fileId] as const,
  latest: (scope: DocumentSessionScope, fileId: string) =>
    [...root(scope), 'files', fileId, 'latest'] as const,
  history: (scope: DocumentSessionScope, fileId: string, params: OCRHistoryParams) =>
    [...root(scope), 'files', fileId, 'history', params] as const,
  runs: (scope: DocumentSessionScope) => [...root(scope), 'runs'] as const,
  run: (scope: DocumentSessionScope, runId: string) =>
    [...root(scope), 'runs', runId] as const,
  pages: (scope: DocumentSessionScope, runId: string, params: OCRPageListParams) =>
    [...root(scope), 'runs', runId, 'pages', params] as const,
  page: (scope: DocumentSessionScope, runId: string, pageNumber: number) =>
    [...root(scope), 'runs', runId, 'pages', pageNumber] as const,
  blocks: (scope: DocumentSessionScope, runId: string, params: OCRBlockListParams) =>
    [...root(scope), 'runs', runId, 'blocks', params] as const,
} as const;
