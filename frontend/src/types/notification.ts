import type { PaginatedData } from './masterData';

export const notificationChannels = [
  'IN_APP',
  'EMAIL_GRAPH',
  'TEAMS',
  'TELEGRAM',
] as const;
export type NotificationChannel = (typeof notificationChannels)[number];

export type NotificationSeverity =
  | 'INFORMATION'
  | 'WARNING'
  | 'ERROR'
  | 'CRITICAL';

export const notificationEventTypes = [
  'DOCUMENT_UPLOADED',
  'DOCUMENT_REPLACED',
  'DOCUMENT_REVISION_CREATED',
  'EXTRACTION_COMPLETED',
  'EXTRACTION_FAILED',
  'OCR_COMPLETED',
  'OCR_FAILED',
  'LANGUAGE_DETECTION_COMPLETED',
  'COMPLIANCE_VALIDATION_COMPLETED',
  'COMPLIANCE_VALIDATION_FAILED',
  'SIMILARITY_COMPLETED',
  'GLOSSARY_VALIDATION_COMPLETED',
  'CRITICAL_FINDING_CREATED',
  'MAJOR_FINDING_CREATED',
  'FINDING_ASSIGNED',
  'FINDING_RESOLVED',
  'FINDING_REOPENED',
  'ACCEPTED_RISK_EXPIRING',
  'SHAREPOINT_SYNC_COMPLETED',
  'SHAREPOINT_SYNC_PARTIAL',
  'SHAREPOINT_SYNC_FAILED',
  'SHAREPOINT_CONFLICT_CREATED',
  'SHAREPOINT_CONNECTION_FAILED',
  'GRAPH_SUBSCRIPTION_RENEWAL_FAILED',
  'REPORT_GENERATED',
  'REPORT_FAILED',
  'SYSTEM_BACKUP_FAILED',
  'SYSTEM_DISK_SPACE_LOW',
  'SYSTEM_WORKER_UNAVAILABLE',
  'SYSTEM_SECURITY_ALERT',
] as const;
export type NotificationEventType = (typeof notificationEventTypes)[number];

export interface InAppNotification {
  id: string;
  userId: string;
  eventType: NotificationEventType;
  title: string;
  message: string;
  severity: NotificationSeverity;
  relatedEntityType: string | null;
  relatedEntityId: string | null;
  actionUrl: string | null;
  isRead: boolean;
  readAt: string | null;
  dismissedAt: string | null;
  createdAt: string;
  expiresAt: string | null;
}

export interface NotificationListParams {
  page: number;
  pageSize: number;
  unreadOnly?: boolean;
}
export type NotificationList = PaginatedData<InAppNotification>;

export interface NotificationUnreadCount {
  unreadCount: number;
}

export interface NotificationMutationResult {
  notificationId: string | null;
  affectedCount: number;
}

export type NotificationDigestMode = 'NONE' | 'DAILY' | 'WEEKLY';

export interface NotificationPreferenceItem {
  eventType: NotificationEventType;
  inAppEnabled: boolean;
  emailEnabled: boolean;
  teamsEnabled: boolean;
  telegramEnabled: boolean;
  digestMode: NotificationDigestMode;
  quietHoursEnabled: boolean;
  quietHoursStart: string | null;
  quietHoursEnd: string | null;
  timezone: string;
}

export interface NotificationPreference extends NotificationPreferenceItem {
  id: string;
  userId: string;
  createdAt: string;
  updatedAt: string;
}

export interface NotificationPreferencesUpdate {
  preferences: readonly NotificationPreferenceItem[];
}

export type NotificationContentType =
  | 'PLAIN_TEXT'
  | 'HTML'
  | 'MARKDOWN'
  | 'JSON_CARD';

export interface NotificationTemplate {
  id: string;
  code: string;
  name: string;
  eventType: NotificationEventType;
  channel: NotificationChannel;
  subjectTemplate: string | null;
  bodyTemplate: string;
  contentType: NotificationContentType;
  languageCode: string;
  version: number;
  isDefault: boolean;
  isActive: boolean;
  createdBy: string | null;
  updatedBy: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface NotificationTemplateCreate {
  code: string;
  name: string;
  eventType: NotificationEventType;
  channel: NotificationChannel;
  subjectTemplate?: string | null;
  bodyTemplate: string;
  contentType?: NotificationContentType;
  languageCode?: string;
  version?: number;
  isDefault?: boolean;
  isActive?: boolean;
}

export interface NotificationTemplateUpdate {
  name?: string;
  subjectTemplate?: string | null;
  bodyTemplate?: string;
  contentType?: NotificationContentType;
  isDefault?: boolean;
  isActive?: boolean;
}

export interface NotificationTemplateTestRequest {
  variables: Readonly<Record<string, unknown>>;
  recipient?: string | null;
  send?: boolean;
}

export interface NotificationTemplateTestResult {
  subject: string | null;
  body: string;
  contentType: NotificationContentType;
  sent: boolean;
}

export interface NotificationAdminListParams {
  page: number;
  pageSize: number;
  eventType?: NotificationEventType;
  channel?: NotificationChannel;
  includeInactive?: boolean;
}
export type NotificationTemplateList = PaginatedData<NotificationTemplate>;

export type NotificationRecipientType =
  | 'EVENT_ACTOR'
  | 'DOCUMENT_OWNER'
  | 'DOCUMENT_CONTROLLER'
  | 'DEPARTMENT_USERS'
  | 'ROLE'
  | 'SPECIFIC_USERS'
  | 'SPECIFIC_EMAILS'
  | 'TEAMS_CHANNEL'
  | 'TELEGRAM_CHAT';

export type NotificationScopeType =
  | 'GLOBAL'
  | 'DEPARTMENT'
  | 'DOCUMENT_TYPE'
  | 'DEPARTMENT_DOCUMENT_TYPE';

export interface NotificationRule {
  id: string;
  name: string;
  eventType: NotificationEventType;
  channel: NotificationChannel;
  scopeType: NotificationScopeType;
  departmentId: string | null;
  documentTypeId: string | null;
  severityFilterJson: readonly NotificationSeverity[];
  recipientType: NotificationRecipientType;
  recipientValueJson: Readonly<Record<string, unknown>>;
  templateId: string;
  sendImmediately: boolean;
  digestEnabled: boolean;
  digestSchedule: string | null;
  isMandatory: boolean;
  isActive: boolean;
  createdBy: string | null;
  updatedBy: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface NotificationRuleCreate {
  name: string;
  eventType: NotificationEventType;
  channel: NotificationChannel;
  scopeType?: NotificationScopeType;
  departmentId?: string | null;
  documentTypeId?: string | null;
  severityFilterJson?: readonly NotificationSeverity[];
  recipientType: NotificationRecipientType;
  recipientValueJson?: Readonly<Record<string, unknown>>;
  templateId: string;
  sendImmediately?: boolean;
  digestEnabled?: boolean;
  digestSchedule?: string | null;
  isMandatory?: boolean;
  isActive?: boolean;
}

export interface NotificationRuleUpdate {
  name?: string;
  severityFilterJson?: readonly NotificationSeverity[];
  recipientType?: NotificationRecipientType;
  recipientValueJson?: Readonly<Record<string, unknown>>;
  templateId?: string;
  sendImmediately?: boolean;
  digestEnabled?: boolean;
  digestSchedule?: string | null;
  isMandatory?: boolean;
  isActive?: boolean;
}

export type NotificationRuleList = PaginatedData<NotificationRule>;

export type NotificationDeliveryStatus =
  | 'QUEUED'
  | 'SENDING'
  | 'SENT'
  | 'DELIVERED'
  | 'FAILED'
  | 'RETRY_SCHEDULED'
  | 'CANCELLED'
  | 'SKIPPED';

export interface NotificationDelivery {
  id: string;
  eventType: NotificationEventType;
  channel: NotificationChannel;
  templateId: string | null;
  recipientType: NotificationRecipientType;
  recipientReference: string;
  subject: string | null;
  payloadHash: string;
  status: NotificationDeliveryStatus;
  attemptCount: number;
  maximumAttempts: number;
  providerMessageId: string | null;
  sentAt: string | null;
  deliveredAt: string | null;
  failedAt: string | null;
  nextRetryAt: string | null;
  errorCode: string | null;
  errorMessage: string | null;
  metadataJson: Readonly<Record<string, unknown>>;
  createdAt: string;
  updatedAt: string;
}

export interface NotificationDeliveryListParams {
  page: number;
  pageSize: number;
  status?: NotificationDeliveryStatus;
  eventType?: NotificationEventType;
  channel?: NotificationChannel;
}
export type NotificationDeliveryList = PaginatedData<NotificationDelivery>;

export interface NotificationRetryResult {
  deliveryId: string;
  status: NotificationDeliveryStatus;
}
