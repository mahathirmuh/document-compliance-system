import type { AxiosRequestConfig } from 'axios';

import { apiClient } from './client';
import type { ApiResponse } from '../types/auth';
import type {
  DocumentRemoteStatus,
  SharePointFileVersionList,
} from '../types/sharepoint';
import type {
  ConflictAssignmentRequest,
  ConflictResolutionRequest,
  SharePointSyncConflict,
  SharePointSyncJob,
  SharePointSyncProfile,
  SharePointSyncProfileWrite,
  SharePointSyncRunRequest,
  SyncConflictList,
  SyncConflictListParams,
  SyncExport,
  SyncItemList,
  SyncItemListParams,
  SyncJobCreate,
  SyncJobList,
  SyncJobListParams,
  SyncProfileList,
  SyncProfileListParams,
  SyncDeltaResetResult,
} from '../types/synchronisation';
import { getDownloadFileName } from '../utils/downloadFile';

const basePath = '/sharepoint';
const withSignal = (signal?: AbortSignal): AxiosRequestConfig =>
  signal ? { signal } : {};

export const listSyncProfiles = async (
  params: SyncProfileListParams,
  signal?: AbortSignal,
): Promise<SyncProfileList> => {
  const { data } = await apiClient.get<ApiResponse<SyncProfileList>>(
    `${basePath}/sync-profiles`,
    { params, ...withSignal(signal) },
  );
  return data.data;
};

export const getSyncProfile = async (
  profileId: string,
  signal?: AbortSignal,
): Promise<SharePointSyncProfile> => {
  const { data } = await apiClient.get<ApiResponse<SharePointSyncProfile>>(
    `${basePath}/sync-profiles/${profileId}`,
    withSignal(signal),
  );
  return data.data;
};

export const createSyncProfile = async (
  payload: SharePointSyncProfileWrite,
): Promise<SharePointSyncProfile> => {
  const { data } = await apiClient.post<ApiResponse<SharePointSyncProfile>>(
    `${basePath}/sync-profiles`,
    payload,
  );
  return data.data;
};

export const updateSyncProfile = async (
  profileId: string,
  payload: SharePointSyncProfileWrite,
): Promise<SharePointSyncProfile> => {
  const { data } = await apiClient.put<ApiResponse<SharePointSyncProfile>>(
    `${basePath}/sync-profiles/${profileId}`,
    payload,
  );
  return data.data;
};

export const setSyncProfileActive = async (
  profileId: string,
  active: boolean,
): Promise<SharePointSyncProfile> => {
  const { data } = await apiClient.post<ApiResponse<SharePointSyncProfile>>(
    `${basePath}/sync-profiles/${profileId}/${active ? 'activate' : 'deactivate'}`,
  );
  return data.data;
};

export const runSyncProfile = async (
  profileId: string,
  payload: SharePointSyncRunRequest,
): Promise<SharePointSyncJob> => {
  const { data } = await apiClient.post<ApiResponse<SharePointSyncJob>>(
    `${basePath}/sync-profiles/${profileId}/run`,
    payload,
  );
  return data.data;
};

export const resetSyncProfileDelta = async (
  profileId: string,
  reason: string,
): Promise<SyncDeltaResetResult> => {
  const { data } = await apiClient.post<ApiResponse<SyncDeltaResetResult>>(
    `${basePath}/sync-profiles/${profileId}/reset-delta`,
    { confirmationReason: reason },
  );
  return data.data;
};

export const listSyncJobs = async (
  params: SyncJobListParams,
  signal?: AbortSignal,
): Promise<SyncJobList> => {
  const { data } = await apiClient.get<ApiResponse<SyncJobList>>(
    `${basePath}/sync-jobs`,
    { params, ...withSignal(signal) },
  );
  return data.data;
};

export const createSyncJob = async (
  payload: SyncJobCreate,
): Promise<SharePointSyncJob> => {
  const { data } = await apiClient.post<ApiResponse<SharePointSyncJob>>(
    `${basePath}/sync-jobs`,
    payload,
  );
  return data.data;
};

export const getSyncJob = async (
  jobId: string,
  signal?: AbortSignal,
): Promise<SharePointSyncJob> => {
  const { data } = await apiClient.get<ApiResponse<SharePointSyncJob>>(
    `${basePath}/sync-jobs/${jobId}`,
    withSignal(signal),
  );
  return data.data;
};

export const cancelSyncJob = async (
  jobId: string,
): Promise<SharePointSyncJob> => {
  const { data } = await apiClient.post<ApiResponse<SharePointSyncJob>>(
    `${basePath}/sync-jobs/${jobId}/cancel`,
  );
  return data.data;
};

export const retrySyncJob = async (
  jobId: string,
): Promise<SharePointSyncJob> => {
  const { data } = await apiClient.post<ApiResponse<SharePointSyncJob>>(
    `${basePath}/sync-jobs/${jobId}/retry`,
  );
  return data.data;
};

export const listSyncJobItems = async (
  jobId: string,
  params: SyncItemListParams,
  signal?: AbortSignal,
): Promise<SyncItemList> => {
  const { data } = await apiClient.get<ApiResponse<SyncItemList>>(
    `${basePath}/sync-jobs/${jobId}/items`,
    { params, ...withSignal(signal) },
  );
  return data.data;
};

export const exportSyncJob = async (
  jobId: string,
  format: 'json' | 'xlsx',
): Promise<SyncExport> => {
  const response = await apiClient.get<Blob>(`${basePath}/sync-jobs/${jobId}/export`, {
    params: { format },
    responseType: 'blob',
  });
  return {
    blob: response.data,
    fileName: getDownloadFileName(response.headers['content-disposition']),
  };
};

export const listSyncConflicts = async (
  params: SyncConflictListParams,
  signal?: AbortSignal,
): Promise<SyncConflictList> => {
  const { data } = await apiClient.get<ApiResponse<SyncConflictList>>(
    `${basePath}/conflicts`,
    { params, ...withSignal(signal) },
  );
  return data.data;
};

export const getSyncConflict = async (
  conflictId: string,
  signal?: AbortSignal,
): Promise<SharePointSyncConflict> => {
  const { data } = await apiClient.get<ApiResponse<SharePointSyncConflict>>(
    `${basePath}/conflicts/${conflictId}`,
    withSignal(signal),
  );
  return data.data;
};

export const assignSyncConflict = async (
  conflictId: string,
  payload: ConflictAssignmentRequest,
): Promise<SharePointSyncConflict> => {
  const { data } = await apiClient.post<ApiResponse<SharePointSyncConflict>>(
    `${basePath}/conflicts/${conflictId}/assign`,
    payload,
  );
  return data.data;
};

export const resolveSyncConflict = async (
  conflictId: string,
  payload: ConflictResolutionRequest,
): Promise<SharePointSyncConflict> => {
  const { data } = await apiClient.post<ApiResponse<SharePointSyncConflict>>(
    `${basePath}/conflicts/${conflictId}/resolve`,
    payload,
  );
  return data.data;
};

export const ignoreSyncConflict = async (
  conflictId: string,
  comment: string,
): Promise<SharePointSyncConflict> => {
  const { data } = await apiClient.post<ApiResponse<SharePointSyncConflict>>(
    `${basePath}/conflicts/${conflictId}/ignore`,
    { comment },
  );
  return data.data;
};

const documentFileSharePointPath = (fileId: string): string =>
  `/document-files/${fileId}/sharepoint`;

export const pushDocumentFile = async (
  fileId: string,
): Promise<SharePointSyncJob> => {
  const { data } = await apiClient.post<ApiResponse<SharePointSyncJob>>(
    `${documentFileSharePointPath(fileId)}/push`,
  );
  return data.data;
};

export const pullDocumentFile = async (
  fileId: string,
): Promise<SharePointSyncJob> => {
  const { data } = await apiClient.post<ApiResponse<SharePointSyncJob>>(
    `${documentFileSharePointPath(fileId)}/pull`,
  );
  return data.data;
};

export const getDocumentRemoteStatus = async (
  fileId: string,
  signal?: AbortSignal,
): Promise<DocumentRemoteStatus> => {
  const { data } = await apiClient.get<ApiResponse<DocumentRemoteStatus>>(
    `${documentFileSharePointPath(fileId)}/status`,
    withSignal(signal),
  );
  return data.data;
};

export const listDocumentRemoteVersions = async (
  fileId: string,
  params: { page: number; pageSize: number },
  signal?: AbortSignal,
): Promise<SharePointFileVersionList> => {
  const { data } = await apiClient.get<ApiResponse<SharePointFileVersionList>>(
    `${documentFileSharePointPath(fileId)}/versions`,
    { params, ...withSignal(signal) },
  );
  return data.data;
};

export const reconcileDocumentFile = async (
  fileId: string,
): Promise<SharePointSyncJob> => {
  const { data } = await apiClient.post<ApiResponse<SharePointSyncJob>>(
    `${documentFileSharePointPath(fileId)}/reconcile`,
  );
  return data.data;
};

export const sharePointSyncApi = {
  listProfiles: listSyncProfiles,
  getProfile: getSyncProfile,
  createProfile: createSyncProfile,
  updateProfile: updateSyncProfile,
  setProfileActive: setSyncProfileActive,
  runProfile: runSyncProfile,
  resetProfileDelta: resetSyncProfileDelta,
  listJobs: listSyncJobs,
  createJob: createSyncJob,
  getJob: getSyncJob,
  cancelJob: cancelSyncJob,
  retryJob: retrySyncJob,
  listJobItems: listSyncJobItems,
  exportJob: exportSyncJob,
  listConflicts: listSyncConflicts,
  getConflict: getSyncConflict,
  assignConflict: assignSyncConflict,
  resolveConflict: resolveSyncConflict,
  ignoreConflict: ignoreSyncConflict,
  pushDocumentFile,
  pullDocumentFile,
  getDocumentRemoteStatus,
  listDocumentRemoteVersions,
  reconcileDocumentFile,
} as const;
