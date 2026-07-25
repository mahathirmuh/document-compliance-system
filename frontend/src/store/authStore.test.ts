import { describe, expect, it } from 'vitest';

import { useAuthStore } from './authStore';
import type { AuthSession } from '../types/auth';

const session: AuthSession = {
  accessToken: 'access-token',
  refreshToken: 'refresh-token',
  tokenType: 'bearer',
  expiresIn: 900,
  user: {
    id: '00000000-0000-4000-8000-000000000001',
    name: 'System Administrator',
    email: 'admin@example.com',
    role: 'SUPER_ADMIN',
    departmentId: null,
    isActive: true,
  },
  permissions: ['dashboard:view'],
};

describe('authStore persistence', () => {
  it('persists the session through the isolated storage boundary', () => {
    useAuthStore.getState().setAuth(session);

    const persisted = window.localStorage.getItem('document-compliance-auth');

    expect(persisted).toContain('access-token');
    expect(persisted).toContain('refresh-token');
    expect(persisted).not.toContain('password');
    expect(persisted).not.toContain('sessionGeneration');
  });

  it('removes persisted credentials when auth is cleared', () => {
    const generationBeforeLogin = useAuthStore.getState().sessionGeneration;
    useAuthStore.getState().setAuth(session);
    const generationAfterLogin = useAuthStore.getState().sessionGeneration;
    useAuthStore.getState().clearAuth();

    const persisted = window.localStorage.getItem('document-compliance-auth');

    expect(generationAfterLogin).toBe(generationBeforeLogin + 1);
    expect(useAuthStore.getState().sessionGeneration).toBe(generationAfterLogin + 1);
    expect(persisted).not.toContain('access-token');
    expect(persisted).not.toContain('refresh-token');
  });
});
