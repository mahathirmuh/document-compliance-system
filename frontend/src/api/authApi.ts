import type {
  ApiResponse,
  CurrentUserResponse,
  LoginRequest,
  LoginResponse,
  RefreshTokenResponse,
} from '../types/auth';
import { apiClient } from './axios';

export const authApi = {
  async login(payload: LoginRequest): Promise<LoginResponse> {
    const { data: response } = await apiClient.post<ApiResponse<LoginResponse>>(
      '/auth/login',
      payload,
    );
    return response.data;
  },

  async refreshToken(refreshToken: string): Promise<RefreshTokenResponse> {
    const { data: response } = await apiClient.post<ApiResponse<RefreshTokenResponse>>(
      '/auth/refresh',
      { refreshToken },
    );
    return response.data;
  },

  async logout(refreshToken: string): Promise<void> {
    await apiClient.post<ApiResponse<null>>('/auth/logout', { refreshToken });
  },

  async getCurrentUser(): Promise<CurrentUserResponse> {
    const { data: response } =
      await apiClient.get<ApiResponse<CurrentUserResponse>>('/auth/me');
    return response.data;
  },
};
