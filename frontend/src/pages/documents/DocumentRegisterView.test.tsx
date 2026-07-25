import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '../../providers/ToastProvider';
import { useAuthStore } from '../../store/authStore';
import { superAdminSession } from '../../test/authFixtures';
import type { DocumentListItem } from '../../types/document';
import { DocumentRegisterView } from './DocumentRegisterView';

const documentQueryState = vi.hoisted(() => ({
  items: [] as DocumentListItem[],
}));

vi.mock('../../components/documents/DocumentExportButton', () => ({
  DocumentExportButton: () => <button type="button">Export</button>,
}));
vi.mock('../../components/documents/DocumentImportDialog', () => ({
  DocumentImportDialog: () => null,
}));
vi.mock('../../hooks/useDocuments', () => ({
  useDocuments: () => ({
    data: {
      items: documentQueryState.items,
      page: 1,
      pageSize: 20,
      totalItems: documentQueryState.items.length,
      totalPages: documentQueryState.items.length > 0 ? 1 : 0,
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));
vi.mock('../../hooks/useDocumentListControls', () => ({
  useDocumentListControls: (archived: boolean) => ({
    params: {
      page: 1,
      pageSize: 20,
      sortBy: 'updatedAt',
      sortOrder: 'desc',
      isArchived: archived,
    },
    filters: {
      search: '',
      departmentId: '',
      sectionId: '',
      documentTypeId: '',
      documentStatusId: '',
      revisionCode: '',
      hasSharePointUrl: undefined,
      createdFrom: '',
      createdTo: '',
      effectiveFrom: '',
      effectiveTo: '',
    },
    page: 1,
    pageSize: 20,
    sortBy: 'updatedAt',
    sortOrder: 'desc',
    setFilters: vi.fn(),
    resetFilters: vi.fn(),
    setPage: vi.fn(),
    setPageSize: vi.fn(),
    setSort: vi.fn(),
  }),
}));
vi.mock('../../hooks/useDocumentMutations', () => ({
  useDocumentMutations: () => {
    const mutation = { isPending: false, mutateAsync: vi.fn() };
    return {
      archive: mutation,
      restore: mutation,
      bulkArchive: mutation,
      bulkRestore: mutation,
      bulkUpdateStatus: mutation,
    };
  },
}));
vi.mock('../../hooks/useDocumentFormOptions', () => ({
  useDocumentFormOptions: () => ({
    data: {
      defaultCompanyCode: 'MTI',
      departments: [
        {
          id: '22222222-2222-4222-8222-222222222222',
          code: 'HRM',
          name: 'Human Resource',
        },
      ],
      sections: [],
      documentTypes: [],
      documentStatuses: [],
      validationRules: [],
    },
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

const renderRegister = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ToastProvider>
          <DocumentRegisterView archived={false} />
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

const documentItem: DocumentListItem = {
  id: '11111111-1111-4111-8111-111111111111',
  companyCode: 'MTI',
  departmentId: '22222222-2222-4222-8222-222222222222',
  sectionId: null,
  documentTypeId: '33333333-3333-4333-8333-333333333333',
  documentNumber: '001',
  baseDocumentCode: 'MTI-HRM-POL-001',
  title: 'Human Resources Policy',
  department: {
    id: '22222222-2222-4222-8222-222222222222',
    code: 'HRM',
    name: 'Human Resource',
  },
  section: null,
  documentType: {
    id: '33333333-3333-4333-8333-333333333333',
    code: 'POL',
    name: 'Policy',
  },
  currentRevision: null,
  isArchived: false,
  updatedAt: '2026-07-25T10:00:00+08:00',
};

describe('DocumentRegisterView action permissions', () => {
  beforeEach(() => {
    documentQueryState.items = [];
  });

  it('hides create, import, and export actions for a view-only user', () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      permissions: ['documents:view'],
      user: { ...superAdminSession.user, role: 'VIEWER' },
    });
    renderRegister();
    expect(screen.getByText('No documents found')).toBeInTheDocument();
    expect(screen.queryByText('Add Document')).not.toBeInTheDocument();
    expect(screen.queryByText('Import XLSX')).not.toBeInTheDocument();
    expect(screen.queryByText('Export')).not.toBeInTheDocument();
  });

  it('shows each register action when its permission is granted', () => {
    useAuthStore.getState().setAuth(superAdminSession);
    renderRegister();
    expect(screen.getByRole('link', { name: 'Add Document' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Import XLSX' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Export' })).toBeInTheDocument();
  });

  it('clears bulk selection when the filter context changes', () => {
    documentQueryState.items = [documentItem];
    useAuthStore.getState().setAuth(superAdminSession);
    renderRegister();

    fireEvent.click(
      screen.getAllByLabelText(
        `Select ${documentItem.baseDocumentCode}`,
      )[0] as HTMLElement,
    );
    expect(screen.getByText('1 selected')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Filter by department'), {
      target: { value: documentItem.departmentId },
    });

    expect(screen.queryByText('1 selected')).not.toBeInTheDocument();
    expect(
      screen.getAllByLabelText(`Select ${documentItem.baseDocumentCode}`)[0],
    ).not.toBeChecked();
  });
});
