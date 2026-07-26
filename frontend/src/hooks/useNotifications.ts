import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  createNotificationRule,
  createNotificationTemplate,
  dismissNotification,
  getNotificationPreferences,
  getNotificationUnreadCount,
  listNotificationDeliveries,
  listNotificationRules,
  listNotifications,
  listNotificationTemplates,
  markAllNotificationsRead,
  markNotificationRead,
  retryNotificationDelivery,
  setNotificationRuleActive,
  testNotificationTemplate,
  updateNotificationPreferences,
  updateNotificationRule,
  updateNotificationTemplate,
} from '../api/notificationApi';
import type {
  NotificationAdminListParams,
  NotificationDeliveryListParams,
  NotificationListParams,
  NotificationPreferencesUpdate,
  NotificationRuleCreate,
  NotificationRuleUpdate,
  NotificationTemplateTestRequest,
  NotificationTemplateCreate,
  NotificationTemplateUpdate,
} from '../types/notification';
import { useDocumentSession } from './useDocumentSession';

const notificationPollingMs = 45_000;

export const notificationKeys = {
  root: (scope: readonly [string, number]) =>
    ['notifications', scope[0], scope[1]] as const,
  list: (scope: readonly [string, number], params: object) =>
    [...notificationKeys.root(scope), 'list', params] as const,
  unread: (scope: readonly [string, number]) =>
    [...notificationKeys.root(scope), 'unread'] as const,
  preferences: (scope: readonly [string, number]) =>
    [...notificationKeys.root(scope), 'preferences'] as const,
  templates: (scope: readonly [string, number], params: object) =>
    [...notificationKeys.root(scope), 'templates', params] as const,
  rules: (scope: readonly [string, number], params: object) =>
    [...notificationKeys.root(scope), 'rules', params] as const,
  deliveries: (scope: readonly [string, number], params: object) =>
    [...notificationKeys.root(scope), 'deliveries', params] as const,
} as const;

export const useNotifications = (params: NotificationListParams, enabled = true) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: notificationKeys.list(scope, params),
    queryFn: ({ signal }) => listNotifications(params, signal),
    enabled,
    placeholderData: (previous) => previous,
    refetchInterval: enabled ? notificationPollingMs : false,
  });
};

export const useNotificationUnreadCount = (enabled = true) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: notificationKeys.unread(scope),
    queryFn: ({ signal }) => getNotificationUnreadCount(signal),
    enabled,
    refetchInterval: enabled ? notificationPollingMs : false,
  });
};

export const useNotificationPreferences = () => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: notificationKeys.preferences(scope),
    queryFn: ({ signal }) => getNotificationPreferences(signal),
  });
};

export const useNotificationTemplates = (params: NotificationAdminListParams) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: notificationKeys.templates(scope, params),
    queryFn: ({ signal }) => listNotificationTemplates(params, signal),
    placeholderData: (previous) => previous,
  });
};

export const useNotificationRules = (params: NotificationAdminListParams) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: notificationKeys.rules(scope, params),
    queryFn: ({ signal }) => listNotificationRules(params, signal),
    placeholderData: (previous) => previous,
  });
};

export const useNotificationDeliveries = (params: NotificationDeliveryListParams) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: notificationKeys.deliveries(scope, params),
    queryFn: ({ signal }) => listNotificationDeliveries(params, signal),
    placeholderData: (previous) => previous,
    refetchInterval: (query) =>
      query.state.data?.items.some((item) =>
        ['QUEUED', 'SENDING', 'RETRY_SCHEDULED'].includes(item.status),
      )
        ? 10_000
        : false,
  });
};

export const useNotificationMutations = () => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();
  const invalidate = async (): Promise<void> => {
    await queryClient.invalidateQueries({ queryKey: notificationKeys.root(scope) });
  };
  return {
    markRead: useMutation({
      mutationFn: markNotificationRead,
      onSuccess: invalidate,
    }),
    markAllRead: useMutation({
      mutationFn: markAllNotificationsRead,
      onSuccess: invalidate,
    }),
    dismiss: useMutation({
      mutationFn: dismissNotification,
      onSuccess: invalidate,
    }),
    updatePreferences: useMutation({
      mutationFn: (payload: NotificationPreferencesUpdate) =>
        updateNotificationPreferences(payload),
      onSuccess: invalidate,
    }),
    createTemplate: useMutation({
      mutationFn: (payload: NotificationTemplateCreate) =>
        createNotificationTemplate(payload),
      onSuccess: invalidate,
    }),
    updateTemplate: useMutation({
      mutationFn: ({
        payload,
        templateId,
      }: {
        templateId: string;
        payload: NotificationTemplateUpdate;
      }) => updateNotificationTemplate(templateId, payload),
      onSuccess: invalidate,
    }),
    testTemplate: useMutation({
      mutationFn: ({
        payload,
        templateId,
      }: {
        templateId: string;
        payload: NotificationTemplateTestRequest;
      }) => testNotificationTemplate(templateId, payload),
      onSuccess: invalidate,
    }),
    createRule: useMutation({
      mutationFn: (payload: NotificationRuleCreate) =>
        createNotificationRule(payload),
      onSuccess: invalidate,
    }),
    updateRule: useMutation({
      mutationFn: ({
        payload,
        ruleId,
      }: {
        ruleId: string;
        payload: NotificationRuleUpdate;
      }) => updateNotificationRule(ruleId, payload),
      onSuccess: invalidate,
    }),
    setRuleActive: useMutation({
      mutationFn: ({ active, ruleId }: { ruleId: string; active: boolean }) =>
        setNotificationRuleActive(ruleId, active),
      onSuccess: invalidate,
    }),
    retryDelivery: useMutation({
      mutationFn: retryNotificationDelivery,
      onSuccess: invalidate,
    }),
  } as const;
};
