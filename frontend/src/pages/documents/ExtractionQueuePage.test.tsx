import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '../../providers/ToastProvider';
import { useAuthStore } from '../../store/authStore';
import { superAdminSession } from '../../test/authFixtures';
import { queuedExtractionJob } from '../../test/extractionFixtures';
import { ExtractionQueuePage } from './ExtractionQueuePage';

const jobsHook = vi.hoisted(() => vi.fn());
const cancelMutation = vi.hoisted(() => ({
  mutateAsync: vi.fn(),
  isPending: false,
}));

vi.mock('../../hooks/useExtractionJobs', () => ({
  useExtractionJobs: (params: object, options: object) => jobsHook(params, options),
}));

vi.mock('../../hooks/useExtraction', () => ({
  useExtractionMutations: () => ({
    cancel: cancelMutation,
  }),
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

const renderPage = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ToastProvider>
          <ExtractionQueuePage />
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

describe('ExtractionQueuePage', () => {
  beforeEach(() => {
    jobsHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        items: [queuedExtractionJob],
        page: 1,
        pageSize: 20,
        totalItems: 1,
        totalPages: 1,
      },
    });
    cancelMutation.mutateAsync.mockResolvedValue({
      id: queuedExtractionJob.id,
      status: 'CANCEL_REQUESTED',
      progress: 45,
      currentStage: 'Cancellation requested',
      cancelledAt: null,
    });
  });

  it('renders loading state and the live progress row', () => {
    jobsHook.mockReturnValueOnce({
      isLoading: true,
      error: null,
      data: undefined,
    });
    const { rerender } = renderPage();
    expect(screen.getByLabelText('Loading extraction queue')).toBeInTheDocument();

    jobsHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        items: [queuedExtractionJob],
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
            <ExtractionQueuePage />
          </ToastProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(
      screen.getByText(queuedExtractionJob.document.baseDocumentCode),
    ).toBeInTheDocument();
    expect(screen.getByText('Extracting page 9 of 20')).toBeInTheDocument();
  });

  it('applies queue filters and locks department scope without global permission', () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      user: {
        ...superAdminSession.user,
        role: 'DEPARTMENT_USER',
        departmentId: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      },
      permissions: [
        'documents:view',
        'documents:extract',
        'documents:view_extracted_content',
        'documents:view_extraction_history',
      ],
    });
    renderPage();

    expect(screen.getByLabelText('Department')).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Status'), {
      target: { value: 'EXTRACTING' },
    });
    fireEvent.change(screen.getByLabelText('File Type'), {
      target: { value: 'PDF' },
    });

    expect(jobsHook).toHaveBeenLastCalledWith(
      expect.objectContaining({
        departmentId: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
        status: 'EXTRACTING',
        extractorType: 'PDF',
      }),
      { pollActive: true },
    );
  });

  it('requests safe-checkpoint cancellation from the row action', async () => {
    useAuthStore.getState().setAuth(superAdminSession);
    renderPage();

    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(
      screen.getByRole('dialog', { name: 'Request extraction cancellation?' }),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Request Cancellation' }));

    expect(cancelMutation.mutateAsync).toHaveBeenCalledWith(queuedExtractionJob.id);
    expect(await screen.findByText('Cancellation requested')).toBeInTheDocument();
  });
});
