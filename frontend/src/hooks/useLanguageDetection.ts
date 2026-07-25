import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';

import {
  cancelLanguageDetection,
  exportLanguageResults,
  getLanguageDetectionJob,
  redetectLanguage,
  startLanguageDetection,
} from '../api/languageDetectionApi';
import type {
  LanguageDetectionStartRequest,
  LanguageRedetectRequest,
} from '../types/languageDetection';
import { isTerminalLanguageDetectionStatus } from '../types/languageDetection';
import { documentFileKeys } from './documentFileQueryKeys';
import { documentKeys } from './documentQueryKeys';
import { languageDetectionKeys } from './languageDetectionQueryKeys';
import { useDocumentSession } from './useDocumentSession';

const pollIntervalMs = 3_000;

export const useLanguageDetectionJob = (
  jobId: string | null,
  options: { enabled?: boolean; poll?: boolean } = {},
) => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();
  const invalidatedTerminal = useRef<string | null>(null);
  const query = useQuery({
    queryKey: languageDetectionKeys.job(scope, jobId ?? 'none'),
    queryFn: ({ signal }) => getLanguageDetectionJob(jobId ?? '', signal),
    enabled: (options.enabled ?? true) && jobId !== null,
    refetchInterval: (state) => {
      if (!options.poll || !state.state.data) {
        return false;
      }
      return isTerminalLanguageDetectionStatus(state.state.data.status)
        ? false
        : pollIntervalMs;
    },
  });

  useEffect(() => {
    const status = query.data?.status;
    if (
      !jobId ||
      !status ||
      !isTerminalLanguageDetectionStatus(status) ||
      invalidatedTerminal.current === `${jobId}:${status}`
    ) {
      return;
    }
    invalidatedTerminal.current = `${jobId}:${status}`;
    void Promise.all([
      queryClient.invalidateQueries({
        queryKey: languageDetectionKeys.jobLists(scope),
      }),
      queryClient.invalidateQueries({ queryKey: languageDetectionKeys.runs(scope) }),
      queryClient.invalidateQueries({ queryKey: languageDetectionKeys.files(scope) }),
      queryClient.invalidateQueries({ queryKey: documentFileKeys.all(scope) }),
      queryClient.invalidateQueries({ queryKey: documentKeys.all(scope) }),
    ]);
  }, [jobId, query.data?.status, queryClient, scope]);

  return query;
};

export const useLanguageDetectionMutations = () => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();
  const invalidate = async (): Promise<void> => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: languageDetectionKeys.all(scope) }),
      queryClient.invalidateQueries({ queryKey: documentFileKeys.all(scope) }),
      queryClient.invalidateQueries({ queryKey: documentKeys.all(scope) }),
    ]);
  };

  return {
    start: useMutation({
      mutationFn: (payload: LanguageDetectionStartRequest) =>
        startLanguageDetection(payload),
      onSuccess: invalidate,
    }),
    cancel: useMutation({
      mutationFn: cancelLanguageDetection,
      onSuccess: invalidate,
    }),
    redetect: useMutation({
      mutationFn: ({
        payload,
        runId,
      }: {
        runId: string;
        payload: LanguageRedetectRequest;
      }) => redetectLanguage(runId, payload),
      onSuccess: invalidate,
    }),
    export: useMutation({
      mutationFn: ({ format, runId }: { runId: string; format: 'json' | 'xlsx' }) =>
        exportLanguageResults(runId, format),
    }),
  } as const;
};
