import axios, {
  AxiosHeaders,
  type AxiosError,
  type InternalAxiosRequestConfig,
} from 'axios';

import { useAuthStore } from '../store/authStore';
import type { ApiResponse, RefreshTokenResponse } from '../types/auth';

interface RetryableRequestConfig extends InternalAxiosRequestConfig {
  _authRetry?: boolean;
  _authSessionGeneration?: number;
  _authRefreshToken?: string | null;
}

const configuredBaseUrl =
  import.meta.env.VITE_API_URL?.trim() || import.meta.env.VITE_API_BASE_URL?.trim();

const baseURL = configuredBaseUrl || '/api/v1';

export const apiClient = axios.create({
  baseURL,
  timeout: 10_000,
  headers: {
    Accept: 'application/json',
  },
});

const refreshClient = axios.create({
  baseURL,
  timeout: 10_000,
  headers: {
    Accept: 'application/json',
  },
});

interface ActiveRefresh {
  refreshToken: string;
  promise: Promise<RefreshTokenResponse>;
}

let activeRefresh: ActiveRefresh | null = null;
let authRedirectInProgress = false;

const isRefreshExcludedEndpoint = (url?: string): boolean =>
  url?.includes('/auth/login') === true ||
  url?.includes('/auth/refresh') === true ||
  url?.includes('/auth/logout') === true;

const performRefresh = async (refreshToken: string): Promise<RefreshTokenResponse> => {
  const { data: response } = await refreshClient.post<
    ApiResponse<RefreshTokenResponse>
  >('/auth/refresh', { refreshToken });
  return response.data;
};

const getRefreshedSession = (refreshToken: string): Promise<RefreshTokenResponse> => {
  if (activeRefresh === null || activeRefresh.refreshToken !== refreshToken) {
    const refreshPromise = performRefresh(refreshToken)
      .then((tokens) => {
        const authState = useAuthStore.getState();
        if (!authState.isAuthenticated || authState.refreshToken !== refreshToken) {
          throw new Error('Authentication session changed during token refresh.');
        }
        authState.updateTokens(tokens);
        return tokens;
      })
      .finally(() => {
        if (activeRefresh?.refreshToken === refreshToken) {
          activeRefresh = null;
        }
      });
    activeRefresh = {
      refreshToken,
      promise: refreshPromise,
    };
  }

  return activeRefresh.promise;
};

const clearSessionAndRedirect = (): void => {
  useAuthStore.getState().clearAuth();

  if (
    typeof window !== 'undefined' &&
    window.location.pathname !== '/login' &&
    !authRedirectInProgress
  ) {
    authRedirectInProgress = true;
    window.location.assign('/login');
  }
};

apiClient.interceptors.request.use((config) => {
  const authState = useAuthStore.getState();
  const accessToken = authState.accessToken;
  const request = config as RetryableRequestConfig;

  if (request._authSessionGeneration === undefined) {
    request._authSessionGeneration = authState.sessionGeneration;
    request._authRefreshToken = authState.refreshToken;
  }

  if (accessToken && !isRefreshExcludedEndpoint(config.url)) {
    const headers = AxiosHeaders.from(config.headers);
    headers.set('Authorization', `Bearer ${accessToken}`);
    config.headers = headers;
  }

  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const request = error.config as RetryableRequestConfig | undefined;

    if (
      error.response?.status !== 401 ||
      request === undefined ||
      isRefreshExcludedEndpoint(request.url)
    ) {
      return Promise.reject(error);
    }

    const authState = useAuthStore.getState();
    if (
      request._authSessionGeneration === undefined ||
      request._authSessionGeneration !== authState.sessionGeneration
    ) {
      return Promise.reject(error);
    }

    if (request._authRetry === true) {
      clearSessionAndRedirect();
      return Promise.reject(error);
    }

    const refreshToken = authState.refreshToken;
    if (!refreshToken) {
      clearSessionAndRedirect();
      return Promise.reject(error);
    }

    request._authRetry = true;

    if (request._authRefreshToken !== refreshToken) {
      const currentAccessToken = authState.accessToken;
      if (!currentAccessToken) {
        clearSessionAndRedirect();
        return Promise.reject(error);
      }
      const headers = AxiosHeaders.from(request.headers);
      headers.set('Authorization', `Bearer ${currentAccessToken}`);
      request.headers = headers;
      return apiClient(request);
    }

    let tokens: RefreshTokenResponse;
    try {
      tokens = await getRefreshedSession(refreshToken);
    } catch (refreshError: unknown) {
      const currentAuthState = useAuthStore.getState();
      if (
        currentAuthState.sessionGeneration === request._authSessionGeneration &&
        currentAuthState.refreshToken === refreshToken
      ) {
        clearSessionAndRedirect();
      }
      return Promise.reject(refreshError);
    }

    const headers = AxiosHeaders.from(request.headers);
    headers.set('Authorization', `Bearer ${tokens.accessToken}`);
    request.headers = headers;
    return apiClient(request);
  },
);
