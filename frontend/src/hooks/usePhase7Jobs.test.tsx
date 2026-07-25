import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import type { PropsWithChildren } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  getLanguageDetectionJob,
  listLanguageDetectionDocuments,
} from '../api/languageDetectionApi';
import { getOCRJob } from '../api/ocrApi';
import { useAuthStore } from '../store/authStore';
import { superAdminSession } from '../test/authFixtures';
import {
  languageDocument,
  languageJobDetail,
  ocrJobDetail,
  phase7Ids,
} from '../test/phase7Fixtures';
import { useLanguageDetectionJob } from './useLanguageDetection';
import { useLanguageDetectionDocuments } from './useLanguageDetectionDocuments';
import { useOCRJob } from './useOCR';

vi.mock('../api/ocrApi', () => ({
  getOCRJob: vi.fn(),
  getLatestOCR: vi.fn(),
  getOCRRun: vi.fn(),
  listOCRPages: vi.fn(),
  getOCRPage: vi.fn(),
  listOCRBlocks: vi.fn(),
  startOCR: vi.fn(),
  cancelOCR: vi.fn(),
  reOCR: vi.fn(),
  exportOCR: vi.fn(),
}));

vi.mock('../api/languageDetectionApi', () => ({
  getLanguageDetectionJob: vi.fn(),
  listLanguageDetectionDocuments: vi.fn(),
  startLanguageDetection: vi.fn(),
  cancelLanguageDetection: vi.fn(),
  redetectLanguage: vi.fn(),
  exportLanguageResults: vi.fn(),
}));

const mockedGetOCRJob = vi.mocked(getOCRJob);
const mockedGetLanguageJob = vi.mocked(getLanguageDetectionJob);
const mockedListLanguageDocuments = vi.mocked(listLanguageDetectionDocuments);

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  });
  return ({ children }: PropsWithChildren) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe('Phase 7 job polling', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useAuthStore.getState().setAuth(superAdminSession);
    mockedGetOCRJob.mockReset();
    mockedGetLanguageJob.mockReset();
    mockedListLanguageDocuments.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('polls OCR every three seconds and stops at partial completion', async () => {
    mockedGetOCRJob.mockResolvedValueOnce(ocrJobDetail).mockResolvedValue({
      ...ocrJobDetail,
      status: 'PARTIALLY_COMPLETED',
      progress: 100,
      currentStage: 'Completed with one failed page',
      completedAt: '2026-07-25T12:01:03+08:00',
      runId: phase7Ids.run,
    });
    const { result } = renderHook(() => useOCRJob(phase7Ids.job, { poll: true }), {
      wrapper: createWrapper(),
    });

    await act(async () => vi.advanceTimersByTimeAsync(100));
    expect(result.current.data?.status).toBe('RECOGNISING');
    await act(async () => vi.advanceTimersByTimeAsync(3_000));
    expect(result.current.data?.status).toBe('PARTIALLY_COMPLETED');
    await act(async () => vi.advanceTimersByTimeAsync(9_000));
    expect(mockedGetOCRJob).toHaveBeenCalledTimes(2);
  });

  it('polls language detection every three seconds and stops after cancellation', async () => {
    mockedGetLanguageJob.mockResolvedValueOnce(languageJobDetail).mockResolvedValue({
      ...languageJobDetail,
      status: 'CANCELLED',
      progress: 55,
      currentStage: 'Cancelled',
      cancelledAt: '2026-07-25T12:02:10+08:00',
    });
    const { result } = renderHook(
      () => useLanguageDetectionJob(phase7Ids.languageJob, { poll: true }),
      { wrapper: createWrapper() },
    );

    await act(async () => vi.advanceTimersByTimeAsync(100));
    expect(result.current.data?.status).toBe('DETECTING');
    await act(async () => vi.advanceTimersByTimeAsync(3_000));
    expect(result.current.data?.status).toBe('CANCELLED');
    await act(async () => vi.advanceTimersByTimeAsync(9_000));
    expect(mockedGetLanguageJob).toHaveBeenCalledTimes(2);
  });

  it('polls the document inventory while a listed language job is active', async () => {
    const activeResult = {
      items: [
        {
          ...languageDocument,
          languageDetectionStatus: 'DETECTING' as const,
          languageProgress: 55,
        },
      ],
      page: 1,
      pageSize: 20,
      totalItems: 1,
      totalPages: 1,
    };
    mockedListLanguageDocuments.mockResolvedValueOnce(activeResult).mockResolvedValue({
      ...activeResult,
      items: [languageDocument],
    });
    const params = { page: 1, pageSize: 20 };
    const { result } = renderHook(
      () =>
        useLanguageDetectionDocuments(params, {
          pollActive: true,
        }),
      { wrapper: createWrapper() },
    );

    await act(async () => vi.advanceTimersByTimeAsync(100));
    expect(result.current.data?.items[0]?.languageDetectionStatus).toBe('DETECTING');
    await act(async () => vi.advanceTimersByTimeAsync(3_000));
    expect(result.current.data?.items[0]?.languageDetectionStatus).toBe('COMPLETED');
    await act(async () => vi.advanceTimersByTimeAsync(9_000));
    expect(mockedListLanguageDocuments).toHaveBeenCalledTimes(2);
  });
});
