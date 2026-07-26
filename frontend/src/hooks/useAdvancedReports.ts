import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  createReportSchedule,
  deleteReportSnapshot,
  disableReportSchedule,
  downloadReportSnapshot,
  generateAdvancedReport,
  getReportJob,
  getReportSnapshot,
  listReportJobs,
  listReportSchedules,
  listReportSnapshots,
  runReportSchedule,
  updateReportSchedule,
} from '../api/advancedReportingApi';
import type {
  ReportGenerateRequest,
  ReportJobListParams,
  ReportScheduleCreate,
  ReportScheduleListParams,
  ReportScheduleUpdate,
  ReportSnapshotListParams,
} from '../types/advancedReporting';
import { isTerminalReportJobStatus } from '../types/advancedReporting';
import { useDocumentSession } from './useDocumentSession';

const pollingIntervalMs = 3_000;

export const advancedReportKeys = {
  root: (scope: readonly [string, number]) =>
    ['advanced-reports', scope[0], scope[1]] as const,
  jobs: (scope: readonly [string, number], params: object) =>
    [...advancedReportKeys.root(scope), 'jobs', params] as const,
  job: (scope: readonly [string, number], jobId: string) =>
    [...advancedReportKeys.root(scope), 'jobs', jobId] as const,
  snapshots: (scope: readonly [string, number], params: object) =>
    [...advancedReportKeys.root(scope), 'snapshots', params] as const,
  snapshot: (scope: readonly [string, number], snapshotId: string) =>
    [...advancedReportKeys.root(scope), 'snapshots', snapshotId] as const,
  schedules: (scope: readonly [string, number], params: object) =>
    [...advancedReportKeys.root(scope), 'schedules', params] as const,
} as const;

export const useReportJob = (jobId: string | null, poll = true) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: advancedReportKeys.job(scope, jobId ?? 'none'),
    queryFn: ({ signal }) => getReportJob(jobId ?? '', signal),
    enabled: jobId !== null,
    refetchInterval: (query) =>
      poll && query.state.data && !isTerminalReportJobStatus(query.state.data.status)
        ? pollingIntervalMs
        : false,
  });
};

export const useReportJobs = (params: ReportJobListParams) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: advancedReportKeys.jobs(scope, params),
    queryFn: ({ signal }) => listReportJobs(params, signal),
    placeholderData: (previous) => previous,
    refetchInterval: (query) =>
      query.state.data?.items.some((job) => !isTerminalReportJobStatus(job.status))
        ? pollingIntervalMs
        : false,
  });
};

export const useReportSnapshots = (params: ReportSnapshotListParams) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: advancedReportKeys.snapshots(scope, params),
    queryFn: ({ signal }) => listReportSnapshots(params, signal),
    placeholderData: (previous) => previous,
  });
};

export const useReportSnapshot = (snapshotId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: advancedReportKeys.snapshot(scope, snapshotId ?? 'none'),
    queryFn: ({ signal }) => getReportSnapshot(snapshotId ?? '', signal),
    enabled: snapshotId !== null,
  });
};

export const useReportSchedules = (params: ReportScheduleListParams) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: advancedReportKeys.schedules(scope, params),
    queryFn: ({ signal }) => listReportSchedules(params, signal),
    placeholderData: (previous) => previous,
  });
};

export const useAdvancedReportMutations = () => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();
  const invalidate = async (): Promise<void> => {
    await queryClient.invalidateQueries({
      queryKey: advancedReportKeys.root(scope),
    });
  };
  return {
    generate: useMutation({
      mutationFn: (payload: ReportGenerateRequest) => generateAdvancedReport(payload),
      onSuccess: invalidate,
    }),
    download: useMutation({ mutationFn: downloadReportSnapshot }),
    deleteSnapshot: useMutation({
      mutationFn: deleteReportSnapshot,
      onSuccess: invalidate,
    }),
    createSchedule: useMutation({
      mutationFn: (payload: ReportScheduleCreate) => createReportSchedule(payload),
      onSuccess: invalidate,
    }),
    updateSchedule: useMutation({
      mutationFn: ({
        payload,
        scheduleId,
      }: {
        scheduleId: string;
        payload: ReportScheduleUpdate;
      }) => updateReportSchedule(scheduleId, payload),
      onSuccess: invalidate,
    }),
    runSchedule: useMutation({
      mutationFn: runReportSchedule,
      onSuccess: invalidate,
    }),
    disableSchedule: useMutation({
      mutationFn: disableReportSchedule,
      onSuccess: invalidate,
    }),
  } as const;
};
