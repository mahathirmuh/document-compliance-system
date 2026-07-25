import axios, { type AxiosRequestConfig } from 'axios';

import { apiClient } from './client';
import type { ApiResponse } from '../types/auth';
import type {
  LanguageBlockList,
  LanguageBlockListParams,
  LanguageContainerList,
  LanguageContainerListParams,
  LanguageDetectionCancelResult,
  LanguageDetectionDocumentList,
  LanguageDetectionDocumentListParams,
  LanguageDetectionHistory,
  LanguageDetectionJob,
  LanguageDetectionJobList,
  LanguageDetectionJobListParams,
  LanguageDetectionQueuedResult,
  LanguageDetectionRun,
  LanguageDetectionStartRequest,
  LanguageDownload,
  LanguageHistoryParams,
  LanguageRedetectRequest,
  LanguageSummary,
} from '../types/languageDetection';
import { getDownloadFileName } from '../utils/downloadFile';

const jobPath = '/language-detection/jobs';
const runPath = '/language-detection/runs';
const documentPath = '/language-detection/documents';
const exportTimeout = 10 * 60 * 1_000;

export const languageDetectionParamsSerializer = { indexes: null } as const;

const withSignal = (signal?: AbortSignal): AxiosRequestConfig =>
  signal ? { signal } : {};

export const startLanguageDetection = async (
  payload: LanguageDetectionStartRequest,
): Promise<LanguageDetectionQueuedResult> => {
  const { data: response } = await apiClient.post<
    ApiResponse<LanguageDetectionQueuedResult>
  >(jobPath, payload);
  return response.data;
};

export const getLanguageDetectionJob = async (
  jobId: string,
  signal?: AbortSignal,
): Promise<LanguageDetectionJob> => {
  const { data: response } = await apiClient.get<ApiResponse<LanguageDetectionJob>>(
    `${jobPath}/${jobId}`,
    withSignal(signal),
  );
  return response.data;
};

export const listLanguageDetectionJobs = async (
  params: LanguageDetectionJobListParams,
  signal?: AbortSignal,
): Promise<LanguageDetectionJobList> => {
  const { data: response } = await apiClient.get<ApiResponse<LanguageDetectionJobList>>(
    jobPath,
    {
      params,
      paramsSerializer: languageDetectionParamsSerializer,
      ...withSignal(signal),
    },
  );
  return response.data;
};

export const listLanguageDetectionDocuments = async (
  params: LanguageDetectionDocumentListParams,
  signal?: AbortSignal,
): Promise<LanguageDetectionDocumentList> => {
  const { data: response } = await apiClient.get<
    ApiResponse<LanguageDetectionDocumentList>
  >(documentPath, {
    params,
    ...withSignal(signal),
  });
  return response.data;
};

export const cancelLanguageDetection = async (
  jobId: string,
): Promise<LanguageDetectionCancelResult> => {
  const { data: response } = await apiClient.post<
    ApiResponse<LanguageDetectionCancelResult>
  >(`${jobPath}/${jobId}/cancel`);
  return response.data;
};

export const getLanguageDetectionRun = async (
  runId: string,
  signal?: AbortSignal,
): Promise<LanguageDetectionRun> => {
  const { data: response } = await apiClient.get<ApiResponse<LanguageDetectionRun>>(
    `${runPath}/${runId}`,
    withSignal(signal),
  );
  return response.data;
};

export const getLanguageSummary = async (
  runId: string,
  signal?: AbortSignal,
): Promise<LanguageSummary> => {
  const { data: response } = await apiClient.get<ApiResponse<LanguageSummary>>(
    `${runPath}/${runId}/summary`,
    withSignal(signal),
  );
  return response.data;
};

export const listLanguageBlocks = async (
  runId: string,
  params: LanguageBlockListParams,
  signal?: AbortSignal,
): Promise<LanguageBlockList> => {
  const { data: response } = await apiClient.get<ApiResponse<LanguageBlockList>>(
    `${runPath}/${runId}/blocks`,
    { params, ...withSignal(signal) },
  );
  return response.data;
};

export const listLanguageContainers = async (
  runId: string,
  params: LanguageContainerListParams,
  signal?: AbortSignal,
): Promise<LanguageContainerList> => {
  const { data: response } = await apiClient.get<ApiResponse<LanguageContainerList>>(
    `${runPath}/${runId}/containers`,
    { params, ...withSignal(signal) },
  );
  return response.data;
};

export const getLatestLanguageDetection = async (
  fileId: string,
  signal?: AbortSignal,
): Promise<LanguageDetectionRun | null> => {
  try {
    const { data: response } = await apiClient.get<
      ApiResponse<LanguageDetectionRun | null>
    >(`/document-files/${fileId}/language-detection`, withSignal(signal));
    return response.data;
  } catch (error: unknown) {
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      return null;
    }
    throw error;
  }
};

export const getLanguageDetectionHistory = async (
  fileId: string,
  params: LanguageHistoryParams,
  signal?: AbortSignal,
): Promise<LanguageDetectionHistory> => {
  const { data: response } = await apiClient.get<ApiResponse<LanguageDetectionHistory>>(
    `/document-files/${fileId}/language-detection-history`,
    {
      params,
      ...withSignal(signal),
    },
  );
  return response.data;
};

export const redetectLanguage = async (
  runId: string,
  payload: LanguageRedetectRequest,
): Promise<LanguageDetectionQueuedResult> => {
  const { data: response } = await apiClient.post<
    ApiResponse<LanguageDetectionQueuedResult>
  >(`${runPath}/${runId}/redetect`, payload);
  return response.data;
};

export const exportLanguageResults = async (
  runId: string,
  format: 'json' | 'xlsx',
): Promise<LanguageDownload> => {
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

export const languageDetectionApi = {
  startLanguageDetection,
  listLanguageDetectionDocuments,
  getLanguageDetectionJob,
  listLanguageDetectionJobs,
  cancelLanguageDetection,
  getLanguageDetectionRun,
  getLanguageSummary,
  listLanguageBlocks,
  listLanguageContainers,
  getLatestLanguageDetection,
  getLanguageDetectionHistory,
  redetectLanguage,
  exportLanguageResults,
} as const;
