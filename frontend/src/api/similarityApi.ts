import axios, { type AxiosRequestConfig } from 'axios';

import { apiClient } from './client';
import type { ApiResponse } from '../types/auth';
import type {
  SectionSimilarityList,
  SimilarityCancelResult,
  SimilarityDownload,
  SimilarityExportFormat,
  SimilarityHistory,
  SimilarityHistoryParams,
  SimilarityJob,
  SimilarityJobList,
  SimilarityJobListParams,
  SimilarityQueuedResult,
  SimilarityRerunRequest,
  SimilarityResultList,
  SimilarityResultListParams,
  SimilarityRun,
  SimilarityStartRequest,
  SimilaritySummary,
} from '../types/similarity';
import { getDownloadFileName } from '../utils/downloadFile';

const jobsPath = '/similarity/jobs';
const runsPath = '/similarity/runs';
const exportTimeout = 10 * 60 * 1_000;
const paramsSerializer = { indexes: null } as const;

const withSignal = (signal?: AbortSignal): AxiosRequestConfig =>
  signal ? { signal } : {};

export const startSimilarity = async (
  payload: SimilarityStartRequest,
): Promise<SimilarityQueuedResult> => {
  const { data: response } = await apiClient.post<ApiResponse<SimilarityQueuedResult>>(
    jobsPath,
    payload,
  );
  return response.data;
};

export const listSimilarityJobs = async (
  params: SimilarityJobListParams,
  signal?: AbortSignal,
): Promise<SimilarityJobList> => {
  const { data: response } = await apiClient.get<ApiResponse<SimilarityJobList>>(
    jobsPath,
    { params, paramsSerializer, ...withSignal(signal) },
  );
  return response.data;
};

export const getSimilarityJob = async (
  jobId: string,
  signal?: AbortSignal,
): Promise<SimilarityJob> => {
  const { data: response } = await apiClient.get<ApiResponse<SimilarityJob>>(
    `${jobsPath}/${jobId}`,
    withSignal(signal),
  );
  return response.data;
};

export const cancelSimilarity = async (
  jobId: string,
): Promise<SimilarityCancelResult> => {
  const { data: response } = await apiClient.post<ApiResponse<SimilarityCancelResult>>(
    `${jobsPath}/${jobId}/cancel`,
  );
  return response.data;
};

export const getSimilarityRun = async (
  runId: string,
  signal?: AbortSignal,
): Promise<SimilarityRun> => {
  const { data: response } = await apiClient.get<ApiResponse<SimilarityRun>>(
    `${runsPath}/${runId}`,
    withSignal(signal),
  );
  return response.data;
};

export const getSimilaritySummary = async (
  runId: string,
  signal?: AbortSignal,
): Promise<SimilaritySummary> => {
  const { data: response } = await apiClient.get<ApiResponse<SimilaritySummary>>(
    `${runsPath}/${runId}/summary`,
    withSignal(signal),
  );
  return response.data;
};

export const listSimilarityResults = async (
  runId: string,
  params: SimilarityResultListParams,
  signal?: AbortSignal,
): Promise<SimilarityResultList> => {
  const { data: response } = await apiClient.get<ApiResponse<SimilarityResultList>>(
    `${runsPath}/${runId}/results`,
    { params, ...withSignal(signal) },
  );
  return response.data;
};

export const listSectionSimilarity = async (
  runId: string,
  signal?: AbortSignal,
): Promise<SectionSimilarityList> => {
  const { data: response } = await apiClient.get<ApiResponse<SectionSimilarityList>>(
    `${runsPath}/${runId}/sections`,
    withSignal(signal),
  );
  return response.data;
};

export const rerunSimilarity = async (
  runId: string,
  payload: SimilarityRerunRequest,
): Promise<SimilarityQueuedResult> => {
  const { data: response } = await apiClient.post<ApiResponse<SimilarityQueuedResult>>(
    `${runsPath}/${runId}/rerun`,
    payload,
  );
  return response.data;
};

export const exportSimilarity = async (
  runId: string,
  format: SimilarityExportFormat,
): Promise<SimilarityDownload> => {
  const response = await apiClient.get<Blob>(`${runsPath}/${runId}/export`, {
    params: { format },
    responseType: 'blob',
    timeout: exportTimeout,
  });
  return {
    blob: response.data,
    fileName: getDownloadFileName(response.headers['content-disposition']),
  };
};

export const getFileSimilarity = async (
  fileId: string,
  signal?: AbortSignal,
): Promise<SimilarityRun | null> => {
  try {
    const { data: response } = await apiClient.get<ApiResponse<SimilarityRun | null>>(
      `/document-files/${fileId}/similarity`,
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

export const getSimilarityHistory = async (
  fileId: string,
  params: SimilarityHistoryParams,
  signal?: AbortSignal,
): Promise<SimilarityHistory> => {
  const { data: response } = await apiClient.get<ApiResponse<SimilarityHistory>>(
    `/document-files/${fileId}/similarity-history`,
    { params, ...withSignal(signal) },
  );
  return response.data;
};

export const similarityApi = {
  startSimilarity,
  listSimilarityJobs,
  getSimilarityJob,
  cancelSimilarity,
  getSimilarityRun,
  getSimilaritySummary,
  listSimilarityResults,
  listSectionSimilarity,
  rerunSimilarity,
  exportSimilarity,
  getFileSimilarity,
  getSimilarityHistory,
} as const;
