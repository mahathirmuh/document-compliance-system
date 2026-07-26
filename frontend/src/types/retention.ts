import type { PaginatedData } from './masterData';

export const retentionEntityTypes = [
  'TEMP_UPLOAD',
  'REPORT_SNAPSHOT',
  'JOB_LOG',
  'NOTIFICATION',
  'AUDIT_LOG',
  'DELETED_FILE',
  'EXTRACTION_HISTORY',
  'OCR_HISTORY',
  'SYNC_HISTORY',
  'WEBHOOK_EVENT',
] as const;
export type RetentionEntityType = (typeof retentionEntityTypes)[number];

export type RetentionScopeType =
  | 'GLOBAL'
  | 'DEPARTMENT'
  | 'DOCUMENT_TYPE'
  | 'DEPARTMENT_DOCUMENT_TYPE';

export interface RetentionPolicy {
  id: string;
  name: string;
  entityType: RetentionEntityType;
  scopeType: RetentionScopeType;
  departmentId: string | null;
  documentTypeId: string | null;
  retentionDays: number;
  archiveAfterDays: number | null;
  deleteAfterDays: number | null;
  legalHoldEnabled: boolean;
  isActive: boolean;
  createdBy: string | null;
  updatedBy: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface RetentionPolicyCreate {
  name: string;
  entityType: RetentionEntityType;
  scopeType?: RetentionScopeType;
  departmentId?: string | null;
  documentTypeId?: string | null;
  retentionDays: number;
  archiveAfterDays?: number | null;
  deleteAfterDays?: number | null;
  legalHoldEnabled?: boolean;
  isActive?: boolean;
}

export interface RetentionPolicyUpdate {
  name?: string;
  retentionDays?: number;
  archiveAfterDays?: number | null;
  deleteAfterDays?: number | null;
  legalHoldEnabled?: boolean;
  isActive?: boolean;
}

export interface RetentionPolicyListParams {
  page: number;
  pageSize: number;
  entityType?: RetentionEntityType;
  includeInactive?: boolean;
}
export type RetentionPolicyList = PaginatedData<RetentionPolicy>;

export interface RetentionRunRequest {
  entityType: RetentionEntityType;
  dryRun: boolean;
  batchSize?: number;
}

export interface RetentionRunResult {
  entityType: RetentionEntityType;
  dryRun: boolean;
  scannedCount: number;
  eligibleCount: number;
  archivedCount: number;
  softDeletedCount: number;
  permanentlyDeletedCount: number;
  legalHoldSkippedCount: number;
  warnings: readonly string[];
}
