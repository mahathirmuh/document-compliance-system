import type { AxiosRequestConfig } from 'axios';

import { apiClient } from './client';
import type { ApiResponse } from '../types/auth';
import type {
  GraphSubscription,
  GraphSubscriptionCreate,
  GraphSubscriptionDeleteResult,
  GraphSubscriptionDisableRequest,
  GraphSubscriptionList,
  GraphSubscriptionListParams,
  GraphSubscriptionRenewRequest,
  SharePointConnection,
  SharePointConnectionCreate,
  SharePointConnectionList,
  SharePointConnectionListParams,
  SharePointConnectionTestResult,
  SharePointConnectionUpdate,
  SharePointDrive,
  SharePointFolderCreate,
  SharePointFolderItem,
  SharePointFolderListParams,
  SharePointFolderMapping,
  SharePointFolderMappingList,
  SharePointFolderMappingWrite,
  SharePointMappingListParams,
  SharePointMetadataMapping,
  SharePointMetadataMappingList,
  SharePointMetadataMappingWrite,
  SharePointSiteResolution,
} from '../types/sharepoint';

const basePath = '/integrations/sharepoint';
const withSignal = (signal?: AbortSignal): AxiosRequestConfig =>
  signal ? { signal } : {};

export const listSharePointConnections = async (
  params: SharePointConnectionListParams,
  signal?: AbortSignal,
): Promise<SharePointConnectionList> => {
  const { data } = await apiClient.get<ApiResponse<SharePointConnectionList>>(
    `${basePath}/connections`,
    { params, ...withSignal(signal) },
  );
  return data.data;
};

export const getSharePointConnection = async (
  connectionId: string,
  signal?: AbortSignal,
): Promise<SharePointConnection> => {
  const { data } = await apiClient.get<ApiResponse<SharePointConnection>>(
    `${basePath}/connections/${connectionId}`,
    withSignal(signal),
  );
  return data.data;
};

export const createSharePointConnection = async (
  payload: SharePointConnectionCreate,
): Promise<SharePointConnection> => {
  const { data } = await apiClient.post<ApiResponse<SharePointConnection>>(
    `${basePath}/connections`,
    payload,
  );
  return data.data;
};

export const updateSharePointConnection = async (
  connectionId: string,
  payload: SharePointConnectionUpdate,
): Promise<SharePointConnection> => {
  const { data } = await apiClient.put<ApiResponse<SharePointConnection>>(
    `${basePath}/connections/${connectionId}`,
    payload,
  );
  return data.data;
};

export const testSharePointConnection = async (
  connectionId: string,
): Promise<SharePointConnectionTestResult> => {
  const { data } = await apiClient.post<ApiResponse<SharePointConnectionTestResult>>(
    `${basePath}/connections/${connectionId}/test`,
  );
  return data.data;
};

export const disableSharePointConnection = async (
  connectionId: string,
): Promise<SharePointConnection> => {
  const { data } = await apiClient.post<ApiResponse<SharePointConnection>>(
    `${basePath}/connections/${connectionId}/disable`,
  );
  return data.data;
};

export const resolveSharePointSite = async (
  connectionId: string,
  signal?: AbortSignal,
): Promise<SharePointSiteResolution> => {
  const { data } = await apiClient.get<ApiResponse<SharePointSiteResolution>>(
    `${basePath}/sites/resolve`,
    { params: { connectionId }, ...withSignal(signal) },
  );
  return data.data;
};

export const listSharePointDrives = async (
  connectionId: string,
  signal?: AbortSignal,
): Promise<SharePointDrive[]> => {
  const { data } = await apiClient.get<ApiResponse<SharePointDrive[]>>(
    `${basePath}/drives`,
    { params: { connectionId }, ...withSignal(signal) },
  );
  return data.data;
};

export const listSharePointFolders = async (
  params: SharePointFolderListParams,
  signal?: AbortSignal,
): Promise<SharePointFolderItem[]> => {
  const { data } = await apiClient.get<ApiResponse<SharePointFolderItem[]>>(
    `${basePath}/folders`,
    { params, ...withSignal(signal) },
  );
  return data.data;
};

export const createSharePointFolder = async (
  payload: SharePointFolderCreate,
): Promise<SharePointFolderItem> => {
  const { data } = await apiClient.post<ApiResponse<SharePointFolderItem>>(
    `${basePath}/folders`,
    payload,
  );
  return data.data;
};

export const listSharePointFolderMappings = async (
  params: SharePointMappingListParams,
  signal?: AbortSignal,
): Promise<SharePointFolderMappingList> => {
  const { data } = await apiClient.get<ApiResponse<SharePointFolderMappingList>>(
    `${basePath}/folder-mappings`,
    { params, ...withSignal(signal) },
  );
  return data.data;
};

export const createSharePointFolderMapping = async (
  payload: SharePointFolderMappingWrite,
): Promise<SharePointFolderMapping> => {
  const { data } = await apiClient.post<ApiResponse<SharePointFolderMapping>>(
    `${basePath}/folder-mappings`,
    payload,
  );
  return data.data;
};

export const updateSharePointFolderMapping = async (
  mappingId: string,
  payload: SharePointFolderMappingWrite,
): Promise<SharePointFolderMapping> => {
  const { data } = await apiClient.put<ApiResponse<SharePointFolderMapping>>(
    `${basePath}/folder-mappings/${mappingId}`,
    payload,
  );
  return data.data;
};

export const listSharePointMetadataMappings = async (
  params: SharePointMappingListParams,
  signal?: AbortSignal,
): Promise<SharePointMetadataMappingList> => {
  const { data } = await apiClient.get<ApiResponse<SharePointMetadataMappingList>>(
    `${basePath}/metadata-mappings`,
    { params, ...withSignal(signal) },
  );
  return data.data;
};

export const createSharePointMetadataMapping = async (
  payload: SharePointMetadataMappingWrite,
): Promise<SharePointMetadataMapping> => {
  const { data } = await apiClient.post<ApiResponse<SharePointMetadataMapping>>(
    `${basePath}/metadata-mappings`,
    payload,
  );
  return data.data;
};

export const updateSharePointMetadataMapping = async (
  mappingId: string,
  payload: SharePointMetadataMappingWrite,
): Promise<SharePointMetadataMapping> => {
  const { data } = await apiClient.put<ApiResponse<SharePointMetadataMapping>>(
    `${basePath}/metadata-mappings/${mappingId}`,
    payload,
  );
  return data.data;
};

export const listGraphSubscriptions = async (
  params: GraphSubscriptionListParams,
  signal?: AbortSignal,
): Promise<GraphSubscriptionList> => {
  const { data } = await apiClient.get<ApiResponse<GraphSubscriptionList>>(
    `${basePath}/subscriptions`,
    { params, ...withSignal(signal) },
  );
  return data.data;
};

export const createGraphSubscription = async (
  payload: GraphSubscriptionCreate,
): Promise<GraphSubscription> => {
  const { data } = await apiClient.post<ApiResponse<GraphSubscription>>(
    `${basePath}/subscriptions`,
    payload,
  );
  return data.data;
};

export const renewGraphSubscription = async (
  subscriptionId: string,
  payload: GraphSubscriptionRenewRequest,
): Promise<GraphSubscription> => {
  const { data } = await apiClient.post<ApiResponse<GraphSubscription>>(
    `${basePath}/subscriptions/${subscriptionId}/renew`,
    payload,
  );
  return data.data;
};

export const disableGraphSubscription = async (
  subscriptionId: string,
  payload: GraphSubscriptionDisableRequest,
): Promise<GraphSubscription> => {
  const { data } = await apiClient.post<ApiResponse<GraphSubscription>>(
    `${basePath}/subscriptions/${subscriptionId}/disable`,
    payload,
  );
  return data.data;
};

export const deleteGraphSubscription = async (
  subscriptionId: string,
): Promise<GraphSubscriptionDeleteResult> => {
  const { data } = await apiClient.post<
    ApiResponse<GraphSubscriptionDeleteResult>
  >(`${basePath}/subscriptions/${subscriptionId}/delete`);
  return data.data;
};

export const sharePointApi = {
  listConnections: listSharePointConnections,
  getConnection: getSharePointConnection,
  createConnection: createSharePointConnection,
  updateConnection: updateSharePointConnection,
  testConnection: testSharePointConnection,
  disableConnection: disableSharePointConnection,
  resolveSite: resolveSharePointSite,
  listDrives: listSharePointDrives,
  listFolders: listSharePointFolders,
  createFolder: createSharePointFolder,
  listFolderMappings: listSharePointFolderMappings,
  createFolderMapping: createSharePointFolderMapping,
  updateFolderMapping: updateSharePointFolderMapping,
  listMetadataMappings: listSharePointMetadataMappings,
  createMetadataMapping: createSharePointMetadataMapping,
  updateMetadataMapping: updateSharePointMetadataMapping,
  listSubscriptions: listGraphSubscriptions,
  createSubscription: createGraphSubscription,
  renewSubscription: renewGraphSubscription,
  disableSubscription: disableGraphSubscription,
  deleteSubscription: deleteGraphSubscription,
} as const;
