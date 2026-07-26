import { Pause, RefreshCw } from 'lucide-react';
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
  Phase10Empty,
  Phase10StatusBadge,
} from '../../components/phase10/Phase10Ui';
import {
  useGraphSubscriptions,
  useSharePointConnectionMutations,
} from '../../hooks/useSharePointConnections';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type { GraphSubscription } from '../../types/sharepoint';
import { formatDateTime } from '../../utils/formatters';

export function GraphSubscriptionsPage() {
  const [page, setPage] = useState(1);
  const query = useGraphSubscriptions({ page, pageSize: 20 });
  const mutations = useSharePointConnectionMutations();
  const canConfigure = useAuthStore((state) =>
    state.hasPermission('sharepoint:configure'),
  );
  const { showToast } = useToast();

  const renew = async (subscription: GraphSubscription): Promise<void> => {
    try {
      await mutations.renewSubscription.mutateAsync(subscription.id);
      showToast({ tone: 'success', title: 'Graph subscription renewed' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Subscription renewal failed',
        message: getApiErrorMessage(error, 'Check Graph permissions and connection.'),
      });
    }
  };

  const disable = async (subscription: GraphSubscription): Promise<void> => {
    try {
      await mutations.disableSubscription.mutateAsync(subscription.id);
      showToast({ tone: 'success', title: 'Graph subscription disabled' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Subscription could not be disabled',
        message: getApiErrorMessage(error, 'Try again.'),
      });
    }
  };

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Integrations"
        title="Microsoft Graph Subscriptions"
        description="Monitor scoped webhook subscriptions and renewal status. Notification URLs and client-state values are never displayed."
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
                      {subscription.connectionName ?? '—'}
                    </Phase10Cell>
                    <Phase10Cell>{subscription.syncProfileName ?? '—'}</Phase10Cell>
                    <Phase10Cell>{subscription.resource}</Phase10Cell>
                    <Phase10Cell>{subscription.changeType}</Phase10Cell>
                    <Phase10Cell>
                      <Phase10StatusBadge status={subscription.status} />
                    </Phase10Cell>
                    <Phase10Cell>
                      {formatDateTime(subscription.expirationDateTime)}
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
                            onClick={() => void renew(subscription)}
                          />
                          <Phase10Action
                            label="Disable"
                            icon={Pause}
                            tone="danger"
                            disabled={['DISABLED', 'DELETED'].includes(
                              subscription.status,
                            )}
                            onClick={() => void disable(subscription)}
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
    </div>
  );
}
