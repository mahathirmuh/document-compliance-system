import { RotateCcw } from 'lucide-react';
import { useState } from 'react';

import { getApiErrorMessage } from '../../api/errors';
import {
  Phase8ErrorAlert,
  Phase8FilterField,
  Phase8Loading,
  Phase8Pagination,
} from '../../components/compliance/Phase8TableUtilities';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import {
  Phase10Action,
  Phase10Cell,
  Phase10Empty,
  Phase10StatusBadge,
  phase10InputClass,
} from '../../components/phase10/Phase10Ui';
import {
  useNotificationDeliveries,
  useNotificationMutations,
} from '../../hooks/useNotifications';
import { useToast } from '../../providers/useToast';
import {
  notificationChannels,
  type NotificationChannel,
  type NotificationDeliveryStatus,
} from '../../types/notification';
import { formatDateTime } from '../../utils/formatters';

export function NotificationDeliveriesPage() {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<NotificationDeliveryStatus | ''>('');
  const [channel, setChannel] = useState<NotificationChannel | ''>('');
  const query = useNotificationDeliveries({
    page,
    pageSize: 20,
    ...(status ? { status } : {}),
    ...(channel ? { channel } : {}),
  });
  const mutations = useNotificationMutations();
  const { showToast } = useToast();
  const retry = async (deliveryId: string): Promise<void> => {
    try {
      await mutations.retryDelivery.mutateAsync(deliveryId);
      showToast({ tone: 'success', title: 'Notification retry scheduled' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Delivery could not be retried',
        message: getApiErrorMessage(error, 'Retry limit may be exhausted.'),
      });
    }
  };
  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Administration"
        title="Notification Deliveries"
        description="Inspect asynchronous channel delivery, provider-safe errors, attempts, and controlled retry history."
      />
      <div className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 sm:grid-cols-2">
        <Phase8FilterField label="Status">
          <select
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as NotificationDeliveryStatus | '');
              setPage(1);
            }}
            className={phase10InputClass}
          >
            <option value="">All statuses</option>
            {[
              'QUEUED',
              'SENDING',
              'SENT',
              'DELIVERED',
              'FAILED',
              'RETRY_SCHEDULED',
              'CANCELLED',
              'SKIPPED',
            ].map((value) => (
              <option key={value} value={value}>
                {value.replaceAll('_', ' ')}
              </option>
            ))}
          </select>
        </Phase8FilterField>
        <Phase8FilterField label="Channel">
          <select
            value={channel}
            onChange={(event) => {
              setChannel(event.target.value as NotificationChannel | '');
              setPage(1);
            }}
            className={phase10InputClass}
          >
            <option value="">All channels</option>
            {notificationChannels.map((value) => (
              <option key={value} value={value}>
                {value.replaceAll('_', ' ')}
              </option>
            ))}
          </select>
        </Phase8FilterField>
      </div>
      {query.isLoading && <Phase8Loading label="Loading notification deliveries" />}
      {query.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            query.error,
            'Notification deliveries could not be loaded.',
          )}
          onRetry={() => void query.refetch()}
        />
      )}
      {query.data && query.data.items.length === 0 && (
        <Phase10Empty>No deliveries match these filters.</Phase10Empty>
      )}
      {query.data && query.data.items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
            <table className="min-w-[80rem] divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  {[
                    'Created',
                    'Event',
                    'Channel',
                    'Recipient',
                    'Subject',
                    'Status',
                    'Attempts',
                    'Sent',
                    'Delivered',
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
                {query.data.items.map((delivery) => (
                  <tr key={delivery.id}>
                    <Phase10Cell>{formatDateTime(delivery.createdAt)}</Phase10Cell>
                    <Phase10Cell strong>
                      {delivery.eventType.replaceAll('_', ' ')}
                    </Phase10Cell>
                    <Phase10Cell>{delivery.channel.replaceAll('_', ' ')}</Phase10Cell>
                    <Phase10Cell>{delivery.recipientReference}</Phase10Cell>
                    <Phase10Cell>{delivery.subject ?? '—'}</Phase10Cell>
                    <Phase10Cell>
                      <Phase10StatusBadge status={delivery.status} />
                    </Phase10Cell>
                    <Phase10Cell>
                      {delivery.attemptCount} / {delivery.maximumAttempts}
                    </Phase10Cell>
                    <Phase10Cell>
                      {delivery.sentAt ? formatDateTime(delivery.sentAt) : '—'}
                    </Phase10Cell>
                    <Phase10Cell>
                      {delivery.deliveredAt
                        ? formatDateTime(delivery.deliveredAt)
                        : '—'}
                    </Phase10Cell>
                    <Phase10Cell>{delivery.errorMessage ?? '—'}</Phase10Cell>
                    <td className="px-4 py-3">
                      {['FAILED', 'CANCELLED'].includes(delivery.status) &&
                        delivery.attemptCount < delivery.maximumAttempts && (
                          <Phase10Action
                            label="Retry Delivery"
                            icon={RotateCcw}
                            disabled={mutations.retryDelivery.isPending}
                            onClick={() => void retry(delivery.id)}
                          />
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
            label="deliveries"
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
}
