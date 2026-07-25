import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  confirmImport,
  downloadImportTemplate,
  previewImport,
} from '../../api/documentImportApi';
import { ToastProvider } from '../../providers/ToastProvider';
import { useAuthStore } from '../../store/authStore';
import { superAdminSession } from '../../test/authFixtures';
import type { DocumentImportPreviewRow } from '../../types/documentImport';
import { DocumentImportDialog } from './DocumentImportDialog';

vi.mock('../../api/documentImportApi', () => ({
  confirmImport: vi.fn(),
  downloadImportTemplate: vi.fn(),
  previewImport: vi.fn(),
}));

const renderDialog = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      mutations: { retry: false },
      queries: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <DocumentImportDialog isOpen onClose={vi.fn()} />
      </ToastProvider>
    </QueryClientProvider>,
  );
};

describe('DocumentImportDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('is hidden without documents:import', () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      permissions: ['documents:view'],
    });
    renderDialog();
    expect(screen.queryByText('Import Document Register')).not.toBeInTheDocument();
  });

  it('rejects files that are not XLSX workbooks', () => {
    useAuthStore.getState().setAuth(superAdminSession);
    renderDialog();
    const input = screen.getByLabelText(/Choose an XLSX workbook/);
    fireEvent.change(input, {
      target: {
        files: [new File(['data'], 'register.csv', { type: 'text/csv' })],
      },
    });
    expect(screen.getByText('Choose a valid .xlsx workbook.')).toBeInTheDocument();
    expect(previewImport).not.toHaveBeenCalled();
  });

  it('renders the backend preview summary and row result', async () => {
    useAuthStore.getState().setAuth(superAdminSession);
    vi.mocked(previewImport).mockResolvedValue({
      totalRows: 2,
      validCreateRows: 1,
      validAddRevisionRows: 0,
      warningRows: 0,
      duplicateRows: 0,
      invalidRows: 1,
      warnings: [],
      rows: [
        {
          rowNumber: 2,
          status: 'VALID_CREATE',
          baseDocumentCode: 'MTI-HRM-POL-001',
          revisionCode: 'Rev.000',
          title: 'Human Resources Policy',
          departmentCode: 'HRM',
          documentTypeCode: 'POL',
          data: { document_status_code: 'DRAFT' },
          errors: [],
          warnings: [],
        },
      ],
    });
    renderDialog();
    const input = screen.getByLabelText(/Choose an XLSX workbook/);
    fireEvent.change(input, {
      target: {
        files: [
          new File(['xlsx'], 'register.xlsx', {
            type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          }),
        ],
      },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Generate preview' }));

    expect(await screen.findByText('Valid Create')).toBeInTheDocument();
    expect(screen.getByText('MTI-HRM-POL-001')).toBeInTheDocument();
    expect(screen.getAllByText('VALID CREATE').length).toBeGreaterThan(0);
  });

  it('paginates every matching preview row and reports the visible range', async () => {
    useAuthStore.getState().setAuth(superAdminSession);
    const rows: DocumentImportPreviewRow[] = Array.from({ length: 55 }, (_, index) => ({
      rowNumber: index + 2,
      status: 'VALID_CREATE',
      baseDocumentCode: `MTI-HRM-POL-${String(index + 1).padStart(3, '0')}`,
      revisionCode: 'Rev.000',
      title: `Policy ${index + 1}`,
      departmentCode: 'HRM',
      documentTypeCode: 'POL',
      data: { document_status_code: 'DRAFT' },
      errors: [],
      warnings: [],
    }));
    vi.mocked(previewImport).mockResolvedValue({
      totalRows: rows.length,
      validCreateRows: rows.length,
      validAddRevisionRows: 0,
      warningRows: 0,
      duplicateRows: 0,
      invalidRows: 0,
      warnings: [],
      rows,
    });
    renderDialog();

    fireEvent.change(screen.getByLabelText(/Choose an XLSX workbook/), {
      target: {
        files: [
          new File(['xlsx'], 'register.xlsx', {
            type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          }),
        ],
      },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Generate preview' }));

    expect(await screen.findByText('MTI-HRM-POL-001')).toBeInTheDocument();
    expect(screen.getByText(/Showing 1.50 of 55 matching rows/)).toBeInTheDocument();
    expect(screen.queryByText('MTI-HRM-POL-055')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Next' }));

    expect(await screen.findByText('MTI-HRM-POL-055')).toBeInTheDocument();
    expect(screen.getByText(/Showing 51.55 of 55 matching rows/)).toBeInTheDocument();
    expect(screen.getByText('Page 2 of 2')).toBeInTheDocument();
  });

  it('delegates the configurable workbook size limit to the backend', async () => {
    useAuthStore.getState().setAuth(superAdminSession);
    vi.mocked(previewImport).mockResolvedValue({
      totalRows: 0,
      validCreateRows: 0,
      validAddRevisionRows: 0,
      warningRows: 0,
      duplicateRows: 0,
      invalidRows: 0,
      warnings: [],
      rows: [],
    });
    renderDialog();
    const workbook = new File(['xlsx'], 'large-register.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
    Object.defineProperty(workbook, 'size', {
      configurable: true,
      value: 100 * 1024 * 1024,
    });

    fireEvent.change(screen.getByLabelText(/Choose an XLSX workbook/), {
      target: { files: [workbook] },
    });

    expect(
      screen.getByText('The server enforces the configured workbook size limit.'),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Generate preview' })).toBeEnabled();
    fireEvent.click(screen.getByRole('button', { name: 'Generate preview' }));

    await waitFor(() => {
      expect(previewImport).toHaveBeenCalledWith(workbook);
    });
  });

  it('hides metadata and revision import modes without their permissions', () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      permissions: ['documents:view', 'documents:import'],
    });
    renderDialog();
    expect(screen.queryByText('Upsert metadata')).not.toBeInTheDocument();
    expect(screen.queryByText('Create and add revisions')).not.toBeInTheDocument();
  });
});

void confirmImport;
void downloadImportTemplate;
