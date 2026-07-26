import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '../../providers/ToastProvider';
import { useAuthStore } from '../../store/authStore';
import { superAdminSession } from '../../test/authFixtures';
import { SimilarityHistoryPage } from './SimilarityHistoryPage';
import { SimilarityQueuePage } from './SimilarityQueuePage';

const similarityJobsHook = vi.hoisted(() => vi.fn());
const cancelSimilarity = vi.hoisted(() => ({
  mutateAsync: vi.fn(),
  isPending: false,
}));
const similarityMutations = vi.hoisted(() => ({
  start: { mutateAsync: vi.fn(), isPending: false },
  rerun: { mutateAsync: vi.fn(), isPending: false },
  export: { mutateAsync: vi.fn(), isPending: false },
}));
const downloadFile = vi.hoisted(() => vi.fn());

vi.mock('../../hooks/useSimilarityJobs', () => ({
  useSimilarityJobs: (params: object, options?: object) =>
    similarityJobsHook(params, options),
  useCancelSimilarity: () => cancelSimilarity,
}));

vi.mock('../../hooks/useSimilarity', () => ({
  useSimilarityMutations: () => similarityMutations,
}));

vi.mock('../../hooks/useDocumentFormOptions', () => ({
  useDocumentFormOptions: () => ({
    data: {
      departments: [{ id: 'department-id', code: 'HSE', name: 'Health and Safety' }],
    },
  }),
}));

vi.mock('../../utils/downloadFile', () => ({
  downloadFile,
}));

const timestamp = '2026-07-26T01:00:00Z';
const job = {
  id: 'job-id',
  documentId: 'document-id',
  documentRevisionId: 'revision-id',
  documentFileId: 'file-id',
  complianceRunId: 'compliance-run-id',
  languageDetectionRunId: 'language-run-id',
  jobType: 'INITIAL_SIMILARITY',
  status: 'ENCODING',
  progress: 45,
  currentStage: 'ENCODING',
  provider: 'sentence_transformers',
  modelName: 'multilingual-e5-base',
  sourceContentHash: null,
  attemptNumber: 1,
  maximumAttempts: 2,
  requestedBy: { id: 'user-id', name: 'Quality Reviewer' },
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
  document: {
    id: 'document-id',
    baseDocumentCode: 'SOP-HSE-001',
    title: 'Safety Procedure',
    departmentId: 'department-id',
  },
  revision: {
    id: 'revision-id',
    revisionCode: 'R01',
    fullDocumentCode: 'SOP-HSE-001-R01',
  },
  file: {
    id: 'file-id',
    filename: 'safety.docx',
    fileExtension: '.docx',
  },
};

const list = (item: object) => ({
  isLoading: false,
  error: null,
  data: {
    items: [item],
    page: 1,
    pageSize: 20,
    totalItems: 1,
    totalPages: 1,
  },
  refetch: vi.fn(),
});

const renderPage = (page: React.ReactNode) =>
  render(
    <MemoryRouter>
      <ToastProvider>{page}</ToastProvider>
    </MemoryRouter>,
  );

describe('Phase 9 similarity queue and history', () => {
  beforeEach(() => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      user: {
        ...superAdminSession.user,
        departmentId: 'department-id',
      },
      permissions: ['similarity:view', 'similarity:run', 'similarity:rerun'],
    });
    similarityJobsHook.mockReset();
    cancelSimilarity.mutateAsync.mockReset();
    similarityMutations.rerun.mutateAsync.mockReset();
    similarityMutations.export.mutateAsync.mockReset();
    downloadFile.mockReset();
  });

  it('shows live progress, locks department scope, and confirms cancellation', async () => {
    similarityJobsHook.mockReturnValue(list(job));
    cancelSimilarity.mutateAsync.mockResolvedValue({
      ...job,
      status: 'CANCEL_REQUESTED',
    });

    renderPage(<SimilarityQueuePage />);

    expect(screen.getByText('45%')).toBeInTheDocument();
    expect(screen.getByLabelText('Department')).toBeDisabled();
    expect(
      screen.getByText('Department scope is locked to your assigned department.'),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(
      screen.getByRole('dialog', { name: 'Cancel similarity analysis?' }),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Request Cancellation' }));
    expect(cancelSimilarity.mutateAsync).toHaveBeenCalledWith('job-id');
  });

  it('requires an audit reason before re-running a retained result', async () => {
    similarityJobsHook.mockReturnValue(
      list({
        ...job,
        status: 'COMPLETED',
        progress: 100,
        completedAt: timestamp,
        resultSummary: {
          runId: 'run-id',
          averageSimilarity: 0.81,
          lowSimilarityGroups: 2,
          numberMismatches: 1,
          negationMismatches: 1,
        },
      }),
    );
    similarityMutations.rerun.mutateAsync.mockResolvedValue({
      id: 'rerun-job-id',
      status: 'QUEUED',
      progress: 0,
      documentFileId: 'file-id',
      runId: null,
      reusedExistingResult: false,
    });

    renderPage(<SimilarityHistoryPage />);

    expect(screen.getByText('81.0%')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Re-run' }));
    const submit = screen.getByRole('button', { name: 'Queue Re-run' });
    expect(submit).toBeDisabled();
    await userEvent.type(
      screen.getByLabelText('Re-run reason'),
      'Model configuration was reviewed',
    );
    await userEvent.click(submit);
    expect(similarityMutations.rerun.mutateAsync).toHaveBeenCalledWith({
      runId: 'run-id',
      payload: { reason: 'Model configuration was reviewed' },
    });
  });

  it('exports a retained similarity run through its authenticated API mutation', async () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      permissions: ['similarity:view', 'similarity:export'],
    });
    similarityJobsHook.mockReturnValue(
      list({
        ...job,
        status: 'COMPLETED',
        progress: 100,
        completedAt: timestamp,
        resultSummary: { runId: 'run-id', averageSimilarity: 0.9 },
      }),
    );
    const result = { blob: new Blob(['result']), fileName: 'similarity.json' };
    similarityMutations.export.mutateAsync.mockResolvedValue(result);

    renderPage(<SimilarityHistoryPage />);
    await userEvent.click(screen.getByRole('button', { name: 'json' }));

    expect(similarityMutations.export.mutateAsync).toHaveBeenCalledWith({
      runId: 'run-id',
      format: 'json',
    });
    expect(downloadFile).toHaveBeenCalledWith(result, 'SOP-HSE-001_similarity.json');
  });
});
