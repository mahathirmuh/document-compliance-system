import { Save } from 'lucide-react';
import { useEffect, useState } from 'react';

import { getApiErrorMessage } from '../../api/errors';
import {
  Phase8ErrorAlert,
  Phase8Loading,
} from '../../components/compliance/Phase8TableUtilities';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { phase10InputClass } from '../../components/phase10/Phase10Ui';
import {
  useNotificationMutations,
  useNotificationPreferences,
} from '../../hooks/useNotifications';
import { useToast } from '../../providers/useToast';
import {
  notificationEventTypes,
  type NotificationDigestMode,
  type NotificationPreference,
  type NotificationPreferenceItem,
} from '../../types/notification';

const defaultPreference = (
  eventType: NotificationPreferenceItem['eventType'],
): NotificationPreferenceItem => ({
  eventType,
  inAppEnabled: true,
  emailEnabled: false,
  teamsEnabled: false,
  telegramEnabled: false,
  digestMode: 'NONE',
  quietHoursEnabled: false,
  quietHoursStart: null,
  quietHoursEnd: null,
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
});

const editablePreference = (
  preference: NotificationPreference,
): NotificationPreferenceItem => ({
  eventType: preference.eventType,
  inAppEnabled: preference.inAppEnabled,
  emailEnabled: preference.emailEnabled,
  teamsEnabled: preference.teamsEnabled,
  telegramEnabled: preference.telegramEnabled,
  digestMode: preference.digestMode,
  quietHoursEnabled: preference.quietHoursEnabled,
  quietHoursStart: preference.quietHoursStart,
  quietHoursEnd: preference.quietHoursEnd,
  timezone: preference.timezone,
});

export function NotificationSettingsPage() {
  const query = useNotificationPreferences();
  const mutations = useNotificationMutations();
  const [items, setItems] = useState<NotificationPreferenceItem[]>([]);
  const { showToast } = useToast();

  useEffect(() => {
    if (!query.data) return;
    const stored = new Map(
      query.data.map((preference) => [
        preference.eventType,
        editablePreference(preference),
      ]),
    );
    setItems(
      notificationEventTypes.map(
        (eventType) => stored.get(eventType) ?? defaultPreference(eventType),
      ),
    );
  }, [query.data]);

  const updateItem = (
    eventType: NotificationPreferenceItem['eventType'],
    patch: Partial<NotificationPreferenceItem>,
  ): void => {
    setItems((current) =>
      current.map((item) =>
        item.eventType === eventType ? { ...item, ...patch } : item,
      ),
    );
  };

  const save = async (): Promise<void> => {
    try {
      await mutations.updatePreferences.mutateAsync({ preferences: items });
      showToast({ tone: 'success', title: 'Notification preferences saved' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Preferences could not be saved',
        message: getApiErrorMessage(error, 'Review quiet hours and timezone.'),
      });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <MasterDataPageHeader
          eyebrow="Settings"
          title="Notification Settings"
          description="Choose channels, digest delivery, timezone, and quiet hours for each event."
        />
        <button
          type="button"
          disabled={!query.data || mutations.updatePreferences.isPending}
          onClick={() => void save()}
          className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-blue-700 px-4 text-xs font-semibold text-white disabled:opacity-50"
        >
          <Save className="size-4" aria-hidden="true" />
          {mutations.updatePreferences.isPending ? 'Saving…' : 'Save Preferences'}
        </button>
      </div>
      {query.isLoading && <Phase8Loading label="Loading notification preferences" />}
      {query.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            query.error,
            'Notification preferences could not be loaded.',
          )}
          onRetry={() => void query.refetch()}
        />
      )}
      {query.data && (
        <>
          <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
            <table className="min-w-[88rem] divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  {[
                    'Event',
                    'In App',
                    'Email',
                    'Teams',
                    'Telegram',
                    'Digest',
                    'Quiet Hours',
                    'Timezone',
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
                {items.map((item) => (
                  <tr key={item.eventType}>
                    <td className="px-4 py-3 text-xs font-semibold text-slate-900">
                      {item.eventType.replaceAll('_', ' ')}
                    </td>
                    <ChannelCell
                      label={`${item.eventType} in app`}
                      checked={item.inAppEnabled}
                      onChange={(value) =>
                        updateItem(item.eventType, { inAppEnabled: value })
                      }
                    />
                    <ChannelCell
                      label={`${item.eventType} email`}
                      checked={item.emailEnabled}
                      onChange={(value) =>
                        updateItem(item.eventType, { emailEnabled: value })
                      }
                    />
                    <ChannelCell
                      label={`${item.eventType} teams`}
                      checked={item.teamsEnabled}
                      onChange={(value) =>
                        updateItem(item.eventType, { teamsEnabled: value })
                      }
                    />
                    <ChannelCell
                      label={`${item.eventType} telegram`}
                      checked={item.telegramEnabled}
                      onChange={(value) =>
                        updateItem(item.eventType, { telegramEnabled: value })
                      }
                    />
                    <td className="px-4 py-3">
                      <select
                        aria-label={`${item.eventType} digest`}
                        value={item.digestMode}
                        onChange={(event) =>
                          updateItem(item.eventType, {
                            digestMode: event.target.value as NotificationDigestMode,
                          })
                        }
                        className="min-h-9 rounded-lg border border-slate-300 bg-white px-2 text-xs"
                      >
                        {['NONE', 'DAILY', 'WEEKLY'].map((mode) => (
                          <option key={mode} value={mode}>
                            {mode}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex min-w-64 items-center gap-2">
                        <input
                          type="checkbox"
                          aria-label={`${item.eventType} quiet hours`}
                          checked={item.quietHoursEnabled}
                          onChange={(event) =>
                            updateItem(item.eventType, {
                              quietHoursEnabled: event.target.checked,
                              quietHoursStart: event.target.checked
                                ? (item.quietHoursStart ?? '22:00')
                                : null,
                              quietHoursEnd: event.target.checked
                                ? (item.quietHoursEnd ?? '07:00')
                                : null,
                            })
                          }
                        />
                        <input
                          type="time"
                          aria-label={`${item.eventType} quiet hours start`}
                          disabled={!item.quietHoursEnabled}
                          value={item.quietHoursStart ?? ''}
                          onChange={(event) =>
                            updateItem(item.eventType, {
                              quietHoursStart: event.target.value || null,
                            })
                          }
                          className="min-h-9 rounded-lg border border-slate-300 px-2 text-xs"
                        />
                        <span className="text-xs text-slate-400">to</span>
                        <input
                          type="time"
                          aria-label={`${item.eventType} quiet hours end`}
                          disabled={!item.quietHoursEnabled}
                          value={item.quietHoursEnd ?? ''}
                          onChange={(event) =>
                            updateItem(item.eventType, {
                              quietHoursEnd: event.target.value || null,
                            })
                          }
                          className="min-h-9 rounded-lg border border-slate-300 px-2 text-xs"
                        />
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <input
                        aria-label={`${item.eventType} timezone`}
                        value={item.timezone}
                        onChange={(event) =>
                          updateItem(item.eventType, {
                            timezone: event.target.value,
                          })
                        }
                        className={`min-w-48 ${phase10InputClass}`}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="rounded-2xl bg-slate-50 p-4 text-xs leading-5 text-slate-600">
            Production channel availability and mandatory system-critical delivery are
            enforced by the authenticated backend.
          </p>
        </>
      )}
    </div>
  );
}

function ChannelCell({
  checked,
  label,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <td className="px-4 py-3">
      <input
        type="checkbox"
        aria-label={label}
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
    </td>
  );
}
