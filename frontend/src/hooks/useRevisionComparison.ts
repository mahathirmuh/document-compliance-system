import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  cancelRevisionComparison,
  exportRevisionComparison,
  getRevisionComparison,
  getRevisionComparisonJob,
  getRevisionComparisonSummary,
  getRevisionFindingChanges,
  getRevisionLanguageChanges,
  getRevisionSectionChanges,
  listDocumentRevisionComparisons,
  listRevisionChanges,
  listRevisionComparisonJobs,
  startRevisionComparison,
} from '../api/revisionComparisonApi';
import type {
  RevisionChangeListParams,
  RevisionComparisonExportFormat,
  RevisionComparisonJobListParams,
  RevisionComparisonRequest,
} from '../types/revisionComparison';
import { isTerminalRevisionComparisonJobStatus } from '../types/revisionComparison';
import { useDocumentSession } from './useDocumentSession';

const pollingIntervalMs = 3_000;

export const revisionComparisonKeys = {
  root: (scope: readonly [string, number]) =>
    ['revision-comparison', scope[0], scope[1]] as const,
  jobs: (scope: readonly [string, number], params: object) =>
    [...revisionComparisonKeys.root(scope), 'jobs', params] as const,
  job: (scope: readonly [string, number], jobId: string) =>
    [...revisionComparisonKeys.root(scope), 'jobs', jobId] as const,
  comparison: (scope: readonly [string, number], comparisonId: string) =>
    [...revisionComparisonKeys.root(scope), 'comparison', comparisonId] as const,
  resource: (
    scope: readonly [string, number],
    comparisonId: string,
    resource: string,
    params?: object,
  ) =>
    [
      ...revisionComparisonKeys.comparison(scope, comparisonId),
      resource,
      ...(params ? [params] : []),
    ] as const,
  documentHistory: (scope: readonly [string, number], documentId: string) =>
    [...revisionComparisonKeys.root(scope), 'documents', documentId] as const,
} as const;

export const useRevisionComparisonJob = (jobId: string | null, poll = true) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: revisionComparisonKeys.job(scope, jobId ?? 'none'),
    queryFn: ({ signal }) => getRevisionComparisonJob(jobId ?? '', signal),
    enabled: jobId !== null,
    refetchInterval: (query) =>
      poll &&
      query.state.data &&
      !isTerminalRevisionComparisonJobStatus(query.state.data.status)
        ? pollingIntervalMs
        : false,
  });
};

export const useRevisionComparisonJobs = (params: RevisionComparisonJobListParams) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: revisionComparisonKeys.jobs(scope, params),
    queryFn: ({ signal }) => listRevisionComparisonJobs(params, signal),
    placeholderData: (previous) => previous,
    refetchInterval: (query) =>
      query.state.data?.items.some(
        (job) => !isTerminalRevisionComparisonJobStatus(job.status),
      )
        ? pollingIntervalMs
        : false,
  });
};

export const useRevisionComparison = (comparisonId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: revisionComparisonKeys.comparison(scope, comparisonId ?? 'none'),
    queryFn: ({ signal }) => getRevisionComparison(comparisonId ?? '', signal),
    enabled: comparisonId !== null,
  });
};

export const useRevisionComparisonSummary = (comparisonId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: revisionComparisonKeys.resource(scope, comparisonId ?? 'none', 'summary'),
    queryFn: ({ signal }) => getRevisionComparisonSummary(comparisonId ?? '', signal),
    enabled: comparisonId !== null,
  });
};

export const useRevisionChanges = (
  comparisonId: string | null,
  params: RevisionChangeListParams,
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: revisionComparisonKeys.resource(
      scope,
      comparisonId ?? 'none',
      'changes',
      params,
    ),
    queryFn: ({ signal }) => listRevisionChanges(comparisonId ?? '', params, signal),
    enabled: comparisonId !== null,
    placeholderData: (previous) => previous,
  });
};

export const useRevisionSectionChanges = (comparisonId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: revisionComparisonKeys.resource(
      scope,
      comparisonId ?? 'none',
      'sections',
    ),
    queryFn: ({ signal }) => getRevisionSectionChanges(comparisonId ?? '', signal),
    enabled: comparisonId !== null,
  });
};

export const useRevisionLanguageChanges = (comparisonId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: revisionComparisonKeys.resource(
      scope,
      comparisonId ?? 'none',
      'languages',
    ),
    queryFn: ({ signal }) => getRevisionLanguageChanges(comparisonId ?? '', signal),
    enabled: comparisonId !== null,
  });
};

export const useRevisionFindingChanges = (comparisonId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: revisionComparisonKeys.resource(
      scope,
      comparisonId ?? 'none',
      'findings',
    ),
    queryFn: ({ signal }) => getRevisionFindingChanges(comparisonId ?? '', signal),
    enabled: comparisonId !== null,
  });
};

export const useDocumentRevisionComparisonHistory = (documentId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: revisionComparisonKeys.documentHistory(scope, documentId ?? 'none'),
    queryFn: ({ signal }) =>
      listDocumentRevisionComparisons(
        documentId ?? '',
        { page: 1, pageSize: 20 },
        signal,
      ),
    enabled: documentId !== null,
  });
};

export const useRevisionComparisonMutations = () => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();
  const invalidate = async (): Promise<void> => {
    await queryClient.invalidateQueries({
      queryKey: revisionComparisonKeys.root(scope),
    });
  };
  return {
    start: useMutation({
      mutationFn: (payload: RevisionComparisonRequest) =>
        startRevisionComparison(payload),
      onSuccess: invalidate,
    }),
    cancel: useMutation({
      mutationFn: cancelRevisionComparison,
      onSuccess: invalidate,
    }),
    export: useMutation({
      mutationFn: ({
        comparisonId,
        format,
      }: {
        comparisonId: string;
        format: RevisionComparisonExportFormat;
      }) => exportRevisionComparison(comparisonId, format),
    }),
  } as const;
};
