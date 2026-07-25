import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';

import { listOCRJobs } from '../api/ocrApi';
import type { OCRJobListParams } from '../types/ocr';
import { isActiveOCRStatus, isTerminalOCRStatus } from '../types/ocr';
import { documentFileKeys } from './documentFileQueryKeys';
import { documentKeys } from './documentQueryKeys';
import { languageDetectionKeys } from './languageDetectionQueryKeys';
import { ocrKeys } from './ocrQueryKeys';
import { useDocumentSession } from './useDocumentSession';

const pollIntervalMs = 3_000;

export const useOCRJobs = (
  params: OCRJobListParams,
  options: { enabled?: boolean; pollActive?: boolean } = {},
) => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();
  const previousActiveJobs = useRef(new Map<string, string>());
  const invalidatedJobs = useRef(new Set<string>());
  const query = useQuery({
    queryKey: ocrKeys.jobList(scope, params),
    queryFn: ({ signal }) => listOCRJobs(params, signal),
    enabled: options.enabled ?? true,
    placeholderData: (previous) => previous,
    refetchInterval: (state) =>
      options.pollActive &&
      state.state.data?.items.some((job) => isActiveOCRStatus(job.status))
        ? pollIntervalMs
        : false,
  });

  useEffect(() => {
    if (!query.data) {
      return;
    }
    const jobsById = new Map(query.data.items.map((job) => [job.id, job]));
    const active = new Map(
      query.data.items
        .filter((job) => isActiveOCRStatus(job.status))
        .map((job) => [job.id, job.file.id]),
    );
    const resolvedFiles = new Set<string>();
    active.forEach((_fileId, jobId) => invalidatedJobs.current.delete(jobId));
    previousActiveJobs.current.forEach((fileId, jobId) => {
      const current = jobsById.get(jobId);
      if (
        (current === undefined || isTerminalOCRStatus(current.status)) &&
        !invalidatedJobs.current.has(jobId)
      ) {
        invalidatedJobs.current.add(jobId);
        resolvedFiles.add(fileId);
      }
    });
    previousActiveJobs.current = active;

    if (resolvedFiles.size === 0) {
      return;
    }
    void Promise.all([
      queryClient.invalidateQueries({ queryKey: ocrKeys.runs(scope) }),
      queryClient.invalidateQueries({ queryKey: ocrKeys.files(scope) }),
      queryClient.invalidateQueries({ queryKey: languageDetectionKeys.all(scope) }),
      queryClient.invalidateQueries({ queryKey: documentFileKeys.all(scope) }),
      queryClient.invalidateQueries({ queryKey: documentKeys.all(scope) }),
    ]);
  }, [query.data, queryClient, scope]);

  return query;
};
