import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { exportDocumentRegister } from '../../api/documentExportApi';
import { ToastProvider } from '../../providers/ToastProvider';
import { downloadFile } from '../../utils/downloadFile';
import { DocumentExportButton } from './DocumentExportButton';

vi.mock('../../api/documentExportApi', () => ({
  exportDocumentRegister: vi.fn(),
}));
vi.mock('../../utils/downloadFile', () => ({
  downloadFile: vi.fn(),
}));

describe('DocumentExportButton', () => {
  it('exports with active filters and honors the response filename', async () => {
    const download = {
      blob: new Blob(['xlsx']),
      fileName: 'document_register_2026-07-25_10-00.xlsx',
    };
    vi.mocked(exportDocumentRegister).mockResolvedValue(download);
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <DocumentExportButton
            params={{
              departmentId: '11111111-1111-4111-8111-111111111111',
              isArchived: false,
            }}
          />
        </ToastProvider>
      </QueryClientProvider>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Export' }));

    await waitFor(() => {
      expect(exportDocumentRegister).toHaveBeenCalledWith({
        departmentId: '11111111-1111-4111-8111-111111111111',
        isArchived: false,
      });
    });
    expect(downloadFile).toHaveBeenCalledWith(
      download,
      expect.stringMatching(/^document_register_\d{4}-\d{2}-\d{2}\.xlsx$/),
    );
  });

  it('forwards an exact base document code for a detail export', async () => {
    vi.mocked(exportDocumentRegister).mockResolvedValue({
      blob: new Blob(['xlsx']),
      fileName: 'document_record.xlsx',
    });
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <DocumentExportButton
            params={{ baseDocumentCode: 'MTI-HRM-POL-001' }}
            label="Export Record"
          />
        </ToastProvider>
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Export Record' }));

    await waitFor(() => {
      expect(exportDocumentRegister).toHaveBeenCalledWith({
        baseDocumentCode: 'MTI-HRM-POL-001',
      });
    });
  });
});
