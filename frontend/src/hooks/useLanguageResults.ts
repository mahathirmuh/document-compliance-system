import { useQuery } from '@tanstack/react-query';

import {
  getLanguageDetectionHistory,
  getLanguageDetectionRun,
  getLanguageSummary,
  getLatestLanguageDetection,
  listLanguageBlocks,
  listLanguageContainers,
} from '../api/languageDetectionApi';
import type {
  LanguageBlockListParams,
  LanguageContainerListParams,
  LanguageHistoryParams,
} from '../types/languageDetection';
import { languageDetectionKeys } from './languageDetectionQueryKeys';
import { useDocumentSession } from './useDocumentSession';

export const useLatestLanguageDetection = (fileId: string | null, enabled = true) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: languageDetectionKeys.latest(scope, fileId ?? 'none'),
    queryFn: ({ signal }) => getLatestLanguageDetection(fileId ?? '', signal),
    enabled: enabled && fileId !== null,
  });
};

export const useLanguageDetectionRun = (runId: string | null, enabled = true) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: languageDetectionKeys.run(scope, runId ?? 'none'),
    queryFn: ({ signal }) => getLanguageDetectionRun(runId ?? '', signal),
    enabled: enabled && runId !== null,
  });
};

export const useLanguageSummary = (runId: string | null, enabled = true) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: languageDetectionKeys.summary(scope, runId ?? 'none'),
    queryFn: ({ signal }) => getLanguageSummary(runId ?? '', signal),
    enabled: enabled && runId !== null,
  });
};

export const useLanguageBlocks = (
  runId: string | null,
  params: LanguageBlockListParams,
  enabled = true,
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: languageDetectionKeys.blocks(scope, runId ?? 'none', params),
    queryFn: ({ signal }) => listLanguageBlocks(runId ?? '', params, signal),
    enabled: enabled && runId !== null,
    placeholderData: (previous) => previous,
  });
};

export const useLanguageContainers = (
  runId: string | null,
  params: LanguageContainerListParams,
  enabled = true,
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: languageDetectionKeys.containers(scope, runId ?? 'none', params),
    queryFn: ({ signal }) => listLanguageContainers(runId ?? '', params, signal),
    enabled: enabled && runId !== null,
    placeholderData: (previous) => previous,
  });
};

export const useLanguageDetectionHistory = (
  fileId: string | null,
  params: LanguageHistoryParams,
  enabled = true,
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: languageDetectionKeys.history(scope, fileId ?? 'none', params),
    queryFn: ({ signal }) => getLanguageDetectionHistory(fileId ?? '', params, signal),
    enabled: enabled && fileId !== null,
    placeholderData: (previous) => previous,
  });
};
