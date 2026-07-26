import type { AxiosRequestConfig } from 'axios';

import { apiClient } from './client';
import type { ApiResponse } from '../types/auth';
import type {
  NotificationAdminListParams,
  NotificationDeliveryList,
  NotificationDeliveryListParams,
  NotificationList,
  NotificationListParams,
  NotificationMutationResult,
  NotificationPreference,
  NotificationPreferencesUpdate,
  NotificationRule,
  NotificationRuleCreate,
  NotificationRuleList,
  NotificationRuleUpdate,
  NotificationRetryResult,
  NotificationTemplate,
  NotificationTemplateCreate,
  NotificationTemplateList,
  NotificationTemplateTestRequest,
  NotificationTemplateTestResult,
  NotificationTemplateUpdate,
  NotificationUnreadCount,
} from '../types/notification';

const withSignal = (signal?: AbortSignal): AxiosRequestConfig =>
  signal ? { signal } : {};

export const listNotifications = async (
  params: NotificationListParams,
  signal?: AbortSignal,
): Promise<NotificationList> => {
  const { data } = await apiClient.get<ApiResponse<NotificationList>>(
    '/notifications',
    { params, ...withSignal(signal) },
  );
  return data.data;
};

export const getNotificationUnreadCount = async (
  signal?: AbortSignal,
): Promise<NotificationUnreadCount> => {
  const { data } = await apiClient.get<ApiResponse<NotificationUnreadCount>>(
    '/notifications/unread-count',
    withSignal(signal),
  );
  return data.data;
};

export const markNotificationRead = async (
  notificationId: string,
): Promise<NotificationMutationResult> => {
  const { data } = await apiClient.post<ApiResponse<NotificationMutationResult>>(
    `/notifications/${notificationId}/read`,
  );
  return data.data;
};

export const markAllNotificationsRead =
  async (): Promise<NotificationMutationResult> => {
    const { data } = await apiClient.post<ApiResponse<NotificationMutationResult>>(
      '/notifications/read-all',
    );
    return data.data;
  };

export const dismissNotification = async (
  notificationId: string,
): Promise<NotificationMutationResult> => {
  const { data } = await apiClient.post<ApiResponse<NotificationMutationResult>>(
    `/notifications/${notificationId}/dismiss`,
  );
  return data.data;
};

export const getNotificationPreferences = async (
  signal?: AbortSignal,
): Promise<NotificationPreference[]> => {
  const { data } = await apiClient.get<ApiResponse<NotificationPreference[]>>(
    '/notification-preferences',
    withSignal(signal),
  );
  return data.data;
};

export const updateNotificationPreferences = async (
  payload: NotificationPreferencesUpdate,
): Promise<NotificationPreference[]> => {
  const { data } = await apiClient.put<ApiResponse<NotificationPreference[]>>(
    '/notification-preferences',
    payload,
  );
  return data.data;
};

export const listNotificationTemplates = async (
  params: NotificationAdminListParams,
  signal?: AbortSignal,
): Promise<NotificationTemplateList> => {
  const { data } = await apiClient.get<ApiResponse<NotificationTemplateList>>(
    '/admin/notification-templates',
    { params, ...withSignal(signal) },
  );
  return data.data;
};

export const createNotificationTemplate = async (
  payload: NotificationTemplateCreate,
): Promise<NotificationTemplate> => {
  const { data } = await apiClient.post<ApiResponse<NotificationTemplate>>(
    '/admin/notification-templates',
    payload,
  );
  return data.data;
};

export const updateNotificationTemplate = async (
  templateId: string,
  payload: NotificationTemplateUpdate,
): Promise<NotificationTemplate> => {
  const { data } = await apiClient.put<ApiResponse<NotificationTemplate>>(
    `/admin/notification-templates/${templateId}`,
    payload,
  );
  return data.data;
};

export const testNotificationTemplate = async (
  templateId: string,
  payload: NotificationTemplateTestRequest,
): Promise<NotificationTemplateTestResult> => {
  const { data } = await apiClient.post<
    ApiResponse<NotificationTemplateTestResult>
  >(`/admin/notification-templates/${templateId}/test`, payload);
  return data.data;
};

export const listNotificationRules = async (
  params: NotificationAdminListParams,
  signal?: AbortSignal,
): Promise<NotificationRuleList> => {
  const { data } = await apiClient.get<ApiResponse<NotificationRuleList>>(
    '/admin/notification-rules',
    { params, ...withSignal(signal) },
  );
  return data.data;
};

export const createNotificationRule = async (
  payload: NotificationRuleCreate,
): Promise<NotificationRule> => {
  const { data } = await apiClient.post<ApiResponse<NotificationRule>>(
    '/admin/notification-rules',
    payload,
  );
  return data.data;
};

export const updateNotificationRule = async (
  ruleId: string,
  payload: NotificationRuleUpdate,
): Promise<NotificationRule> => {
  const { data } = await apiClient.put<ApiResponse<NotificationRule>>(
    `/admin/notification-rules/${ruleId}`,
    payload,
  );
  return data.data;
};

export const setNotificationRuleActive = async (
  ruleId: string,
  active: boolean,
): Promise<NotificationRule> => {
  const { data } = await apiClient.post<ApiResponse<NotificationRule>>(
    `/admin/notification-rules/${ruleId}/${active ? 'activate' : 'deactivate'}`,
  );
  return data.data;
};

export const listNotificationDeliveries = async (
  params: NotificationDeliveryListParams,
  signal?: AbortSignal,
): Promise<NotificationDeliveryList> => {
  const { data } = await apiClient.get<ApiResponse<NotificationDeliveryList>>(
    '/admin/notification-deliveries',
    { params, ...withSignal(signal) },
  );
  return data.data;
};

export const retryNotificationDelivery = async (
  deliveryId: string,
): Promise<NotificationRetryResult> => {
  const { data } = await apiClient.post<ApiResponse<NotificationRetryResult>>(
    `/admin/notification-deliveries/${deliveryId}/retry`,
  );
  return data.data;
};

export const notificationApi = {
  list: listNotifications,
  unreadCount: getNotificationUnreadCount,
  markRead: markNotificationRead,
  markAllRead: markAllNotificationsRead,
  dismiss: dismissNotification,
  getPreferences: getNotificationPreferences,
  updatePreferences: updateNotificationPreferences,
  listTemplates: listNotificationTemplates,
  createTemplate: createNotificationTemplate,
  updateTemplate: updateNotificationTemplate,
  testTemplate: testNotificationTemplate,
  listRules: listNotificationRules,
  createRule: createNotificationRule,
  updateRule: updateNotificationRule,
  setRuleActive: setNotificationRuleActive,
  listDeliveries: listNotificationDeliveries,
  retryDelivery: retryNotificationDelivery,
} as const;
