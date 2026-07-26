import type { PaginatedData } from './masterData';
import type { FolderMappingScope } from './sharepoint';

export const syncDirections = ['OUTBOUND', 'INBOUND', 'BIDIRECTIONAL'] as const;
export type SyncDirection = (typeof syncDirections)[number];

export const syncStatuses = [
  'QUEUED',
  'AUTHENTICATING',
  'DISCOVERING',
  'COMPARING',
  'TRANSFERRING',
  'UPDATING_METADATA',
  'RESOLVING_CONFLICTS',
  'PERSISTING',
  'COMPLETED',
  'PARTIALLY_COMPLETED',
  'FAILED',
  'CANCEL_REQUESTED',
  'CANCELLED',
  'DEAD_LETTER',
] as const;
export type SyncStatus = (typeof syncStatuses)[number];

export const terminalSyncStatuses: readonly SyncStatus[] = [
  'COMPLETED',
  'PARTIALLY_COMPLETED',
  'FAILED',
  'CANCELLED',
  'DEAD_LETTER',
];
export const isTerminalSyncStatus = (status: SyncStatus): boolean =>
  terminalSyncStatuses.includes(status);

export const syncJobTypes = [
  'MANUAL_FULL',
  'MANUAL_INCREMENTAL',
  'SCHEDULED_FULL',
  'SCHEDULED_INCREMENTAL',
  'WEBHOOK_INCREMENTAL',
  'SINGLE_FILE_PUSH',
  'SINGLE_FILE_PULL',
  'RECONCILIATION',
] as const;
export type SyncJobType = (typeof syncJobTypes)[number];

export type SyncConflictPolicy =
  | 'MANUAL'
  | 'APPLICATION_WINS'
  | 'SHAREPOINT_WINS'
  | 'LATEST_MODIFIED_WINS'
  | 'CREATE_COPY';

export type SyncDeletePolicy =
  | 'IGNORE_REMOTE_DELETE'
  | 'ARCHIVE_LOCAL'
  | 'MARK_MISSING'
  | 'DELETE_LOCAL_SOFT';

export type SyncScopeType = FolderMappingScope;

export interface SharePointSyncProfileWrite {
  name: string;
  description?: string | null;
  sharepointConnectionId: string;
  direction?: SyncDirection;
  scopeType?: SyncScopeType;
  departmentId?: string | null;
  sectionId?: string | null;
  documentTypeId?: string | null;
  folderMappingId?: string | null;
  metadataMappingProfile?: Readonly<Record<string, unknown>>;
  conflictPolicy?: SyncConflictPolicy;
  deletePolicy?: SyncDeletePolicy;
  syncSchedule?: string | null;
  deltaSyncEnabled?: boolean;
  webhookEnabled?: boolean;
  isActive?: boolean;
}

export interface SharePointSyncProfile
  extends Required<
    Pick<
      SharePointSyncProfileWrite,
      | 'name'
      | 'sharepointConnectionId'
      | 'direction'
      | 'scopeType'
      | 'metadataMappingProfile'
      | 'conflictPolicy'
      | 'deletePolicy'
      | 'deltaSyncEnabled'
      | 'webhookEnabled'
      | 'isActive'
    >
  > {
  id: string;
  description: string | null;
  departmentId: string | null;
  sectionId: string | null;
  documentTypeId: string | null;
  folderMappingId: string | null;
  syncSchedule: string | null;
  createdBy: string | null;
  updatedBy: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface SyncProfileListParams {
  page: number;
  pageSize: number;
  includeInactive?: boolean;
}
export type SyncProfileList = PaginatedData<SharePointSyncProfile>;

export interface SharePointSyncRunRequest {
  jobType?: SyncJobType;
  scope?: Readonly<Record<string, unknown>>;
}

export interface SharePointSyncJob {
  id: string;
  syncProfileId: string;
  sharepointConnectionId: string;
  jobType: SyncJobType;
  direction: SyncDirection;
  status: SyncStatus;
  progress: number;
  currentStage: string | null;
  scope: Readonly<Record<string, unknown>>;
  requestedBy: string | null;
  requestedAt: string;
  startedAt: string | null;
  completedAt: string | null;
  failedAt: string | null;
  cancelledAt: string | null;
  attemptNumber: number;
  maximumAttempts: number;
  itemsDiscovered: number;
  itemsProcessed: number;
  itemsCreated: number;
  itemsUpdated: number;
  itemsSkipped: number;
  itemsConflicted: number;
  itemsFailed: number;
  errorCode: string | null;
  errorMessage: string | null;
  resultSummary: Readonly<Record<string, unknown>> | null;
  createdAt: string;
  updatedAt: string;
}

export interface SyncJobListParams {
  page: number;
  pageSize: number;
  status?: SyncStatus | readonly SyncStatus[];
}
export type SyncJobList = PaginatedData<SharePointSyncJob>;

export interface SyncJobCreate {
  syncProfileId: string;
  jobType?: SyncJobType;
  direction?: SyncDirection | null;
  scope?: Readonly<Record<string, unknown>>;
}

export type SyncItemOperation =
  | 'CREATE_REMOTE'
  | 'UPDATE_REMOTE'
  | 'CREATE_LOCAL'
  | 'UPDATE_LOCAL'
  | 'MOVE_REMOTE'
  | 'RENAME_REMOTE'
  | 'UPDATE_REMOTE_METADATA'
  | 'UPDATE_LOCAL_METADATA'
  | 'REMOTE_DELETE_DETECTED'
  | 'LOCAL_DELETE_DETECTED'
  | 'SKIP'
  | 'CONFLICT';

export type SyncItemStatus =
  | 'QUEUED'
  | 'PROCESSING'
  | 'COMPLETED'
  | 'SKIPPED'
  | 'CONFLICT'
  | 'FAILED'
  | 'CANCELLED'
  | 'DEAD_LETTER';

export interface SharePointSyncItem {
  id: string;
  syncJobId: string;
  documentId: string | null;
  documentRevisionId: string | null;
  documentFileId: string | null;
  remoteDriveId: string | null;
  remoteItemId: string | null;
  remotePath: string | null;
  operation: SyncItemOperation;
  status: SyncItemStatus;
  localHashBefore: string | null;
  localHashAfter: string | null;
  remoteEtagBefore: string | null;
  remoteEtagAfter: string | null;
  remoteSize: number | null;
  conflictId: string | null;
  errorCode: string | null;
  errorMessage: string | null;
  metadata: Readonly<Record<string, unknown>>;
  startedAt: string | null;
  completedAt: string | null;
  createdAt: string;
}

export interface SyncItemListParams {
  page: number;
  pageSize: number;
}
export type SyncItemList = PaginatedData<SharePointSyncItem>;

export type SharePointConflictType =
  | 'BOTH_MODIFIED'
  | 'LOCAL_DELETED_REMOTE_MODIFIED'
  | 'REMOTE_DELETED_LOCAL_MODIFIED'
  | 'METADATA_CONFLICT'
  | 'PATH_CONFLICT'
  | 'DUPLICATE_REMOTE_ITEM'
  | 'HASH_MISMATCH'
  | 'VERSION_MISMATCH';

export type SharePointConflictStatus =
  | 'OPEN'
  | 'IN_REVIEW'
  | 'RESOLVED'
  | 'IGNORED';
export type SharePointConflictResolution =
  | 'KEEP_LOCAL'
  | 'KEEP_REMOTE'
  | 'KEEP_BOTH'
  | 'MERGE_METADATA'
  | 'IGNORE_REMOTE_CHANGE'
  | 'IGNORE_LOCAL_CHANGE';

export interface ConflictVersionSnapshot
  extends Readonly<Record<string, unknown>> {
  filename?: string;
  path?: string;
  sha256Hash?: string;
  etag?: string;
  size?: number;
  modifiedAt?: string;
  modifiedBy?: string;
  metadata?: Readonly<Record<string, unknown>>;
}

export interface SharePointSyncConflict {
  id: string;
  syncJobId: string;
  syncItemId: string | null;
  documentId: string | null;
  documentRevisionId: string | null;
  documentFileId: string | null;
  remoteItemId: string | null;
  conflictType: SharePointConflictType;
  status: SharePointConflictStatus;
  localVersion: ConflictVersionSnapshot;
  remoteVersion: ConflictVersionSnapshot;
  detectedAt: string;
  assignedTo: string | null;
  resolution: SharePointConflictResolution | null;
  resolvedBy: string | null;
  resolvedAt: string | null;
  resolutionComment: string | null;
  resultDocumentFileId: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface SyncConflictListParams {
  page: number;
  pageSize: number;
  status?: SharePointConflictStatus | readonly SharePointConflictStatus[];
}
export type SyncConflictList = PaginatedData<SharePointSyncConflict>;

export interface ConflictAssignmentRequest {
  assignedTo: string;
}

export interface ConflictResolutionRequest {
  resolution: SharePointConflictResolution;
  comment: string;
}

export interface SyncExport {
  blob: Blob;
  fileName: string | null;
}

export interface SyncDeltaResetResult {
  reset: boolean;
}
