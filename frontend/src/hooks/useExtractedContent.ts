import { useMutation, useQuery } from '@tanstack/react-query';

import {
  exportExtractedContent,
  getExtractionRun,
  getLatestExtraction,
  listExtractionBlocks,
  listExtractionContainers,
  listExtractionTables,
  searchExtractedContent,
} from '../api/extractionApi';
import type {
  ExtractionBlockListParams,
  ExtractionContainerListParams,
  ExtractionSearchParams,
  ExtractionTableListParams,
} from '../types/extractedContent';
import { extractionKeys } from './extractionQueryKeys';
import { useDocumentSession } from './useDocumentSession';

export const useLatestExtraction = (fileId: string | null, enabled = true) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: extractionKeys.latest(scope, fileId ?? 'none'),
    queryFn: ({ signal }) => getLatestExtraction(fileId ?? '', signal),
    enabled: enabled && fileId !== null,
  });
};

export const useExtractionRun = (runId: string | null, enabled = true) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: extractionKeys.run(scope, runId ?? 'none'),
    queryFn: ({ signal }) => getExtractionRun(runId ?? '', signal),
    enabled: enabled && runId !== null,
  });
};

export const useExtractionContainers = (
  runId: string | null,
  params: ExtractionContainerListParams,
  enabled = true,
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: extractionKeys.containers(scope, runId ?? 'none', params),
    queryFn: ({ signal }) => listExtractionContainers(runId ?? '', params, signal),
    enabled: enabled && runId !== null,
    placeholderData: (previous) => previous,
  });
};

export const useExtractionBlocks = (
  runId: string | null,
  params: ExtractionBlockListParams,
  enabled = true,
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: extractionKeys.blocks(scope, runId ?? 'none', params),
    queryFn: ({ signal }) => listExtractionBlocks(runId ?? '', params, signal),
    enabled: enabled && runId !== null,
    placeholderData: (previous) => previous,
  });
};

export const useExtractionTables = (
  runId: string | null,
  params: ExtractionTableListParams,
  enabled = true,
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: extractionKeys.tables(scope, runId ?? 'none', params),
    queryFn: ({ signal }) => listExtractionTables(runId ?? '', params, signal),
    enabled: enabled && runId !== null,
    placeholderData: (previous) => previous,
  });
};

export const useExtractedContentSearch = (
  runId: string | null,
  params: ExtractionSearchParams,
  enabled = true,
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: extractionKeys.search(scope, runId ?? 'none', params),
    queryFn: ({ signal }) => searchExtractedContent(runId ?? '', params, signal),
    enabled:
      enabled &&
      runId !== null &&
      params.q.trim().length >= 2 &&
      params.q.trim().length <= 200,
    placeholderData: (previous) => previous,
  });
};

export const useExtractionExport = () =>
  useMutation({
    mutationFn: ({ format, runId }: { runId: string; format: 'json' | 'txt' }) =>
      exportExtractedContent(runId, format),
  });
