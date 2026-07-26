import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useAuthStore } from '../store/authStore';
import { physicalFileFixture } from '../test/documentFileFixtures';
import type { AuthSession } from '../types/auth';
import { NotificationCentre } from './notifications/NotificationCentre';
import { DocumentRemotePanel } from './sharepoint/DocumentRemotePanel';
import { SharePointFolderBrowser } from './sharepoint/SharePointFolderBrowser';

const mocks = vi.hoisted(() => ({
  createFolder: vi.fn(),
  folders: {
    data: [
      {
        id: 'folder-id',
        name: 'Controlled',
        webUrl: null,
        parentReference: null,
        childCount: 2,
      },
    ],
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  },
  unread: {
    data: { unreadCount: 2 },
    isLoading: false,
    error: null,
  },
  notifications: {
    data: {
      items: [
        {
          id: 'notification-id',
          userId: 'user-id',
          eventType: 'SHAREPOINT_SYNC_FAILED',
          title: 'SharePoint sync failed',
          message: 'Review the failed job.',
          severity: 'ERROR',
          relatedEntityType: 'sync_job',
          relatedEntityId: 'job-id',
          actionUrl: '/documents/sharepoint-sync-history',
          isRead: false,
          readAt: null,
          createdAt: '2026-07-26T01:00:00Z',
          expiresAt: null,
        },
      ],
      page: 1,
      pageSize: 10,
      totalItems: 1,
      totalPages: 1,
    },
    isLoading: false,
    error: null,
  },
  markRead: vi.fn(),
  markAllRead: vi.fn(),
  dismiss: vi.fn(),
  pushFile: vi.fn(),
  pullFile: vi.fn(),
  reconcileFile: vi.fn(),
  remoteStatus: {
    data: {
      documentFileId: '11111111-1111-4111-8111-111111111111',
      storageProvider: 'HYBRID',
      sharepointConnectionId: 'connection-id',
      connectionName: 'Controlled Library',
      remoteDriveId: 'drive-id',
      remoteItemId: 'item-id',
      remotePath: '/DocumentCompliance/MTI-HRM-POL-001.pdf',
      remoteWebUrl: 'https://contoso.sharepoint.com/sites/controlled/file.pdf',
      remoteEtag: 'etag',
      remoteVersionId: '3.0',
      remoteLastModifiedAt: '2026-07-26T01:00:00Z',
      remoteLastModifiedBy: 'Controller',
      remoteSize: 1250,
      remoteMimeType: 'application/pdf',
      remoteSyncStatus: 'SYNCED',
      lastSyncedAt: '2026-07-26T01:05:00Z',
      syncErrorCode: null,
      syncErrorMessage: null,
      activeJobId: null,
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  },
  versions: {
    data: {
      items: [],
      page: 1,
      pageSize: 50,
      totalItems: 0,
      totalPages: 0,
    },
    isLoading: false,
    error: null,
  },
  showToast: vi.fn(),
}));

vi.mock('../hooks/useSharePointMappings', () => ({
  useSharePointFolders: () => mocks.folders,
  useSharePointMappingMutations: () => ({
    createFolder: {
      mutateAsync: mocks.createFolder,
      isPending: false,
    },
  }),
}));

vi.mock('../hooks/useNotifications', () => ({
  useNotificationUnreadCount: () => mocks.unread,
  useNotifications: () => mocks.notifications,
  useNotificationMutations: () => ({
    markRead: { mutateAsync: mocks.markRead, isPending: false },
    markAllRead: { mutateAsync: mocks.markAllRead, isPending: false },
    dismiss: { mutateAsync: mocks.dismiss, isPending: false },
  }),
}));

vi.mock('../hooks/useSharePointSync', () => ({
  useDocumentRemoteStatus: () => mocks.remoteStatus,
  useDocumentRemoteVersions: () => mocks.versions,
  useSharePointSyncMutations: () => ({
    pushFile: { mutateAsync: mocks.pushFile, isPending: false },
    pullFile: { mutateAsync: mocks.pullFile, isPending: false },
    reconcileFile: { mutateAsync: mocks.reconcileFile, isPending: false },
  }),
}));

vi.mock('../providers/useToast', () => ({
  useToast: () => ({ showToast: mocks.showToast }),
}));

const session = (permissions: AuthSession['permissions']): AuthSession => ({
  accessToken: 'access',
  refreshToken: 'refresh',
  tokenType: 'bearer',
  expiresIn: 900,
  user: {
    id: 'user-id',
    name: 'Controller',
    email: 'controller@example.com',
    role: 'DOCUMENT_CONTROLLER',
    departmentId: null,
    isActive: true,
  },
  permissions,
});

describe('Phase 10 components', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.markRead.mockResolvedValue({});
    mocks.markAllRead.mockResolvedValue({ unreadCount: 0 });
    mocks.dismiss.mockResolvedValue({});
    mocks.pushFile.mockResolvedValue({ id: 'job-id' });
    mocks.pullFile.mockResolvedValue({ id: 'job-id' });
    mocks.reconcileFile.mockResolvedValue({ id: 'job-id' });
    useAuthStore.getState().clearAuth();
  });

  it('browses and selects only folders from the chosen connection', async () => {
    const onSelect = vi.fn();
    render(
      <SharePointFolderBrowser
        connectionId="connection-id"
        initialPath="DocumentCompliance"
        canCreateFolder={false}
        onSelect={onSelect}
      />,
    );
    expect(screen.getByText('DocumentCompliance/Controlled')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Select Controlled' }));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: 'folder-id' }));
    expect(screen.queryByLabelText('New folder name')).not.toBeInTheDocument();
  });

  it('creates a folder only when creation permission is passed', async () => {
    mocks.createFolder.mockResolvedValue({
      ...mocks.folders.data[0],
      id: 'new-folder',
      name: 'New Folder',
    });
    render(
      <SharePointFolderBrowser
        connectionId="connection-id"
        canCreateFolder
        onSelect={vi.fn()}
      />,
    );
    await userEvent.type(screen.getByLabelText('New folder name'), 'New Folder');
    await userEvent.click(screen.getByRole('button', { name: 'Create' }));
    expect(mocks.createFolder).toHaveBeenCalledWith({
      connectionId: 'connection-id',
      parentItemId: null,
      name: 'New Folder',
    });
  });

  it('shows unread notifications and marks all as read', async () => {
    useAuthStore.getState().setAuth(session(['notifications:view']));
    render(
      <MemoryRouter>
        <NotificationCentre />
      </MemoryRouter>,
    );
    await userEvent.click(
      screen.getByRole('button', { name: 'Notifications, 2 unread' }),
    );
    expect(screen.getByText('SharePoint sync failed')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Mark all read' }));
    expect(mocks.markAllRead).toHaveBeenCalledTimes(1);
  });

  it('loads remote metadata and confirms a push through the backend', async () => {
    useAuthStore
      .getState()
      .setAuth(
        session([
          'sharepoint:view',
          'sharepoint:push',
          'sharepoint:pull',
          'sharepoint:view_history',
        ]),
      );
    render(
      <MemoryRouter>
        <DocumentRemotePanel documentFile={physicalFileFixture} />
      </MemoryRouter>,
    );
    expect(screen.getByText('connection-id')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open in SharePoint' })).toHaveAttribute(
      'href',
      'https://contoso.sharepoint.com/sites/controlled/file.pdf',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Push to SharePoint' }));
    await userEvent.click(screen.getByRole('button', { name: 'Queue Push' }));
    expect(mocks.pushFile).toHaveBeenCalledWith(physicalFileFixture.id);
  });

  it('blocks every remote action for a quarantined file', () => {
    useAuthStore
      .getState()
      .setAuth(session(['sharepoint:view', 'sharepoint:push', 'sharepoint:pull']));
    render(
      <MemoryRouter>
        <DocumentRemotePanel
          documentFile={{ ...physicalFileFixture, fileStatus: 'QUARANTINED' }}
        />
      </MemoryRouter>,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('quarantined');
    expect(
      screen.queryByRole('button', { name: 'Push to SharePoint' }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('link', { name: 'Open in SharePoint' }),
    ).not.toBeInTheDocument();
  });
});
