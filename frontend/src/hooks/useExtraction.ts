import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';

import {
  cancelExtraction,
  getExtractionJob,
  reextractDocumentFile,
  startExtraction,
} from '../api/extractionApi';
import type { ExtractionRequest, ReExtractionRequest } from '../types/extraction';
import { isTerminalExtractionStatus } from '../types/extraction';
import { documentFileKeys } from './documentFileQueryKeys';
import { documentKeys } from './documentQueryKeys';
import { extractionKeys } from './extractionQueryKeys';
import { useDocumentSession } from './useDocumentSession';

const pollIntervalMs = 3_000;

interface ReExtractionVariables {
  fileId: string;
  payload: ReExtractionRequest;
}

export const useExtractionJob = (
  jobId: string | null,
  options: { poll?: boolean; enabled?: boolean } = {},
) => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();
  const invalidatedTerminal = useRef<string | null>(null);
  const query = useQuery({
    queryKey: extractionKeys.job(scope, jobId ?? 'none'),
    queryFn: ({ signal }) => getExtractionJob(jobId ?? '', signal),
    enabled: (options.enabled ?? true) && jobId !== null,
    refetchInterval: (state) => {
      if (!options.poll || !state.state.data) {
        return false;
      }
      return isTerminalExtractionStatus(state.state.data.status)
        ? false
        : pollIntervalMs;
    },
  });

  useEffect(() => {
    const status = query.data?.status;
    if (
      !jobId ||
      !status ||
      !isTerminalExtractionStatus(status) ||
      invalidatedTerminal.current === `${jobId}:${status}`
    ) {
      return;
    }
    invalidatedTerminal.current = `${jobId}:${status}`;
    void Promise.all([
      queryClient.invalidateQueries({ queryKey: extractionKeys.jobLists(scope) }),
      queryClient.invalidateQueries({ queryKey: extractionKeys.runs(scope) }),
      queryClient.invalidateQueries({ queryKey: documentFileKeys.all(scope) }),
      queryClient.invalidateQueries({ queryKey: documentKeys.all(scope) }),
    ]);
  }, [jobId, query.data?.status, queryClient, scope]);

  return query;
};

export const useExtractionMutations = () => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();

  const invalidate = async (): Promise<void> => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: extractionKeys.all(scope) }),
      queryClient.invalidateQueries({ queryKey: documentFileKeys.all(scope) }),
      queryClient.invalidateQueries({ queryKey: documentKeys.all(scope) }),
    ]);
  };

  return {
    start: useMutation({
      mutationFn: (payload: ExtractionRequest) => startExtraction(payload),
      onSuccess: invalidate,
    }),
    reextract: useMutation({
      mutationFn: ({ fileId, payload }: ReExtractionVariables) =>
        reextractDocumentFile(fileId, payload),
      onSuccess: invalidate,
    }),
    cancel: useMutation({
      mutationFn: cancelExtraction,
      onSuccess: invalidate,
    }),
  } as const;
};
