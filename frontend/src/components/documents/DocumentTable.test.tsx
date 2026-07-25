import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '../../providers/ToastProvider';
import type { DocumentListItem } from '../../types/document';
import { ArchiveDocumentDialog } from './ArchiveDocumentDialog';
import { DocumentTable } from './DocumentTable';
import { ConfirmationDialog } from '../master-data/ConfirmationDialog';

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

const renderTable = (
  overrides: Partial<React.ComponentProps<typeof DocumentTable>> = {},
) =>
  render(
    <MemoryRouter>
      <ToastProvider>
        <DocumentTable
          items={[]}
          isLoading={false}
          page={1}
          pageSize={20}
          totalItems={0}
          totalPages={0}
          sortBy="updatedAt"
          sortOrder="desc"
          selectedIds={new Set()}
          canUpdate={false}
          canArchive={false}
          canRestore={false}
          canManageRevisions={false}
          canSelect={false}
          onSelectionChange={vi.fn()}
          onSort={vi.fn()}
          onPageChange={vi.fn()}
          onPageSizeChange={vi.fn()}
          onArchive={vi.fn()}
          onRestore={vi.fn()}
          onRetry={vi.fn()}
          {...overrides}
        />
      </ToastProvider>
    </MemoryRouter>,
  );

describe('DocumentTable', () => {
  it('renders loading and empty register states', () => {
    const { rerender } = renderTable({ isLoading: true });
    expect(screen.getAllByLabelText(/Loading document/).length).toBeGreaterThan(0);

    rerender(
      <MemoryRouter>
        <ToastProvider>
          <DocumentTable
            items={[]}
            isLoading={false}
            page={1}
            pageSize={20}
            totalItems={0}
            totalPages={0}
            sortBy="updatedAt"
            sortOrder="desc"
            selectedIds={new Set()}
            canUpdate={false}
            canArchive={false}
            canRestore={false}
            canManageRevisions={false}
            canSelect={false}
            onSelectionChange={vi.fn()}
            onSort={vi.fn()}
            onPageChange={vi.fn()}
            onPageSizeChange={vi.fn()}
            onArchive={vi.fn()}
            onRestore={vi.fn()}
            onRetry={vi.fn()}
          />
        </ToastProvider>
      </MemoryRouter>,
    );
    expect(screen.getByText('No documents found')).toBeInTheDocument();
  });

  it('hides mutation actions for a view-only user', () => {
    renderTable({ items: [documentItem], totalItems: 1, totalPages: 1 });

    expect(screen.getAllByText('View').length).toBeGreaterThan(0);
    expect(screen.queryByText('Edit')).not.toBeInTheDocument();
    expect(screen.queryByText('Revisions')).not.toBeInTheDocument();
    expect(screen.queryByText('Archive')).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText('Select all documents on this page'),
    ).not.toBeInTheDocument();
  });

  it('shows restore instead of edit for an archived document', () => {
    const onRestore = vi.fn();
    renderTable({
      items: [{ ...documentItem, isArchived: true }],
      totalItems: 1,
      totalPages: 1,
      canUpdate: true,
      canRestore: true,
      canSelect: true,
      onRestore,
    });

    expect(screen.getAllByText('Restore').length).toBeGreaterThan(0);
    expect(screen.queryByText('Edit')).not.toBeInTheDocument();
    fireEvent.click(screen.getAllByText('Restore')[0] as HTMLElement);
    expect(onRestore).toHaveBeenCalledWith(
      expect.objectContaining({ id: documentItem.id }),
    );
  });

  it('delegates supported current-revision and audit sorting', () => {
    const onSort = vi.fn();
    renderTable({ onSort });

    fireEvent.click(screen.getByRole('button', { name: 'Effective Date' }));
    fireEvent.click(screen.getByRole('button', { name: 'Updated At' }));

    expect(onSort).toHaveBeenNthCalledWith(1, 'effectiveDate');
    expect(onSort).toHaveBeenNthCalledWith(2, 'updatedAt');
  });
});

describe('restore confirmation', () => {
  it('requires an explicit confirmation click', () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmationDialog
        isOpen
        title="Restore document?"
        message="Restore this document to the active register."
        confirmLabel="Restore"
        tone="primary"
        onCancel={vi.fn()}
        onConfirm={onConfirm}
      />,
    );
    expect(onConfirm).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Restore' }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });
});

describe('ArchiveDocumentDialog', () => {
  it('requires a reason before confirming an archive', async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    render(
      <ArchiveDocumentDialog
        isOpen
        isPending={false}
        onClose={vi.fn()}
        onConfirm={onConfirm}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Archive' }));
    expect(await screen.findByText('Archive reason is required.')).toBeInTheDocument();
    expect(onConfirm).not.toHaveBeenCalled();

    fireEvent.change(screen.getByPlaceholderText(/Explain why/), {
      target: { value: 'Document is no longer used.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Archive' }));
    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledWith('Document is no longer used.');
    });
  });
});
