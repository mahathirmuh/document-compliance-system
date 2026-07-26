import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import type { PropsWithChildren } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { getComplianceJob, listComplianceJobs } from '../api/complianceApi';
import { useAuthStore } from '../store/authStore';
import { superAdminSession } from '../test/authFixtures';
import { complianceJob, phase8Ids } from '../test/phase8Fixtures';
import { useComplianceJob, useComplianceJobs } from './useComplianceJobs';

vi.mock('../api/complianceApi', () => ({
  getComplianceJob: vi.fn(),
  listComplianceJobs: vi.fn(),
  cancelComplianceJob: vi.fn(),
}));

const mockedGetJob = vi.mocked(getComplianceJob);
const mockedListJobs = vi.mocked(listComplianceJobs);

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  });
  return ({ children }: PropsWithChildren) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe('Phase 8 compliance polling', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useAuthStore.getState().setAuth(superAdminSession);
    mockedGetJob.mockReset();
    mockedListJobs.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('polls an active validation every three seconds and stops when complete', async () => {
    mockedGetJob.mockResolvedValueOnce(complianceJob).mockResolvedValue({
      ...complianceJob,
      status: 'COMPLETED',
      progress: 100,
      currentStage: 'COMPLETED',
      completedAt: '2026-07-26T08:01:00+08:00',
      resultSummary: {
        runId: phase8Ids.run,
        complianceStatus: 'PARTIALLY_COMPLIANT',
        complianceScore: 82.5,
        totalFindings: 2,
        criticalFindings: 0,
        majorFindings: 1,
        minorFindings: 1,
      },
    });
    const { result } = renderHook(
      () => useComplianceJob(phase8Ids.job, { poll: true }),
      { wrapper: createWrapper() },
    );

    await act(async () => vi.advanceTimersByTimeAsync(100));
    expect(result.current.data?.status).toBe('VALIDATING_LANGUAGES');
    await act(async () => vi.advanceTimersByTimeAsync(3_000));
    expect(result.current.data?.status).toBe('COMPLETED');
    await act(async () => vi.advanceTimersByTimeAsync(9_000));
    expect(mockedGetJob).toHaveBeenCalledTimes(2);
  });

  it('polls the queue only while at least one listed job is active', async () => {
    const activeList = {
      items: [complianceJob],
      page: 1,
      pageSize: 20,
      totalItems: 1,
      totalPages: 1,
    };
    mockedListJobs.mockResolvedValueOnce(activeList).mockResolvedValue({
      ...activeList,
      items: [
        {
          ...complianceJob,
          status: 'CANCELLED',
          progress: 45,
          currentStage: 'CANCELLED',
          cancelledAt: '2026-07-26T08:00:30+08:00',
        },
      ],
    });
    const params = { page: 1, pageSize: 20 };
    const { result } = renderHook(
      () => useComplianceJobs(params, { pollActive: true }),
      { wrapper: createWrapper() },
    );

    await act(async () => vi.advanceTimersByTimeAsync(100));
    expect(result.current.data?.items[0]?.status).toBe('VALIDATING_LANGUAGES');
    await act(async () => vi.advanceTimersByTimeAsync(3_000));
    expect(result.current.data?.items[0]?.status).toBe('CANCELLED');
    await act(async () => vi.advanceTimersByTimeAsync(9_000));
    expect(mockedListJobs).toHaveBeenCalledTimes(2);
  });

  it('keeps compliance status in the server request and query key', async () => {
    const emptyPage = {
      items: [],
      page: 1,
      pageSize: 20,
      totalItems: 0,
      totalPages: 0,
    };
    mockedListJobs.mockResolvedValue(emptyPage);
    const wrapper = createWrapper();
    const compliantParams = {
      page: 1,
      pageSize: 20,
      complianceStatus: 'COMPLIANT' as const,
    };
    const nonCompliantParams = {
      page: 1,
      pageSize: 20,
      complianceStatus: 'NON_COMPLIANT' as const,
    };

    renderHook(() => useComplianceJobs(compliantParams), { wrapper });
    renderHook(() => useComplianceJobs(nonCompliantParams), { wrapper });
    await act(async () => vi.advanceTimersByTimeAsync(100));

    expect(mockedListJobs).toHaveBeenCalledWith(
      compliantParams,
      expect.any(AbortSignal),
    );
    expect(mockedListJobs).toHaveBeenCalledWith(
      nonCompliantParams,
      expect.any(AbortSignal),
    );
    expect(mockedListJobs).toHaveBeenCalledTimes(2);
  });
});
