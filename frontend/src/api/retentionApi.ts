import type { AxiosRequestConfig } from 'axios';

import { apiClient } from './client';
import type { ApiResponse } from '../types/auth';
import type {
  RetentionPolicy,
  RetentionPolicyCreate,
  RetentionPolicyList,
  RetentionPolicyListParams,
  RetentionPolicyUpdate,
  RetentionRunRequest,
  RetentionRunResult,
} from '../types/retention';

const basePath = '/admin/retention-policies';
const withSignal = (signal?: AbortSignal): AxiosRequestConfig =>
  signal ? { signal } : {};

export const listRetentionPolicies = async (
  params: RetentionPolicyListParams,
  signal?: AbortSignal,
): Promise<RetentionPolicyList> => {
  const { data } = await apiClient.get<ApiResponse<RetentionPolicyList>>(basePath, {
    params,
    ...withSignal(signal),
  });
  return data.data;
};

export const createRetentionPolicy = async (
  payload: RetentionPolicyCreate,
): Promise<RetentionPolicy> => {
  const { data } = await apiClient.post<ApiResponse<RetentionPolicy>>(
    basePath,
    payload,
  );
  return data.data;
};

export const updateRetentionPolicy = async (
  policyId: string,
  payload: RetentionPolicyUpdate,
): Promise<RetentionPolicy> => {
  const { data } = await apiClient.put<ApiResponse<RetentionPolicy>>(
    `${basePath}/${policyId}`,
    payload,
  );
  return data.data;
};

export const runRetentionPolicies = async (
  payload: RetentionRunRequest,
): Promise<RetentionRunResult> => {
  const { data } = await apiClient.post<ApiResponse<RetentionRunResult>>(
    `${basePath}/run`,
    payload,
  );
  return data.data;
};

export const retentionApi = {
  list: listRetentionPolicies,
  create: createRetentionPolicy,
  update: updateRetentionPolicy,
  run: runRetentionPolicies,
} as const;
