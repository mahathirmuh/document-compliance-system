import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '../../providers/ToastProvider';
import { useAuthStore } from '../../store/authStore';
import { superAdminSession } from '../../test/authFixtures';
import { uploadItemFixture } from '../../test/documentFileFixtures';
import type { UploadPreviewResponse } from '../../types/documentUpload';
import { supportedDocumentMimeTypes } from '../../types/documentFile';
import { UploadDocumentPage } from './UploadDocumentPage';

const workflow = vi.hoisted(() => ({
  progress: 0,
  uploadPending: false,
  upload: vi.fn(),
  confirm: vi.fn(),
  cancel: vi.fn(),
  reset: vi.fn(),
}));

const contextDocument = vi.hoisted(() => ({
  data: undefined as
    { isArchived: boolean; baseDocumentCode: string; title: string } | undefined,
  isLoading: false,
  error: null as Error | null,
}));

vi.mock('../../hooks/useDocument', () => ({
  useDocument: () => contextDocument,
}));

vi.mock('../../hooks/useDocumentUpload', () => ({
  useDocumentUpload: () => ({
    progress: workflow.progress,
    upload: {
      isPending: workflow.uploadPending,
      mutateAsync: workflow.upload,
      reset: vi.fn(),
    },
    confirm: {
      isPending: false,
      mutateAsync: workflow.confirm,
      reset: vi.fn(),
    },
    cancel: {
      isPending: false,
      mutateAsync: workflow.cancel,
      reset: vi.fn(),
    },
    reset: workflow.reset,
  }),
}));

vi.mock('../../components/documents/ManualIdentificationForm', () => ({
  ManualIdentificationForm: ({ initialAction }: { initialAction?: string | null }) => (
    <div>Manual metadata form: {initialAction}</div>
  ),
}));

const preview = (expiresAt: string): UploadPreviewResponse => ({
  sessionId: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  sessionType: 'SINGLE',
  status: 'READY_FOR_CONFIRMATION',
  totalFiles: 1,
  totalSize: 1_250,
  expiresAt,
  committedAt: null,
  cancelledAt: null,
  items: [uploadItemFixture],
});

const renderPage = (initialEntry = '/documents/upload') =>
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <ToastProvider>
        <UploadDocumentPage />
      </ToastProvider>
    </MemoryRouter>,
  );

const choosePdf = (): void => {
  fireEvent.change(screen.getByLabelText('Browse document files'), {
    target: {
      files: [
        new File(['valid'], 'policy.pdf', {
          type: supportedDocumentMimeTypes.pdf,
        }),
      ],
    },
  });
};

beforeEach(() => {
  useAuthStore.getState().setAuth(superAdminSession);
});

afterEach(() => {
  workflow.progress = 0;
  workflow.uploadPending = false;
  workflow.upload.mockReset();
  workflow.confirm.mockReset();
  workflow.cancel.mockReset();
  workflow.reset.mockReset();
  contextDocument.data = undefined;
  contextDocument.isLoading = false;
  contextDocument.error = null;
});

describe('UploadDocumentPage', () => {
  it('displays Axios upload progress without polling', () => {
    workflow.uploadPending = true;
    workflow.progress = 47;
    renderPage();

    expect(screen.getByText('Uploading and validating')).toBeInTheDocument();
    expect(screen.getByText('47%')).toBeInTheDocument();
    expect(
      screen.getByRole('progressbar', { name: 'Uploading and validating' }),
    ).toHaveAttribute('aria-valuenow', '47');
  });

  it('shows identification and lets the user select a manual create action', async () => {
    workflow.upload.mockResolvedValue(
      preview(new Date(Date.now() + 3_600_000).toISOString()),
    );
    renderPage();
    choosePdf();
    fireEvent.click(screen.getByRole('button', { name: 'Upload and Identify' }));

    expect(await screen.findByText('Identification result')).toBeInTheDocument();
    expect(screen.getByText('Worker Policy')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Review Action' }));
    fireEvent.click(
      screen.getByRole('radio', {
        name: 'Create document and first revision',
      }),
    );
    fireEvent.click(screen.getByRole('button', { name: 'Continue to Metadata' }));

    expect(
      screen.getByText('Manual metadata form: CREATE_DOCUMENT_AND_REVISION'),
    ).toBeInTheDocument();
  });

  it('blocks confirmation and explains when a session has expired', async () => {
    workflow.upload.mockResolvedValue(
      preview(new Date(Date.now() - 60_000).toISOString()),
    );
    renderPage();
    choosePdf();
    fireEvent.click(screen.getByRole('button', { name: 'Upload and Identify' }));

    expect(await screen.findByText('Upload session expired')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Review Action' })).toBeDisabled();
    expect(screen.getByText(/Confirmation is no longer allowed/)).toBeInTheDocument();
  });

  it('blocks direct contextual upload when the target document is archived', () => {
    contextDocument.data = {
      isArchived: true,
      baseDocumentCode: 'MTI-HRM-POL-001',
      title: 'Archived Policy',
    };
    renderPage(
      '/documents/upload?documentId=22222222-2222-4222-8222-222222222222&revisionId=33333333-3333-4333-8333-333333333333',
    );

    expect(screen.getByText('Archived document upload blocked')).toBeInTheDocument();
    expect(screen.getByLabelText('Browse document files')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Upload and Identify' })).toBeDisabled();
    expect(workflow.upload).not.toHaveBeenCalled();
  });
});
