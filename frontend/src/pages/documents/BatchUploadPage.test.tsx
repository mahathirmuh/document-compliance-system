import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '../../providers/ToastProvider';
import { useAuthStore } from '../../store/authStore';
import { superAdminSession } from '../../test/authFixtures';
import { uploadItemFixture } from '../../test/documentFileFixtures';
import type {
  UploadConfirmationResult,
  UploadPreviewResponse,
} from '../../types/documentUpload';
import { supportedDocumentMimeTypes } from '../../types/documentFile';
import { BatchUploadPage } from './BatchUploadPage';

const workflow = vi.hoisted(() => ({
  progress: 0,
  fileProgress: [] as number[],
  uploadPending: false,
  confirmPending: false,
  cancelPending: false,
  upload: vi.fn(),
  confirm: vi.fn(),
  cancel: vi.fn(),
  reset: vi.fn(),
}));

vi.mock('../../hooks/useBatchDocumentUpload', () => ({
  useBatchDocumentUpload: () => ({
    progress: workflow.progress,
    fileProgress: workflow.fileProgress,
    upload: {
      isPending: workflow.uploadPending,
      mutateAsync: workflow.upload,
      reset: vi.fn(),
    },
    confirm: {
      isPending: workflow.confirmPending,
      mutateAsync: workflow.confirm,
      reset: vi.fn(),
    },
    cancel: {
      isPending: workflow.cancelPending,
      mutateAsync: workflow.cancel,
      reset: vi.fn(),
    },
    reset: workflow.reset,
  }),
}));

vi.mock('../../components/documents/ManualIdentificationForm', () => ({
  ManualIdentificationForm: () => <div>Batch metadata correction</div>,
}));

const invalidItem = {
  ...uploadItemFixture,
  uploadItemId: '66666666-6666-4666-8666-666666666666',
  originalFilename: 'unsafe.pptx',
  sanitizedFilename: 'unsafe.pptx',
  fileExtension: null,
  mimeType: null,
  detectedMimeType: null,
  fileSize: null,
  sha256Hash: null,
  identificationStatus: 'INVALID' as const,
  proposedAction: 'SKIP' as const,
  parsedMetadata: null,
  matchedDocument: null,
  matchedRevision: null,
  errors: ['File type is not supported.'],
  status: 'FAILED' as const,
};

const batchPreview: UploadPreviewResponse = {
  sessionId: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  sessionType: 'BATCH',
  status: 'READY_FOR_CONFIRMATION',
  totalFiles: 2,
  totalSize: 1_250,
  expiresAt: new Date(Date.now() + 3_600_000).toISOString(),
  committedAt: null,
  cancelledAt: null,
  items: [uploadItemFixture, invalidItem],
};

const batchResult: UploadConfirmationResult = {
  sessionId: batchPreview.sessionId,
  status: 'PARTIALLY_COMMITTED',
  total: 2,
  committed: 1,
  skipped: 1,
  failed: 0,
  documentsCreated: 0,
  revisionsCreated: 0,
  filesAttached: 1,
  filesReplaced: 0,
  items: [
    {
      uploadItemId: uploadItemFixture.uploadItemId,
      action: 'ATTACH_TO_EXISTING_REVISION',
      status: 'COMMITTED',
      documentId: uploadItemFixture.matchedDocument?.id ?? null,
      revisionId: uploadItemFixture.matchedRevision?.id ?? null,
      documentFileId: '77777777-7777-4777-8777-777777777777',
      baseDocumentCode: 'MTI-HRM-POL-001',
      revisionCode: 'Rev.000',
      fileStatus: 'AVAILABLE',
      error: null,
    },
    {
      uploadItemId: invalidItem.uploadItemId,
      action: 'SKIP',
      status: 'SKIPPED',
      documentId: null,
      revisionId: null,
      documentFileId: null,
      baseDocumentCode: null,
      revisionCode: null,
      fileStatus: null,
      error: null,
    },
  ],
};

const renderPage = () =>
  render(
    <MemoryRouter>
      <ToastProvider>
        <BatchUploadPage />
      </ToastProvider>
    </MemoryRouter>,
  );

const selectFiles = (): void => {
  fireEvent.change(screen.getByLabelText('Browse document files'), {
    target: {
      files: [
        new File(['one'], 'one.pdf', { type: supportedDocumentMimeTypes.pdf }),
        new File(['two'], 'two.docx', { type: supportedDocumentMimeTypes.docx }),
      ],
    },
  });
};

beforeEach(() => {
  useAuthStore.getState().setAuth(superAdminSession);
});

afterEach(() => {
  workflow.progress = 0;
  workflow.fileProgress = [];
  workflow.uploadPending = false;
  workflow.confirmPending = false;
  workflow.cancelPending = false;
  workflow.upload.mockReset();
  workflow.confirm.mockReset();
  workflow.cancel.mockReset();
  workflow.reset.mockReset();
});

describe('BatchUploadPage', () => {
  it('shows a multi-file list and overall limits before upload', () => {
    renderPage();
    selectFiles();

    expect(screen.getByText('one.pdf')).toBeInTheDocument();
    expect(screen.getByText('two.docx')).toBeInTheDocument();
    expect(screen.getByText(/2\/50 files selected/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Upload and Identify' })).toBeEnabled();
  });

  it('filters partial identification results and disables an invalid item', async () => {
    workflow.upload.mockResolvedValue(batchPreview);
    renderPage();
    selectFiles();
    fireEvent.click(screen.getByRole('button', { name: 'Upload and Identify' }));

    expect(await screen.findByText('Identification results')).toBeInTheDocument();
    expect(screen.getByText('unsafe.pptx')).toBeInTheDocument();
    expect(screen.getByLabelText('Select unsafe.pptx')).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Result'), {
      target: { value: 'INVALID' },
    });
    expect(screen.getByText('unsafe.pptx')).toBeInTheDocument();
    expect(screen.queryByText('MTI-HRM-POL-001_Rev.000.pdf')).not.toBeInTheDocument();
  });

  it('applies one permitted bulk action only to selected valid rows', async () => {
    workflow.upload.mockResolvedValue(batchPreview);
    renderPage();
    selectFiles();
    fireEvent.click(screen.getByRole('button', { name: 'Upload and Identify' }));
    await screen.findByText('Identification results');

    fireEvent.change(screen.getByLabelText('Bulk action'), {
      target: { value: 'CREATE_DOCUMENT_AND_REVISION' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Apply to Selected' }));

    expect(
      screen.getByLabelText(`Action for ${uploadItemFixture.originalFilename}`),
    ).toHaveValue('CREATE_DOCUMENT_AND_REVISION');
    expect(screen.getByLabelText('Action for unsafe.pptx')).toHaveValue('SKIP');
  });

  it('confirms selected valid files and displays a partial result summary', async () => {
    workflow.upload.mockResolvedValue(batchPreview);
    workflow.confirm.mockResolvedValue(batchResult);
    renderPage();
    selectFiles();
    fireEvent.click(screen.getByRole('button', { name: 'Upload and Identify' }));
    await screen.findByText('Identification results');
    fireEvent.click(screen.getByRole('button', { name: 'Confirm 1 Selected' }));

    expect(await screen.findByText('Batch Upload Result')).toBeInTheDocument();
    expect(screen.getByText('Confirmation completed')).toBeInTheDocument();
    expect(screen.getByText('Committed')).toBeInTheDocument();
    expect(screen.getByText('Skipped')).toBeInTheDocument();
    expect(workflow.confirm).toHaveBeenCalledWith(
      expect.objectContaining({
        sessionId: batchPreview.sessionId,
        payload: expect.objectContaining({
          items: expect.arrayContaining([
            expect.objectContaining({
              uploadItemId: invalidItem.uploadItemId,
              action: 'SKIP',
            }),
          ]),
        }),
      }),
    );
  });

  it('cancels the temporary session before starting over', async () => {
    workflow.upload.mockResolvedValue(batchPreview);
    workflow.cancel.mockResolvedValue({
      ...batchPreview,
      status: 'CANCELLED',
      cancelledAt: new Date().toISOString(),
    });
    renderPage();
    selectFiles();
    fireEvent.click(screen.getByRole('button', { name: 'Upload and Identify' }));
    await screen.findByText('Identification results');

    fireEvent.click(screen.getByRole('button', { name: 'Start Over' }));

    expect(workflow.cancel).toHaveBeenCalledWith(batchPreview.sessionId);
    expect(
      await screen.findByRole('button', { name: 'Upload and Identify' }),
    ).toBeInTheDocument();
  });

  it('shows expiry and blocks confirmation for an expired batch preview', async () => {
    workflow.upload.mockResolvedValue({
      ...batchPreview,
      expiresAt: new Date(Date.now() - 60_000).toISOString(),
    });
    renderPage();
    selectFiles();
    fireEvent.click(screen.getByRole('button', { name: 'Upload and Identify' }));

    expect(await screen.findByText('Batch upload session expired')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Confirm 1 Selected' })).toBeDisabled();
  });
});
