import type { PaginatedData } from './masterData';

export type HealthState = 'healthy' | 'degraded' | 'unhealthy' | 'disabled';

export interface DependencyHealth {
  name: string;
  status: HealthState;
  checkedAt: string;
  latencyMs: number | null;
  message: string | null;
  details: Readonly<Record<string, unknown>>;
}

export interface WorkerHealth {
  workerName: string;
  queueName: string;
  status: HealthState;
  lastHeartbeatAt: string | null;
  ageSeconds: number | null;
}

export interface SystemHealthSummary {
  status: HealthState;
  checkedAt: string;
  dependencies: DependencyHealth[];
  workers: WorkerHealth[];
}

export type DeadLetterStatus = 'ACTIVE' | 'RETRY_QUEUED' | 'RETRIED' | 'DISMISSED';

export interface DeadLetterJob {
  id: string;
  taskName: string;
  entityType: string;
  entityId: string | null;
  attempts: number;
  maximumAttempts: number;
  errorCode: string;
  lastError: string;
  firstFailedAt: string;
  lastFailedAt: string;
  retryHistory: readonly Readonly<Record<string, unknown>>[];
  sanitizedArguments: Readonly<Record<string, unknown>>;
  status: DeadLetterStatus;
  dismissedBy: string | null;
  dismissedAt: string | null;
  dismissalReason: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface DeadLetterListParams {
  page: number;
  pageSize: number;
  status?: DeadLetterStatus;
  taskName?: string;
}
export type DeadLetterJobList = PaginatedData<DeadLetterJob>;

export interface DeadLetterActionRequest {
  reason: string;
}

export interface DeadLetterMutationResult {
  jobId: string;
  status: DeadLetterStatus;
}
