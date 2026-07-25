import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { authApi } from '../api/authApi';
import { useAuthStore } from '../store/authStore';
import { AuthProvider } from './AuthProvider';

vi.mock('../api/authApi', () => ({
  authApi: {
    getCurrentUser: vi.fn(),
  },
}));

const user = {
  id: '00000000-0000-4000-8000-000000000001',
  name: 'System Administrator',
  email: 'admin@example.com',
  role: 'SUPER_ADMIN' as const,
  departmentId: null,
  isActive: true,
};

describe('AuthProvider', () => {
  it('revalidates a persisted token before rendering the application', async () => {
    vi.mocked(authApi.getCurrentUser).mockResolvedValue({
      user,
      permissions: ['dashboard:view'],
    });
    useAuthStore.setState({
      accessToken: 'persisted-access-token',
      refreshToken: 'persisted-refresh-token',
      isAuthenticated: true,
      isInitializing: true,
    });

    render(
      <AuthProvider>
        <div>Application ready</div>
      </AuthProvider>,
    );

    expect(screen.getByText('Restoring your secure session...')).toBeInTheDocument();
    expect(await screen.findByText('Application ready')).toBeInTheDocument();
    expect(authApi.getCurrentUser).toHaveBeenCalledOnce();
    expect(useAuthStore.getState().user).toEqual(user);
  });

  it('clears an inconsistent persisted session without tokens', async () => {
    useAuthStore.setState({
      user,
      permissions: ['dashboard:view'],
      accessToken: null,
      refreshToken: null,
      isAuthenticated: true,
      isInitializing: true,
    });

    render(
      <AuthProvider>
        <div>Signed-out application</div>
      </AuthProvider>,
    );

    expect(await screen.findByText('Signed-out application')).toBeInTheDocument();
    await waitFor(() => {
      expect(useAuthStore.getState().isAuthenticated).toBe(false);
    });
    expect(authApi.getCurrentUser).not.toHaveBeenCalled();
  });
});
