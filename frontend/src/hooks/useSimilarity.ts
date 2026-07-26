import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  exportSimilarity,
  getFileSimilarity,
  getSimilarityHistory,
  getSimilarityRun,
  getSimilaritySummary,
  listSectionSimilarity,
  listSimilarityResults,
  rerunSimilarity,
  startSimilarity,
} from '../api/similarityApi';
import type {
  SimilarityExportFormat,
  SimilarityHistoryParams,
  SimilarityRerunRequest,
  SimilarityResultListParams,
  SimilarityStartRequest,
} from '../types/similarity';
import { documentFileKeys } from './documentFileQueryKeys';
import { documentKeys } from './documentQueryKeys';
import { useDocumentSession } from './useDocumentSession';

export const similarityKeys = {
  root: (scope: readonly [string, number]) =>
    ['similarity', scope[0], scope[1]] as const,
  jobs: (scope: readonly [string, number]) =>
    [...similarityKeys.root(scope), 'jobs'] as const,
  jobList: (scope: readonly [string, number], params: object) =>
    [...similarityKeys.jobs(scope), 'list', params] as const,
  job: (scope: readonly [string, number], jobId: string) =>
    [...similarityKeys.jobs(scope), 'detail', jobId] as const,
  runs: (scope: readonly [string, number]) =>
    [...similarityKeys.root(scope), 'runs'] as const,
  run: (scope: readonly [string, number], runId: string) =>
    [...similarityKeys.runs(scope), 'detail', runId] as const,
  summary: (scope: readonly [string, number], runId: string) =>
    [...similarityKeys.runs(scope), runId, 'summary'] as const,
  results: (
    scope: readonly [string, number],
    runId: string,
    params: SimilarityResultListParams,
  ) => [...similarityKeys.runs(scope), runId, 'results', params] as const,
  sections: (scope: readonly [string, number], runId: string) =>
    [...similarityKeys.runs(scope), runId, 'sections'] as const,
  latest: (scope: readonly [string, number], fileId: string) =>
    [...similarityKeys.root(scope), 'files', fileId, 'latest'] as const,
  history: (
    scope: readonly [string, number],
    fileId: string,
    params: SimilarityHistoryParams,
  ) => [...similarityKeys.root(scope), 'files', fileId, 'history', params] as const,
} as const;

export const useSimilarity = (runId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: similarityKeys.run(scope, runId ?? 'none'),
    queryFn: ({ signal }) => getSimilarityRun(runId ?? '', signal),
    enabled: runId !== null,
  });
};

export const useSimilaritySummary = (runId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: similarityKeys.summary(scope, runId ?? 'none'),
    queryFn: ({ signal }) => getSimilaritySummary(runId ?? '', signal),
    enabled: runId !== null,
  });
};

export const useSimilarityResults = (
  runId: string | null,
  params: SimilarityResultListParams,
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: similarityKeys.results(scope, runId ?? 'none', params),
    queryFn: ({ signal }) => listSimilarityResults(runId ?? '', params, signal),
    enabled: runId !== null,
    placeholderData: (previous) => previous,
  });
};

export const useSectionSimilarity = (runId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: similarityKeys.sections(scope, runId ?? 'none'),
    queryFn: ({ signal }) => listSectionSimilarity(runId ?? '', signal),
    enabled: runId !== null,
  });
};

export const useLatestSimilarity = (fileId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: similarityKeys.latest(scope, fileId ?? 'none'),
    queryFn: ({ signal }) => getFileSimilarity(fileId ?? '', signal),
    enabled: fileId !== null,
  });
};

export const useSimilarityHistory = (
  fileId: string | null,
  params: SimilarityHistoryParams,
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: similarityKeys.history(scope, fileId ?? 'none', params),
    queryFn: ({ signal }) => getSimilarityHistory(fileId ?? '', params, signal),
    enabled: fileId !== null,
    placeholderData: (previous) => previous,
  });
};

export const useSimilarityMutations = () => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();
  const invalidate = async (): Promise<void> => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: similarityKeys.root(scope) }),
      queryClient.invalidateQueries({ queryKey: documentFileKeys.all(scope) }),
      queryClient.invalidateQueries({ queryKey: documentKeys.all(scope) }),
    ]);
  };

  return {
    start: useMutation({
      mutationFn: (payload: SimilarityStartRequest) => startSimilarity(payload),
      onSuccess: invalidate,
    }),
    rerun: useMutation({
      mutationFn: ({
        payload,
        runId,
      }: {
        runId: string;
        payload: SimilarityRerunRequest;
      }) => rerunSimilarity(runId, payload),
      onSuccess: invalidate,
    }),
    export: useMutation({
      mutationFn: ({
        format,
        runId,
      }: {
        runId: string;
        format: SimilarityExportFormat;
      }) => exportSimilarity(runId, format),
    }),
  } as const;
};
