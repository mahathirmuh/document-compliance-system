import {
  AxiosError,
  AxiosHeaders,
  type AxiosAdapter,
  type InternalAxiosRequestConfig,
} from 'axios';
import { describe, expect, it } from 'vitest';

import { useAuthStore } from '../store/authStore';
import type { AuthSession } from '../types/auth';
import { apiClient } from './axios';

const makeSession = (suffix: string): AuthSession => ({
  accessToken: `access-${suffix}`,
  refreshToken: `refresh-${suffix}`,
  tokenType: 'bearer',
  expiresIn: 900,
  user: {
    id: `00000000-0000-4000-8000-00000000000${suffix}`,
    name: `User ${suffix}`,
    email: `user-${suffix}@example.com`,
    role: 'VIEWER',
    departmentId: null,
    isActive: true,
  },
  permissions: ['dashboard:view'],
});

const unauthorized = (config: InternalAxiosRequestConfig): AxiosError =>
  new AxiosError('Unauthorized', AxiosError.ERR_BAD_REQUEST, config, undefined, {
    config,
    data: null,
    headers: new AxiosHeaders(),
    status: 401,
    statusText: 'Unauthorized',
  });

describe('authentication interceptor session isolation', () => {
  it('does not let a stale 401 clear or refresh a newer login', async () => {
    window.history.replaceState({}, '', '/login');
    useAuthStore.getState().setAuth(makeSession('1'));

    let rejectOldRequest: (() => void) | undefined;
    let markAdapterReady: (() => void) | undefined;
    const adapterReady = new Promise<void>((resolve) => {
      markAdapterReady = resolve;
    });
    const adapter: AxiosAdapter = (config) =>
      new Promise((_resolve, reject) => {
        rejectOldRequest = () => reject(unauthorized(config));
        markAdapterReady?.();
      });

    const oldRequest = apiClient.get('/protected', { adapter });
    await adapterReady;

    useAuthStore.getState().clearAuth();
    useAuthStore.getState().setAuth(makeSession('2'));
    rejectOldRequest?.();

    await expect(oldRequest).rejects.toBeInstanceOf(AxiosError);
    expect(useAuthStore.getState().refreshToken).toBe('refresh-2');
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it('clears the current session when its one retry is still unauthorized', async () => {
    window.history.replaceState({}, '', '/login');
    useAuthStore.getState().setAuth(makeSession('1'));
    let adapterCalls = 0;
    const adapter: AxiosAdapter = async (config) => {
      adapterCalls += 1;
      if (adapterCalls === 1) {
        useAuthStore.getState().updateTokens({
          accessToken: 'access-rotated',
          refreshToken: 'refresh-rotated',
          tokenType: 'bearer',
          expiresIn: 900,
        });
      }
      throw unauthorized(config);
    };

    await expect(apiClient.get('/protected', { adapter })).rejects.toBeInstanceOf(
      AxiosError,
    );

    expect(adapterCalls).toBe(2);
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(useAuthStore.getState().refreshToken).toBeNull();
  });
});
