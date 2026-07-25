import { apiClient } from './client';

export interface ApiErrorDetail {
  field?: string;
  message: string;
}

export interface ApiEnvelope<TData> {
  success: boolean;
  message: string;
  data: TData;
  errors: ApiErrorDetail[] | null;
}

export interface HealthData {
  status: 'healthy';
  service: string;
  version?: string;
}

export type HealthResponse = ApiEnvelope<HealthData>;

export const fetchHealth = async (): Promise<HealthData> => {
  const { data: response } = await apiClient.get<HealthResponse>('/health');

  if (!response.success || response.data.status !== 'healthy') {
    throw new Error(response.message || 'The backend returned an unhealthy status.');
  }

  return response.data;
};
