import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  createGraphSubscription,
  createSharePointConnection,
  deleteGraphSubscription,
  disableGraphSubscription,
  disableSharePointConnection,
  getSharePointConnection,
  listGraphSubscriptions,
  listSharePointConnections,
  listSharePointDrives,
  renewGraphSubscription,
  testSharePointConnection,
  updateSharePointConnection,
} from '../api/sharepointApi';
import type {
  GraphSubscriptionCreate,
  GraphSubscriptionDisableRequest,
  GraphSubscriptionListParams,
  GraphSubscriptionRenewRequest,
  SharePointConnectionCreate,
  SharePointConnectionListParams,
  SharePointConnectionUpdate,
} from '../types/sharepoint';
import { useDocumentSession } from './useDocumentSession';

export const sharePointConnectionKeys = {
  root: (scope: readonly [string, number]) =>
    ['sharepoint-connections', scope[0], scope[1]] as const,
  list: (scope: readonly [string, number], params: object) =>
    [...sharePointConnectionKeys.root(scope), 'list', params] as const,
  detail: (scope: readonly [string, number], connectionId: string) =>
    [...sharePointConnectionKeys.root(scope), 'detail', connectionId] as const,
  drives: (scope: readonly [string, number], connectionId: string) =>
    [...sharePointConnectionKeys.root(scope), 'drives', connectionId] as const,
  subscriptions: (scope: readonly [string, number], params: object) =>
    [...sharePointConnectionKeys.root(scope), 'subscriptions', params] as const,
} as const;

export const useSharePointConnections = (params: SharePointConnectionListParams) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: sharePointConnectionKeys.list(scope, params),
    queryFn: ({ signal }) => listSharePointConnections(params, signal),
    placeholderData: (previous) => previous,
  });
};

export const useSharePointConnection = (connectionId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: sharePointConnectionKeys.detail(scope, connectionId ?? 'none'),
    queryFn: ({ signal }) => getSharePointConnection(connectionId ?? '', signal),
    enabled: connectionId !== null,
  });
};

export const useSharePointDrives = (connectionId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: sharePointConnectionKeys.drives(scope, connectionId ?? 'none'),
    queryFn: ({ signal }) => listSharePointDrives(connectionId ?? '', signal),
    enabled: connectionId !== null,
  });
};

export const useGraphSubscriptions = (params: GraphSubscriptionListParams) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: sharePointConnectionKeys.subscriptions(scope, params),
    queryFn: ({ signal }) => listGraphSubscriptions(params, signal),
    placeholderData: (previous) => previous,
    refetchInterval: 60_000,
  });
};

export const useSharePointConnectionMutations = () => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();
  const invalidate = async (): Promise<void> => {
    await queryClient.invalidateQueries({
      queryKey: sharePointConnectionKeys.root(scope),
    });
  };
  return {
    create: useMutation({
      mutationFn: (payload: SharePointConnectionCreate) =>
        createSharePointConnection(payload),
      onSuccess: invalidate,
    }),
    update: useMutation({
      mutationFn: ({
        connectionId,
        payload,
      }: {
        connectionId: string;
        payload: SharePointConnectionUpdate;
      }) => updateSharePointConnection(connectionId, payload),
      onSuccess: invalidate,
    }),
    test: useMutation({
      mutationFn: testSharePointConnection,
      onSuccess: invalidate,
    }),
    disable: useMutation({
      mutationFn: disableSharePointConnection,
      onSuccess: invalidate,
    }),
    setDefault: useMutation({
      mutationFn: (connectionId: string) =>
        updateSharePointConnection(connectionId, { isDefault: true }),
      onSuccess: invalidate,
    }),
    createSubscription: useMutation({
      mutationFn: (payload: GraphSubscriptionCreate) =>
        createGraphSubscription(payload),
      onSuccess: invalidate,
    }),
    renewSubscription: useMutation({
      mutationFn: ({
        payload,
        subscriptionId,
      }: {
        subscriptionId: string;
        payload: GraphSubscriptionRenewRequest;
      }) => renewGraphSubscription(subscriptionId, payload),
      onSuccess: invalidate,
    }),
    disableSubscription: useMutation({
      mutationFn: ({
        payload,
        subscriptionId,
      }: {
        subscriptionId: string;
        payload: GraphSubscriptionDisableRequest;
      }) => disableGraphSubscription(subscriptionId, payload),
      onSuccess: invalidate,
    }),
    deleteSubscription: useMutation({
      mutationFn: deleteGraphSubscription,
      onSuccess: invalidate,
    }),
  } as const;
};
