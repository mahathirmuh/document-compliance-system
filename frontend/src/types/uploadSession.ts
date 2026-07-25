export const uploadSessionTypes = ['SINGLE', 'BATCH', 'REPLACE'] as const;

export type UploadSessionType = (typeof uploadSessionTypes)[number];

export const uploadSessionStatuses = [
  'CREATED',
  'UPLOADING',
  'READY_FOR_CONFIRMATION',
  'COMMITTED',
  'PARTIALLY_COMMITTED',
  'CANCELLED',
  'EXPIRED',
  'FAILED',
] as const;

export type UploadSessionStatus = (typeof uploadSessionStatuses)[number];

export interface UploadSessionSummary {
  id: string;
  sessionType: UploadSessionType;
  status: UploadSessionStatus;
  totalFiles: number;
  totalSize: number;
  expiresAt: string;
  committedAt: string | null;
  cancelledAt: string | null;
  createdAt: string;
  updatedAt: string;
}
