import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import type { PropsWithChildren } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { getReportJob } from '../api/advancedReportingApi';
import { getGlossaryValidationJob } from '../api/glossaryApi';
import { getRevisionComparisonJob } from '../api/revisionComparisonApi';
import { getSimilarityJob } from '../api/similarityApi';
import { useAuthStore } from '../store/authStore';
import { superAdminSession } from '../test/authFixtures';
import { useReportJob } from './useAdvancedReports';
import { useGlossaryValidationJob } from './useGlossaryValidation';
import { useRevisionComparisonJob } from './useRevisionComparison';
import { useSimilarityJob } from './useSimilarityJobs';

vi.mock('../api/similarityApi', () => ({
  getSimilarityJob: vi.fn(),
  listSimilarityJobs: vi.fn(),
  cancelSimilarity: vi.fn(),
}));

vi.mock('../api/glossaryApi', () => ({
  cancelGlossaryValidation: vi.fn(),
  exportGlossaryValidation: vi.fn(),
  getFileGlossaryValidation: vi.fn(),
  getGlossaryHistory: vi.fn(),
  getGlossaryValidationJob: vi.fn(),
  getGlossaryValidationRun: vi.fn(),
  getGlossaryValidationSummary: vi.fn(),
  listGlossaryMatches: vi.fn(),
  listGlossaryValidationFindings: vi.fn(),
  listGlossaryValidationJobs: vi.fn(),
  revalidateGlossary: vi.fn(),
  startGlossaryValidation: vi.fn(),
}));

vi.mock('../api/revisionComparisonApi', () => ({
  cancelRevisionComparison: vi.fn(),
  exportRevisionComparison: vi.fn(),
  getRevisionComparison: vi.fn(),
  getRevisionComparisonJob: vi.fn(),
  getRevisionComparisonSummary: vi.fn(),
  getRevisionFindingChanges: vi.fn(),
  getRevisionLanguageChanges: vi.fn(),
  getRevisionSectionChanges: vi.fn(),
  listDocumentRevisionComparisons: vi.fn(),
  listRevisionChanges: vi.fn(),
  listRevisionComparisonJobs: vi.fn(),
  startRevisionComparison: vi.fn(),
}));

vi.mock('../api/advancedReportingApi', () => ({
  createReportSchedule: vi.fn(),
  deleteReportSnapshot: vi.fn(),
  disableReportSchedule: vi.fn(),
  downloadReportSnapshot: vi.fn(),
  generateAdvancedReport: vi.fn(),
  getReportJob: vi.fn(),
  getReportSnapshot: vi.fn(),
  listReportJobs: vi.fn(),
  listReportSchedules: vi.fn(),
  listReportSnapshots: vi.fn(),
  runReportSchedule: vi.fn(),
  updateReportSchedule: vi.fn(),
}));

const mockedSimilarityJob = vi.mocked(getSimilarityJob);
const mockedGlossaryJob = vi.mocked(getGlossaryValidationJob);
const mockedRevisionJob = vi.mocked(getRevisionComparisonJob);
const mockedReportJob = vi.mocked(getReportJob);

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  });
  return ({ children }: PropsWithChildren) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

const timestamp = '2026-07-26T01:00:00Z';

const similarityJob = {
  id: 'similarity-job-id',
  documentId: 'document-id',
  documentRevisionId: 'revision-id',
  documentFileId: 'file-id',
  complianceRunId: 'compliance-run-id',
  languageDetectionRunId: 'language-run-id',
  jobType: 'INITIAL_SIMILARITY' as const,
  status: 'ENCODING' as const,
  progress: 45,
  currentStage: 'Encoding multilingual groups',
  provider: 'sentence_transformer',
  modelName: 'local-model',
  sourceContentHash: null,
  attemptNumber: 1,
  maximumAttempts: 3,
  requestedBy: null,
  requestedAt: timestamp,
  startedAt: timestamp,
  completedAt: null,
  failedAt: null,
  cancelledAt: null,
  errorCode: null,
  errorMessage: null,
  errorDetails: null,
  resultSummary: null,
  createdAt: timestamp,
  updatedAt: timestamp,
};

const glossaryJob = {
  id: 'glossary-run-id',
  jobId: 'glossary-job-id',
  documentId: 'document-id',
  documentRevisionId: 'revision-id',
  documentFileId: 'file-id',
  complianceRunId: 'compliance-run-id',
  languageDetectionRunId: 'language-run-id',
  glossaryProfileIds: ['profile-id'],
  profileSnapshots: [],
  jobType: 'INITIAL' as const,
  status: 'MATCHING_TERMS' as const,
  progress: 40,
  currentStage: 'Matching terms',
  sourceContentHash: 'a'.repeat(64),
  totalTerms: 10,
  matchedTerms: 3,
  preferredTermMatches: 2,
  forbiddenTermMatches: 1,
  missingRequiredTranslations: 0,
  inconsistentTerms: 0,
  exceptionAppliedCount: 0,
  totalFindings: 1,
  metrics: {},
  warnings: [],
  errorCode: null,
  errorMessage: null,
  requestedBy: 'user-id',
  requestedAt: timestamp,
  startedAt: timestamp,
  completedAt: null,
  failedAt: null,
  cancelRequestedAt: null,
  cancelledAt: null,
  createdAt: timestamp,
  updatedAt: timestamp,
};

const revisionJob = {
  id: 'revision-job-id',
  documentId: 'document-id',
  baseRevisionId: 'revision-1',
  targetRevisionId: 'revision-2',
  baseDocumentFileId: 'file-1',
  targetDocumentFileId: 'file-2',
  jobType: 'INITIAL' as const,
  status: 'COMPARING_CONTENT' as const,
  progress: 55,
  currentStage: 'Comparing bounded content',
  requestedBy: 'user-id',
  requestedAt: timestamp,
  startedAt: timestamp,
  completedAt: null,
  failedAt: null,
  cancelledAt: null,
  errorCode: null,
  errorMessage: null,
  resultSummary: null,
};

const reportJob = {
  id: 'report-job-id',
  reportType: 'COMPLIANCE_OVERVIEW' as const,
  reportName: 'Compliance overview',
  outputFormat: 'xlsx' as const,
  status: 'BUILDING_DATASET' as const,
  snapshotStatus: 'GENERATING' as const,
  progress: 35,
  currentStage: 'Building authorized dataset',
  requestedAt: timestamp,
  startedAt: timestamp,
  completedAt: null,
  errorCode: null,
  errorMessage: null,
};

describe('Phase 9 job polling', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useAuthStore.getState().setAuth(superAdminSession);
    mockedSimilarityJob.mockReset();
    mockedGlossaryJob.mockReset();
    mockedRevisionJob.mockReset();
    mockedReportJob.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('polls similarity every three seconds and stops at partial completion', async () => {
    mockedSimilarityJob.mockResolvedValueOnce(similarityJob).mockResolvedValue({
      ...similarityJob,
      status: 'PARTIALLY_COMPLETED',
      progress: 100,
      completedAt: timestamp,
    });
    const { result } = renderHook(
      () => useSimilarityJob('similarity-job-id', { poll: true }),
      { wrapper: createWrapper() },
    );

    await act(async () => vi.advanceTimersByTimeAsync(100));
    expect(result.current.data?.status).toBe('ENCODING');
    await act(async () => vi.advanceTimersByTimeAsync(3_000));
    expect(result.current.data?.status).toBe('PARTIALLY_COMPLETED');
    await act(async () => vi.advanceTimersByTimeAsync(9_000));
    expect(mockedSimilarityJob).toHaveBeenCalledTimes(2);
  });

  it('stops glossary polling when the worker fails', async () => {
    mockedGlossaryJob.mockResolvedValueOnce(glossaryJob).mockResolvedValue({
      ...glossaryJob,
      status: 'FAILED',
      progress: 40,
      failedAt: timestamp,
      errorCode: 'GLOSSARY_MATCH_FAILED',
      errorMessage: 'Matching failed safely.',
    });
    const { result } = renderHook(() => useGlossaryValidationJob('glossary-job-id'), {
      wrapper: createWrapper(),
    });

    await act(async () => vi.advanceTimersByTimeAsync(100));
    expect(result.current.data?.status).toBe('MATCHING_TERMS');
    await act(async () => vi.advanceTimersByTimeAsync(3_000));
    expect(result.current.data?.status).toBe('FAILED');
    await act(async () => vi.advanceTimersByTimeAsync(9_000));
    expect(mockedGlossaryJob).toHaveBeenCalledTimes(2);
  });

  it('stops revision comparison polling after cancellation', async () => {
    mockedRevisionJob.mockResolvedValueOnce(revisionJob).mockResolvedValue({
      ...revisionJob,
      status: 'CANCELLED',
      progress: 55,
      cancelledAt: timestamp,
    });
    const { result } = renderHook(() => useRevisionComparisonJob('revision-job-id'), {
      wrapper: createWrapper(),
    });

    await act(async () => vi.advanceTimersByTimeAsync(100));
    expect(result.current.data?.status).toBe('COMPARING_CONTENT');
    await act(async () => vi.advanceTimersByTimeAsync(3_000));
    expect(result.current.data?.status).toBe('CANCELLED');
    await act(async () => vi.advanceTimersByTimeAsync(9_000));
    expect(mockedRevisionJob).toHaveBeenCalledTimes(2);
  });

  it('stops report polling after the snapshot is completed', async () => {
    mockedReportJob.mockResolvedValueOnce(reportJob).mockResolvedValue({
      ...reportJob,
      status: 'COMPLETED',
      snapshotStatus: 'AVAILABLE',
      progress: 100,
      completedAt: timestamp,
    });
    const { result } = renderHook(() => useReportJob('report-job-id'), {
      wrapper: createWrapper(),
    });

    await act(async () => vi.advanceTimersByTimeAsync(100));
    expect(result.current.data?.status).toBe('BUILDING_DATASET');
    await act(async () => vi.advanceTimersByTimeAsync(3_000));
    expect(result.current.data?.status).toBe('COMPLETED');
    await act(async () => vi.advanceTimersByTimeAsync(9_000));
    expect(mockedReportJob).toHaveBeenCalledTimes(2);
  });
});
