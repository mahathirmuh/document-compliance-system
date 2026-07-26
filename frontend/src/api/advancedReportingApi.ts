import type { AxiosRequestConfig } from 'axios';

import { apiClient } from './client';
import type { ApiResponse } from '../types/auth';
import type {
  ReportDownload,
  ReportGenerateRequest,
  ReportJob,
  ReportJobList,
  ReportJobListParams,
  ReportSchedule,
  ReportScheduleCreate,
  ReportScheduleList,
  ReportScheduleListParams,
  ReportScheduleUpdate,
  ReportScheduleRunResult,
  ReportSnapshot,
  ReportSnapshotList,
  ReportSnapshotListParams,
  ReportSnapshotDeleteResult,
} from '../types/advancedReporting';
import { getDownloadFileName } from '../utils/downloadFile';

const reportsPath = '/reports';
const paramsSerializer = { indexes: null } as const;

const withSignal = (signal?: AbortSignal): AxiosRequestConfig =>
  signal ? { signal } : {};

export const generateAdvancedReport = async (
  payload: ReportGenerateRequest,
): Promise<ReportJob> => {
  const { data: response } = await apiClient.post<ApiResponse<ReportJob>>(
    `${reportsPath}/generate`,
    payload,
  );
  return response.data;
};

export const listReportJobs = async (
  params: ReportJobListParams,
  signal?: AbortSignal,
): Promise<ReportJobList> => {
  const { data: response } = await apiClient.get<ApiResponse<ReportJobList>>(
    `${reportsPath}/jobs`,
    { params, paramsSerializer, ...withSignal(signal) },
  );
  return response.data;
};

export const getReportJob = async (
  jobId: string,
  signal?: AbortSignal,
): Promise<ReportJob> => {
  const { data: response } = await apiClient.get<ApiResponse<ReportJob>>(
    `${reportsPath}/jobs/${jobId}`,
    withSignal(signal),
  );
  return response.data;
};

export const listReportSnapshots = async (
  params: ReportSnapshotListParams,
  signal?: AbortSignal,
): Promise<ReportSnapshotList> => {
  const { data: response } = await apiClient.get<ApiResponse<ReportSnapshotList>>(
    `${reportsPath}/snapshots`,
    { params, ...withSignal(signal) },
  );
  return response.data;
};

export const getReportSnapshot = async (
  snapshotId: string,
  signal?: AbortSignal,
): Promise<ReportSnapshot> => {
  const { data: response } = await apiClient.get<ApiResponse<ReportSnapshot>>(
    `${reportsPath}/snapshots/${snapshotId}`,
    withSignal(signal),
  );
  return response.data;
};

export const downloadReportSnapshot = async (
  snapshotId: string,
): Promise<ReportDownload> => {
  const response = await apiClient.get<Blob>(
    `${reportsPath}/snapshots/${snapshotId}/download`,
    { responseType: 'blob', timeout: 10 * 60 * 1_000 },
  );
  return {
    blob: response.data,
    fileName: getDownloadFileName(response.headers['content-disposition']),
  };
};

export const deleteReportSnapshot = async (
  snapshotId: string,
): Promise<ReportSnapshotDeleteResult> => {
  const { data: response } = await apiClient.post<
    ApiResponse<ReportSnapshotDeleteResult>
  >(`${reportsPath}/snapshots/${snapshotId}/delete`);
  return response.data;
};

export const listReportSchedules = async (
  params: ReportScheduleListParams,
  signal?: AbortSignal,
): Promise<ReportScheduleList> => {
  const { data: response } = await apiClient.get<ApiResponse<ReportScheduleList>>(
    `${reportsPath}/schedules`,
    { params, ...withSignal(signal) },
  );
  return response.data;
};

export const createReportSchedule = async (
  payload: ReportScheduleCreate,
): Promise<ReportSchedule> => {
  const { data: response } = await apiClient.post<ApiResponse<ReportSchedule>>(
    `${reportsPath}/schedules`,
    payload,
  );
  return response.data;
};

export const updateReportSchedule = async (
  scheduleId: string,
  payload: ReportScheduleUpdate,
): Promise<ReportSchedule> => {
  const { data: response } = await apiClient.put<ApiResponse<ReportSchedule>>(
    `${reportsPath}/schedules/${scheduleId}`,
    payload,
  );
  return response.data;
};

export const runReportSchedule = async (
  scheduleId: string,
): Promise<ReportScheduleRunResult> => {
  const { data: response } = await apiClient.post<ApiResponse<ReportScheduleRunResult>>(
    `${reportsPath}/schedules/${scheduleId}/run`,
  );
  return response.data;
};

export const disableReportSchedule = async (
  scheduleId: string,
): Promise<ReportSchedule> => {
  const { data: response } = await apiClient.post<ApiResponse<ReportSchedule>>(
    `${reportsPath}/schedules/${scheduleId}/disable`,
  );
  return response.data;
};

export const advancedReportingApi = {
  generateAdvancedReport,
  listReportJobs,
  getReportJob,
  listReportSnapshots,
  getReportSnapshot,
  downloadReportSnapshot,
  deleteReportSnapshot,
  listReportSchedules,
  createReportSchedule,
  updateReportSchedule,
  runReportSchedule,
  disableReportSchedule,
} as const;
