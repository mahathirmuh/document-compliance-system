import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '../../providers/ToastProvider';
import { useAuthStore } from '../../store/authStore';
import { superAdminSession } from '../../test/authFixtures';
import { physicalFileFixture } from '../../test/documentFileFixtures';
import {
  languageBlocks,
  languageContainer,
  languageRun,
  languageSummary,
  phase7Ids,
} from '../../test/phase7Fixtures';
import { LanguageResultPage } from './LanguageResultPage';

const documentHook = vi.hoisted(() => vi.fn());
const documentFilesHook = vi.hoisted(() => vi.fn());
const revisionFilesHook = vi.hoisted(() => vi.fn());
const latestHook = vi.hoisted(() => vi.fn());
const runHook = vi.hoisted(() => vi.fn());
const summaryHook = vi.hoisted(() => vi.fn());
const containersHook = vi.hoisted(() => vi.fn());
const blocksHook = vi.hoisted(() => vi.fn());
const historyHook = vi.hoisted(() => vi.fn());
const jobsHook = vi.hoisted(() => vi.fn());
const languageMutations = vi.hoisted(() => ({
  redetect: { mutateAsync: vi.fn(), isPending: false },
  export: { mutateAsync: vi.fn(), isPending: false },
}));

vi.mock('../../hooks/useDocument', () => ({
  useDocument: () => documentHook(),
}));

vi.mock('../../hooks/useDocumentFiles', () => ({
  useDocumentFiles: () => documentFilesHook(),
  useRevisionFiles: () => revisionFilesHook(),
}));

vi.mock('../../hooks/useLanguageDetection', () => ({
  useLanguageDetectionMutations: () => languageMutations,
}));

vi.mock('../../hooks/useLanguageDetectionJobs', () => ({
  useLanguageDetectionJobs: (params: object, options: object) =>
    jobsHook(params, options),
}));

vi.mock('../../hooks/useLanguageResults', () => ({
  useLatestLanguageDetection: (fileId: string | null, enabled: boolean) =>
    latestHook(fileId, enabled),
  useLanguageDetectionRun: (runId: string | null, enabled: boolean) =>
    runHook(runId, enabled),
  useLanguageSummary: (runId: string | null, enabled: boolean) =>
    summaryHook(runId, enabled),
  useLanguageContainers: (runId: string | null, params: object, enabled: boolean) =>
    containersHook(runId, params, enabled),
  useLanguageBlocks: (runId: string | null, params: object, enabled: boolean) =>
    blocksHook(runId, params, enabled),
  useLanguageDetectionHistory: (
    fileId: string | null,
    params: object,
    enabled: boolean,
  ) => historyHook(fileId, params, enabled),
}));

const revision = {
  id: phase7Ids.revision,
  revisionCode: 'Rev.007',
};

const currentFile = {
  ...physicalFileFixture,
  id: phase7Ids.file,
  documentId: phase7Ids.document,
  documentRevisionId: phase7Ids.revision,
  originalFilename: 'MTI-HRM-SOP-007_Rev.007.pdf',
};

const paginated = <TItem,>(
  items: TItem[],
  {
    page = 1,
    pageSize = 100,
    totalItems = items.length,
    totalPages = totalItems > 0 ? 1 : 0,
  }: {
    page?: number;
    pageSize?: number;
    totalItems?: number;
    totalPages?: number;
  } = {},
) => ({
  items,
  page,
  pageSize,
  totalItems,
  totalPages,
});

const renderPage = () =>
  render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: { queries: { retry: false } },
        })
      }
    >
      <MemoryRouter
        initialEntries={[
          `/documents/${phase7Ids.document}/revisions/${phase7Ids.revision}/language-results?runId=${phase7Ids.languageRun}`,
        ]}
      >
        <ToastProvider>
          <Routes>
            <Route
              path="/documents/:documentId/revisions/:revisionId/language-results"
              element={<LanguageResultPage />}
            />
          </Routes>
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );

describe('LanguageResultPage container pagination', () => {
  beforeEach(() => {
    useAuthStore.getState().setAuth(superAdminSession);
    documentHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        id: phase7Ids.document,
        baseDocumentCode: 'MTI-HRM-SOP-007',
        title: 'Multilingual Document Control',
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
      data: languageRun,
    });
    summaryHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: languageSummary,
    });
    containersHook.mockImplementation(
      (_runId: string | null, params: { page: number }) => ({
        isLoading: false,
        error: null,
        data:
          params.page === 1
            ? paginated([languageContainer], {
                page: 1,
                pageSize: 500,
                totalItems: 501,
                totalPages: 2,
              })
            : paginated(
                [
                  {
                    ...languageContainer,
                    id: '10000000-0000-4000-8000-000000000098',
                    containerId: '10000000-0000-4000-8000-000000000097',
                    containerIndex: 501,
                    containerName: 'Page 501',
                  },
                ],
                {
                  page: 2,
                  pageSize: 500,
                  totalItems: 501,
                  totalPages: 2,
                },
              ),
      }),
    );
    blocksHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: paginated(languageBlocks),
    });
    historyHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: paginated([]),
    });
    jobsHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: paginated([], { pageSize: 10 }),
    });
  });

  it('loads the next bounded container page and updates filter options', async () => {
    renderPage();

    expect(screen.queryByText('Page 501')).not.toBeInTheDocument();
    expect(containersHook).toHaveBeenCalledWith(
      phase7Ids.languageRun,
      { page: 1, pageSize: 500 },
      true,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Next container page' }));

    expect(containersHook).toHaveBeenLastCalledWith(
      phase7Ids.languageRun,
      { page: 2, pageSize: 500 },
      true,
    );
    expect(screen.getAllByText('Page 501').length).toBeGreaterThan(0);
    expect(screen.getByRole('option', { name: 'Page 501' })).toBeInTheDocument();
  });

  it('paginates language detection history beyond the first ten runs', async () => {
    historyHook.mockImplementation(
      (_fileId: string | null, params: { page: number }) => ({
        isLoading: false,
        error: null,
        data: paginated(
          [
            {
              id:
                params.page === 1
                  ? phase7Ids.languageRun
                  : '10000000-0000-4000-8000-000000000099',
              jobId: phase7Ids.languageJob,
              detectorName: 'hybrid-fasttext-unicode',
              detectorVersion: '1.0.0',
              status: 'COMPLETED',
              sourceContentHash: 'd'.repeat(64),
              totalBlocks: 2,
              detectedBlocks: 2,
              unknownBlocks: 0,
              averageConfidence: 0.9,
              requestedBy: null,
              redetectionReason: null,
              completedAt: '2026-07-25T12:02:15+08:00',
              isLatest: params.page === 1,
            },
          ],
          {
            page: params.page,
            pageSize: 10,
            totalItems: 11,
            totalPages: 2,
          },
        ),
      }),
    );
    renderPage();

    expect(historyHook).toHaveBeenCalledWith(
      phase7Ids.file,
      { page: 1, pageSize: 10 },
      true,
    );
    expect(screen.getByText('Page 1 of 2 · 11 runs')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Next history page' }));

    expect(historyHook).toHaveBeenLastCalledWith(
      phase7Ids.file,
      { page: 2, pageSize: 10 },
      true,
    );
    expect(screen.getByText('Page 2 of 2 · 11 runs')).toBeInTheDocument();
  });
});
