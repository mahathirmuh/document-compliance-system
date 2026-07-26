import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  cancelSyncJob,
  createSyncJob,
  createSyncProfile,
  exportSyncJob,
  getDocumentRemoteStatus,
  getSyncJob,
  getSyncProfile,
  listDocumentRemoteVersions,
  listSyncJobItems,
  listSyncJobs,
  listSyncProfiles,
  pullDocumentFile,
  pushDocumentFile,
  reconcileDocumentFile,
  resetSyncProfileDelta,
  retrySyncJob,
  runSyncProfile,
  setSyncProfileActive,
  updateSyncProfile,
} from '../api/sharepointSyncApi';
import type { SharePointFileActionRequest } from '../types/sharepoint';
import type {
  SharePointSyncProfileWrite,
  SyncItemListParams,
  SyncJobActionRequest,
  SyncJobCreate,
  SyncJobListParams,
  SyncProfileListParams,
} from '../types/synchronisation';
import { isTerminalSyncStatus } from '../types/synchronisation';
import { useDocumentSession } from './useDocumentSession';

const syncPollingMs = 3_000;

export const sharePointSyncKeys = {
  root: (scope: readonly [string, number]) =>
    ['sharepoint-sync', scope[0], scope[1]] as const,
  profiles: (scope: readonly [string, number], params: object) =>
    [...sharePointSyncKeys.root(scope), 'profiles', params] as const,
  profile: (scope: readonly [string, number], profileId: string) =>
    [...sharePointSyncKeys.root(scope), 'profile', profileId] as const,
  jobs: (scope: readonly [string, number], params: object) =>
    [...sharePointSyncKeys.root(scope), 'jobs', params] as const,
  job: (scope: readonly [string, number], jobId: string) =>
    [...sharePointSyncKeys.root(scope), 'job', jobId] as const,
  items: (scope: readonly [string, number], jobId: string, params: object) =>
    [...sharePointSyncKeys.root(scope), 'items', jobId, params] as const,
  remoteStatus: (scope: readonly [string, number], fileId: string) =>
    [...sharePointSyncKeys.root(scope), 'remote-status', fileId] as const,
  remoteVersions: (scope: readonly [string, number], fileId: string) =>
    [...sharePointSyncKeys.root(scope), 'remote-versions', fileId] as const,
} as const;

export const useSharePointSyncProfiles = (params: SyncProfileListParams) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: sharePointSyncKeys.profiles(scope, params),
    queryFn: ({ signal }) => listSyncProfiles(params, signal),
    placeholderData: (previous) => previous,
  });
};

export const useSharePointSyncProfile = (profileId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: sharePointSyncKeys.profile(scope, profileId ?? 'none'),
    queryFn: ({ signal }) => getSyncProfile(profileId ?? '', signal),
    enabled: profileId !== null,
  });
};

export const useSharePointSyncJobs = (params: SyncJobListParams) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: sharePointSyncKeys.jobs(scope, params),
    queryFn: ({ signal }) => listSyncJobs(params, signal),
    placeholderData: (previous) => previous,
    refetchInterval: (query) =>
      query.state.data?.items.some((job) => !isTerminalSyncStatus(job.status))
        ? syncPollingMs
        : false,
  });
};

export const useSharePointSyncJob = (jobId: string | null, poll = true) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: sharePointSyncKeys.job(scope, jobId ?? 'none'),
    queryFn: ({ signal }) => getSyncJob(jobId ?? '', signal),
    enabled: jobId !== null,
    refetchInterval: (query) =>
      poll && query.state.data && !isTerminalSyncStatus(query.state.data.status)
        ? syncPollingMs
        : false,
  });
};

export const useSharePointSyncItems = (
  jobId: string | null,
  params: SyncItemListParams,
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: sharePointSyncKeys.items(scope, jobId ?? 'none', params),
    queryFn: ({ signal }) => listSyncJobItems(jobId ?? '', params, signal),
    enabled: jobId !== null,
    placeholderData: (previous) => previous,
  });
};

export const useDocumentRemoteStatus = (fileId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: sharePointSyncKeys.remoteStatus(scope, fileId ?? 'none'),
    queryFn: ({ signal }) => getDocumentRemoteStatus(fileId ?? '', signal),
    enabled: fileId !== null,
    refetchInterval: (query) =>
      query.state.data?.activeJobId || query.state.data?.remoteSyncStatus === 'SYNCING'
        ? syncPollingMs
        : false,
  });
};

export const useDocumentRemoteVersions = (fileId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: sharePointSyncKeys.remoteVersions(scope, fileId ?? 'none'),
    queryFn: ({ signal }) => listDocumentRemoteVersions(fileId ?? '', signal),
    enabled: fileId !== null,
  });
};

export const useSharePointSyncMutations = () => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();
  const invalidate = async (): Promise<void> => {
    await queryClient.invalidateQueries({ queryKey: sharePointSyncKeys.root(scope) });
  };
  return {
    createProfile: useMutation({
      mutationFn: (payload: SharePointSyncProfileWrite) => createSyncProfile(payload),
      onSuccess: invalidate,
    }),
    updateProfile: useMutation({
      mutationFn: ({
        profileId,
        payload,
      }: {
        profileId: string;
        payload: Partial<SharePointSyncProfileWrite>;
      }) => updateSyncProfile(profileId, payload),
      onSuccess: invalidate,
    }),
    setProfileActive: useMutation({
      mutationFn: ({ active, profileId }: { profileId: string; active: boolean }) =>
        setSyncProfileActive(profileId, active),
      onSuccess: invalidate,
    }),
    runProfile: useMutation({
      mutationFn: ({
        jobType,
        profileId,
      }: {
        profileId: string;
        jobType: SyncJobCreate['jobType'];
      }) => runSyncProfile(profileId, jobType),
      onSuccess: invalidate,
    }),
    resetDelta: useMutation({
      mutationFn: ({ profileId, reason }: { profileId: string; reason: string }) =>
        resetSyncProfileDelta(profileId, reason),
      onSuccess: invalidate,
    }),
    createJob: useMutation({
      mutationFn: (payload: SyncJobCreate) => createSyncJob(payload),
      onSuccess: invalidate,
    }),
    cancelJob: useMutation({
      mutationFn: ({
        jobId,
        payload,
      }: {
        jobId: string;
        payload: SyncJobActionRequest;
      }) => cancelSyncJob(jobId, payload),
      onSuccess: invalidate,
    }),
    retryJob: useMutation({
      mutationFn: ({
        jobId,
        payload,
      }: {
        jobId: string;
        payload: SyncJobActionRequest;
      }) => retrySyncJob(jobId, payload),
      onSuccess: invalidate,
    }),
    exportJob: useMutation({
      mutationFn: ({ format, jobId }: { jobId: string; format: 'json' | 'xlsx' }) =>
        exportSyncJob(jobId, format),
    }),
    pushFile: useMutation({
      mutationFn: ({
        fileId,
        payload,
      }: {
        fileId: string;
        payload: SharePointFileActionRequest;
      }) => pushDocumentFile(fileId, payload),
      onSuccess: invalidate,
    }),
    pullFile: useMutation({
      mutationFn: ({
        fileId,
        payload,
      }: {
        fileId: string;
        payload: SharePointFileActionRequest;
      }) => pullDocumentFile(fileId, payload),
      onSuccess: invalidate,
    }),
    reconcileFile: useMutation({
      mutationFn: ({
        fileId,
        payload,
      }: {
        fileId: string;
        payload: SharePointFileActionRequest;
      }) => reconcileDocumentFile(fileId, payload),
      onSuccess: invalidate,
    }),
  } as const;
};
