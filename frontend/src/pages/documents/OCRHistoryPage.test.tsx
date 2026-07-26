import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '../../providers/ToastProvider';
import { useAuthStore } from '../../store/authStore';
import { superAdminSession } from '../../test/authFixtures';
import { ocrJob } from '../../test/phase7Fixtures';
import {
  terminalOCRJobStatuses,
  type OCRJobListItem,
  type OCRJobStatus,
} from '../../types/ocr';
import { OCRHistoryPage } from './OCRHistoryPage';

const jobsHook = vi.hoisted(() => vi.fn());
const ocrMutations = vi.hoisted(() => ({
  export: { mutateAsync: vi.fn(), isPending: false },
}));

vi.mock('../../hooks/useOCRJobs', () => ({
  useOCRJobs: (params: object, options: object) => jobsHook(params, options),
}));

vi.mock('../../hooks/useOCR', () => ({
  useOCRMutations: () => ocrMutations,
}));

const historyJob = (status: OCRJobStatus, sequence: number): OCRJobListItem => ({
  ...ocrJob,
  id: `10000000-0000-4000-8000-${sequence.toString().padStart(12, '0')}`,
  document: {
    ...ocrJob.document,
    id: `20000000-0000-4000-8000-${sequence.toString().padStart(12, '0')}`,
    baseDocumentCode: `MTI-HRM-SOP-${sequence.toString().padStart(3, '0')}`,
  },
  revision: {
    ...ocrJob.revision,
    id: `30000000-0000-4000-8000-${sequence.toString().padStart(12, '0')}`,
  },
  file: {
    ...ocrJob.file,
    id: `40000000-0000-4000-8000-${sequence.toString().padStart(12, '0')}`,
    filename: `history-${sequence}.pdf`,
  },
  status,
  progress: 100,
  currentStage: status === 'FAILED' ? 'Failed' : 'Completed',
  processedPageNumbers: status === 'FAILED' ? [] : [1, 2],
  failedPageNumbers: status === 'FAILED' ? [1, 2] : [],
  completedAt: '2026-07-25T12:01:03+08:00',
  runId: `50000000-0000-4000-8000-${sequence.toString().padStart(12, '0')}`,
  resultSummary: {
    totalBlocks: status === 'FAILED' ? 0 : 7,
    averageConfidence: status === 'FAILED' ? null : 0.84,
  },
});

const completedJob = historyJob('COMPLETED', 1);
const partiallyCompletedJob = historyJob('PARTIALLY_COMPLETED', 2);
const failedJob = historyJob('FAILED', 3);

const renderPage = () =>
  render(
    <MemoryRouter>
      <ToastProvider>
        <OCRHistoryPage />
      </ToastProvider>
    </MemoryRouter>,
  );

describe('OCRHistoryPage', () => {
  beforeEach(() => {
    useAuthStore.getState().setAuth(superAdminSession);
    ocrMutations.export.mutateAsync.mockReset();
    jobsHook.mockReset();
    jobsHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        items: [completedJob, partiallyCompletedJob, failedJob],
        page: 1,
        pageSize: 20,
        totalItems: 23,
        totalPages: 2,
      },
    });
  });

  it('renders terminal history and only offers Re-run for usable source runs', () => {
    renderPage();

    expect(jobsHook).toHaveBeenCalledWith(
      expect.objectContaining({
        page: 1,
        pageSize: 20,
        status: terminalOCRJobStatuses,
        sortBy: 'completedAt',
        sortOrder: 'desc',
      }),
      { pollActive: false },
    );
    expect(screen.getByText('Completed')).toBeInTheDocument();
    expect(screen.getByText('Partially Completed')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();

    const completedRow = screen
      .getByText(completedJob.document.baseDocumentCode)
      .closest('tr');
    const partiallyCompletedRow = screen
      .getByText(partiallyCompletedJob.document.baseDocumentCode)
      .closest('tr');
    const failedRow = screen
      .getByText(failedJob.document.baseDocumentCode)
      .closest('tr');

    expect(completedRow).not.toBeNull();
    expect(partiallyCompletedRow).not.toBeNull();
    expect(failedRow).not.toBeNull();
    expect(
      within(completedRow as HTMLTableRowElement).getByRole('link', {
        name: 'Re-run',
      }),
    ).toHaveAttribute('href', expect.stringContaining(`runId=${completedJob.runId}`));
    expect(
      within(partiallyCompletedRow as HTMLTableRowElement).getByRole('link', {
        name: 'Re-run',
      }),
    ).toHaveAttribute(
      'href',
      expect.stringContaining(`runId=${partiallyCompletedJob.runId}`),
    );
    expect(
      within(failedRow as HTMLTableRowElement).queryByRole('link', {
        name: 'Re-run',
      }),
    ).not.toBeInTheDocument();
  });

  it('updates the server history query when pagination advances', async () => {
    renderPage();

    await userEvent.click(screen.getByRole('button', { name: 'Next' }));

    expect(jobsHook).toHaveBeenLastCalledWith(
      expect.objectContaining({
        page: 2,
        pageSize: 20,
        status: terminalOCRJobStatuses,
      }),
      { pollActive: false },
    );
    expect(screen.getByText('Page 2 of 2')).toBeInTheDocument();
  });
});
