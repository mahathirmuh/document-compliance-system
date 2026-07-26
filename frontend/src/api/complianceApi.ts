import axios, { type AxiosRequestConfig } from 'axios';

import { apiClient } from './client';
import type { ApiResponse } from '../types/auth';
import type {
  ComplianceComparison,
  ComplianceCancelResult,
  ComplianceDownload,
  ComplianceExportFormat,
  ComplianceHistory,
  ComplianceHistoryParams,
  ComplianceJob,
  ComplianceJobList,
  ComplianceJobListParams,
  ComplianceOverview,
  ComplianceOverviewParams,
  ComplianceQueuedResult,
  ComplianceReport,
  ComplianceReportParams,
  ComplianceRevalidateRequest,
  ComplianceRun,
  ComplianceScoreBreakdown,
  ComplianceStartRequest,
  ComplianceSummary,
  ComplianceResultListParams,
  DetectedSectionList,
  TranslationGroupList,
  TranslationGroupListParams,
} from '../types/compliance';
import { getDownloadFileName } from '../utils/downloadFile';

const jobPath = '/compliance/jobs';
const runPath = '/compliance/runs';
const exportTimeout = 10 * 60 * 1_000;

const withSignal = (signal?: AbortSignal): AxiosRequestConfig =>
  signal ? { signal } : {};

export const complianceParamsSerializer = { indexes: null } as const;

export const startComplianceValidation = async (
  payload: ComplianceStartRequest,
): Promise<ComplianceQueuedResult> => {
  const { data: response } = await apiClient.post<ApiResponse<ComplianceQueuedResult>>(
    jobPath,
    payload,
  );
  return response.data;
};

export const getComplianceJob = async (
  jobId: string,
  signal?: AbortSignal,
): Promise<ComplianceJob> => {
  const { data: response } = await apiClient.get<ApiResponse<ComplianceJob>>(
    `${jobPath}/${jobId}`,
    withSignal(signal),
  );
  return response.data;
};

export const listComplianceJobs = async (
  params: ComplianceJobListParams,
  signal?: AbortSignal,
): Promise<ComplianceJobList> => {
  const { data: response } = await apiClient.get<ApiResponse<ComplianceJobList>>(
    jobPath,
    {
      params,
      paramsSerializer: complianceParamsSerializer,
      ...withSignal(signal),
    },
  );
  return response.data;
};

export const cancelComplianceJob = async (
  jobId: string,
): Promise<ComplianceCancelResult> => {
  const { data: response } = await apiClient.post<ApiResponse<ComplianceCancelResult>>(
    `${jobPath}/${jobId}/cancel`,
  );
  return response.data;
};

export const getComplianceRun = async (
  runId: string,
  signal?: AbortSignal,
): Promise<ComplianceRun> => {
  const { data: response } = await apiClient.get<ApiResponse<ComplianceRun>>(
    `${runPath}/${runId}`,
    withSignal(signal),
  );
  return response.data;
};

export const getComplianceSummary = async (
  runId: string,
  signal?: AbortSignal,
): Promise<ComplianceSummary> => {
  const { data: response } = await apiClient.get<ApiResponse<ComplianceSummary>>(
    `${runPath}/${runId}/summary`,
    withSignal(signal),
  );
  return response.data;
};

export const getScoreBreakdown = async (
  runId: string,
  signal?: AbortSignal,
): Promise<ComplianceScoreBreakdown> => {
  const { data: response } = await apiClient.get<ApiResponse<ComplianceScoreBreakdown>>(
    `${runPath}/${runId}/score-breakdown`,
    withSignal(signal),
  );
  return response.data;
};

export const listDetectedSections = async (
  runId: string,
  params: ComplianceResultListParams,
  signal?: AbortSignal,
): Promise<DetectedSectionList> => {
  const { data: response } = await apiClient.get<ApiResponse<DetectedSectionList>>(
    `${runPath}/${runId}/sections`,
    { params, ...withSignal(signal) },
  );
  return response.data;
};

export const listTranslationGroups = async (
  runId: string,
  params: TranslationGroupListParams,
  signal?: AbortSignal,
): Promise<TranslationGroupList> => {
  const { data: response } = await apiClient.get<ApiResponse<TranslationGroupList>>(
    `${runPath}/${runId}/translation-groups`,
    { params, ...withSignal(signal) },
  );
  return response.data;
};

export const getDocumentCompliance = async (
  fileId: string,
  signal?: AbortSignal,
): Promise<ComplianceRun | null> => {
  try {
    const { data: response } = await apiClient.get<ApiResponse<ComplianceRun | null>>(
      `/document-files/${fileId}/compliance`,
      withSignal(signal),
    );
    return response.data;
  } catch (error: unknown) {
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      return null;
    }
    throw error;
  }
};

export const getComplianceHistory = async (
  fileId: string,
  params: ComplianceHistoryParams,
  signal?: AbortSignal,
): Promise<ComplianceHistory> => {
  const { data: response } = await apiClient.get<ApiResponse<ComplianceHistory>>(
    `/document-files/${fileId}/compliance-history`,
    { params, ...withSignal(signal) },
  );
  return response.data;
};

export const revalidateCompliance = async (
  runId: string,
  payload: ComplianceRevalidateRequest,
): Promise<ComplianceQueuedResult> => {
  const { data: response } = await apiClient.post<ApiResponse<ComplianceQueuedResult>>(
    `${runPath}/${runId}/revalidate`,
    payload,
  );
  return response.data;
};

export const compareComplianceRuns = async (
  runId: string,
  otherRunId: string,
  signal?: AbortSignal,
): Promise<ComplianceComparison> => {
  const { data: response } = await apiClient.get<ApiResponse<ComplianceComparison>>(
    `${runPath}/${runId}/compare/${otherRunId}`,
    withSignal(signal),
  );
  return response.data;
};

export const exportCompliance = async (
  runId: string,
  format: ComplianceExportFormat,
): Promise<ComplianceDownload> => {
  const response = await apiClient.get<Blob>(`${runPath}/${runId}/export`, {
    params: { format },
    responseType: 'blob',
    timeout: exportTimeout,
  });
  return {
    blob: response.data,
    fileName: getDownloadFileName(response.headers['content-disposition']),
  };
};

export const getComplianceOverview = async (
  params: ComplianceOverviewParams,
  signal?: AbortSignal,
): Promise<ComplianceOverview> => {
  const { data: response } = await apiClient.get<ApiResponse<ComplianceOverview>>(
    '/compliance/overview',
    { params, ...withSignal(signal) },
  );
  return response.data;
};

export const getComplianceReport = async (
  params: ComplianceReportParams,
  signal?: AbortSignal,
): Promise<ComplianceReport> => {
  const { data: response } = await apiClient.get<ApiResponse<ComplianceReport>>(
    '/reports/compliance',
    { params, ...withSignal(signal) },
  );
  return response.data;
};

export const exportComplianceReport = async (
  format: ComplianceExportFormat,
  params: Omit<ComplianceReportParams, 'page' | 'pageSize'>,
): Promise<ComplianceDownload> => {
  const response = await apiClient.get<Blob>('/reports/compliance', {
    params: { ...params, format },
    responseType: 'blob',
    timeout: exportTimeout,
  });
  return {
    blob: response.data,
    fileName: getDownloadFileName(response.headers['content-disposition']),
  };
};

export const complianceApi = {
  startComplianceValidation,
  getComplianceJob,
  listComplianceJobs,
  cancelComplianceJob,
  getComplianceRun,
  getComplianceSummary,
  getScoreBreakdown,
  listDetectedSections,
  listTranslationGroups,
  getDocumentCompliance,
  getComplianceHistory,
  revalidateCompliance,
  compareComplianceRuns,
  exportCompliance,
  getComplianceOverview,
  getComplianceReport,
  exportComplianceReport,
} as const;
