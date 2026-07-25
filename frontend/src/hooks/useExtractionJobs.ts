import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';

import { listExtractionJobs } from '../api/extractionApi';
import type { ExtractionJobListParams } from '../types/extraction';
import {
  isActiveExtractionStatus,
  isTerminalExtractionStatus,
} from '../types/extraction';
import { documentFileKeys } from './documentFileQueryKeys';
import { documentKeys } from './documentQueryKeys';
import { extractionKeys } from './extractionQueryKeys';
import { useDocumentSession } from './useDocumentSession';

const pollIntervalMs = 3_000;

export const useExtractionJobs = (
  params: ExtractionJobListParams,
  options: { enabled?: boolean; pollActive?: boolean } = {},
) => {
  const scope = useDocumentSession();
  const sessionUserId = scope[0];
  const sessionGeneration = scope[1];
  const queryClient = useQueryClient();
  const previousActiveJobs = useRef(new Map<string, string>());
  const invalidatedJobs = useRef(new Set<string>());
  const trackedSession = useRef(`${sessionUserId}:${sessionGeneration}`);
  const query = useQuery({
    queryKey: extractionKeys.jobList(scope, params),
    queryFn: ({ signal }) => listExtractionJobs(params, signal),
    enabled: options.enabled ?? true,
    placeholderData: (previous) => previous,
    refetchInterval: (query) => {
      if (!options.pollActive) {
        return false;
      }
      return query.state.data?.items.some((job) => isActiveExtractionStatus(job.status))
        ? pollIntervalMs
        : false;
    },
  });

  useEffect(() => {
    const sessionKey = `${sessionUserId}:${sessionGeneration}`;
    if (trackedSession.current !== sessionKey) {
      trackedSession.current = sessionKey;
      previousActiveJobs.current.clear();
      invalidatedJobs.current.clear();
    }

    if (!query.data) {
      return;
    }

    const jobsById = new Map(query.data.items.map((job) => [job.id, job]));
    const currentActiveJobs = new Map(
      query.data.items
        .filter((job) => isActiveExtractionStatus(job.status))
        .map((job) => [job.id, job.file.id]),
    );
    const resolvedFileIds = new Set<string>();

    currentActiveJobs.forEach((_fileId, jobId) => {
      invalidatedJobs.current.delete(jobId);
    });
    previousActiveJobs.current.forEach((fileId, jobId) => {
      const currentJob = jobsById.get(jobId);
      const resolved =
        currentJob === undefined || isTerminalExtractionStatus(currentJob.status);
      if (resolved && !invalidatedJobs.current.has(jobId)) {
        invalidatedJobs.current.add(jobId);
        resolvedFileIds.add(fileId);
      }
    });
    previousActiveJobs.current = currentActiveJobs;

    if (resolvedFileIds.size === 0) {
      return;
    }

    const invalidationScope = [sessionUserId, sessionGeneration] as const;
    void Promise.all([
      queryClient.invalidateQueries({
        queryKey: extractionKeys.runs(invalidationScope),
      }),
      ...[...resolvedFileIds].map((fileId) =>
        queryClient.invalidateQueries({
          queryKey: extractionKeys.file(invalidationScope, fileId),
        }),
      ),
      queryClient.invalidateQueries({
        queryKey: documentFileKeys.all(invalidationScope),
      }),
      queryClient.invalidateQueries({
        queryKey: documentKeys.all(invalidationScope),
      }),
    ]);
  }, [query.data, queryClient, sessionGeneration, sessionUserId]);

  return query;
};
