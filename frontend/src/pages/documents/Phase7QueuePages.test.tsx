import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '../../providers/ToastProvider';
import { useAuthStore } from '../../store/authStore';
import { superAdminSession } from '../../test/authFixtures';
import {
  languageDocument,
  ocrJob,
  undetectedLanguageDocument,
} from '../../test/phase7Fixtures';
import { LanguageDetectionPage } from './LanguageDetectionPage';
import { OCRQueuePage } from './OCRQueuePage';

const ocrJobsHook = vi.hoisted(() => vi.fn());
const languageDocumentsHook = vi.hoisted(() => vi.fn());
const ocrMutations = vi.hoisted(() => ({
  cancel: { mutateAsync: vi.fn(), isPending: false },
  export: { mutateAsync: vi.fn(), isPending: false },
}));
const languageMutations = vi.hoisted(() => ({
  start: { mutateAsync: vi.fn(), isPending: false },
  redetect: { mutateAsync: vi.fn(), isPending: false },
  export: { mutateAsync: vi.fn(), isPending: false },
}));

vi.mock('../../hooks/useOCRJobs', () => ({
  useOCRJobs: (params: object, options: object) => ocrJobsHook(params, options),
}));

vi.mock('../../hooks/useOCR', () => ({
  useOCRMutations: () => ocrMutations,
}));

vi.mock('../../hooks/useLanguageDetectionDocuments', () => ({
  useLanguageDetectionDocuments: (params: object, options: object) =>
    languageDocumentsHook(params, options),
}));

vi.mock('../../hooks/useLanguageDetection', () => ({
  useLanguageDetectionJob: () => ({}),
  useLanguageDetectionMutations: () => languageMutations,
}));

vi.mock('../../hooks/useDocumentFormOptions', () => ({
  useDocumentFormOptions: () => ({
    data: {
      departments: [
        {
          id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
          code: 'HRM',
          name: 'Human Resources',
        },
      ],
    },
  }),
}));

const renderPage = (page: React.ReactNode) =>
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter>
        <ToastProvider>{page}</ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );

describe('Phase 7 queue pages', () => {
  beforeEach(() => {
    useAuthStore.getState().setAuth(superAdminSession);
    ocrMutations.cancel.mutateAsync.mockReset();
    languageMutations.start.mutateAsync.mockReset();
    languageMutations.redetect.mutateAsync.mockReset();
    languageMutations.export.mutateAsync.mockReset();
    ocrJobsHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        items: [ocrJob],
        page: 1,
        pageSize: 20,
        totalItems: 1,
        totalPages: 1,
      },
    });
    languageDocumentsHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        items: [languageDocument],
        page: 1,
        pageSize: 20,
        totalItems: 1,
        totalPages: 1,
      },
    });
  });

  it('renders OCR loading, live progress, profile, and safe cancellation', async () => {
    ocrJobsHook.mockReturnValueOnce({
      isLoading: true,
      error: null,
      data: undefined,
    });
    const { rerender } = renderPage(<OCRQueuePage />);
    expect(screen.getByLabelText('Loading OCR queue')).toBeInTheDocument();

    ocrJobsHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        items: [ocrJob],
        page: 1,
        pageSize: 20,
        totalItems: 1,
        totalPages: 1,
      },
    });
    rerender(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <ToastProvider>
            <OCRQueuePage />
          </ToastProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByText(ocrJob.document.baseDocumentCode)).toBeInTheDocument();
    expect(screen.getAllByText(/Automatic Multilingual/).length).toBeGreaterThan(0);
    expect(screen.getByText(ocrJob.currentStage ?? '')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(
      screen.getByRole('dialog', { name: 'Request OCR cancellation?' }),
    ).toBeInTheDocument();
  });

  it('locks a department user OCR filter to their own department', () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      user: {
        ...superAdminSession.user,
        role: 'DEPARTMENT_USER',
        departmentId: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      },
      permissions: [
        'documents:view',
        'documents:ocr',
        'documents:view_ocr_results',
        'documents:view_ocr_history',
      ],
    });
    renderPage(<OCRQueuePage />);

    expect(screen.getByLabelText('Department')).toBeDisabled();
    expect(ocrJobsHook).toHaveBeenCalledWith(
      expect.objectContaining({
        departmentId: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      }),
      { pollActive: true },
    );
  });

  it('passes the selected OCR request date range to the backend query', async () => {
    renderPage(<OCRQueuePage />);

    await userEvent.type(screen.getByLabelText('Requested From'), '2026-07-01');
    await userEvent.type(screen.getByLabelText('Requested To'), '2026-07-25');

    expect(ocrJobsHook).toHaveBeenLastCalledWith(
      expect.objectContaining({
        requestedFrom: expect.any(String),
        requestedTo: expect.any(String),
      }),
      { pollActive: true },
    );
  });

  it('shows preliminary language presence without compliance wording', () => {
    renderPage(<LanguageDetectionPage />);

    expect(screen.getByText(/preliminary language detection/i)).toBeInTheDocument();
    expect(screen.getAllByText('Present')).toHaveLength(2);
    expect(screen.getByText('Insufficient Evidence')).toBeInTheDocument();
    expect(screen.queryByText(/non-compliant/i)).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'View Results' })).toHaveAttribute(
      'href',
      expect.stringContaining('/language-results'),
    );
  });

  it('queues detection with the latest usable extraction and OCR source', async () => {
    languageDocumentsHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        items: [undetectedLanguageDocument],
        page: 1,
        pageSize: 20,
        totalItems: 1,
        totalPages: 1,
      },
    });
    languageMutations.start.mutateAsync.mockResolvedValue({
      jobId: 'job-id',
    });
    renderPage(<LanguageDetectionPage />);

    await userEvent.click(screen.getByRole('button', { name: 'Detect Languages' }));

    expect(languageMutations.start.mutateAsync).toHaveBeenCalledWith({
      documentFileId: undetectedLanguageDocument.file.id,
      extractionRunId: undetectedLanguageDocument.extractionRunId,
      ocrRunId: undetectedLanguageDocument.ocrRunId,
      force: false,
    });
  });

  it('uses the reason dialog for re-detection', async () => {
    languageMutations.redetect.mutateAsync.mockResolvedValue({
      jobId: 'job-id',
    });
    renderPage(<LanguageDetectionPage />);

    await userEvent.click(screen.getByRole('button', { name: 'Re-detect' }));
    await userEvent.type(
      screen.getByLabelText('Reason'),
      'Detector configuration updated.',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Queue Re-detection' }));

    expect(languageMutations.redetect.mutateAsync).toHaveBeenCalledWith({
      runId: languageDocument.languageDetectionRunId,
      payload: { reason: 'Detector configuration updated.' },
    });
  });

  it('hides row detection without detect permission', () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      permissions: ['documents:view', 'documents:view_language_results'],
    });
    languageDocumentsHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        items: [undetectedLanguageDocument],
        page: 1,
        pageSize: 20,
        totalItems: 1,
        totalPages: 1,
      },
    });
    renderPage(<LanguageDetectionPage />);

    expect(
      screen.queryByRole('button', { name: 'Detect Languages' }),
    ).not.toBeInTheDocument();
  });

  it('gates re-detection and export independently from result viewing', () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      permissions: ['documents:view', 'documents:view_language_results'],
    });
    renderPage(<LanguageDetectionPage />);

    expect(screen.getByRole('link', { name: 'View Results' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Re-detect' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'json' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'xlsx' })).not.toBeInTheDocument();
  });

  it('locks the language document inventory to a department user', () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      user: {
        ...superAdminSession.user,
        role: 'DEPARTMENT_USER',
        departmentId: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      },
      permissions: [
        'documents:view',
        'documents:detect_language',
        'documents:view_language_results',
      ],
    });
    renderPage(<LanguageDetectionPage />);

    expect(screen.getByLabelText('Department')).toBeDisabled();
    expect(languageDocumentsHook).toHaveBeenCalledWith(
      expect.objectContaining({
        departmentId: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      }),
      { pollActive: true },
    );
  });
});
