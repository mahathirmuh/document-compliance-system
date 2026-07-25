import type { AxiosRequestConfig } from 'axios';

import { apiClient } from './client';
import type { ApiResponse } from '../types/auth';
import type {
  BinaryDownload,
  ImportMode,
  ImportPreview,
  ImportResult,
  MasterDataEntityType,
  MasterDataOverview,
} from '../types/masterData';
import { getDownloadFileName } from '../utils/downloadFile';

const binaryRequestConfig: AxiosRequestConfig = {
  responseType: 'blob',
  timeout: 60_000,
};

const toDownload = (
  blob: Blob,
  contentDisposition: string | undefined,
): BinaryDownload => ({
  blob,
  fileName: getDownloadFileName(contentDisposition),
});

const createImportForm = (
  entityType: MasterDataEntityType,
  file: File,
  mode?: ImportMode,
): FormData => {
  const form = new FormData();
  form.append('entityType', entityType);
  form.append('file', file);
  if (mode) {
    form.append('mode', mode);
  }
  return form;
};

export const masterDataApi = {
  async getOverview(): Promise<MasterDataOverview> {
    const { data: response } = await apiClient.get<ApiResponse<MasterDataOverview>>(
      '/master-data/overview',
    );
    return response.data;
  },

  async previewImport(
    entityType: MasterDataEntityType,
    file: File,
  ): Promise<ImportPreview> {
    const { data: response } = await apiClient.post<ApiResponse<ImportPreview>>(
      '/master-data/import/preview',
      createImportForm(entityType, file),
      { timeout: 60_000 },
    );
    return response.data;
  },

  async confirmImport(
    entityType: MasterDataEntityType,
    file: File,
    mode: ImportMode,
  ): Promise<ImportResult> {
    const { data: response } = await apiClient.post<ApiResponse<ImportResult>>(
      '/master-data/import/confirm',
      createImportForm(entityType, file, mode),
      { timeout: 120_000 },
    );
    return response.data;
  },

  async downloadTemplate(entityType: MasterDataEntityType): Promise<BinaryDownload> {
    const response = await apiClient.get<Blob>(
      `/master-data/import/template/${entityType}`,
      binaryRequestConfig,
    );
    return toDownload(response.data, response.headers['content-disposition']);
  },

  async exportXlsx(
    entityType: MasterDataEntityType,
    params?: Record<string, string | number | boolean>,
  ): Promise<BinaryDownload> {
    const response = await apiClient.get<Blob>(`/master-data/export/${entityType}`, {
      ...binaryRequestConfig,
      params,
    });
    return toDownload(response.data, response.headers['content-disposition']);
  },
};
