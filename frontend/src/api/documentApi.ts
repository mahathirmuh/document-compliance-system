import type { AxiosRequestConfig } from 'axios';

import { apiClient } from './client';
import type { ApiResponse } from '../types/auth';
import type {
  DocumentArchiveRequest,
  DocumentBulkArchiveRequest,
  DocumentBulkRestoreRequest,
  DocumentBulkResult,
  DocumentBulkUpdateStatusRequest,
  DocumentCreate,
  DocumentDetail,
  DocumentList,
  DocumentListParams,
  DocumentParseRequest,
  DocumentParseResponse,
  DocumentRestoreRequest,
  DocumentUpdate,
} from '../types/document';
import type { DocumentFormOptions } from '../types/documentFormOptions';

const resourcePath = '/documents';

const withSignal = (signal?: AbortSignal): AxiosRequestConfig =>
  signal ? { signal } : {};

export const listDocuments = async (
  params: DocumentListParams,
  signal?: AbortSignal,
): Promise<DocumentList> => {
  const { data: response } = await apiClient.get<ApiResponse<DocumentList>>(
    resourcePath,
    {
      params,
      ...withSignal(signal),
    },
  );
  return response.data;
};

export const getDocumentFormOptions = async (
  signal?: AbortSignal,
): Promise<DocumentFormOptions> => {
  const { data: response } = await apiClient.get<ApiResponse<DocumentFormOptions>>(
    `${resourcePath}/form-options`,
    withSignal(signal),
  );
  return response.data;
};

export const getDocument = async (
  documentId: string,
  signal?: AbortSignal,
): Promise<DocumentDetail> => {
  const { data: response } = await apiClient.get<ApiResponse<DocumentDetail>>(
    `${resourcePath}/${documentId}`,
    withSignal(signal),
  );
  return response.data;
};

export const createDocument = async (
  payload: DocumentCreate,
): Promise<DocumentDetail> => {
  const { data: response } = await apiClient.post<ApiResponse<DocumentDetail>>(
    resourcePath,
    payload,
  );
  return response.data;
};

export const updateDocument = async (
  documentId: string,
  payload: DocumentUpdate,
): Promise<DocumentDetail> => {
  const { data: response } = await apiClient.put<ApiResponse<DocumentDetail>>(
    `${resourcePath}/${documentId}`,
    payload,
  );
  return response.data;
};

export const archiveDocument = async (
  documentId: string,
  payload: DocumentArchiveRequest,
): Promise<DocumentDetail> => {
  const { data: response } = await apiClient.post<ApiResponse<DocumentDetail>>(
    `${resourcePath}/${documentId}/archive`,
    payload,
  );
  return response.data;
};

export const restoreDocument = async (
  documentId: string,
  payload: DocumentRestoreRequest = {},
): Promise<DocumentDetail> => {
  const { data: response } = await apiClient.post<ApiResponse<DocumentDetail>>(
    `${resourcePath}/${documentId}/restore`,
    payload,
  );
  return response.data;
};

export const parseDocumentCode = async (
  payload: DocumentParseRequest,
  signal?: AbortSignal,
): Promise<DocumentParseResponse> => {
  const { data: response } = await apiClient.post<ApiResponse<DocumentParseResponse>>(
    `${resourcePath}/parse-code`,
    payload,
    withSignal(signal),
  );
  return response.data;
};

export const bulkArchive = async (
  payload: DocumentBulkArchiveRequest,
): Promise<DocumentBulkResult> => {
  const { data: response } = await apiClient.post<ApiResponse<DocumentBulkResult>>(
    `${resourcePath}/bulk/archive`,
    payload,
  );
  return response.data;
};

export const bulkRestore = async (
  payload: DocumentBulkRestoreRequest,
): Promise<DocumentBulkResult> => {
  const { data: response } = await apiClient.post<ApiResponse<DocumentBulkResult>>(
    `${resourcePath}/bulk/restore`,
    payload,
  );
  return response.data;
};

export const bulkUpdateStatus = async (
  payload: DocumentBulkUpdateStatusRequest,
): Promise<DocumentBulkResult> => {
  const { data: response } = await apiClient.post<ApiResponse<DocumentBulkResult>>(
    `${resourcePath}/bulk/update-status`,
    payload,
  );
  return response.data;
};

export const documentApi = {
  listDocuments,
  getDocumentFormOptions,
  getDocument,
  createDocument,
  updateDocument,
  archiveDocument,
  restoreDocument,
  parseDocumentCode,
  bulkArchive,
  bulkRestore,
  bulkUpdateStatus,
} as const;
