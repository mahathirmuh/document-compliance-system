import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '../../providers/ToastProvider';
import type { DocumentRevisionListItem } from '../../types/documentRevision';
import { RevisionFormDialog } from './RevisionFormDialog';
import { RevisionTable } from './RevisionTable';
import { SetCurrentRevisionDialog } from './SetCurrentRevisionDialog';
import { SupersedeRevisionDialog } from './SupersedeRevisionDialog';

const revision = (
  id: string,
  code: string,
  isCurrent: boolean,
): DocumentRevisionListItem => ({
  id,
  documentId: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  revisionCode: code,
  revisionNumber: Number(code.slice(-3)),
  fullDocumentCode: `MTI-HRM-POL-001_${code}`,
  documentStatusId: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  validationRuleId: null,
  status: {
    id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
    code: 'DRAFT',
    name: 'Draft',
  },
  validationRule: null,
  issueDate: null,
  effectiveDate: null,
  reviewDate: null,
  expiryDate: null,
  sharepointUrl: null,
  externalReference: null,
  remarks: null,
  isCurrent,
  isSuperseded: false,
  supersededAt: null,
  supersededByRevisionId: null,
  createdAt: '2026-07-25T10:00:00+08:00',
  updatedAt: '2026-07-25T10:00:00+08:00',
});

const revisions = [
  revision('11111111-1111-4111-8111-111111111111', 'Rev.000', false),
  revision('22222222-2222-4222-8222-222222222222', 'Rev.001', true),
];

describe('RevisionTable permissions', () => {
  it('shows revision data without mutation actions in read-only mode', () => {
    const onView = vi.fn();
    render(
      <ToastProvider>
        <RevisionTable
          revisions={revisions}
          canManage={false}
          onView={onView}
          onEdit={vi.fn()}
          onSetCurrent={vi.fn()}
          onSupersede={vi.fn()}
        />
      </ToastProvider>,
    );
    expect(screen.getByText('Rev.000')).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: 'View' })[0]!);
    expect(onView).toHaveBeenCalledWith(revisions[0]);
    expect(screen.queryByText('Edit')).not.toBeInTheDocument();
    expect(screen.queryByText('Set Current')).not.toBeInTheDocument();
    expect(screen.queryByText('Supersede')).not.toBeInTheDocument();
  });

  it('shows explicit revision actions with manage permission', () => {
    render(
      <ToastProvider>
        <RevisionTable
          revisions={revisions}
          canManage
          onView={vi.fn()}
          onEdit={vi.fn()}
          onSetCurrent={vi.fn()}
          onSupersede={vi.fn()}
        />
      </ToastProvider>,
    );
    expect(screen.getAllByText('Edit')).toHaveLength(2);
    expect(screen.getByText('Set Current')).toBeInTheDocument();
    expect(screen.getAllByText('Supersede')).toHaveLength(2);
  });
});

describe('revision action dialogs', () => {
  it('requires and submits an audit reason when editing a normalized code', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <RevisionFormDialog
        isOpen
        revision={revisions[0] ?? null}
        statuses={[
          {
            id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
            code: 'DRAFT',
            name: 'Draft',
          },
        ]}
        validationRules={[]}
        isPending={false}
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.change(screen.getByLabelText('Revision Code'), {
      target: { value: '0' },
    });
    expect(screen.queryByLabelText(/Change Reason/)).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Revision Code'), {
      target: { value: 'Rev.B-2' },
    });
    expect(screen.getByLabelText(/Change Reason/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Save Revision' }));
    expect(
      await screen.findByText(
        'Change reason is required when changing the revision code.',
      ),
    ).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/Change Reason/), {
      target: { value: 'Align the controlled legacy code.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save Revision' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          revisionCode: 'Rev.B-2',
          changeReason: 'Align the controlled legacy code.',
        }),
      );
    });
  });

  it('submits an optional reason when setting the current revision', () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    render(
      <SetCurrentRevisionDialog
        revision={revisions[0] ?? null}
        isPending={false}
        onClose={vi.fn()}
        onConfirm={onConfirm}
      />,
    );
    fireEvent.change(screen.getByLabelText('Reason (optional)'), {
      target: { value: 'Latest approved metadata' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Set Current' }));
    expect(onConfirm).toHaveBeenCalledWith('Latest approved metadata');
  });

  it('requires a replacement and reason before superseding', async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    render(
      <SupersedeRevisionDialog
        revision={revisions[0] ?? null}
        revisions={revisions}
        isPending={false}
        onClose={vi.fn()}
        onConfirm={onConfirm}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Supersede Revision' }));
    expect(
      await screen.findByText('Select the replacing revision.'),
    ).toBeInTheDocument();
    expect(screen.getByText('Reason is required.')).toBeInTheDocument();
    expect(onConfirm).not.toHaveBeenCalled();
  });
});
