import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';

import {
  cancelOCR,
  exportOCR,
  getLatestOCR,
  getOCRJob,
  getOCRPage,
  getOCRRun,
  listOCRBlocks,
  listOCRPages,
  reOCR,
  startOCR,
} from '../api/ocrApi';
import type {
  OCRBlockListParams,
  OCRPageListParams,
  OCRReprocessRequest,
  OCRStartRequest,
} from '../types/ocr';
import { isTerminalOCRStatus } from '../types/ocr';
import { documentFileKeys } from './documentFileQueryKeys';
import { documentKeys } from './documentQueryKeys';
import { languageDetectionKeys } from './languageDetectionQueryKeys';
import { ocrKeys } from './ocrQueryKeys';
import { useDocumentSession } from './useDocumentSession';

const pollIntervalMs = 3_000;

export const useOCRJob = (
  jobId: string | null,
  options: { enabled?: boolean; poll?: boolean } = {},
) => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();
  const invalidatedTerminal = useRef<string | null>(null);
  const query = useQuery({
    queryKey: ocrKeys.job(scope, jobId ?? 'none'),
    queryFn: ({ signal }) => getOCRJob(jobId ?? '', signal),
    enabled: (options.enabled ?? true) && jobId !== null,
    refetchInterval: (state) => {
      if (!options.poll || !state.state.data) {
        return false;
      }
      return isTerminalOCRStatus(state.state.data.status) ? false : pollIntervalMs;
    },
  });

  useEffect(() => {
    const status = query.data?.status;
    if (
      !jobId ||
      !status ||
      !isTerminalOCRStatus(status) ||
      invalidatedTerminal.current === `${jobId}:${status}`
    ) {
      return;
    }
    invalidatedTerminal.current = `${jobId}:${status}`;
    void Promise.all([
      queryClient.invalidateQueries({ queryKey: ocrKeys.jobLists(scope) }),
      queryClient.invalidateQueries({ queryKey: ocrKeys.runs(scope) }),
      queryClient.invalidateQueries({ queryKey: ocrKeys.files(scope) }),
      queryClient.invalidateQueries({ queryKey: languageDetectionKeys.all(scope) }),
      queryClient.invalidateQueries({ queryKey: documentFileKeys.all(scope) }),
      queryClient.invalidateQueries({ queryKey: documentKeys.all(scope) }),
    ]);
  }, [jobId, query.data?.status, queryClient, scope]);

  return query;
};

export const useLatestOCR = (fileId: string | null, enabled = true) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: ocrKeys.latest(scope, fileId ?? 'none'),
    queryFn: ({ signal }) => getLatestOCR(fileId ?? '', signal),
    enabled: enabled && fileId !== null,
  });
};

export const useOCRRun = (runId: string | null, enabled = true) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: ocrKeys.run(scope, runId ?? 'none'),
    queryFn: ({ signal }) => getOCRRun(runId ?? '', signal),
    enabled: enabled && runId !== null,
  });
};

export const useOCRPages = (
  runId: string | null,
  params: OCRPageListParams,
  enabled = true,
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: ocrKeys.pages(scope, runId ?? 'none', params),
    queryFn: ({ signal }) => listOCRPages(runId ?? '', params, signal),
    enabled: enabled && runId !== null,
    placeholderData: (previous) => previous,
  });
};

export const useOCRPage = (
  runId: string | null,
  pageNumber: number | null,
  enabled = true,
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: ocrKeys.page(scope, runId ?? 'none', pageNumber ?? 0),
    queryFn: ({ signal }) => getOCRPage(runId ?? '', pageNumber ?? 0, signal),
    enabled: enabled && runId !== null && pageNumber !== null,
  });
};

export const useOCRBlocks = (
  runId: string | null,
  params: OCRBlockListParams,
  enabled = true,
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: ocrKeys.blocks(scope, runId ?? 'none', params),
    queryFn: ({ signal }) => listOCRBlocks(runId ?? '', params, signal),
    enabled: enabled && runId !== null,
    placeholderData: (previous) => previous,
  });
};

export const useOCRMutations = () => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();
  const invalidate = async (): Promise<void> => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ocrKeys.all(scope) }),
      queryClient.invalidateQueries({ queryKey: languageDetectionKeys.all(scope) }),
      queryClient.invalidateQueries({ queryKey: documentFileKeys.all(scope) }),
      queryClient.invalidateQueries({ queryKey: documentKeys.all(scope) }),
    ]);
  };

  return {
    start: useMutation({
      mutationFn: (payload: OCRStartRequest) => startOCR(payload),
      onSuccess: invalidate,
    }),
    cancel: useMutation({
      mutationFn: cancelOCR,
      onSuccess: invalidate,
    }),
    reocr: useMutation({
      mutationFn: ({
        payload,
        runId,
      }: {
        runId: string;
        payload: OCRReprocessRequest;
      }) => reOCR(runId, payload),
      onSuccess: invalidate,
    }),
    export: useMutation({
      mutationFn: ({ format, runId }: { runId: string; format: 'json' | 'txt' }) =>
        exportOCR(runId, format),
    }),
  } as const;
};
