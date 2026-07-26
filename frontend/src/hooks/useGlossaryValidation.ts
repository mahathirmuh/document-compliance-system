import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  cancelGlossaryValidation,
  exportGlossaryValidation,
  getFileGlossaryValidation,
  getGlossaryHistory,
  getGlossaryValidationJob,
  getGlossaryValidationRun,
  getGlossaryValidationSummary,
  listGlossaryMatches,
  listGlossaryValidationFindings,
  listGlossaryValidationJobs,
  revalidateGlossary,
  startGlossaryValidation,
} from '../api/glossaryApi';
import type { GlossaryExportFormat } from '../types/glossary';
import type {
  GlossaryHistoryParams,
  GlossaryMatchListParams,
  GlossaryValidationJobListParams,
  GlossaryValidationRequest,
} from '../types/glossaryValidation';
import { isTerminalGlossaryValidationJobStatus } from '../types/glossaryValidation';
import { glossaryKeys } from './useGlossary';
import { useDocumentSession } from './useDocumentSession';

const pollingIntervalMs = 3_000;

const validationKey = (
  scope: readonly [string, number],
  ...parts: readonly unknown[]
) => [...glossaryKeys.validation(scope), ...parts] as const;

export const useGlossaryValidationJob = (jobId: string | null, poll = true) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: validationKey(scope, 'jobs', jobId ?? 'none'),
    queryFn: ({ signal }) => getGlossaryValidationJob(jobId ?? '', signal),
    enabled: jobId !== null,
    refetchInterval: (query) =>
      poll &&
      query.state.data &&
      !isTerminalGlossaryValidationJobStatus(query.state.data.status)
        ? pollingIntervalMs
        : false,
  });
};

export const useGlossaryValidationJobs = (params: GlossaryValidationJobListParams) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: validationKey(scope, 'jobs', 'list', params),
    queryFn: ({ signal }) => listGlossaryValidationJobs(params, signal),
    placeholderData: (previous) => previous,
    refetchInterval: (query) =>
      query.state.data?.items.some(
        (job) => !isTerminalGlossaryValidationJobStatus(job.status),
      )
        ? pollingIntervalMs
        : false,
  });
};

export const useGlossaryValidationRun = (runId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: validationKey(scope, 'runs', runId ?? 'none'),
    queryFn: ({ signal }) => getGlossaryValidationRun(runId ?? '', signal),
    enabled: runId !== null,
  });
};

export const useGlossaryValidationSummary = (runId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: validationKey(scope, 'runs', runId ?? 'none', 'summary'),
    queryFn: ({ signal }) => getGlossaryValidationSummary(runId ?? '', signal),
    enabled: runId !== null,
  });
};

export const useGlossaryMatches = (
  runId: string | null,
  params: GlossaryMatchListParams,
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: validationKey(scope, 'runs', runId ?? 'none', 'matches', params),
    queryFn: ({ signal }) => listGlossaryMatches(runId ?? '', params, signal),
    enabled: runId !== null,
    placeholderData: (previous) => previous,
  });
};

export const useGlossaryValidationFindings = (
  runId: string | null,
  params: { page: number; pageSize: number },
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: validationKey(scope, 'runs', runId ?? 'none', 'findings', params),
    queryFn: ({ signal }) =>
      listGlossaryValidationFindings(runId ?? '', params, signal),
    enabled: runId !== null,
    placeholderData: (previous) => previous,
  });
};

export const useLatestGlossaryValidation = (fileId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: validationKey(scope, 'files', fileId ?? 'none', 'latest'),
    queryFn: ({ signal }) => getFileGlossaryValidation(fileId ?? '', signal),
    enabled: fileId !== null,
  });
};

export const useGlossaryHistory = (
  fileId: string | null,
  params: GlossaryHistoryParams,
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: validationKey(scope, 'files', fileId ?? 'none', 'history', params),
    queryFn: ({ signal }) => getGlossaryHistory(fileId ?? '', params, signal),
    enabled: fileId !== null,
    placeholderData: (previous) => previous,
  });
};

export const useGlossaryValidationMutations = () => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();
  const invalidate = async (): Promise<void> => {
    await queryClient.invalidateQueries({
      queryKey: glossaryKeys.validation(scope),
    });
  };
  return {
    start: useMutation({
      mutationFn: (payload: GlossaryValidationRequest) =>
        startGlossaryValidation(payload),
      onSuccess: invalidate,
    }),
    cancel: useMutation({
      mutationFn: cancelGlossaryValidation,
      onSuccess: invalidate,
    }),
    revalidate: useMutation({
      mutationFn: ({ reason, runId }: { runId: string; reason: string }) =>
        revalidateGlossary(runId, { reason }),
      onSuccess: invalidate,
    }),
    export: useMutation({
      mutationFn: ({
        format,
        runId,
      }: {
        runId: string;
        format: GlossaryExportFormat;
      }) => exportGlossaryValidation(runId, format),
    }),
  } as const;
};
