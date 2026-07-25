import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import type { PropsWithChildren } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { getExtractionJob, listExtractionJobs } from '../api/extractionApi';
import { useAuthStore } from '../store/authStore';
import { superAdminSession } from '../test/authFixtures';
import {
  extractionIds,
  failedExtractionJob,
  queuedExtractionJob,
} from '../test/extractionFixtures';
import { documentFileKeys } from './documentFileQueryKeys';
import { documentKeys } from './documentQueryKeys';
import { extractionKeys } from './extractionQueryKeys';
import { useExtractionJob } from './useExtraction';
import { useExtractionJobs } from './useExtractionJobs';

vi.mock('../api/extractionApi', () => ({
  getExtractionJob: vi.fn(),
  listExtractionJobs: vi.fn(),
  startExtraction: vi.fn(),
  reextractDocumentFile: vi.fn(),
  cancelExtraction: vi.fn(),
}));

const mockedGetExtractionJob = vi.mocked(getExtractionJob);
const mockedListExtractionJobs = vi.mocked(listExtractionJobs);

describe('extraction query hooks', () => {
  beforeEach(() => {
    mockedGetExtractionJob.mockReset();
    mockedListExtractionJobs.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('polls every three seconds and stops after a terminal status', async () => {
    vi.useFakeTimers();
    useAuthStore.getState().setAuth(superAdminSession);
    mockedGetExtractionJob
      .mockResolvedValueOnce({
        ...failedExtractionJob,
        ...queuedExtractionJob,
      })
      .mockResolvedValue({
        ...failedExtractionJob,
        status: 'COMPLETED',
        progress: 100,
        currentStage: 'Completed',
        runId: extractionIds.run,
        completedAt: '2026-07-25T12:00:15+08:00',
        failedAt: null,
        error: null,
      });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: Infinity } },
    });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(
      () => useExtractionJob(extractionIds.job, { poll: true }),
      { wrapper },
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.data?.status).toBe('EXTRACTING');
    expect(mockedGetExtractionJob).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3_000);
    });
    expect(result.current.data?.status).toBe('COMPLETED');
    expect(mockedGetExtractionJob).toHaveBeenCalledTimes(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(9_000);
    });
    expect(mockedGetExtractionJob).toHaveBeenCalledTimes(2);
  });

  it('invalidates result and file caches once when a listed job becomes terminal', async () => {
    vi.useFakeTimers();
    useAuthStore.getState().setAuth(superAdminSession);
    const completedJob = {
      ...queuedExtractionJob,
      status: 'COMPLETED' as const,
      progress: 100,
      currentStage: 'Completed',
      completedAt: '2026-07-25T12:00:15+08:00',
      runId: extractionIds.run,
    };
    mockedListExtractionJobs
      .mockResolvedValueOnce({
        items: [queuedExtractionJob],
        page: 1,
        pageSize: 20,
        totalItems: 1,
        totalPages: 1,
      })
      .mockResolvedValue({
        items: [completedJob],
        page: 1,
        pageSize: 20,
        totalItems: 1,
        totalPages: 1,
      });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: Infinity } },
    });
    const invalidateQueries = vi.spyOn(queryClient, 'invalidateQueries');
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    const params = {
      page: 1,
      pageSize: 20,
      sortBy: 'requestedAt' as const,
      sortOrder: 'desc' as const,
    };
    const { result } = renderHook(
      () => useExtractionJobs(params, { pollActive: true }),
      { wrapper },
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(result.current.data?.items[0]?.status).toBe('EXTRACTING');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3_000);
    });
    expect(result.current.data?.items[0]?.status).toBe('COMPLETED');

    const authState = useAuthStore.getState();
    const scope = [
      authState.user?.id ?? 'anonymous',
      authState.sessionGeneration,
    ] as const;
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: extractionKeys.runs(scope),
    });
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: extractionKeys.file(scope, extractionIds.file),
    });
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: documentFileKeys.all(scope),
    });
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: documentKeys.all(scope),
    });
    expect(invalidateQueries).toHaveBeenCalledTimes(4);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(9_000);
    });
    expect(mockedListExtractionJobs).toHaveBeenCalledTimes(2);
    expect(invalidateQueries).toHaveBeenCalledTimes(4);
  });
});
