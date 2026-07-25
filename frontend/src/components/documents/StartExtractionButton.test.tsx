import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { StartExtractionButton } from './StartExtractionButton';
import { ToastProvider } from '../../providers/ToastProvider';
import { useAuthStore } from '../../store/authStore';
import { superAdminSession } from '../../test/authFixtures';
import { extractionIds } from '../../test/extractionFixtures';

const startMutation = vi.hoisted(() => ({
  mutateAsync: vi.fn(),
  isPending: false,
}));

vi.mock('../../hooks/useExtraction', () => ({
  useExtractionMutations: () => ({
    start: startMutation,
  }),
}));

describe('StartExtractionButton', () => {
  it('queues the current file and reports the returned job', async () => {
    useAuthStore.getState().setAuth(superAdminSession);
    startMutation.mutateAsync.mockResolvedValue({
      jobId: extractionIds.job,
      status: 'QUEUED',
      progress: 0,
      documentFileId: extractionIds.file,
      reusedExistingResult: false,
      runId: null,
    });
    const onQueued = vi.fn();
    render(
      <ToastProvider>
        <StartExtractionButton fileId={extractionIds.file} onQueued={onQueued} />
      </ToastProvider>,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Extract Content' }));

    expect(startMutation.mutateAsync).toHaveBeenCalledWith({
      documentFileId: extractionIds.file,
    });
    expect(onQueued).toHaveBeenCalledWith(
      expect.objectContaining({ jobId: extractionIds.job }),
    );
    expect(await screen.findByText('Extraction queued')).toBeInTheDocument();
  });

  it('does not render without the extraction permission', () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      permissions: ['documents:view'],
    });
    render(
      <ToastProvider>
        <StartExtractionButton fileId={extractionIds.file} />
      </ToastProvider>,
    );

    expect(
      screen.queryByRole('button', { name: 'Extract Content' }),
    ).not.toBeInTheDocument();
  });
});
