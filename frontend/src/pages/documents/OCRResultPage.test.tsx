import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '../../providers/ToastProvider';
import { useAuthStore } from '../../store/authStore';
import { superAdminSession } from '../../test/authFixtures';
import { physicalFileFixture } from '../../test/documentFileFixtures';
import { ocrBlocks, ocrPage, ocrRun, phase7Ids } from '../../test/phase7Fixtures';
import { OCRResultPage } from './OCRResultPage';

const documentHook = vi.hoisted(() => vi.fn());
const documentFilesHook = vi.hoisted(() => vi.fn());
const revisionFilesHook = vi.hoisted(() => vi.fn());
const latestHook = vi.hoisted(() => vi.fn());
const runHook = vi.hoisted(() => vi.fn());
const pagesHook = vi.hoisted(() => vi.fn());
const pageHook = vi.hoisted(() => vi.fn());
const blocksHook = vi.hoisted(() => vi.fn());
const jobsHook = vi.hoisted(() => vi.fn());
const ocrMutations = vi.hoisted(() => ({
  reocr: { mutateAsync: vi.fn(), isPending: false },
  export: { mutateAsync: vi.fn(), isPending: false },
}));

vi.mock('../../hooks/useDocument', () => ({
  useDocument: () => documentHook(),
}));

vi.mock('../../hooks/useDocumentFiles', () => ({
  useDocumentFiles: () => documentFilesHook(),
  useRevisionFiles: () => revisionFilesHook(),
}));

vi.mock('../../hooks/useOCR', () => ({
  useLatestOCR: (fileId: string | null, enabled: boolean) =>
    latestHook(fileId, enabled),
  useOCRRun: (runId: string | null, enabled: boolean) => runHook(runId, enabled),
  useOCRPages: (runId: string | null, params: object, enabled: boolean) =>
    pagesHook(runId, params, enabled),
  useOCRPage: (runId: string | null, pageNumber: number | null, enabled: boolean) =>
    pageHook(runId, pageNumber, enabled),
  useOCRBlocks: (runId: string | null, params: object, enabled: boolean) =>
    blocksHook(runId, params, enabled),
  useOCRMutations: () => ocrMutations,
}));

vi.mock('../../hooks/useOCRJobs', () => ({
  useOCRJobs: (params: object, options: object) => jobsHook(params, options),
}));

const currentFile = {
  ...physicalFileFixture,
  id: phase7Ids.file,
  documentId: phase7Ids.document,
  documentRevisionId: phase7Ids.revision,
  originalFilename: ocrRun.file.filename,
  sanitizedFilename: ocrRun.file.filename,
};

const revision = {
  id: phase7Ids.revision,
  revisionCode: ocrRun.revision.revisionCode,
};

const renderPage = () =>
  render(
    <MemoryRouter
      initialEntries={[
        `/documents/${phase7Ids.document}/revisions/${phase7Ids.revision}/ocr-results?runId=${phase7Ids.run}`,
      ]}
    >
      <ToastProvider>
        <Routes>
          <Route
            path="/documents/:documentId/revisions/:revisionId/ocr-results"
            element={<OCRResultPage />}
          />
        </Routes>
      </ToastProvider>
    </MemoryRouter>,
  );

describe('OCRResultPage block filters', () => {
  beforeEach(() => {
    useAuthStore.getState().setAuth(superAdminSession);
    documentHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        id: phase7Ids.document,
        baseDocumentCode: ocrRun.document.baseDocumentCode,
        title: ocrRun.document.title,
        isArchived: false,
        revisions: [revision],
        currentRevision: revision,
      },
    });
    documentFilesHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: [],
    });
    revisionFilesHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: [currentFile],
    });
    latestHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: null,
    });
    runHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: ocrRun,
    });
    pagesHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        items: [ocrPage],
        page: 1,
        pageSize: 500,
        totalItems: 1,
        totalPages: 1,
      },
    });
    pageHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: { page: ocrPage, blocks: ocrBlocks },
    });
    blocksHook.mockImplementation(
      (_runId: string | null, params: { page: number }) => ({
        isLoading: false,
        error: null,
        data: {
          items: ocrBlocks,
          page: params.page,
          pageSize: 500,
          totalItems: 501,
          totalPages: 2,
        },
      }),
    );
    jobsHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        items: [],
        page: 1,
        pageSize: 10,
        totalItems: 0,
        totalPages: 0,
      },
    });
    ocrMutations.reocr.mutateAsync.mockReset();
    ocrMutations.export.mutateAsync.mockReset();
  });

  it('sends exact server confidence bounds and preserves them across block pages', async () => {
    renderPage();

    await waitFor(() => {
      expect(blocksHook).toHaveBeenLastCalledWith(
        phase7Ids.run,
        {
          pageNumber: ocrPage.pageNumber,
          page: 1,
          pageSize: 500,
        },
        true,
      );
    });

    await userEvent.selectOptions(screen.getByLabelText('OCR confidence'), 'HIGH');
    expect(blocksHook).toHaveBeenLastCalledWith(
      phase7Ids.run,
      {
        pageNumber: ocrPage.pageNumber,
        minimumConfidence: ocrRun.reviewConfidenceThreshold,
        page: 1,
        pageSize: 500,
      },
      true,
    );

    await userEvent.selectOptions(screen.getByLabelText('OCR confidence'), 'LOW');
    expect(blocksHook).toHaveBeenLastCalledWith(
      phase7Ids.run,
      {
        pageNumber: ocrPage.pageNumber,
        maximumConfidence: Math.max(0, ocrRun.lowConfidenceThreshold - Number.EPSILON),
        page: 1,
        pageSize: 500,
      },
      true,
    );

    await userEvent.selectOptions(screen.getByLabelText('OCR confidence'), 'REVIEW');
    expect(blocksHook).toHaveBeenLastCalledWith(
      phase7Ids.run,
      {
        pageNumber: ocrPage.pageNumber,
        minimumConfidence: ocrRun.lowConfidenceThreshold,
        maximumConfidence: Math.max(
          0,
          ocrRun.reviewConfidenceThreshold - Number.EPSILON,
        ),
        page: 1,
        pageSize: 500,
      },
      true,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(blocksHook).toHaveBeenLastCalledWith(
      phase7Ids.run,
      {
        pageNumber: ocrPage.pageNumber,
        minimumConfidence: ocrRun.lowConfidenceThreshold,
        maximumConfidence: Math.max(
          0,
          ocrRun.reviewConfidenceThreshold - Number.EPSILON,
        ),
        page: 2,
        pageSize: 500,
      },
      true,
    );
    expect(screen.getByText(/Block page 2 of 2/)).toBeInTheDocument();
  });
});
