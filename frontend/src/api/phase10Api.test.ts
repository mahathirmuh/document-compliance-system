import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
}));

vi.mock('./client', () => ({ apiClient: apiClientMock }));

import {
  createSharePointConnection,
  listSharePointFolders,
  testSharePointConnection,
} from './sharepointApi';
import {
  cancelSyncJob,
  getDocumentRemoteStatus,
  resolveSyncConflict,
} from './sharepointSyncApi';
import {
  getNotificationUnreadCount,
  markAllNotificationsRead,
  updateNotificationPreferences,
} from './notificationApi';
import { getSystemHealth, retryDeadLetterJob } from './systemHealthApi';
import { executeRetentionCleanup } from './retentionApi';

const response = <T>(data: T) => ({
  data: { success: true, message: 'OK', data, errors: null },
});

describe('Phase 10 API contracts', () => {
  beforeEach(() => {
    apiClientMock.get.mockReset();
    apiClientMock.post.mockReset();
    apiClientMock.put.mockReset();
  });

  it('creates and tests backend-scoped SharePoint connections without calling Graph', async () => {
    const connection = {
      id: 'connection-id',
      name: 'Controlled Library',
      status: 'CONNECTED' as const,
    };
    apiClientMock.post
      .mockResolvedValueOnce(response(connection))
      .mockResolvedValueOnce(
        response({
          connectionId: 'connection-id',
          status: 'CONNECTED',
          message: 'Connected',
          siteResolved: true,
          driveResolved: true,
          testedAt: '2026-07-26T01:00:00Z',
        }),
      );

    const payload = {
      name: 'Controlled Library',
      siteHostname: 'contoso.sharepoint.com',
      sitePath: '/sites/Controlled',
      rootFolderPath: 'DocumentCompliance',
      authMode: 'CLIENT_SECRET' as const,
      replaceClientSecret: 'replacement-only',
    };
    await createSharePointConnection(payload);
    await testSharePointConnection('connection-id');

    expect(apiClientMock.post).toHaveBeenNthCalledWith(
      1,
      '/integrations/sharepoint/connections',
      payload,
    );
    expect(apiClientMock.post).toHaveBeenNthCalledWith(
      2,
      '/integrations/sharepoint/connections/connection-id/test',
    );
    expect(
      apiClientMock.post.mock.calls.every(([url]) =>
        String(url).startsWith('/'),
      ),
    ).toBe(true);
  });

  it('browses only within the selected backend connection and folder cursor', async () => {
    apiClientMock.get.mockResolvedValue(
      response({ items: [], nextCursor: null, parent: null }),
    );
    const params = {
      connectionId: 'connection-id',
      parentId: 'folder-id',
      cursor: 'opaque-cursor',
      pageSize: 50,
    };
    await listSharePointFolders(params);
    expect(apiClientMock.get).toHaveBeenCalledWith(
      '/integrations/sharepoint/folders',
      expect.objectContaining({ params }),
    );
  });

  it('requires an audited reason for sync cancellation and conflict resolution', async () => {
    apiClientMock.post.mockResolvedValue(response({ id: 'result-id' }));
    await cancelSyncJob('job-id', { reason: 'Operator requested cancellation.' });
    await resolveSyncConflict('conflict-id', {
      resolution: 'KEEP_LOCAL',
      comment: 'Approved local revision is authoritative.',
    });
    expect(apiClientMock.post).toHaveBeenNthCalledWith(
      1,
      '/sharepoint/sync-jobs/job-id/cancel',
      { reason: 'Operator requested cancellation.' },
    );
    expect(apiClientMock.post).toHaveBeenNthCalledWith(
      2,
      '/sharepoint/conflicts/conflict-id/resolve',
      {
        resolution: 'KEEP_LOCAL',
        comment: 'Approved local revision is authoritative.',
      },
    );
  });

  it('loads remote file status through the authenticated backend', async () => {
    const status = {
      documentFileId: 'file-id',
      storageProvider: 'HYBRID' as const,
      remoteSyncStatus: 'SYNCED' as const,
    };
    apiClientMock.get.mockResolvedValue(response(status));
    await expect(getDocumentRemoteStatus('file-id')).resolves.toEqual(status);
    expect(apiClientMock.get).toHaveBeenCalledWith(
      '/document-files/file-id/sharepoint/status',
      {},
    );
  });

  it('uses private notification endpoints for unread state and mark-all', async () => {
    apiClientMock.get.mockResolvedValue(response({ unreadCount: 4 }));
    apiClientMock.post.mockResolvedValue(response({ unreadCount: 0 }));
    await expect(getNotificationUnreadCount()).resolves.toEqual({ unreadCount: 4 });
    await expect(markAllNotificationsRead()).resolves.toEqual({ unreadCount: 0 });
    expect(apiClientMock.get).toHaveBeenCalledWith(
      '/notifications/unread-count',
      {},
    );
    expect(apiClientMock.post).toHaveBeenCalledWith('/notifications/read-all');
  });

  it('persists quiet hours and channel availability as user preferences', async () => {
    const payload = {
      items: [],
      quietHoursEnabled: true,
      quietHoursStart: '22:00',
      quietHoursEnd: '07:00',
      timezone: 'Asia/Makassar',
    };
    apiClientMock.put.mockResolvedValue(
      response({ ...payload, availableChannels: ['IN_APP'] }),
    );
    await updateNotificationPreferences(payload);
    expect(apiClientMock.put).toHaveBeenCalledWith(
      '/notification-preferences',
      payload,
    );
  });

  it('loads sanitized system health and retries dead-letter jobs with a reason', async () => {
    apiClientMock.get.mockResolvedValue(
      response({
        status: 'degraded',
        environment: 'test',
        version: '1.0.0',
        checkedAt: '2026-07-26T01:00:00Z',
        components: [],
      }),
    );
    apiClientMock.post.mockResolvedValue(response({ id: 'job-id' }));
    await getSystemHealth();
    await retryDeadLetterJob('job-id', { reason: 'Dependency was restored.' });
    expect(apiClientMock.get).toHaveBeenCalledWith('/admin/system-health', {});
    expect(apiClientMock.post).toHaveBeenCalledWith(
      '/admin/dead-letter-jobs/job-id/retry',
      { reason: 'Dependency was restored.' },
    );
  });

  it('starts retention as an explicit dry-run', async () => {
    apiClientMock.post.mockResolvedValue(
      response({
        jobId: 'cleanup-job',
        dryRun: true,
        policiesEvaluated: 1,
        recordsMatched: 12,
        message: 'Preview queued',
      }),
    );
    const payload = {
      policyId: 'policy-id',
      dryRun: true,
      reason: 'Quarterly retention review.',
    };
    await executeRetentionCleanup(payload);
    expect(apiClientMock.post).toHaveBeenCalledWith(
      '/admin/retention-policies/cleanup',
      payload,
    );
  });
});
