import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { parseDocumentCode } from '../../api/documentApi';
import { DocumentCodeParser } from './DocumentCodeParser';

vi.mock('../../api/documentApi', () => ({
  archiveDocument: vi.fn(),
  bulkArchive: vi.fn(),
  bulkRestore: vi.fn(),
  bulkUpdateStatus: vi.fn(),
  createDocument: vi.fn(),
  parseDocumentCode: vi.fn(),
  restoreDocument: vi.fn(),
  updateDocument: vi.fn(),
}));

describe('DocumentCodeParser', () => {
  it('identifies a supported filename through the backend parser', async () => {
    const onParsed = vi.fn();
    vi.mocked(parseDocumentCode).mockResolvedValue({
      companyCode: 'MTI',
      department: {
        id: '11111111-1111-4111-8111-111111111111',
        code: 'HRM',
        name: 'Human Resource',
      },
      section: {
        id: '22222222-2222-4222-8222-222222222222',
        code: 'IER',
        name: 'Industrial Relations',
      },
      documentType: {
        id: '33333333-3333-4333-8333-333333333333',
        code: 'SOP',
        name: 'Standard Operating Procedure',
      },
      documentNumber: '001',
      baseDocumentCode: 'MTI-HRM-IER-SOP-001',
      revisionCode: 'Rev.003',
      fullDocumentCode: 'MTI-HRM-IER-SOP-001_Rev.003',
      fileExtension: 'pdf',
      warnings: [],
    });
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <DocumentCodeParser onParsed={onParsed} />
      </QueryClientProvider>,
    );
    fireEvent.change(screen.getByLabelText('Document code or filename'), {
      target: { value: 'MTI-HRM-IER-SOP-001_Rev.003.pdf' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Identify' }));

    await waitFor(() => {
      expect(parseDocumentCode).toHaveBeenCalledWith({
        value: 'MTI-HRM-IER-SOP-001_Rev.003.pdf',
      });
      expect(onParsed).toHaveBeenCalledWith(
        expect.objectContaining({ revisionCode: 'Rev.003' }),
      );
    });
  });
});
