import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '../../providers/ToastProvider';
import { useAuthStore } from '../../store/authStore';
import { superAdminSession } from '../../test/authFixtures';
import { physicalFileFixture } from '../../test/documentFileFixtures';
import {
  extractedBlocks,
  extractedTable,
  extractionIds,
  extractionRun,
  failedExtractionJob,
  pdfContainers,
} from '../../test/extractionFixtures';
import type {
  ExtractedBlock,
  ExtractedContainer,
  ExtractionRun,
} from '../../types/extractedContent';
import { ExtractedContentPage } from './ExtractedContentPage';

const documentHook = vi.hoisted(() => vi.fn());
const documentFilesHook = vi.hoisted(() => vi.fn());
const revisionFilesHook = vi.hoisted(() => vi.fn());
const latestHook = vi.hoisted(() => vi.fn());
const runHook = vi.hoisted(() => vi.fn());
const jobsHook = vi.hoisted(() => vi.fn());
const jobHook = vi.hoisted(() => vi.fn());
const containersHook = vi.hoisted(() => vi.fn());
const blocksHook = vi.hoisted(() => vi.fn());
const tablesHook = vi.hoisted(() => vi.fn());
const searchHook = vi.hoisted(() => vi.fn());
const exportMutation = vi.hoisted(() => ({
  mutateAsync: vi.fn(),
  isPending: false,
}));
const reextractMutation = vi.hoisted(() => ({
  mutateAsync: vi.fn(),
  isPending: false,
}));
const startMutation = vi.hoisted(() => ({
  mutateAsync: vi.fn(),
  isPending: false,
}));

vi.mock('../../hooks/useDocument', () => ({
  useDocument: () => documentHook(),
}));
vi.mock('../../hooks/useDocumentFiles', () => ({
  useDocumentFiles: () => documentFilesHook(),
  useRevisionFiles: () => revisionFilesHook(),
}));
vi.mock('../../hooks/useExtractionJobs', () => ({
  useExtractionJobs: (params: object, options: object) => jobsHook(params, options),
}));
vi.mock('../../hooks/useExtraction', () => ({
  useExtractionJob: (id: string | null, options: object) => jobHook(id, options),
  useExtractionMutations: () => ({
    reextract: reextractMutation,
    start: startMutation,
  }),
}));
vi.mock('../../hooks/useExtractedContent', () => ({
  useLatestExtraction: (fileId: string | null, enabled: boolean) =>
    latestHook(fileId, enabled),
  useExtractionRun: (runId: string | null, enabled: boolean) => runHook(runId, enabled),
  useExtractionContainers: (runId: string | null, params: object, enabled: boolean) =>
    containersHook(runId, params, enabled),
  useExtractionBlocks: (runId: string | null, params: object, enabled: boolean) =>
    blocksHook(runId, params, enabled),
  useExtractionTables: (runId: string | null, params: object, enabled: boolean) =>
    tablesHook(runId, params, enabled),
  useExtractedContentSearch: (
    runId: string | null,
    params: { q: string },
    enabled: boolean,
  ) => searchHook(runId, params, enabled),
  useExtractionExport: () => exportMutation,
}));

const revision = {
  id: extractionIds.revision,
  revisionCode: 'Rev.000',
};
const currentFile = {
  ...physicalFileFixture,
  id: extractionIds.file,
  documentId: extractionIds.document,
  documentRevisionId: extractionIds.revision,
  originalFilename: extractionRun.file.filename,
  fileExtension: 'pdf' as const,
};

const renderPage = (search = '') => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter
        initialEntries={[
          `/documents/${extractionIds.document}/revisions/${extractionIds.revision}/extracted-content${search}`,
        ]}
      >
        <ToastProvider>
          <Routes>
            <Route
              path="/documents/:documentId/revisions/:revisionId/extracted-content"
              element={<ExtractedContentPage />}
            />
          </Routes>
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

const paginated = <TItem,>(items: TItem[], totalPages = 1) => ({
  items,
  page: 1,
  pageSize: 100,
  totalItems: items.length,
  totalPages,
});

describe('ExtractedContentPage', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  beforeEach(() => {
    useAuthStore.getState().setAuth(superAdminSession);
    documentHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        id: extractionIds.document,
        baseDocumentCode: extractionRun.document.baseDocumentCode,
        title: extractionRun.document.title,
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
      data: extractionRun,
    });
    runHook.mockReturnValue({ isLoading: false, error: null, data: null });
    jobsHook.mockReturnValue({
      data: { items: [], page: 1, pageSize: 10, totalItems: 0, totalPages: 0 },
    });
    jobHook.mockReturnValue({ data: null });
    containersHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: paginated(pdfContainers),
    });
    blocksHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: paginated(extractedBlocks),
    });
    tablesHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: paginated([extractedTable]),
    });
    searchHook.mockImplementation(
      (_runId: string | null, params: { q: string }, enabled: boolean) => ({
        error: null,
        data:
          enabled && params.q.length >= 2
            ? {
                query: params.q,
                totalMatches: 1,
                items: [
                  {
                    blockId: extractedBlocks[0]!.id,
                    blockOrder: extractedBlocks[0]!.blockOrder,
                    containerId: pdfContainers[0]!.id,
                    containerIndex: pdfContainers[0]!.containerIndex,
                    containerName: 'Page 1',
                    sourceReference: extractedBlocks[0]!.sourceReference,
                    blockType: extractedBlocks[0]!.blockType,
                    snippet: 'Document control procedure',
                    location: { page: 1 },
                  },
                ],
              }
            : undefined,
      }),
    );
    exportMutation.mutateAsync.mockResolvedValue({
      blob: new Blob(['export']),
      fileName: 'extraction.json',
    });
    reextractMutation.mutateAsync.mockResolvedValue({
      jobId: extractionIds.job,
      status: 'QUEUED',
      progress: 0,
      documentFileId: extractionIds.file,
      reusedExistingResult: false,
      runId: null,
    });
    startMutation.mutateAsync.mockResolvedValue({
      jobId: extractionIds.job,
      status: 'QUEUED',
      progress: 0,
      documentFileId: extractionIds.file,
      reusedExistingResult: false,
      runId: null,
    });
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:test'),
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: vi.fn(),
    });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
  });

  it('shows completed PDF pages, blocks, bounding metadata, and safe search', async () => {
    renderPage();

    expect(screen.getByText('Document Control Procedure')).toBeInTheDocument();
    expect(screen.getAllByText('Pages').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByRole('button', { name: /Page 2/ })).toBeInTheDocument();
    expect(screen.getByText('PDF:page=1:block=1')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Search extracted content'), {
      target: { value: 'document' },
    });
    await waitFor(
      () =>
        expect(searchHook).toHaveBeenLastCalledWith(
          extractionIds.run,
          expect.objectContaining({ q: 'document' }),
          true,
        ),
      { timeout: 1_500 },
    );
    expect(await screen.findByText('1 results')).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole('button', {
        name: /Page 1 Document control procedure/i,
      }),
    );

    await userEvent.click(screen.getByRole('button', { name: 'Raw Text' }));
    expect(
      screen.getByText(/Raw text is assembled from the current server-side page/),
    ).toBeInTheDocument();
    expect(screen.getByText(/A safe <script>alert\(1\)<\/script>/)).toBeInTheDocument();
  });

  it('does not request job-list tracking for a content-only viewer', () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      user: {
        ...superAdminSession.user,
        role: 'VIEWER',
      },
      permissions: ['documents:view', 'documents:view_extracted_content'],
    });
    renderPage();

    expect(jobsHook).toHaveBeenLastCalledWith(
      expect.any(Object),
      expect.objectContaining({ enabled: false, pollActive: true }),
    );
    expect(latestHook).toHaveBeenLastCalledWith(extractionIds.file, true);
  });

  it('opens a search result on its server-side container and block pages', async () => {
    searchHook.mockImplementation(
      (_runId: string | null, params: { q: string }, enabled: boolean) => ({
        error: null,
        data:
          enabled && params.q.length >= 2
            ? {
                query: params.q,
                totalMatches: 1,
                items: [
                  {
                    blockId: extractedBlocks[0]!.id,
                    blockOrder: 201,
                    containerId: pdfContainers[0]!.id,
                    containerIndex: 101,
                    containerName: 'Page 101',
                    sourceReference: 'PDF:page=101:block=201',
                    blockType: 'TEXT' as const,
                    snippet: 'Remote governance result',
                    location: { page: 101 },
                  },
                ],
              }
            : undefined,
      }),
    );
    renderPage();

    fireEvent.change(screen.getByLabelText('Search extracted content'), {
      target: { value: 'governance' },
    });
    await userEvent.click(
      await screen.findByRole(
        'button',
        { name: /Page 101 Remote governance result/i },
        { timeout: 1_500 },
      ),
    );

    expect(containersHook).toHaveBeenLastCalledWith(
      extractionIds.run,
      expect.objectContaining({ page: 2, pageSize: 100 }),
      true,
    );
    expect(blocksHook).toHaveBeenLastCalledWith(
      extractionIds.run,
      expect.objectContaining({
        containerId: pdfContainers[0]!.id,
        page: 3,
        pageSize: 100,
      }),
      true,
    );
  });

  it('finds and focuses an immutable extracted block beyond its original result page', () => {
    const remoteBlock: ExtractedBlock = {
      ...extractedBlocks[0]!,
      blockOrder: 201,
      sourceReference: 'PDF:page=1:block=201',
      text: 'Remote controlled source block',
    };
    runHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: extractionRun,
    });
    blocksHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: paginated([remoteBlock]),
    });

    renderPage(
      `?runId=${extractionIds.run}&containerId=${extractionIds.container}&blockId=${extractionIds.block}&sourceReference=PDF%3Apage%3D1%3Ablock%3D201`,
    );

    expect(runHook).toHaveBeenLastCalledWith(extractionIds.run, true);
    expect(blocksHook).toHaveBeenLastCalledWith(
      extractionIds.run,
      expect.objectContaining({
        containerId: extractionIds.container,
        search: 'PDF:page=1:block=201',
        page: 1,
        pageSize: 100,
      }),
      true,
    );
    expect(
      globalThis.document.getElementById(`block-${extractionIds.block}`),
    ).toHaveClass('bg-amber-50');
    expect(screen.getByRole('status')).toHaveTextContent('immutable extraction run');
  });

  it('navigates to and focuses an OCR block on its PDF page', () => {
    const ocrBlockId = 'aaaaaaaa-2222-4222-8222-222222222222';
    const ocrBlock: ExtractedBlock = {
      ...extractedBlocks[0]!,
      id: ocrBlockId,
      containerId: extractionIds.secondContainer,
      blockType: 'TEXT',
      blockOrder: 4,
      sourceReference: 'OCR:page=2:block=4',
      text: 'OCR source block',
      contentSource: 'OCR',
      ocrConfidence: 0.93,
    };
    runHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: extractionRun,
    });
    blocksHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: paginated([ocrBlock]),
    });

    renderPage(
      `?runId=${extractionIds.run}&ocrBlockId=${ocrBlockId}&page=2&sourceReference=OCR%3Apage%3D2%3Ablock%3D4`,
    );

    expect(blocksHook).toHaveBeenLastCalledWith(
      extractionIds.run,
      expect.objectContaining({
        containerId: extractionIds.secondContainer,
        contentSource: 'OCR',
        search: 'OCR:page=2:block=4',
      }),
      true,
    );
    expect(globalThis.document.getElementById(`block-${ocrBlockId}`)).toHaveClass(
      'bg-amber-50',
    );
    expect(screen.getByRole('status')).toHaveTextContent('page 2');
  });

  it('uses a DOCX container and source reference to focus the exact block', () => {
    const docxContainer: ExtractedContainer = {
      ...pdfContainers[0]!,
      containerType: 'DOCX_BODY',
      name: 'Document Body',
      title: 'Body',
    };
    const docxBlock: ExtractedBlock = {
      ...extractedBlocks[0]!,
      containerId: docxContainer.id,
      sourceReference: 'DOCX:body:p=205',
      text: 'Late document paragraph',
    };
    runHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: { ...extractionRun, extractorType: 'DOCX' } satisfies ExtractionRun,
    });
    containersHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: paginated([docxContainer]),
    });
    blocksHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: paginated([docxBlock]),
    });

    renderPage(
      `?runId=${extractionIds.run}&containerId=${docxContainer.id}&blockId=${docxBlock.id}&sourceReference=DOCX%3Abody%3Ap%3D205`,
    );

    expect(blocksHook).toHaveBeenLastCalledWith(
      extractionIds.run,
      expect.objectContaining({
        containerId: docxContainer.id,
        search: 'DOCX:body:p=205',
      }),
      true,
    );
    expect(globalThis.document.getElementById(`block-${docxBlock.id}`)).toHaveClass(
      'bg-amber-50',
    );
  });

  it('rejects a requested run that is not bound to the route document', () => {
    runHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        ...extractionRun,
        document: {
          ...extractionRun.document,
          id: 'aaaaaaaa-2222-4222-8222-222222222222',
        },
      } satisfies ExtractionRun,
    });
    renderPage(`?runId=${extractionIds.run}`);

    expect(
      screen.getByText(
        'The requested extraction run does not belong to this document or revision.',
      ),
    ).toHaveRole('alert');
    expect(containersHook).toHaveBeenLastCalledWith(null, expect.any(Object), false);
  });

  it('downloads both permission-gated JSON and TXT exports', async () => {
    renderPage();

    await userEvent.click(screen.getByRole('button', { name: 'Export json' }));
    await userEvent.click(screen.getByRole('button', { name: 'Export txt' }));

    expect(exportMutation.mutateAsync).toHaveBeenNthCalledWith(1, {
      runId: extractionIds.run,
      format: 'json',
    });
    expect(exportMutation.mutateAsync).toHaveBeenNthCalledWith(2, {
      runId: extractionIds.run,
      format: 'txt',
    });
  });

  it('keeps an OCR_REQUIRED run available to the merged OCR viewer', () => {
    latestHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        ...extractionRun,
        status: 'OCR_REQUIRED',
        requiresOcr: true,
        hasSelectableText: false,
        totalBlocks: 0,
        totalCharacters: 0,
        totalWords: 0,
      } satisfies ExtractionRun,
    });
    renderPage();

    expect(
      screen.getByText(/Native selectable text was not detected/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/merged viewer shows the latest authorized OCR blocks/i),
    ).toBeInTheDocument();
    expect(screen.getByText('Document Control Procedure')).toBeInTheDocument();
  });

  it('shows an empty state and a controlled failure message', () => {
    latestHook.mockReturnValue({ isLoading: false, error: null, data: null });
    jobsHook.mockReturnValue({
      data: {
        items: [failedExtractionJob],
        page: 1,
        pageSize: 10,
        totalItems: 1,
        totalPages: 1,
      },
    });
    jobHook.mockReturnValue({ data: failedExtractionJob });
    renderPage();

    expect(screen.getByText('No extracted content is available')).toBeInTheDocument();
    expect(
      screen.getByText('This PDF is password-protected and cannot be extracted.'),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Extract Content' })).toBeInTheDocument();
  });

  it('shows DOCX source-order guidance, heading navigation, and tables', async () => {
    const docxContainer: ExtractedContainer = {
      ...pdfContainers[0]!,
      containerType: 'DOCX_BODY',
      name: 'body',
      title: 'Document body',
    };
    latestHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        ...extractionRun,
        extractorType: 'DOCX',
        totalPages: 0,
        totalParagraphs: 2,
        totalTables: 1,
      } satisfies ExtractionRun,
    });
    containersHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: paginated([docxContainer]),
    });
    renderPage();

    expect(
      screen.getByText(/DOCX content is displayed in source order/i),
    ).toBeInTheDocument();
    expect(screen.getByLabelText('Heading')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Tables' }));
    expect(screen.getByText('Table 1')).toBeInTheDocument();
    expect(screen.getByText('Code')).toBeInTheDocument();
  });

  it('paginates large XLSX cell results instead of rendering the entire sheet', async () => {
    const xlsxContainer: ExtractedContainer = {
      ...pdfContainers[0]!,
      containerType: 'XLSX_WORKSHEET',
      name: 'Register',
      title: 'Register',
    };
    const xlsxCell: ExtractedBlock = {
      ...extractedBlocks[0]!,
      blockType: 'FORMULA',
      sourceReference: 'XLSX:sheet=Register:cell=A4',
      text: '=SUM(A1:A3)',
      styleName: null,
      headingLevel: null,
      metadata: { coordinate: 'A4', formula: '=SUM(A1:A3)', cachedValue: 42 },
    };
    latestHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        ...extractionRun,
        extractorType: 'XLSX',
        totalPages: 0,
        totalSheets: 1,
        totalCells: 201,
      } satisfies ExtractionRun,
    });
    containersHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: paginated([xlsxContainer]),
    });
    blocksHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        ...paginated([xlsxCell], 2),
        pageSize: 200,
        totalItems: 201,
      },
    });
    renderPage();

    expect(screen.getByRole('button', { name: /Register/ })).toBeInTheDocument();
    expect(screen.getByText('A4')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(blocksHook).toHaveBeenLastCalledWith(
      extractionIds.run,
      expect.objectContaining({ page: 2, pageSize: 200 }),
      true,
    );
  });

  it('navigates to an XLSX worksheet and focuses the requested cell', () => {
    const xlsxContainer: ExtractedContainer = {
      ...pdfContainers[0]!,
      containerType: 'XLSX_WORKSHEET',
      name: 'Register',
      title: 'Register',
    };
    const xlsxCell: ExtractedBlock = {
      ...extractedBlocks[0]!,
      containerId: xlsxContainer.id,
      blockType: 'CELL',
      sourceReference: 'XLSX:sheet=Register:cell=Z205',
      text: 'Target cell',
      styleName: null,
      headingLevel: null,
      metadata: { coordinate: 'Z205' },
    };
    latestHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        ...extractionRun,
        extractorType: 'XLSX',
        totalPages: 0,
        totalSheets: 1,
      } satisfies ExtractionRun,
    });
    containersHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: paginated([xlsxContainer]),
    });
    blocksHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: paginated([xlsxCell]),
    });

    renderPage(
      '?worksheet=Register&cell=Z205&sourceReference=XLSX%3Asheet%3DRegister%3Acell%3DZ205',
    );

    expect(containersHook).toHaveBeenLastCalledWith(
      extractionIds.run,
      expect.objectContaining({ search: 'Register', page: 1, pageSize: 100 }),
      true,
    );
    expect(blocksHook).toHaveBeenLastCalledWith(
      extractionIds.run,
      expect.objectContaining({
        containerId: xlsxContainer.id,
        search: 'XLSX:sheet=Register:cell=Z205',
        page: 1,
        pageSize: 200,
      }),
      true,
    );
    expect(globalThis.document.getElementById(`block-${xlsxCell.id}`)).toHaveClass(
      'bg-amber-50',
    );
    expect(screen.getByRole('status')).toHaveTextContent(
      'worksheet Register, cell Z205',
    );
  });

  it('sends source and language filters to the paginated blocks endpoint', async () => {
    renderPage();

    await userEvent.selectOptions(screen.getByLabelText('Content Source'), 'OCR');
    await userEvent.selectOptions(screen.getByLabelText('Detected Language'), 'zh');

    await waitFor(() =>
      expect(blocksHook).toHaveBeenLastCalledWith(
        extractionIds.run,
        expect.objectContaining({
          contentSource: 'OCR',
          languageCode: 'zh',
          page: 1,
        }),
        true,
      ),
    );
  });
});
