import { apiClient } from './client';
import type { DocumentExportParams } from '../types/document';
import type { BinaryDownload } from '../types/masterData';
import { getDownloadFileName } from '../utils/downloadFile';

export const exportDocumentRegister = async (
  params: DocumentExportParams,
  signal?: AbortSignal,
): Promise<BinaryDownload> => {
  const response = await apiClient.get<Blob>('/documents/export', {
    params,
    responseType: 'blob',
    timeout: 120_000,
    ...(signal ? { signal } : {}),
  });
  return {
    blob: response.data,
    fileName: getDownloadFileName(response.headers['content-disposition']),
  };
};

export const documentExportApi = {
  exportDocumentRegister,
} as const;
