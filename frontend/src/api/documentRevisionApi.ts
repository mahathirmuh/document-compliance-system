import type { AxiosRequestConfig } from 'axios';

import { apiClient } from './client';
import type { ApiResponse } from '../types/auth';
import type {
  DocumentRevision,
  DocumentRevisionCreate,
  DocumentRevisionList,
  DocumentRevisionSetCurrentRequest,
  DocumentRevisionSupersedeRequest,
  DocumentRevisionUpdate,
} from '../types/documentRevision';

const revisionPath = (documentId: string): string =>
  `/documents/${documentId}/revisions`;

const withSignal = (signal?: AbortSignal): AxiosRequestConfig =>
  signal ? { signal } : {};

export const listRevisions = async (
  documentId: string,
  signal?: AbortSignal,
): Promise<DocumentRevisionList> => {
  const { data: response } = await apiClient.get<ApiResponse<DocumentRevisionList>>(
    revisionPath(documentId),
    withSignal(signal),
  );
  return response.data;
};

export const createRevision = async (
  documentId: string,
  payload: DocumentRevisionCreate,
): Promise<DocumentRevision> => {
  const { data: response } = await apiClient.post<ApiResponse<DocumentRevision>>(
    revisionPath(documentId),
    payload,
  );
  return response.data;
};

export const getRevision = async (
  documentId: string,
  revisionId: string,
  signal?: AbortSignal,
): Promise<DocumentRevision> => {
  const { data: response } = await apiClient.get<ApiResponse<DocumentRevision>>(
    `${revisionPath(documentId)}/${revisionId}`,
    withSignal(signal),
  );
  return response.data;
};

export const updateRevision = async (
  documentId: string,
  revisionId: string,
  payload: DocumentRevisionUpdate,
): Promise<DocumentRevision> => {
  const { data: response } = await apiClient.put<ApiResponse<DocumentRevision>>(
    `${revisionPath(documentId)}/${revisionId}`,
    payload,
  );
  return response.data;
};

export const setCurrentRevision = async (
  documentId: string,
  revisionId: string,
  payload: DocumentRevisionSetCurrentRequest = {},
): Promise<DocumentRevision> => {
  const { data: response } = await apiClient.post<ApiResponse<DocumentRevision>>(
    `${revisionPath(documentId)}/${revisionId}/set-current`,
    payload,
  );
  return response.data;
};

export const supersedeRevision = async (
  documentId: string,
  revisionId: string,
  payload: DocumentRevisionSupersedeRequest,
): Promise<DocumentRevision> => {
  const { data: response } = await apiClient.post<ApiResponse<DocumentRevision>>(
    `${revisionPath(documentId)}/${revisionId}/supersede`,
    payload,
  );
  return response.data;
};

export const documentRevisionApi = {
  listRevisions,
  createRevision,
  getRevision,
  updateRevision,
  setCurrentRevision,
  supersedeRevision,
} as const;
