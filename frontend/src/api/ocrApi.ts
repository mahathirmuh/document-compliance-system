import axios, { type AxiosRequestConfig } from 'axios';

import { apiClient } from './client';
import type { ApiResponse } from '../types/auth';
import type {
  OCRBlockList,
  OCRBlockListParams,
  OCRCancelResult,
  OCRDownload,
  OCRHistoryParams,
  OCRJob,
  OCRJobList,
  OCRJobListParams,
  OCRPageList,
  OCRPageListParams,
  OCRPageDetail,
  OCRQueuedResult,
  OCRReprocessRequest,
  OCRRun,
  OCRRunHistory,
  OCRStartRequest,
} from '../types/ocr';
import { getDownloadFileName } from '../utils/downloadFile';

const jobPath = '/ocr/jobs';
const runPath = '/ocr/runs';
const exportTimeout = 10 * 60 * 1_000;

export const ocrParamsSerializer = { indexes: null } as const;

const withSignal = (signal?: AbortSignal): AxiosRequestConfig =>
  signal ? { signal } : {};

export const startOCR = async (payload: OCRStartRequest): Promise<OCRQueuedResult> => {
  const { data: response } = await apiClient.post<ApiResponse<OCRQueuedResult>>(
    jobPath,
    payload,
  );
  return response.data;
};

export const getOCRJob = async (
  jobId: string,
  signal?: AbortSignal,
): Promise<OCRJob> => {
  const { data: response } = await apiClient.get<ApiResponse<OCRJob>>(
    `${jobPath}/${jobId}`,
    withSignal(signal),
  );
  return response.data;
};

export const listOCRJobs = async (
  params: OCRJobListParams,
  signal?: AbortSignal,
): Promise<OCRJobList> => {
  const { data: response } = await apiClient.get<ApiResponse<OCRJobList>>(jobPath, {
    params,
    paramsSerializer: ocrParamsSerializer,
    ...withSignal(signal),
  });
  return response.data;
};

export const cancelOCR = async (jobId: string): Promise<OCRCancelResult> => {
  const { data: response } = await apiClient.post<ApiResponse<OCRCancelResult>>(
    `${jobPath}/${jobId}/cancel`,
  );
  return response.data;
};

export const getOCRRun = async (
  runId: string,
  signal?: AbortSignal,
): Promise<OCRRun> => {
  const { data: response } = await apiClient.get<ApiResponse<OCRRun>>(
    `${runPath}/${runId}`,
    withSignal(signal),
  );
  return response.data;
};

export const listOCRPages = async (
  runId: string,
  params: OCRPageListParams,
  signal?: AbortSignal,
): Promise<OCRPageList> => {
  const { data: response } = await apiClient.get<ApiResponse<OCRPageList>>(
    `${runPath}/${runId}/pages`,
    { params, ...withSignal(signal) },
  );
  return response.data;
};

export const getOCRPage = async (
  runId: string,
  pageNumber: number,
  signal?: AbortSignal,
): Promise<OCRPageDetail> => {
  const { data: response } = await apiClient.get<ApiResponse<OCRPageDetail>>(
    `${runPath}/${runId}/pages/${pageNumber}`,
    withSignal(signal),
  );
  return response.data;
};

export const listOCRBlocks = async (
  runId: string,
  params: OCRBlockListParams,
  signal?: AbortSignal,
): Promise<OCRBlockList> => {
  const { data: response } = await apiClient.get<ApiResponse<OCRBlockList>>(
    `${runPath}/${runId}/blocks`,
    { params, ...withSignal(signal) },
  );
  return response.data;
};

export const getLatestOCR = async (
  fileId: string,
  signal?: AbortSignal,
): Promise<OCRRun | null> => {
  try {
    const { data: response } = await apiClient.get<ApiResponse<OCRRun | null>>(
      `/document-files/${fileId}/ocr`,
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

export const getOCRHistory = async (
  fileId: string,
  params: OCRHistoryParams,
  signal?: AbortSignal,
): Promise<OCRRunHistory> => {
  const { data: response } = await apiClient.get<ApiResponse<OCRRunHistory>>(
    `/document-files/${fileId}/ocr-history`,
    { params, ...withSignal(signal) },
  );
  return response.data;
};

export const reOCR = async (
  runId: string,
  payload: OCRReprocessRequest,
): Promise<OCRQueuedResult> => {
  const { data: response } = await apiClient.post<ApiResponse<OCRQueuedResult>>(
    `${runPath}/${runId}/reocr`,
    payload,
  );
  return response.data;
};

export const exportOCR = async (
  runId: string,
  format: 'json' | 'txt',
): Promise<OCRDownload> => {
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

export const ocrApi = {
  startOCR,
  getOCRJob,
  listOCRJobs,
  cancelOCR,
  getOCRRun,
  listOCRPages,
  getOCRPage,
  listOCRBlocks,
  getLatestOCR,
  getOCRHistory,
  reOCR,
  exportOCR,
} as const;
