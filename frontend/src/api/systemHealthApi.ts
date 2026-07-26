import type { AxiosRequestConfig } from 'axios';

import { apiClient } from './client';
import type { ApiResponse } from '../types/auth';
import type {
  DeadLetterActionRequest,
  DeadLetterJobList,
  DeadLetterListParams,
  DeadLetterMutationResult,
  SystemHealthSummary,
} from '../types/systemHealth';

const withSignal = (signal?: AbortSignal): AxiosRequestConfig =>
  signal ? { signal } : {};

export const getSystemHealth = async (
  signal?: AbortSignal,
): Promise<SystemHealthSummary> => {
  const { data } = await apiClient.get<ApiResponse<SystemHealthSummary>>(
    '/system-health',
    withSignal(signal),
  );
  return data.data;
};

export const listDeadLetterJobs = async (
  params: DeadLetterListParams,
  signal?: AbortSignal,
): Promise<DeadLetterJobList> => {
  const { data } = await apiClient.get<ApiResponse<DeadLetterJobList>>(
    '/admin/dead-letter-jobs',
    { params, ...withSignal(signal) },
  );
  return data.data;
};

export const retryDeadLetterJob = async (
  jobId: string,
): Promise<DeadLetterMutationResult> => {
  const { data } = await apiClient.post<ApiResponse<DeadLetterMutationResult>>(
    `/admin/dead-letter-jobs/${jobId}/retry`,
  );
  return data.data;
};

export const dismissDeadLetterJob = async (
  jobId: string,
  payload: DeadLetterActionRequest,
): Promise<DeadLetterMutationResult> => {
  const { data } = await apiClient.post<ApiResponse<DeadLetterMutationResult>>(
    `/admin/dead-letter-jobs/${jobId}/dismiss`,
    payload,
  );
  return data.data;
};

export const systemHealthApi = {
  get: getSystemHealth,
  listDeadLetterJobs,
  retryDeadLetterJob,
  dismissDeadLetterJob,
} as const;
