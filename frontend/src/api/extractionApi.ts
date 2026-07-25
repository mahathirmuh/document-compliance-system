import axios, { type AxiosRequestConfig } from 'axios';

import { apiClient } from './client';
import type { ApiResponse } from '../types/auth';
import type {
  ExtractionCancelResult,
  ExtractionJobDetail,
  ExtractionJobList,
  ExtractionJobListParams,
  ExtractionQueuedResult,
  ExtractionRequest,
  ReExtractionRequest,
} from '../types/extraction';
import type {
  ExtractedBlockList,
  ExtractedContentSearchResponse,
  ExtractedContainerList,
  ExtractedTableList,
  ExtractionBlockListParams,
  ExtractionContainerListParams,
  ExtractionDownload,
  ExtractionRun,
  ExtractionRunHistory,
  ExtractionSearchParams,
  ExtractionTableListParams,
} from '../types/extractedContent';
import { getDownloadFileName } from '../utils/downloadFile';

const extractionPath = '/extractions';
const runPath = '/extraction-runs';
const exportTimeout = 10 * 60 * 1_000;

export const extractionParamsSerializer = { indexes: null } as const;

const withSignal = (signal?: AbortSignal): AxiosRequestConfig =>
  signal ? { signal } : {};

export const startExtraction = async (
  payload: ExtractionRequest,
): Promise<ExtractionQueuedResult> => {
  const { data: response } = await apiClient.post<ApiResponse<ExtractionQueuedResult>>(
    extractionPath,
    payload,
  );
  return response.data;
};

export const reextractDocumentFile = async (
  fileId: string,
  payload: ReExtractionRequest,
): Promise<ExtractionQueuedResult> => {
  const { data: response } = await apiClient.post<ApiResponse<ExtractionQueuedResult>>(
    `/document-files/${fileId}/reextract`,
    payload,
  );
  return response.data;
};

export const cancelExtraction = async (
  jobId: string,
): Promise<ExtractionCancelResult> => {
  const { data: response } = await apiClient.post<ApiResponse<ExtractionCancelResult>>(
    `${extractionPath}/${jobId}/cancel`,
  );
  return response.data;
};

export const getExtractionJob = async (
  jobId: string,
  signal?: AbortSignal,
): Promise<ExtractionJobDetail> => {
  const { data: response } = await apiClient.get<ApiResponse<ExtractionJobDetail>>(
    `${extractionPath}/${jobId}`,
    withSignal(signal),
  );
  return response.data;
};

export const listExtractionJobs = async (
  params: ExtractionJobListParams,
  signal?: AbortSignal,
): Promise<ExtractionJobList> => {
  const { data: response } = await apiClient.get<ApiResponse<ExtractionJobList>>(
    extractionPath,
    {
      params,
      paramsSerializer: extractionParamsSerializer,
      ...withSignal(signal),
    },
  );
  return response.data;
};

export const getLatestExtraction = async (
  fileId: string,
  signal?: AbortSignal,
): Promise<ExtractionRun | null> => {
  try {
    const { data: response } = await apiClient.get<ApiResponse<ExtractionRun | null>>(
      `/document-files/${fileId}/extraction`,
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

export const getExtractionHistory = async (
  fileId: string,
  params: { page: number; pageSize: number },
  signal?: AbortSignal,
): Promise<ExtractionRunHistory> => {
  const { data: response } = await apiClient.get<ApiResponse<ExtractionRunHistory>>(
    `/document-files/${fileId}/extraction-history`,
    {
      params,
      ...withSignal(signal),
    },
  );
  return response.data;
};

export const getExtractionRun = async (
  runId: string,
  signal?: AbortSignal,
): Promise<ExtractionRun> => {
  const { data: response } = await apiClient.get<ApiResponse<ExtractionRun>>(
    `${runPath}/${runId}`,
    withSignal(signal),
  );
  return response.data;
};

export const listExtractionContainers = async (
  runId: string,
  params: ExtractionContainerListParams,
  signal?: AbortSignal,
): Promise<ExtractedContainerList> => {
  const { data: response } = await apiClient.get<ApiResponse<ExtractedContainerList>>(
    `${runPath}/${runId}/containers`,
    {
      params,
      ...withSignal(signal),
    },
  );
  return response.data;
};

export const listExtractionBlocks = async (
  runId: string,
  params: ExtractionBlockListParams,
  signal?: AbortSignal,
): Promise<ExtractedBlockList> => {
  const { data: response } = await apiClient.get<ApiResponse<ExtractedBlockList>>(
    `${runPath}/${runId}/blocks`,
    {
      params,
      ...withSignal(signal),
    },
  );
  return response.data;
};

export const listExtractionTables = async (
  runId: string,
  params: ExtractionTableListParams,
  signal?: AbortSignal,
): Promise<ExtractedTableList> => {
  const { data: response } = await apiClient.get<ApiResponse<ExtractedTableList>>(
    `${runPath}/${runId}/tables`,
    {
      params,
      ...withSignal(signal),
    },
  );
  return response.data;
};

export const searchExtractedContent = async (
  runId: string,
  params: ExtractionSearchParams,
  signal?: AbortSignal,
): Promise<ExtractedContentSearchResponse> => {
  const { data: response } = await apiClient.get<
    ApiResponse<ExtractedContentSearchResponse>
  >(`${runPath}/${runId}/search`, {
    params,
    ...withSignal(signal),
  });
  return response.data;
};

export const exportExtractedContent = async (
  runId: string,
  format: 'json' | 'txt',
): Promise<ExtractionDownload> => {
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

export const extractionApi = {
  startExtraction,
  reextractDocumentFile,
  cancelExtraction,
  getExtractionJob,
  listExtractionJobs,
  getLatestExtraction,
  getExtractionHistory,
  getExtractionRun,
  listExtractionContainers,
  listExtractionBlocks,
  listExtractionTables,
  searchExtractedContent,
  exportExtractedContent,
} as const;
