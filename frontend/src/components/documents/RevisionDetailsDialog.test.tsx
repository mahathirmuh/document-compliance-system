import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { getRevision } from '../../api/documentRevisionApi';
import { ToastProvider } from '../../providers/ToastProvider';
import { useAuthStore } from '../../store/authStore';
import { superAdminSession } from '../../test/authFixtures';
import type {
  DocumentRevision,
  DocumentRevisionListItem,
} from '../../types/documentRevision';
import { RevisionDetailsDialog } from './RevisionDetailsDialog';

vi.mock('../../api/documentRevisionApi', async (importOriginal) => ({
  ...((await importOriginal()) as object),
  getRevision: vi.fn(),
}));

const documentId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const revisionId = '11111111-1111-4111-8111-111111111111';
const revision: DocumentRevisionListItem = {
  id: revisionId,
  documentId,
  revisionCode: 'Rev.002',
  revisionNumber: 2,
  fullDocumentCode: 'MTI-HRM-POL-001_Rev.002',
  documentStatusId: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  validationRuleId: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
  status: {
    id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
    code: 'FINAL',
    name: 'Final',
  },
  validationRule: {
    id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
    code: 'POL-ANNUAL',
    name: 'Annual Policy Review',
  },
  issueDate: '2026-07-01',
  effectiveDate: '2026-07-15',
  reviewDate: '2027-07-01',
  expiryDate: null,
  sharepointUrl: 'https://tenant.sharepoint.com/sites/qms/policy-001',
  externalReference: 'LEGACY-42',
  remarks: 'Approved controlled copy.',
  isCurrent: true,
  isSuperseded: false,
  supersededAt: null,
  supersededByRevisionId: null,
  createdAt: '2026-07-01T10:00:00+08:00',
  updatedAt: '2026-07-15T10:00:00+08:00',
};
const detail: DocumentRevision = {
  ...revision,
  createdBy: {
    id: 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
    name: 'Document Controller',
    email: 'controller@example.com',
  },
  updatedBy: {
    id: 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
    name: 'Quality Approver',
    email: 'approver@example.com',
  },
};

describe('RevisionDetailsDialog viewer access', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      permissions: ['documents:view'],
    });
    vi.mocked(getRevision).mockResolvedValue(detail);
  });

  it('loads and displays read-only revision metadata without mutation actions', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const onClose = vi.fn();
    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <RevisionDetailsDialog
            documentId={documentId}
            revision={revision}
            onClose={onClose}
          />
        </ToastProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByText('Approved controlled copy.')).toBeInTheDocument();
    expect(screen.getByText('LEGACY-42')).toBeInTheDocument();
    expect(screen.getByText('Document Controller')).toBeInTheDocument();
    expect(screen.getByText('controller@example.com')).toBeInTheDocument();
    expect(screen.getByText('Quality Approver')).toBeInTheDocument();
    expect(screen.getByText('approver@example.com')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open SharePoint' })).toHaveAttribute(
      'href',
      revision.sharepointUrl,
    );
    expect(getRevision).toHaveBeenCalledWith(
      documentId,
      revisionId,
      expect.any(AbortSignal),
    );
    expect(screen.queryByText('Edit')).not.toBeInTheDocument();
    expect(screen.queryByText('Set Current')).not.toBeInTheDocument();
    expect(screen.queryByText('Supersede')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
