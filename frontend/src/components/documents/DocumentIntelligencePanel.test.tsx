import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '../../providers/ToastProvider';
import { useAuthStore } from '../../store/authStore';
import { superAdminSession } from '../../test/authFixtures';
import { physicalFileFixture } from '../../test/documentFileFixtures';
import { extractionRun } from '../../test/extractionFixtures';
import { DocumentIntelligencePanel } from './DocumentIntelligencePanel';

const latestExtraction = vi.hoisted(() => vi.fn());
const latestOCR = vi.hoisted(() => vi.fn());
const latestLanguage = vi.hoisted(() => vi.fn());

vi.mock('../../hooks/useExtractedContent', () => ({
  useLatestExtraction: () => latestExtraction(),
}));

vi.mock('../../hooks/useOCR', () => ({
  useLatestOCR: () => latestOCR(),
  useOCRMutations: () => ({
    start: { mutateAsync: vi.fn(), isPending: false },
    reocr: { mutateAsync: vi.fn(), isPending: false },
  }),
}));

vi.mock('../../hooks/useOCRJobs', () => ({
  useOCRJobs: () => ({
    data: { items: [] },
  }),
}));

vi.mock('../../hooks/useLanguageResults', () => ({
  useLatestLanguageDetection: () => latestLanguage(),
  useLanguageSummary: () => ({ data: undefined }),
}));

vi.mock('../../hooks/useLanguageDetectionJobs', () => ({
  useLanguageDetectionJobs: () => ({
    data: { items: [] },
  }),
}));

vi.mock('../../hooks/useLanguageDetection', () => ({
  useLanguageDetectionMutations: () => ({
    start: { mutateAsync: vi.fn(), isPending: false },
    redetect: { mutateAsync: vi.fn(), isPending: false },
  }),
}));

const renderPanel = (extension: 'pdf' | 'docx' | 'xlsx') =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <ToastProvider>
          <DocumentIntelligencePanel
            file={{
              ...physicalFileFixture,
              fileExtension: extension,
              originalFilename: `document.${extension}`,
            }}
          />
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );

describe('DocumentIntelligencePanel format rules', () => {
  beforeEach(() => {
    useAuthStore.getState().setAuth(superAdminSession);
    latestExtraction.mockReturnValue({
      data: { ...extractionRun, requiresOcr: true },
      isLoading: false,
      error: null,
    });
    latestOCR.mockReturnValue({ data: null, error: null });
    latestLanguage.mockReturnValue({ data: null, error: null });
  });

  it('offers OCR only for a current eligible PDF', () => {
    renderPanel('pdf');

    expect(screen.getByRole('button', { name: 'Run OCR' })).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Detect Languages' }),
    ).toBeInTheDocument();
  });

  it.each(['docx', 'xlsx'] as const)(
    'hides OCR for %s but still offers language detection',
    (extension) => {
      renderPanel(extension);

      expect(screen.queryByRole('button', { name: 'Run OCR' })).not.toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: 'Detect Languages' }),
      ).toBeInTheDocument();
    },
  );
});
