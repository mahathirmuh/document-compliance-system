import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useAuthStore } from '../store/authStore';
import type { AuthSession } from '../types/auth';
import { notificationEventTypes } from '../types/notification';
import { BackgroundJobsPage } from './admin/BackgroundJobsPage';
import { SystemHealthPage } from './admin/SystemHealthPage';
import { GraphSubscriptionsPage } from './integrations/GraphSubscriptionsPage';
import { NotificationSettingsPage } from './settings/NotificationSettingsPage';

const mocks = vi.hoisted(() => ({
  createSubscription: vi.fn(),
  renewSubscription: vi.fn(),
  disableSubscription: vi.fn(),
  deleteSubscription: vi.fn(),
  updatePreferences: vi.fn(),
  retryDeadLetter: vi.fn(),
  dismissDeadLetter: vi.fn(),
  showToast: vi.fn(),
  notificationPreferences: [
    {
      id: null,
      userId: 'user-id',
      eventType: 'DOCUMENT_UPLOADED',
      inAppEnabled: true,
      emailEnabled: false,
      teamsEnabled: false,
      telegramEnabled: false,
      digestMode: 'NONE',
      quietHoursEnabled: false,
      quietHoursStart: null,
      quietHoursEnd: null,
      timezone: 'Asia/Makassar',
      createdAt: null,
      updatedAt: null,
    },
  ],
}));

vi.mock('../hooks/useSharePointConnections', () => ({
  useGraphSubscriptions: () => ({
    data: {
      items: [],
      page: 1,
      pageSize: 20,
      totalItems: 0,
      totalPages: 0,
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useSharePointConnections: () => ({
    data: {
      items: [
        {
          id: 'connection-id',
          name: 'Controlled Library',
          driveId: 'drive-id',
          isActive: true,
        },
      ],
    },
  }),
  useSharePointConnectionMutations: () => ({
    createSubscription: {
      mutateAsync: mocks.createSubscription,
      isPending: false,
    },
    renewSubscription: {
      mutateAsync: mocks.renewSubscription,
      isPending: false,
    },
    disableSubscription: {
      mutateAsync: mocks.disableSubscription,
      isPending: false,
    },
    deleteSubscription: {
      mutateAsync: mocks.deleteSubscription,
      isPending: false,
    },
  }),
}));

vi.mock('../hooks/useSharePointSync', () => ({
  useSharePointSyncProfiles: () => ({
    data: {
      items: [
        {
          id: 'profile-id',
          name: 'Outbound Webhook',
          sharepointConnectionId: 'connection-id',
          webhookEnabled: true,
          isActive: true,
        },
      ],
    },
  }),
}));

vi.mock('../hooks/useNotifications', () => ({
  useNotificationPreferences: () => ({
    data: mocks.notificationPreferences,
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useNotificationMutations: () => ({
    updatePreferences: {
      mutateAsync: mocks.updatePreferences,
      isPending: false,
    },
  }),
}));

vi.mock('../hooks/useSystemHealth', () => ({
  useSystemHealth: () => ({
    data: {
      status: 'degraded',
      checkedAt: '2026-07-26T01:00:00Z',
      dependencies: [
        {
          name: 'microsoft_graph',
          status: 'disabled',
          latencyMs: null,
          message: null,
          checkedAt: '2026-07-26T01:00:00Z',
        },
      ],
      workers: [
        {
          workerName: 'sharepoint_worker',
          queueName: 'sharepoint',
          status: 'healthy',
          lastHeartbeatAt: '2026-07-26T00:59:55Z',
          ageSeconds: 5,
        },
      ],
    },
    isLoading: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  }),
  useDeadLetterJobs: () => ({
    data: {
      items: [
        {
          id: 'dead-letter-id',
          taskName: 'sharepoint.sync',
          entityType: 'SharePointSyncJob',
          entityId: 'job-id',
          status: 'ACTIVE',
          attempts: 3,
          maximumAttempts: 5,
          errorCode: 'GRAPH_RATE_LIMITED',
          lastError: 'Remote service asked the worker to retry.',
          firstFailedAt: '2026-07-26T00:30:00Z',
          lastFailedAt: '2026-07-26T01:00:00Z',
          nextRetryAt: null,
          retriedAt: null,
          dismissedAt: null,
          dismissedBy: null,
          dismissalReason: null,
          createdAt: '2026-07-26T00:30:00Z',
          updatedAt: '2026-07-26T01:00:00Z',
        },
      ],
      page: 1,
      pageSize: 20,
      totalItems: 1,
      totalPages: 1,
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useDeadLetterMutations: () => ({
    retry: { mutateAsync: mocks.retryDeadLetter, isPending: false },
    dismiss: { mutateAsync: mocks.dismissDeadLetter, isPending: false },
  }),
}));

vi.mock('../providers/useToast', () => ({
  useToast: () => ({ showToast: mocks.showToast }),
}));

const adminSession: AuthSession = {
  accessToken: 'access',
  refreshToken: 'refresh',
  tokenType: 'bearer',
  expiresIn: 900,
  user: {
    id: 'user-id',
    name: 'Administrator',
    email: 'admin@example.com',
    role: 'SUPER_ADMIN',
    departmentId: null,
    isActive: true,
  },
  permissions: ['sharepoint:configure'],
};

describe('Phase 10 pages', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.createSubscription.mockResolvedValue({ id: 'subscription-id' });
    mocks.updatePreferences.mockResolvedValue([]);
    mocks.retryDeadLetter.mockResolvedValue({ id: 'dead-letter-id' });
    useAuthStore.getState().clearAuth();
  });

  it('creates a scoped Graph subscription with an ephemeral client state', async () => {
    useAuthStore.getState().setAuth(adminSession);
    render(<GraphSubscriptionsPage />);

    await userEvent.click(screen.getByRole('button', { name: 'Add Subscription' }));
    expect(screen.queryByLabelText(/client state/i)).not.toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText('Connection'), 'connection-id');
    await userEvent.selectOptions(
      screen.getByLabelText('Webhook-enabled sync profile'),
      'profile-id',
    );
    await userEvent.type(
      screen.getByLabelText('Notification URL'),
      'https://app.example.com/api/v1/sharepoint/webhook',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Create Subscription' }));

    await waitFor(() => expect(mocks.createSubscription).toHaveBeenCalledTimes(1));
    expect(mocks.createSubscription).toHaveBeenCalledWith(
      expect.objectContaining({
        sharepointConnectionId: 'connection-id',
        syncProfileId: 'profile-id',
        resource: 'drives/drive-id/root',
        changeType: 'updated',
        notificationUrl: 'https://app.example.com/api/v1/sharepoint/webhook',
        lifecycleNotificationUrl: null,
        clientState: expect.stringMatching(/^[a-f0-9]{64}$/),
      }),
    );
  });

  it('normalizes notification preferences and persists quiet hours', async () => {
    render(<NotificationSettingsPage />);

    const quietHours = await screen.findByLabelText('DOCUMENT_UPLOADED quiet hours');
    await userEvent.click(quietHours);
    await userEvent.selectOptions(
      screen.getByLabelText('DOCUMENT_UPLOADED digest'),
      'DAILY',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Save Preferences' }));

    await waitFor(() => expect(mocks.updatePreferences).toHaveBeenCalledTimes(1));
    const payload = mocks.updatePreferences.mock.calls[0]?.[0] as {
      preferences: Array<Record<string, unknown>>;
    };
    expect(payload.preferences).toHaveLength(notificationEventTypes.length);
    expect(payload.preferences).toContainEqual(
      expect.objectContaining({
        eventType: 'DOCUMENT_UPLOADED',
        digestMode: 'DAILY',
        quietHoursEnabled: true,
        quietHoursStart: '22:00',
        quietHoursEnd: '07:00',
        timezone: 'Asia/Makassar',
      }),
    );
  });

  it('renders disabled dependencies and worker heartbeat state safely', () => {
    render(<SystemHealthPage />);

    expect(
      screen.getByText('Integration is disabled; this is not a failure.'),
    ).toBeInTheDocument();
    expect(screen.getByText('sharepoint')).toBeInTheDocument();
    expect(screen.getByText('5 seconds')).toBeInTheDocument();
  });

  it('retries a sanitized dead-letter job by identifier only', async () => {
    render(<BackgroundJobsPage />);

    expect(screen.getByText('GRAPH_RATE_LIMITED')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(mocks.retryDeadLetter).toHaveBeenCalledWith('dead-letter-id');
  });
});
