import type { AxiosRequestConfig } from 'axios';

import { apiClient } from './client';
import type { ApiResponse } from '../types/auth';
import type {
  Finding,
  FindingAcceptRiskRequest,
  FindingAssignRequest,
  FindingBulkActionRequest,
  FindingBulkActionResult,
  FindingDownload,
  FindingExportFormat,
  FindingFalsePositiveRequest,
  FindingList,
  FindingListParams,
  FindingReopenRequest,
  FindingResolveRequest,
  FindingReturnToOpenRequest,
  FindingReviewRequest,
  FindingsReport,
  FindingUpdateRequest,
  ManualFindingRequest,
} from '../types/finding';
import { getDownloadFileName } from '../utils/downloadFile';

const resourcePath = '/findings';
const exportTimeout = 10 * 60 * 1_000;
const withSignal = (signal?: AbortSignal): AxiosRequestConfig =>
  signal ? { signal } : {};

export const findingParamsSerializer = { indexes: null } as const;

export const listFindings = async (
  params: FindingListParams,
  signal?: AbortSignal,
): Promise<FindingList> => {
  const { data: response } = await apiClient.get<ApiResponse<FindingList>>(
    resourcePath,
    {
      params,
      paramsSerializer: findingParamsSerializer,
      ...withSignal(signal),
    },
  );
  return response.data;
};

export const getFinding = async (
  findingId: string,
  signal?: AbortSignal,
): Promise<Finding> => {
  const { data: response } = await apiClient.get<ApiResponse<Finding>>(
    `${resourcePath}/${findingId}`,
    withSignal(signal),
  );
  return response.data;
};

export const createManualFinding = async (
  payload: ManualFindingRequest,
): Promise<Finding> => {
  const { data: response } = await apiClient.post<ApiResponse<Finding>>(
    `${resourcePath}/manual`,
    payload,
  );
  return response.data;
};

export const updateFinding = async (
  findingId: string,
  payload: FindingUpdateRequest,
): Promise<Finding> => {
  const { data: response } = await apiClient.put<ApiResponse<Finding>>(
    `${resourcePath}/${findingId}`,
    payload,
  );
  return response.data;
};

export const reviewFinding = async (
  findingId: string,
  payload: FindingReviewRequest,
): Promise<Finding> => {
  const { data: response } = await apiClient.post<ApiResponse<Finding>>(
    `${resourcePath}/${findingId}/review`,
    payload,
  );
  return response.data;
};

export const resolveFinding = async (
  findingId: string,
  payload: FindingResolveRequest,
): Promise<Finding> => {
  const { data: response } = await apiClient.post<ApiResponse<Finding>>(
    `${resourcePath}/${findingId}/resolve`,
    payload,
  );
  return response.data;
};

export const returnFindingToOpen = async (
  findingId: string,
  payload: FindingReturnToOpenRequest,
): Promise<Finding> => {
  const { data: response } = await apiClient.post<ApiResponse<Finding>>(
    `${resourcePath}/${findingId}/return-to-open`,
    payload,
  );
  return response.data;
};

export const reopenFinding = async (
  findingId: string,
  payload: FindingReopenRequest,
): Promise<Finding> => {
  const { data: response } = await apiClient.post<ApiResponse<Finding>>(
    `${resourcePath}/${findingId}/reopen`,
    payload,
  );
  return response.data;
};

export const markFalsePositive = async (
  findingId: string,
  payload: FindingFalsePositiveRequest,
): Promise<Finding> => {
  const { data: response } = await apiClient.post<ApiResponse<Finding>>(
    `${resourcePath}/${findingId}/false-positive`,
    payload,
  );
  return response.data;
};

export const acceptFindingRisk = async (
  findingId: string,
  payload: FindingAcceptRiskRequest,
): Promise<Finding> => {
  const { data: response } = await apiClient.post<ApiResponse<Finding>>(
    `${resourcePath}/${findingId}/accept-risk`,
    payload,
  );
  return response.data;
};

export const assignFinding = async (
  findingId: string,
  payload: FindingAssignRequest,
): Promise<Finding> => {
  const { data: response } = await apiClient.post<ApiResponse<Finding>>(
    `${resourcePath}/${findingId}/assign`,
    payload,
  );
  return response.data;
};

export const bulkActionFindings = async (
  payload: FindingBulkActionRequest,
): Promise<FindingBulkActionResult> => {
  const { data: response } = await apiClient.post<ApiResponse<FindingBulkActionResult>>(
    `${resourcePath}/bulk-actions`,
    payload,
  );
  return response.data;
};

export const exportFindings = async (
  format: FindingExportFormat,
  params: Omit<FindingListParams, 'page' | 'pageSize'>,
): Promise<FindingDownload> => {
  const response = await apiClient.get<Blob>(`${resourcePath}/export`, {
    params: { ...params, format },
    responseType: 'blob',
    timeout: exportTimeout,
  });
  return {
    blob: response.data,
    fileName: getDownloadFileName(response.headers['content-disposition']),
  };
};

export const getFindingsReport = async (
  params: FindingListParams,
  signal?: AbortSignal,
): Promise<FindingsReport> => {
  const { data: response } = await apiClient.get<ApiResponse<FindingsReport>>(
    '/reports/findings',
    { params, ...withSignal(signal) },
  );
  return response.data;
};

export const findingApi = {
  listFindings,
  getFinding,
  createManualFinding,
  updateFinding,
  reviewFinding,
  returnFindingToOpen,
  resolveFinding,
  reopenFinding,
  markFalsePositive,
  acceptFindingRisk,
  assignFinding,
  bulkActionFindings,
  exportFindings,
  getFindingsReport,
} as const;
