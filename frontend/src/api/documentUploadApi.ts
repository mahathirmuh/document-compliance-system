import type { AxiosProgressEvent, AxiosRequestConfig } from 'axios';

import { apiClient } from './client';
import type { ApiResponse } from '../types/auth';
import type {
  UploadConfirmationRequest,
  UploadConfirmationResult,
  UploadPreviewResponse,
  UploadProgressHandler,
} from '../types/documentUpload';

const resourcePath = '/document-files';
const uploadTimeout = 10 * 60 * 1_000;

const progressConfig = (
  onProgress?: UploadProgressHandler,
  signal?: AbortSignal,
): AxiosRequestConfig => ({
  timeout: uploadTimeout,
  ...(signal ? { signal } : {}),
  onUploadProgress: (event: AxiosProgressEvent): void => {
    if (!onProgress || !event.total) {
      return;
    }
    onProgress(Math.min(100, Math.round((event.loaded * 100) / event.total)));
  },
});

export interface SingleUploadOptions {
  documentId?: string;
  revisionId?: string;
  onProgress?: UploadProgressHandler;
  signal?: AbortSignal;
}

export const uploadSingleFile = async (
  file: File,
  options: SingleUploadOptions = {},
): Promise<UploadPreviewResponse> => {
  const formData = new FormData();
  formData.append('file', file, file.name);
  if (options.documentId) {
    formData.append('documentId', options.documentId);
  }
  if (options.revisionId) {
    formData.append('revisionId', options.revisionId);
  }

  const { data: response } = await apiClient.post<ApiResponse<UploadPreviewResponse>>(
    `${resourcePath}/upload`,
    formData,
    progressConfig(options.onProgress, options.signal),
  );
  return response.data;
};

export const confirmSingleUpload = async (
  sessionId: string,
  payload: UploadConfirmationRequest,
): Promise<UploadConfirmationResult> => {
  const { data: response } = await apiClient.post<
    ApiResponse<UploadConfirmationResult>
  >(`${resourcePath}/upload/${sessionId}/confirm`, payload, {
    timeout: uploadTimeout,
  });
  return response.data;
};

export const cancelUploadSession = async (
  sessionId: string,
): Promise<UploadPreviewResponse> => {
  const { data: response } = await apiClient.post<ApiResponse<UploadPreviewResponse>>(
    `${resourcePath}/upload/${sessionId}/cancel`,
  );
  return response.data;
};

export interface BatchUploadOptions {
  onProgress?: UploadProgressHandler;
  signal?: AbortSignal;
}

export const uploadBatchFiles = async (
  files: readonly File[],
  options: BatchUploadOptions = {},
): Promise<UploadPreviewResponse> => {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file, file.name));

  const { data: response } = await apiClient.post<ApiResponse<UploadPreviewResponse>>(
    `${resourcePath}/batch-upload`,
    formData,
    progressConfig(options.onProgress, options.signal),
  );
  return response.data;
};

export const confirmBatchUpload = async (
  sessionId: string,
  payload: UploadConfirmationRequest,
): Promise<UploadConfirmationResult> => {
  const { data: response } = await apiClient.post<
    ApiResponse<UploadConfirmationResult>
  >(`${resourcePath}/batch-upload/${sessionId}/confirm`, payload, {
    timeout: uploadTimeout,
  });
  return response.data;
};

export const documentUploadApi = {
  uploadSingleFile,
  confirmSingleUpload,
  cancelUploadSession,
  uploadBatchFiles,
  confirmBatchUpload,
} as const;
