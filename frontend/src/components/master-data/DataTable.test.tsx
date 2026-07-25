import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ConfirmationDialog } from './ConfirmationDialog';
import { DataTable, type DataTableColumn } from './DataTable';

interface Row {
  id: string;
  name: string;
}

const columns: readonly DataTableColumn<Row>[] = [
  {
    key: 'name',
    header: 'Name',
    render: (row) => row.name,
  },
];

const defaultProps = {
  columns,
  getRowKey: (row: Row) => row.id,
  errorMessage: null,
  page: 1,
  pageSize: 20,
  totalItems: 0,
  totalPages: 0,
  onSort: vi.fn(),
  onPageChange: vi.fn(),
  onPageSizeChange: vi.fn(),
};

describe('master data table states', () => {
  it('renders a loading skeleton', () => {
    render(<DataTable {...defaultProps} items={[]} isLoading />);
    expect(screen.getAllByLabelText('Loading row').length).toBeGreaterThan(0);
  });

  it('renders the empty state', () => {
    render(<DataTable {...defaultProps} items={[]} isLoading={false} />);
    expect(screen.getByText('No records found')).toBeInTheDocument();
  });

  it('requires explicit confirmation before a status mutation', () => {
    const confirm = vi.fn();
    render(
      <ConfirmationDialog
        isOpen
        title="Deactivate department?"
        message="The record becomes unavailable."
        confirmLabel="Deactivate"
        onCancel={vi.fn()}
        onConfirm={confirm}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Deactivate' }));
    expect(confirm).toHaveBeenCalledOnce();
  });
});
