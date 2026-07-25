import type { AxiosProgressEvent, AxiosRequestConfig } from 'axios';

import { apiClient } from './client';
import type { ApiResponse } from '../types/auth';
import type {
  DocumentFileDeleteRequest,
  DocumentFileDetail,
  DocumentFileDownload,
  DocumentFileHistory,
  DocumentFileHistoryParams,
  DocumentFileList,
  DocumentFileRestoreRequest,
} from '../types/documentFile';
import type { UploadProgressHandler } from '../types/documentUpload';
import { getDownloadFileName } from '../utils/downloadFile';

const resourcePath = '/document-files';
const fileTransferTimeout = 10 * 60 * 1_000;

const withSignal = (signal?: AbortSignal): AxiosRequestConfig =>
  signal ? { signal } : {};

export const getDocumentFile = async (
  fileId: string,
  signal?: AbortSignal,
): Promise<DocumentFileDetail> => {
  const { data: response } = await apiClient.get<ApiResponse<DocumentFileDetail>>(
    `${resourcePath}/${fileId}`,
    withSignal(signal),
  );
  return response.data;
};

const downloadFrom = async (path: string): Promise<DocumentFileDownload> => {
  const response = await apiClient.get<Blob>(path, {
    responseType: 'blob',
    timeout: fileTransferTimeout,
  });
  return {
    blob: response.data,
    fileName: getDownloadFileName(response.headers['content-disposition']),
  };
};

export const downloadDocumentFile = async (
  fileId: string,
): Promise<DocumentFileDownload> => downloadFrom(`${resourcePath}/${fileId}/download`);

export const downloadCurrentRevisionFile = async (
  documentId: string,
  revisionId: string,
): Promise<DocumentFileDownload> =>
  downloadFrom(`/documents/${documentId}/revisions/${revisionId}/download`);

export interface ReplaceDocumentFileInput {
  fileId: string;
  file: File;
  reason: string;
  onProgress?: UploadProgressHandler;
}

export const replaceDocumentFile = async ({
  file,
  fileId,
  onProgress,
  reason,
}: ReplaceDocumentFileInput): Promise<DocumentFileDetail> => {
  const formData = new FormData();
  formData.append('file', file, file.name);
  formData.append('reason', reason);

  const { data: response } = await apiClient.post<ApiResponse<DocumentFileDetail>>(
    `${resourcePath}/${fileId}/replace`,
    formData,
    {
      timeout: fileTransferTimeout,
      onUploadProgress: (event: AxiosProgressEvent): void => {
        if (!onProgress || !event.total) {
          return;
        }
        onProgress(Math.min(100, Math.round((event.loaded * 100) / event.total)));
      },
    },
  );
  return response.data;
};

export const deleteDocumentFile = async (
  fileId: string,
  payload: DocumentFileDeleteRequest,
): Promise<DocumentFileDetail> => {
  const { data: response } = await apiClient.post<ApiResponse<DocumentFileDetail>>(
    `${resourcePath}/${fileId}/delete`,
    payload,
  );
  return response.data;
};

export const restoreDocumentFile = async (
  fileId: string,
  payload: DocumentFileRestoreRequest = {},
): Promise<DocumentFileDetail> => {
  const { data: response } = await apiClient.post<ApiResponse<DocumentFileDetail>>(
    `${resourcePath}/${fileId}/restore`,
    payload,
  );
  return response.data;
};

export const listDocumentFiles = async (
  documentId: string,
  signal?: AbortSignal,
): Promise<DocumentFileList> => {
  const { data: response } = await apiClient.get<ApiResponse<DocumentFileList>>(
    `/documents/${documentId}/files`,
    withSignal(signal),
  );
  return response.data;
};

export const listRevisionFiles = async (
  documentId: string,
  revisionId: string,
  signal?: AbortSignal,
): Promise<DocumentFileList> => {
  const { data: response } = await apiClient.get<ApiResponse<DocumentFileList>>(
    `/documents/${documentId}/revisions/${revisionId}/files`,
    withSignal(signal),
  );
  return response.data;
};

export const listFileHistory = async (
  params: DocumentFileHistoryParams,
  signal?: AbortSignal,
): Promise<DocumentFileHistory> => {
  const { data: response } = await apiClient.get<ApiResponse<DocumentFileHistory>>(
    `${resourcePath}/history`,
    {
      params,
      ...withSignal(signal),
    },
  );
  return response.data;
};

export const documentFileApi = {
  getDocumentFile,
  downloadDocumentFile,
  downloadCurrentRevisionFile,
  replaceDocumentFile,
  deleteDocumentFile,
  restoreDocumentFile,
  listDocumentFiles,
  listRevisionFiles,
  listFileHistory,
} as const;
