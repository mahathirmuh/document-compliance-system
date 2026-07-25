import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '../../providers/ToastProvider';
import { useAuthStore } from '../../store/authStore';
import { superAdminSession } from '../../test/authFixtures';
import { terminalExtractionStatuses } from '../../types/extraction';
import { ExtractionHistoryPage } from './ExtractionHistoryPage';

const jobsHook = vi.hoisted(() => vi.fn());
const reextractMutation = vi.hoisted(() => ({
  mutateAsync: vi.fn(),
  isPending: false,
}));
const exportMutation = vi.hoisted(() => ({
  mutateAsync: vi.fn(),
  isPending: false,
}));

vi.mock('../../hooks/useExtractionJobs', () => ({
  useExtractionJobs: (params: object) => jobsHook(params),
}));

vi.mock('../../hooks/useExtraction', () => ({
  useExtractionMutations: () => ({
    reextract: reextractMutation,
  }),
}));

vi.mock('../../hooks/useExtractedContent', () => ({
  useExtractionExport: () => exportMutation,
  useExtractionRun: () => ({ data: null }),
}));

vi.mock('../../hooks/useDocumentFormOptions', () => ({
  useDocumentFormOptions: () => ({ data: { departments: [] } }),
}));

describe('ExtractionHistoryPage', () => {
  beforeEach(() => {
    useAuthStore.getState().setAuth(superAdminSession);
    jobsHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        items: [],
        page: 1,
        pageSize: 20,
        totalItems: 0,
        totalPages: 0,
      },
    });
  });

  it('requests terminal jobs from the server so pagination totals stay accurate', () => {
    render(
      <MemoryRouter>
        <ToastProvider>
          <ExtractionHistoryPage />
        </ToastProvider>
      </MemoryRouter>,
    );

    expect(jobsHook).toHaveBeenLastCalledWith(
      expect.objectContaining({
        status: terminalExtractionStatuses,
        sortBy: 'completedAt',
        sortOrder: 'desc',
      }),
    );

    fireEvent.change(screen.getByLabelText('Terminal Status'), {
      target: { value: 'FAILED' },
    });
    expect(jobsHook).toHaveBeenLastCalledWith(
      expect.objectContaining({ status: 'FAILED' }),
    );
  });
});
