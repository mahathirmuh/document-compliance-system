import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { PropsWithChildren } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { masterDataApi } from '../../api/masterDataApi';
import { ToastProvider } from '../../providers/ToastProvider';
import { useAuthStore } from '../../store/authStore';
import { superAdminSession } from '../../test/authFixtures';
import { MasterDataImportDialog } from './MasterDataImportDialog';

vi.mock('../../api/masterDataApi', () => ({
  masterDataApi: {
    getOverview: vi.fn(),
    previewImport: vi.fn(),
    confirmImport: vi.fn(),
    downloadTemplate: vi.fn(),
    exportXlsx: vi.fn(),
  },
}));

const preview = {
  entityType: 'departments' as const,
  totalRows: 3,
  validRows: 2,
  invalidRows: 1,
  duplicateRows: 0,
  warnings: [],
  rows: [
    {
      rowNumber: 2,
      status: 'VALID' as const,
      data: { code: 'HRM', name: 'Human Resource' },
      errors: [],
    },
    {
      rowNumber: 3,
      status: 'INVALID' as const,
      data: { code: 'BAD CODE' },
      errors: ['Code contains spaces.'],
    },
  ],
};

function Providers({ children }: PropsWithChildren) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return (
    <QueryClientProvider client={client}>
      <ToastProvider>{children}</ToastProvider>
    </QueryClientProvider>
  );
}

const renderDialog = () =>
  render(
    <Providers>
      <MasterDataImportDialog isOpen onClose={vi.fn()} />
    </Providers>,
  );

describe('MasterDataImportDialog', () => {
  beforeEach(() => {
    vi.mocked(masterDataApi.previewImport).mockResolvedValue(preview);
  });

  it('rejects a non-XLSX upload before calling the backend', async () => {
    const user = userEvent.setup({ applyAccept: false });
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      permissions: ['master_data:view', 'master_data:create'],
    });
    renderDialog();

    const file = new File(['code,name'], 'departments.csv', {
      type: 'text/csv',
    });
    await user.upload(screen.getByLabelText(/Choose an XLSX workbook/i), file);

    expect(screen.getByText('Choose a valid .xlsx workbook.')).toBeInTheDocument();
    expect(masterDataApi.previewImport).not.toHaveBeenCalled();
  });

  it('shows preview totals and locks a create-only user out of UPSERT', async () => {
    const user = userEvent.setup();
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      permissions: ['master_data:view', 'master_data:create'],
    });
    renderDialog();

    const file = new File(['xlsx'], 'departments.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
    await user.upload(screen.getByLabelText(/Choose an XLSX workbook/i), file);
    await user.click(screen.getByRole('button', { name: 'Generate preview' }));

    expect(await screen.findByText('Code contains spaces.')).toBeInTheDocument();
    expect(screen.getByText('Create Only')).toBeInTheDocument();
    expect(screen.queryByText('Upsert')).not.toBeInTheDocument();
    expect(screen.getByText(/Invalid rows will be skipped/)).toBeInTheDocument();
  });

  it('offers UPSERT only to a user with update permission', async () => {
    const user = userEvent.setup();
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      permissions: ['master_data:view', 'master_data:create', 'master_data:update'],
    });
    renderDialog();

    const file = new File(['xlsx'], 'departments.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
    await user.upload(screen.getByLabelText(/Choose an XLSX workbook/i), file);
    await user.click(screen.getByRole('button', { name: 'Generate preview' }));

    expect(await screen.findByText('Upsert')).toBeInTheDocument();
  });
});
