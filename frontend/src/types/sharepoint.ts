import type { PaginatedData } from './masterData';

export const sharePointConnectionStatuses = [
  'NOT_CONFIGURED',
  'CONNECTED',
  'DEGRADED',
  'AUTHENTICATION_FAILED',
  'PERMISSION_DENIED',
  'UNAVAILABLE',
  'DISABLED',
] as const;
export type SharePointConnectionStatus =
  (typeof sharePointConnectionStatuses)[number];

export type SharePointAuthMode = 'CLIENT_SECRET' | 'CERTIFICATE';

export interface SharePointConnection {
  id: string;
  name: string;
  description: string | null;
  tenantIdReference: string;
  siteHostname: string;
  sitePath: string;
  siteId: string | null;
  driveId: string | null;
  libraryName: string;
  rootFolderPath: string;
  authMode: SharePointAuthMode;
  status: SharePointConnectionStatus;
  isDefault: boolean;
  isActive: boolean;
  lastTestedAt: string | null;
  lastTestStatus: string | null;
  lastTestMessage: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface SharePointConnectionCreate {
  name: string;
  description?: string | null;
  tenantIdReference: string;
  siteHostname: string;
  sitePath: string;
  siteId?: string | null;
  driveId?: string | null;
  libraryName: string;
  rootFolderPath?: string;
  authMode?: SharePointAuthMode;
  isDefault?: boolean;
}

export interface SharePointConnectionUpdate {
  name?: string;
  description?: string | null;
  tenantIdReference?: string;
  siteHostname?: string;
  sitePath?: string;
  siteId?: string | null;
  driveId?: string | null;
  libraryName?: string;
  rootFolderPath?: string;
  authMode?: SharePointAuthMode;
  isDefault?: boolean;
  isActive?: boolean;
}

export interface SharePointConnectionListParams {
  page: number;
  pageSize: number;
  includeInactive?: boolean;
}
export type SharePointConnectionList = PaginatedData<SharePointConnection>;

export interface SharePointConnectionTestResult {
  connectionId: string;
  status: SharePointConnectionStatus;
  siteId: string | null;
  driveId: string | null;
  siteRead: boolean;
  driveRead: boolean;
  testedAt: string;
  message: string;
}

export interface SharePointSiteResolution {
  id: string;
  displayName: string | null;
  name: string | null;
  webUrl: string | null;
}

export interface SharePointDrive {
  id: string;
  name: string;
  driveType: string | null;
  webUrl: string | null;
}

export interface SharePointFolderItem {
  id: string;
  name: string;
  webUrl: string | null;
  parentReference: Readonly<Record<string, unknown>> | null;
  childCount: number | null;
}

export interface SharePointFolderListParams {
  connectionId: string;
  parentItemId?: string;
  folderPath?: string;
}

export interface SharePointFolderCreate {
  connectionId: string;
  name: string;
  parentItemId?: string | null;
}

export const folderMappingScopes = [
  'GLOBAL',
  'DEPARTMENT',
  'SECTION',
  'DOCUMENT_TYPE',
  'DEPARTMENT_DOCUMENT_TYPE',
  'SECTION_DOCUMENT_TYPE',
] as const;
export type FolderMappingScope = (typeof folderMappingScopes)[number];

export interface SharePointFolderMapping {
  id: string;
  sharepointConnectionId: string;
  departmentId: string | null;
  sectionId: string | null;
  documentTypeId: string | null;
  mappingScope: FolderMappingScope;
  remoteFolderPath: string;
  remoteFolderId: string | null;
  filenamePattern: string | null;
  createFolderIfMissing: boolean;
  isActive: boolean;
  priority: number;
  createdBy: string | null;
  updatedBy: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface SharePointFolderMappingWrite {
  sharepointConnectionId: string;
  departmentId?: string | null;
  sectionId?: string | null;
  documentTypeId?: string | null;
  mappingScope: FolderMappingScope;
  remoteFolderPath: string;
  remoteFolderId?: string | null;
  filenamePattern?: string | null;
  createFolderIfMissing?: boolean;
  isActive?: boolean;
  priority?: number;
}

export interface SharePointMappingListParams {
  page: number;
  pageSize: number;
  connectionId?: string;
  includeInactive?: boolean;
}
export type SharePointFolderMappingList =
  PaginatedData<SharePointFolderMapping>;

export const metadataMappingDirections = [
  'OUTBOUND',
  'INBOUND',
  'BIDIRECTIONAL',
] as const;
export type MetadataMappingDirection =
  (typeof metadataMappingDirections)[number];

export const metadataMappingDataTypes = [
  'STRING',
  'INTEGER',
  'BOOLEAN',
  'DATE',
  'DATETIME',
  'CHOICE',
  'LOOKUP_TEXT',
  'USER_DISPLAY_NAME',
  'JSON_STRING',
] as const;
export type MetadataMappingDataType =
  (typeof metadataMappingDataTypes)[number];

export interface SharePointMetadataMapping {
  id: string;
  sharepointConnectionId: string;
  documentField: string;
  sharepointFieldInternalName: string;
  dataType: MetadataMappingDataType;
  direction: MetadataMappingDirection;
  isRequired: boolean;
  defaultValue: unknown;
  transformerCode: string | null;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface SharePointMetadataMappingWrite {
  sharepointConnectionId: string;
  documentField: string;
  sharepointFieldInternalName: string;
  dataType?: MetadataMappingDataType;
  direction?: MetadataMappingDirection;
  isRequired?: boolean;
  defaultValue?: unknown;
  transformerCode?: string | null;
  isActive?: boolean;
}

export type SharePointMetadataMappingList =
  PaginatedData<SharePointMetadataMapping>;

export type GraphSubscriptionStatus =
  | 'ACTIVE'
  | 'EXPIRING'
  | 'EXPIRED'
  | 'RENEWAL_FAILED'
  | 'DISABLED'
  | 'DELETED';

export interface GraphSubscription {
  id: string;
  sharepointConnectionId: string;
  syncProfileId: string;
  subscriptionId: string;
  resource: string;
  changeType: string;
  notificationUrl: string;
  lifecycleNotificationUrl: string | null;
  expirationDatetime: string;
  status: GraphSubscriptionStatus;
  lastRenewedAt: string | null;
  lastNotificationAt: string | null;
  renewalAttempts: number;
  errorCode: string | null;
  errorMessage: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface GraphSubscriptionCreate {
  sharepointConnectionId: string;
  syncProfileId: string;
  resource: string;
  changeType?: string;
  notificationUrl: string;
  lifecycleNotificationUrl?: string | null;
  clientState: string;
  expirationDatetime: string;
}

export interface GraphSubscriptionListParams {
  page: number;
  pageSize: number;
  status?: GraphSubscriptionStatus | readonly GraphSubscriptionStatus[];
}
export type GraphSubscriptionList = PaginatedData<GraphSubscription>;

export interface GraphSubscriptionRenewRequest {
  expirationDatetime: string;
}

export interface GraphSubscriptionDisableRequest {
  reason: string;
}

export interface GraphSubscriptionDeleteResult {
  deleted: boolean;
}

export type DocumentStorageProvider = 'LOCAL' | 'SHAREPOINT' | 'HYBRID';

export interface DocumentRemoteStatus {
  documentFileId: string;
  storageProvider: string;
  remoteSyncStatus: string | null;
  sharepointConnectionId: string | null;
  remoteDriveId: string | null;
  remoteItemId: string | null;
  remotePath: string | null;
  remoteWebUrl: string | null;
  remoteEtag: string | null;
  remoteVersionId: string | null;
  remoteLastModifiedAt: string | null;
  remoteSize: number | null;
  lastSyncedAt: string | null;
  syncErrorCode: string | null;
  syncErrorMessage: string | null;
}

export interface SharePointFileVersion {
  id: string;
  documentFileId: string;
  remoteDriveId: string;
  remoteItemId: string;
  remoteVersionId: string;
  remoteEtag: string | null;
  remoteLastModifiedAt: string | null;
  remoteLastModifiedBy: string | null;
  remoteSize: number | null;
  localSha256Hash: string | null;
  syncJobId: string | null;
  createdAt: string;
}

export type SharePointFileVersionList = PaginatedData<SharePointFileVersion>;
