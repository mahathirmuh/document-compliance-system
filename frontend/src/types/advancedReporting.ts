import type { DocumentUserSummary } from './document';
import type { PaginatedData } from './masterData';

export const advancedReportTypes = [
  'COMPLIANCE_OVERVIEW',
  'FINDINGS_ANALYTICS',
  'TRANSLATION_SIMILARITY',
  'GLOSSARY_COMPLIANCE',
  'REVISION_CHANGES',
  'DEPARTMENT_PERFORMANCE',
  'DOCUMENT_TYPE_PERFORMANCE',
  'VALIDATION_RULE_PERFORMANCE',
  'LANGUAGE_QUALITY',
  'PROCESSING_PERFORMANCE',
] as const;
export type AdvancedReportType = (typeof advancedReportTypes)[number];
export type ReportFormat = 'xlsx' | 'json' | 'pdf';

export interface AdvancedReportFilter {
  dateFrom?: string;
  dateTo?: string;
  departmentIds?: readonly string[];
  sectionIds?: readonly string[];
  documentTypeIds?: readonly string[];
  documentStatusIds?: readonly string[];
  validationRuleIds?: readonly string[];
  complianceStatuses?: readonly string[];
  findingSeverities?: readonly string[];
  findingStatuses?: readonly string[];
  languagePairs?: readonly string[];
  glossaryProfileIds?: readonly string[];
  revisionRange?: readonly string[];
  includeArchived?: boolean;
}

export interface ReportGenerateRequest {
  reportType: AdvancedReportType;
  reportName: string;
  filters: AdvancedReportFilter;
  outputFormat: ReportFormat;
  includeCharts?: boolean;
  includeDetailedTables?: boolean;
}

export const reportJobStatuses = [
  'QUEUED',
  'BUILDING_DATASET',
  'GENERATING_CHARTS',
  'CREATING_FILE',
  'STORING_FILE',
  'COMPLETED',
  'FAILED',
  'CANCEL_REQUESTED',
  'CANCELLED',
] as const;
export type ReportJobStatus = (typeof reportJobStatuses)[number];

export const terminalReportJobStatuses: readonly ReportJobStatus[] = [
  'COMPLETED',
  'FAILED',
  'CANCELLED',
];
export const isTerminalReportJobStatus = (status: ReportJobStatus): boolean =>
  terminalReportJobStatuses.includes(status);

export interface ReportJob {
  id: string;
  reportType: AdvancedReportType;
  reportName: string;
  outputFormat: ReportFormat;
  status: ReportJobStatus;
  snapshotStatus: ReportSnapshotStatus;
  progress: number;
  currentStage: string | null;
  requestedAt: string;
  startedAt: string | null;
  completedAt: string | null;
  errorCode: string | null;
  errorMessage: string | null;
}

export interface ReportJobListParams {
  page: number;
  pageSize: number;
  status?: ReportJobStatus | readonly ReportJobStatus[];
  reportType?: AdvancedReportType;
}
export type ReportJobList = PaginatedData<ReportJob>;

export type ReportSnapshotStatus =
  'GENERATING' | 'AVAILABLE' | 'FAILED' | 'EXPIRED' | 'DELETED';

export interface ReportSnapshot {
  id: string;
  reportType: AdvancedReportType;
  reportName: string;
  filters: AdvancedReportFilter;
  datasetHash: string | null;
  status: ReportSnapshotStatus;
  jobStatus: ReportJobStatus;
  generatedBy: string | DocumentUserSummary | null;
  generatedAt: string | null;
  fileFormat: ReportFormat;
  fileSize: number | null;
  expiresAt: string | null;
  metadata: {
    summary?: Readonly<Record<string, string | number | boolean | null>>;
    filterSummary?: readonly string[];
    [key: string]: unknown;
  } | null;
  createdAt: string;
}

export interface ReportSnapshotListParams {
  page: number;
  pageSize: number;
  reportType?: AdvancedReportType;
  status?: ReportSnapshotStatus;
  format?: ReportFormat;
  dateFrom?: string;
  dateTo?: string;
}
export type ReportSnapshotList = PaginatedData<ReportSnapshot>;

export type ReportScheduleType = 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'CUSTOM_CRON';

export interface ReportSchedule {
  id: string;
  name: string;
  reportType: AdvancedReportType;
  filters: AdvancedReportFilter;
  formats: readonly ReportFormat[];
  scheduleType: ReportScheduleType;
  cronExpression: string | null;
  timezone: string;
  isActive: boolean;
  lastRunAt: string | null;
  nextRunAt: string | null;
  createdBy: string | DocumentUserSummary | null;
  updatedBy: string | DocumentUserSummary | null;
  createdAt: string;
  updatedAt: string;
}

export interface ReportScheduleCreate {
  name: string;
  reportType: AdvancedReportType;
  filters: AdvancedReportFilter;
  formats: readonly ReportFormat[];
  scheduleType: ReportScheduleType;
  cronExpression?: string | null;
  timezone: string;
}

export type ReportScheduleUpdate = Partial<ReportScheduleCreate> & {
  isActive?: boolean;
};

export interface ReportScheduleListParams {
  page: number;
  pageSize: number;
  includeInactive?: boolean;
}
export type ReportScheduleList = PaginatedData<ReportSchedule>;

export interface ReportDownload {
  blob: Blob;
  fileName: string | null;
}

export interface ReportScheduleRunResult {
  scheduleId: string;
  jobIds: readonly string[];
}

export interface ReportSnapshotDeleteResult {
  snapshotId: string;
  status: ReportSnapshotStatus;
}
