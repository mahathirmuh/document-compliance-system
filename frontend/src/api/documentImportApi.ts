import type { AxiosRequestConfig } from 'axios';

import { apiClient } from './client';
import type { ApiResponse } from '../types/auth';
import type {
  DocumentImportMode,
  DocumentImportPreview,
  DocumentImportResult,
} from '../types/documentImport';
import type { BinaryDownload } from '../types/masterData';
import { getDownloadFileName } from '../utils/downloadFile';

const importPath = '/documents/import';

const withSignal = (signal?: AbortSignal): AxiosRequestConfig =>
  signal ? { signal } : {};

const createImportForm = (file: File, mode?: DocumentImportMode): FormData => {
  const form = new FormData();
  form.append('file', file);
  if (mode) {
    form.append('mode', mode);
  }
  return form;
};

export const downloadImportTemplate = async (
  signal?: AbortSignal,
): Promise<BinaryDownload> => {
  const response = await apiClient.get<Blob>(`${importPath}/template`, {
    responseType: 'blob',
    timeout: 60_000,
    ...withSignal(signal),
  });
  return {
    blob: response.data,
    fileName: getDownloadFileName(response.headers['content-disposition']),
  };
};

export const previewImport = async (
  file: File,
  signal?: AbortSignal,
): Promise<DocumentImportPreview> => {
  const { data: response } = await apiClient.post<ApiResponse<DocumentImportPreview>>(
    `${importPath}/preview`,
    createImportForm(file),
    {
      timeout: 60_000,
      ...withSignal(signal),
    },
  );
  return response.data;
};

export const confirmImport = async (
  file: File,
  mode: DocumentImportMode,
  signal?: AbortSignal,
): Promise<DocumentImportResult> => {
  const { data: response } = await apiClient.post<ApiResponse<DocumentImportResult>>(
    `${importPath}/confirm`,
    createImportForm(file, mode),
    {
      timeout: 120_000,
      ...withSignal(signal),
    },
  );
  return response.data;
};

export const documentImportApi = {
  downloadImportTemplate,
  previewImport,
  confirmImport,
} as const;
