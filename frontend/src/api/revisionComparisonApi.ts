import type { AxiosRequestConfig } from 'axios';

import { apiClient } from './client';
import type { ApiResponse } from '../types/auth';
import type {
  RevisionChangeList,
  RevisionChangeListParams,
  RevisionComparison,
  RevisionComparisonDownload,
  RevisionComparisonExportFormat,
  RevisionComparisonJob,
  RevisionComparisonJobList,
  RevisionComparisonJobListParams,
  RevisionComparisonRequest,
  RevisionComparisonQueuedResult,
  RevisionComparisonSummary,
  RevisionComparisonHistory,
  RevisionFindingChangeList,
  RevisionLanguageChangeList,
  RevisionSectionChangeList,
} from '../types/revisionComparison';
import { getDownloadFileName } from '../utils/downloadFile';

const jobsPath = '/revision-comparisons/jobs';
const comparisonsPath = '/revision-comparisons';
const exportTimeout = 10 * 60 * 1_000;
const paramsSerializer = { indexes: null } as const;

const withSignal = (signal?: AbortSignal): AxiosRequestConfig =>
  signal ? { signal } : {};

export const startRevisionComparison = async (
  payload: RevisionComparisonRequest,
): Promise<RevisionComparisonQueuedResult> => {
  const { data: response } = await apiClient.post<
    ApiResponse<RevisionComparisonQueuedResult>
  >(jobsPath, payload);
  return response.data;
};

export const listRevisionComparisonJobs = async (
  params: RevisionComparisonJobListParams,
  signal?: AbortSignal,
): Promise<RevisionComparisonJobList> => {
  const { data: response } = await apiClient.get<
    ApiResponse<RevisionComparisonJobList>
  >(jobsPath, { params, paramsSerializer, ...withSignal(signal) });
  return response.data;
};

export const getRevisionComparisonJob = async (
  jobId: string,
  signal?: AbortSignal,
): Promise<RevisionComparisonJob> => {
  const { data: response } = await apiClient.get<ApiResponse<RevisionComparisonJob>>(
    `${jobsPath}/${jobId}`,
    withSignal(signal),
  );
  return response.data;
};

export const cancelRevisionComparison = async (
  jobId: string,
): Promise<RevisionComparisonJob> => {
  const { data: response } = await apiClient.post<ApiResponse<RevisionComparisonJob>>(
    `${jobsPath}/${jobId}/cancel`,
  );
  return response.data;
};

export const getRevisionComparison = async (
  comparisonId: string,
  signal?: AbortSignal,
): Promise<RevisionComparison> => {
  const { data: response } = await apiClient.get<ApiResponse<RevisionComparison>>(
    `${comparisonsPath}/${comparisonId}`,
    withSignal(signal),
  );
  return response.data;
};

export const getRevisionComparisonSummary = async (
  comparisonId: string,
  signal?: AbortSignal,
): Promise<RevisionComparisonSummary> => {
  const { data: response } = await apiClient.get<
    ApiResponse<RevisionComparisonSummary>
  >(`${comparisonsPath}/${comparisonId}/summary`, withSignal(signal));
  return response.data;
};

export const listRevisionChanges = async (
  comparisonId: string,
  params: RevisionChangeListParams,
  signal?: AbortSignal,
): Promise<RevisionChangeList> => {
  const { data: response } = await apiClient.get<ApiResponse<RevisionChangeList>>(
    `${comparisonsPath}/${comparisonId}/changes`,
    { params, ...withSignal(signal) },
  );
  return response.data;
};

export const getRevisionSectionChanges = async (
  comparisonId: string,
  signal?: AbortSignal,
): Promise<RevisionSectionChangeList> => {
  const { data: response } = await apiClient.get<
    ApiResponse<RevisionSectionChangeList>
  >(`${comparisonsPath}/${comparisonId}/sections`, withSignal(signal));
  return response.data;
};

export const getRevisionLanguageChanges = async (
  comparisonId: string,
  signal?: AbortSignal,
): Promise<RevisionLanguageChangeList> => {
  const { data: response } = await apiClient.get<
    ApiResponse<RevisionLanguageChangeList>
  >(`${comparisonsPath}/${comparisonId}/languages`, withSignal(signal));
  return response.data;
};

export const getRevisionFindingChanges = async (
  comparisonId: string,
  signal?: AbortSignal,
): Promise<RevisionFindingChangeList> => {
  const { data: response } = await apiClient.get<
    ApiResponse<RevisionFindingChangeList>
  >(`${comparisonsPath}/${comparisonId}/findings`, withSignal(signal));
  return response.data;
};

export const exportRevisionComparison = async (
  comparisonId: string,
  format: RevisionComparisonExportFormat,
): Promise<RevisionComparisonDownload> => {
  const response = await apiClient.get<Blob>(
    `${comparisonsPath}/${comparisonId}/export`,
    {
      params: { format },
      responseType: 'blob',
      timeout: exportTimeout,
    },
  );
  return {
    blob: response.data,
    fileName: getDownloadFileName(response.headers['content-disposition']),
  };
};

export const listDocumentRevisionComparisons = async (
  documentId: string,
  params: { page: number; pageSize: number },
  signal?: AbortSignal,
): Promise<RevisionComparisonHistory> => {
  const { data: response } = await apiClient.get<
    ApiResponse<RevisionComparisonHistory>
  >(`/documents/${documentId}/revision-comparisons`, {
    params,
    ...withSignal(signal),
  });
  return response.data;
};

export const revisionComparisonApi = {
  startRevisionComparison,
  listRevisionComparisonJobs,
  getRevisionComparisonJob,
  cancelRevisionComparison,
  getRevisionComparison,
  getRevisionComparisonSummary,
  listRevisionChanges,
  getRevisionSectionChanges,
  getRevisionLanguageChanges,
  getRevisionFindingChanges,
  exportRevisionComparison,
  listDocumentRevisionComparisons,
} as const;
