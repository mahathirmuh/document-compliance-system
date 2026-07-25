import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';

import { listLanguageDetectionJobs } from '../api/languageDetectionApi';
import type { LanguageDetectionJobListParams } from '../types/languageDetection';
import {
  isActiveLanguageDetectionStatus,
  isTerminalLanguageDetectionStatus,
} from '../types/languageDetection';
import { documentFileKeys } from './documentFileQueryKeys';
import { documentKeys } from './documentQueryKeys';
import { languageDetectionKeys } from './languageDetectionQueryKeys';
import { useDocumentSession } from './useDocumentSession';

const pollIntervalMs = 3_000;

export const useLanguageDetectionJobs = (
  params: LanguageDetectionJobListParams,
  options: { enabled?: boolean; pollActive?: boolean } = {},
) => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();
  const previousActiveJobs = useRef(new Map<string, string>());
  const invalidatedJobs = useRef(new Set<string>());
  const query = useQuery({
    queryKey: languageDetectionKeys.jobList(scope, params),
    queryFn: ({ signal }) => listLanguageDetectionJobs(params, signal),
    enabled: options.enabled ?? true,
    placeholderData: (previous) => previous,
    refetchInterval: (state) =>
      options.pollActive &&
      state.state.data?.items.some((job) => isActiveLanguageDetectionStatus(job.status))
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
        .filter((job) => isActiveLanguageDetectionStatus(job.status))
        .map((job) => [job.id, job.file.id]),
    );
    const resolvedFiles = new Set<string>();
    active.forEach((_fileId, jobId) => invalidatedJobs.current.delete(jobId));
    previousActiveJobs.current.forEach((fileId, jobId) => {
      const current = jobsById.get(jobId);
      if (
        (current === undefined || isTerminalLanguageDetectionStatus(current.status)) &&
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
      queryClient.invalidateQueries({ queryKey: languageDetectionKeys.runs(scope) }),
      queryClient.invalidateQueries({ queryKey: languageDetectionKeys.files(scope) }),
      queryClient.invalidateQueries({ queryKey: documentFileKeys.all(scope) }),
      queryClient.invalidateQueries({ queryKey: documentKeys.all(scope) }),
    ]);
  }, [query.data, queryClient, scope]);

  return query;
};
