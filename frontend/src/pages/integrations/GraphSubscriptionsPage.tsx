import { Pause, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { useState } from 'react';

import { getApiErrorMessage } from '../../api/errors';
import {
  Phase8ErrorAlert,
  Phase8Loading,
  Phase8Pagination,
} from '../../components/compliance/Phase8TableUtilities';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import {
  Phase10Action,
  Phase10Cell,
  Phase10Dialog,
  Phase10Empty,
  Phase10StatusBadge,
  ReasonDialog,
  phase10InputClass,
} from '../../components/phase10/Phase10Ui';
import {
  useGraphSubscriptions,
  useSharePointConnectionMutations,
  useSharePointConnections,
} from '../../hooks/useSharePointConnections';
import { useSharePointSyncProfiles } from '../../hooks/useSharePointSync';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type {
  GraphSubscription,
  GraphSubscriptionCreate,
} from '../../types/sharepoint';
import { formatDateTime } from '../../utils/formatters';

type SubscriptionDraft = Omit<GraphSubscriptionCreate, 'clientState'>;

const initialSubscriptionDraft = (): SubscriptionDraft => ({
  sharepointConnectionId: '',
  syncProfileId: '',
  resource: '',
  changeType: 'updated',
  notificationUrl: '',
  lifecycleNotificationUrl: null,
  expirationDatetime: new Date(Date.now() + 48 * 60 * 60 * 1000)
    .toISOString()
    .slice(0, 16),
});

const createClientState = (): string => {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return Array.from(bytes, (value) => value.toString(16).padStart(2, '0')).join('');
};

export function GraphSubscriptionsPage() {
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const [draft, setDraft] = useState<SubscriptionDraft>(initialSubscriptionDraft);
  const [renewTarget, setRenewTarget] = useState<GraphSubscription | null>(null);
  const [renewExpiry, setRenewExpiry] = useState('');
  const [disableTarget, setDisableTarget] = useState<GraphSubscription | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<GraphSubscription | null>(null);
  const query = useGraphSubscriptions({ page, pageSize: 20 });
  const connections = useSharePointConnections({ page: 1, pageSize: 100 });
  const profiles = useSharePointSyncProfiles({ page: 1, pageSize: 100 });
  const mutations = useSharePointConnectionMutations();
  const canConfigure = useAuthStore((state) =>
    state.hasPermission('sharepoint:configure'),
  );
  const { showToast } = useToast();

  const create = async (): Promise<void> => {
    if (
      !draft.sharepointConnectionId ||
      !draft.syncProfileId ||
      !draft.resource.trim() ||
      !draft.notificationUrl.trim() ||
      !draft.expirationDatetime
    ) {
      return;
    }
    try {
      await mutations.createSubscription.mutateAsync({
        ...draft,
        resource: draft.resource.trim(),
        notificationUrl: draft.notificationUrl.trim(),
        ...(draft.lifecycleNotificationUrl?.trim()
          ? { lifecycleNotificationUrl: draft.lifecycleNotificationUrl.trim() }
          : { lifecycleNotificationUrl: null }),
        expirationDatetime: new Date(draft.expirationDatetime).toISOString(),
        clientState: createClientState(),
      });
      setCreateOpen(false);
      setDraft(initialSubscriptionDraft());
      showToast({ tone: 'success', title: 'Graph subscription created' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Subscription could not be created',
        message: getApiErrorMessage(
          error,
          'Check the webhook-enabled profile, resource, callback URL, and expiration.',
        ),
      });
    }
  };

  const renew = async (): Promise<void> => {
    if (!renewTarget || !renewExpiry) return;
    try {
      await mutations.renewSubscription.mutateAsync({
        subscriptionId: renewTarget.id,
        payload: { expirationDatetime: new Date(renewExpiry).toISOString() },
      });
      setRenewTarget(null);
      setRenewExpiry('');
      showToast({ tone: 'success', title: 'Graph subscription renewed' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Subscription renewal failed',
        message: getApiErrorMessage(error, 'Check Graph permissions and connection.'),
      });
    }
  };

  const disable = async (reason: string): Promise<void> => {
    if (!disableTarget) return;
    try {
      await mutations.disableSubscription.mutateAsync({
        subscriptionId: disableTarget.id,
        payload: { reason },
      });
      setDisableTarget(null);
      showToast({ tone: 'success', title: 'Graph subscription disabled' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Subscription could not be disabled',
        message: getApiErrorMessage(error, 'Try again.'),
      });
    }
  };

  const remove = async (): Promise<void> => {
    if (!deleteTarget) return;
    try {
      await mutations.deleteSubscription.mutateAsync(deleteTarget.id);
      setDeleteTarget(null);
      showToast({ tone: 'success', title: 'Graph subscription deleted' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Subscription could not be deleted',
        message: getApiErrorMessage(error, 'Try again.'),
      });
    }
  };

  const eligibleProfiles =
    profiles.data?.items.filter(
      (profile) =>
        profile.sharepointConnectionId === draft.sharepointConnectionId &&
        profile.webhookEnabled &&
        profile.isActive,
    ) ?? [];

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Integrations"
        title="Microsoft Graph Subscriptions"
        description="Monitor scoped webhook subscriptions and renewal status. Notification URLs and client-state values are never displayed."
        actions={
          canConfigure ? (
            <button
              type="button"
              onClick={() => setCreateOpen(true)}
              className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-blue-700 px-4 text-xs font-semibold text-white"
            >
              <Plus className="size-4" aria-hidden="true" />
              Add Subscription
            </button>
          ) : null
        }
      />
      {query.isLoading && <Phase8Loading label="Loading Graph subscriptions" />}
      {query.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            query.error,
            'Graph subscriptions could not be loaded.',
          )}
          onRetry={() => void query.refetch()}
        />
      )}
      {query.data && query.data.items.length === 0 && (
        <Phase10Empty>No Graph subscriptions are configured.</Phase10Empty>
      )}
      {query.data && query.data.items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
            <table className="min-w-[72rem] divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  {[
                    'Connection',
                    'Sync Profile',
                    'Resource',
                    'Change Type',
                    'Status',
                    'Expires',
                    'Last Renewed',
                    'Last Notification',
                    'Renewal Attempts',
                    'Error',
                    'Actions',
                  ].map((heading) => (
                    <th
                      key={heading}
                      className="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-500"
                    >
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {query.data.items.map((subscription) => (
                  <tr key={subscription.id}>
                    <Phase10Cell strong>
                      {connections.data?.items.find(
                        (item) => item.id === subscription.sharepointConnectionId,
                      )?.name ?? subscription.sharepointConnectionId}
                    </Phase10Cell>
                    <Phase10Cell>
                      {profiles.data?.items.find(
                        (item) => item.id === subscription.syncProfileId,
                      )?.name ?? subscription.syncProfileId}
                    </Phase10Cell>
                    <Phase10Cell>{subscription.resource}</Phase10Cell>
                    <Phase10Cell>{subscription.changeType}</Phase10Cell>
                    <Phase10Cell>
                      <Phase10StatusBadge status={subscription.status} />
                    </Phase10Cell>
                    <Phase10Cell>
                      {formatDateTime(subscription.expirationDatetime)}
                    </Phase10Cell>
                    <Phase10Cell>
                      {subscription.lastRenewedAt
                        ? formatDateTime(subscription.lastRenewedAt)
                        : 'Never'}
                    </Phase10Cell>
                    <Phase10Cell>
                      {subscription.lastNotificationAt
                        ? formatDateTime(subscription.lastNotificationAt)
                        : 'Never'}
                    </Phase10Cell>
                    <Phase10Cell>{subscription.renewalAttempts}</Phase10Cell>
                    <Phase10Cell>{subscription.errorMessage ?? '—'}</Phase10Cell>
                    <td className="px-4 py-3">
                      {canConfigure && (
                        <div className="flex min-w-max gap-1.5">
                          <Phase10Action
                            label="Renew"
                            icon={RefreshCw}
                            disabled={
                              mutations.renewSubscription.isPending ||
                              subscription.status === 'DELETED'
                            }
                            onClick={() => {
                              const next = new Date(
                                Math.max(
                                  Date.now(),
                                  new Date(subscription.expirationDatetime).getTime(),
                                ) +
                                  48 * 60 * 60 * 1000,
                              );
                              setRenewExpiry(next.toISOString().slice(0, 16));
                              setRenewTarget(subscription);
                            }}
                          />
                          <Phase10Action
                            label="Disable"
                            icon={Pause}
                            tone="danger"
                            disabled={['DISABLED', 'DELETED'].includes(
                              subscription.status,
                            )}
                            onClick={() => setDisableTarget(subscription)}
                          />
                          <Phase10Action
                            label="Delete"
                            icon={Trash2}
                            tone="danger"
                            disabled={
                              mutations.deleteSubscription.isPending ||
                              subscription.status === 'DELETED'
                            }
                            onClick={() => setDeleteTarget(subscription)}
                          />
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Phase8Pagination
            page={page}
            totalItems={query.data.totalItems}
            totalPages={query.data.totalPages}
            label="subscriptions"
            onPageChange={setPage}
          />
        </>
      )}
      <Phase10Dialog
        open={createOpen}
        label="Create Microsoft Graph subscription"
        title="Add Graph Subscription"
        description="The webhook client state is generated securely in memory for this request and is never displayed or stored by the browser."
        onClose={() => {
          setCreateOpen(false);
          setDraft(initialSubscriptionDraft());
        }}
      >
        <form
          className="grid gap-4 sm:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault();
            void create();
          }}
        >
          <label className="text-xs font-semibold text-slate-700">
            Connection
            <select
              aria-label="Connection"
              value={draft.sharepointConnectionId}
              onChange={(event) => {
                const connectionId = event.target.value;
                const connection = connections.data?.items.find(
                  (item) => item.id === connectionId,
                );
                setDraft((current) => ({
                  ...current,
                  sharepointConnectionId: connectionId,
                  syncProfileId: '',
                  resource: connection?.driveId
                    ? `drives/${connection.driveId}/root`
                    : '',
                }));
              }}
              className={`mt-2 ${phase10InputClass}`}
            >
              <option value="">Select connection</option>
              {connections.data?.items
                .filter((connection) => connection.isActive && connection.driveId)
                .map((connection) => (
                  <option key={connection.id} value={connection.id}>
                    {connection.name}
                  </option>
                ))}
            </select>
          </label>
          <label className="text-xs font-semibold text-slate-700">
            Webhook-enabled sync profile
            <select
              aria-label="Webhook-enabled sync profile"
              value={draft.syncProfileId}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  syncProfileId: event.target.value,
                }))
              }
              disabled={!draft.sharepointConnectionId}
              className={`mt-2 ${phase10InputClass}`}
            >
              <option value="">Select profile</option>
              {eligibleProfiles.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.name}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs font-semibold text-slate-700 sm:col-span-2">
            Graph resource
            <input
              aria-label="Graph resource"
              value={draft.resource}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  resource: event.target.value,
                }))
              }
              placeholder="drives/{drive-id}/root"
              className={`mt-2 ${phase10InputClass}`}
            />
          </label>
          <label className="text-xs font-semibold text-slate-700">
            Change type
            <input
              aria-label="Change type"
              value={draft.changeType}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  changeType: event.target.value,
                }))
              }
              className={`mt-2 ${phase10InputClass}`}
            />
          </label>
          <label className="text-xs font-semibold text-slate-700">
            Expiration
            <input
              type="datetime-local"
              aria-label="Expiration"
              value={draft.expirationDatetime}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  expirationDatetime: event.target.value,
                }))
              }
              className={`mt-2 ${phase10InputClass}`}
            />
          </label>
          <label className="text-xs font-semibold text-slate-700 sm:col-span-2">
            Notification URL
            <input
              type="url"
              aria-label="Notification URL"
              value={draft.notificationUrl}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  notificationUrl: event.target.value,
                }))
              }
              placeholder="https://app.example.com/api/v1/sharepoint/webhook"
              className={`mt-2 ${phase10InputClass}`}
            />
          </label>
          <label className="text-xs font-semibold text-slate-700 sm:col-span-2">
            Lifecycle notification URL (optional)
            <input
              type="url"
              aria-label="Lifecycle notification URL"
              value={draft.lifecycleNotificationUrl ?? ''}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  lifecycleNotificationUrl: event.target.value || null,
                }))
              }
              placeholder="https://app.example.com/api/v1/sharepoint/webhook/lifecycle"
              className={`mt-2 ${phase10InputClass}`}
            />
          </label>
          <p className="text-xs leading-5 text-slate-500 sm:col-span-2">
            The callback must be an absolute HTTPS URL accepted by the server
            configuration. The backend also verifies that the resource stays inside the
            selected connection drive.
          </p>
          <div className="flex justify-end gap-2 sm:col-span-2">
            <button
              type="button"
              onClick={() => {
                setCreateOpen(false);
                setDraft(initialSubscriptionDraft());
              }}
              className="min-h-10 rounded-xl border border-slate-300 px-4 text-xs font-semibold"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={
                !draft.sharepointConnectionId ||
                !draft.syncProfileId ||
                !draft.resource.trim() ||
                !draft.notificationUrl.trim() ||
                !draft.expirationDatetime ||
                mutations.createSubscription.isPending
              }
              className="min-h-10 rounded-xl bg-blue-700 px-4 text-xs font-semibold text-white disabled:opacity-50"
            >
              {mutations.createSubscription.isPending
                ? 'Creatingâ€¦'
                : 'Create Subscription'}
            </button>
          </div>
        </form>
      </Phase10Dialog>
      <Phase10Dialog
        open={renewTarget !== null}
        label="Renew Microsoft Graph subscription"
        title="Renew Graph Subscription"
        description="Choose a future expiration. The backend applies Microsoft Graph limits and never exposes client state."
        onClose={() => {
          setRenewTarget(null);
          setRenewExpiry('');
        }}
        width="max-w-lg"
      >
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void renew();
          }}
        >
          <label className="text-xs font-semibold text-slate-700">
            New expiration
            <input
              type="datetime-local"
              aria-label="New expiration"
              value={renewExpiry}
              onChange={(event) => setRenewExpiry(event.target.value)}
              className={`mt-2 ${phase10InputClass}`}
            />
          </label>
          <div className="mt-5 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                setRenewTarget(null);
                setRenewExpiry('');
              }}
              className="min-h-10 rounded-xl border border-slate-300 px-4 text-xs font-semibold"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!renewExpiry || mutations.renewSubscription.isPending}
              className="min-h-10 rounded-xl bg-blue-700 px-4 text-xs font-semibold text-white disabled:opacity-50"
            >
              {mutations.renewSubscription.isPending ? 'Renewing…' : 'Renew'}
            </button>
          </div>
        </form>
      </Phase10Dialog>
      <ReasonDialog
        open={disableTarget !== null}
        title="Disable Graph subscription?"
        description="Webhook delivery for this subscription stops after the backend records the audited reason."
        confirmLabel="Disable Subscription"
        isPending={mutations.disableSubscription.isPending}
        onClose={() => setDisableTarget(null)}
        onConfirm={disable}
      />
      <Phase10Dialog
        open={deleteTarget !== null}
        label="Delete Microsoft Graph subscription"
        title="Delete Graph Subscription?"
        description="This removes the remote webhook subscription and marks the local record deleted. Existing audit history remains available."
        onClose={() => setDeleteTarget(null)}
        width="max-w-lg"
      >
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={() => setDeleteTarget(null)}
            className="min-h-10 rounded-xl border border-slate-300 px-4 text-xs font-semibold"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={mutations.deleteSubscription.isPending}
            onClick={() => void remove()}
            className="min-h-10 rounded-xl bg-rose-700 px-4 text-xs font-semibold text-white disabled:opacity-50"
          >
            {mutations.deleteSubscription.isPending
              ? 'Deletingâ€¦'
              : 'Delete Subscription'}
          </button>
        </div>
      </Phase10Dialog>
    </div>
  );
}
