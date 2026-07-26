import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';

import { fetchHealth } from '../api/health';
import { getDocument } from '../api/documentApi';
import { useAuthStore } from '../store/authStore';
import { superAdminSession } from '../test/authFixtures';
import { AppRoutes } from './AppRoutes';

vi.mock('../api/health', () => ({
  fetchHealth: vi.fn(),
}));
vi.mock('../api/documentApi', () => ({
  getDocument: vi.fn(),
}));

const renderRoutes = (initialEntry = '/dashboard') => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <AppRoutes />
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

describe('application authorization routes', () => {
  it('opens the dashboard for an authenticated user with permission', async () => {
    vi.mocked(fetchHealth).mockResolvedValue({
      status: 'healthy',
      service: 'document-compliance-api',
      version: '0.5.0',
    });
    useAuthStore.getState().setAuth(superAdminSession);

    renderRoutes();

    expect(
      await screen.findByRole('heading', {
        name: 'Welcome, System Administrator',
      }),
    ).toBeInTheDocument();
    expect(await screen.findByText('Backend connected')).toBeInTheDocument();
  });

  it('shows the unauthorized page when dashboard permission is missing', async () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      permissions: ['documents:view'],
      user: {
        ...superAdminSession.user,
        role: 'VIEWER',
      },
    });

    renderRoutes();

    expect(await screen.findByText('403')).toBeInTheDocument();
    expect(
      screen.getByText('You do not have permission to access this page.'),
    ).toBeInTheDocument();
  });

  it('redirects a user without master_data:view away from Master Data', async () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      permissions: ['dashboard:view'],
    });

    renderRoutes('/master-data/departments');

    expect(await screen.findByText('403')).toBeInTheDocument();
    expect(
      screen.getByText('You do not have permission to access this page.'),
    ).toBeInTheDocument();
  });

  it.each([
    '/documents/new',
    '/documents/document-id/edit',
    '/documents/upload',
    '/documents/batch-upload',
    '/documents/upload-history',
  ])(
    'blocks protected document mutation route %s without its permission',
    async (route) => {
      useAuthStore.getState().setAuth({
        ...superAdminSession,
        permissions: ['documents:view'],
        user: {
          ...superAdminSession.user,
          role: 'VIEWER',
        },
      });

      renderRoutes(route);

      expect(await screen.findByText('403')).toBeInTheDocument();
    },
  );

  it('allows a view-only user to open the revision history route', async () => {
    vi.mocked(getDocument).mockImplementation(() => new Promise(() => undefined));
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      permissions: ['documents:view'],
      user: {
        ...superAdminSession.user,
        role: 'VIEWER',
      },
    });

    renderRoutes('/documents/document-id/revisions');

    expect(
      await screen.findByLabelText('Loading revisions', undefined, {
        timeout: 5_000,
      }),
    ).toBeInTheDocument();
    expect(screen.queryByText('403')).not.toBeInTheDocument();
  });

  it.each(['/reports/compliance', '/reports/findings'])(
    'blocks report route %s without reports:view',
    async (route) => {
      useAuthStore.getState().setAuth({
        ...superAdminSession,
        permissions: ['compliance:view', 'findings:view'],
        user: {
          ...superAdminSession.user,
          role: 'VIEWER',
        },
      });

      renderRoutes(route);

      expect(await screen.findByText('403')).toBeInTheDocument();
    },
  );
});
