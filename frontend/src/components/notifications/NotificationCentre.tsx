import {
  Bell,
  CheckCheck,
  CircleAlert,
  Info,
  TriangleAlert,
  X,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router';

import {
  useNotificationMutations,
  useNotifications,
  useNotificationUnreadCount,
} from '../../hooks/useNotifications';
import { useAuthStore } from '../../store/authStore';
import type { InAppNotification, NotificationSeverity } from '../../types/notification';

const safeActionUrl = (value: string | null): string | null =>
  value &&
  value.startsWith('/') &&
  !value.startsWith('//') &&
  !value.includes('\\')
    ? value
    : null;

const relativeTime = (value: string): string => {
  const deltaSeconds = Math.round((new Date(value).getTime() - Date.now()) / 1_000);
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });
  if (Math.abs(deltaSeconds) < 60) return formatter.format(deltaSeconds, 'second');
  const minutes = Math.round(deltaSeconds / 60);
  if (Math.abs(minutes) < 60) return formatter.format(minutes, 'minute');
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) return formatter.format(hours, 'hour');
  return formatter.format(Math.round(hours / 24), 'day');
};

const severityIcon = (severity: NotificationSeverity) => {
  if (severity === 'WARNING') return TriangleAlert;
  if (severity === 'ERROR' || severity === 'CRITICAL') return CircleAlert;
  return Info;
};

export function NotificationCentre() {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const canView = useAuthStore((state) => state.hasPermission('notifications:view'));
  const countQuery = useNotificationUnreadCount(canView);
  const listQuery = useNotifications({ page: 1, pageSize: 10 }, canView && open);
  const mutations = useNotificationMutations();
  const navigate = useNavigate();

  useEffect(() => {
    const close = (event: MouseEvent): void => {
      if (
        open &&
        containerRef.current &&
        event.target instanceof Node &&
        !containerRef.current.contains(event.target)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [open]);

  if (!canView) {
    return null;
  }
  const unread = countQuery.data?.unreadCount ?? 0;

  const openNotification = async (notification: InAppNotification): Promise<void> => {
    if (!notification.isRead) {
      await mutations.markRead.mutateAsync(notification.id);
    }
    const actionUrl = safeActionUrl(notification.actionUrl);
    if (actionUrl) {
      setOpen(false);
      navigate(actionUrl);
    }
  };

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        aria-label={`Notifications${unread ? `, ${unread} unread` : ''}`}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="relative grid size-11 place-items-center rounded-xl border border-slate-200 bg-white text-slate-600 shadow-sm hover:bg-slate-50"
      >
        <Bell className="size-5" aria-hidden="true" />
        {unread > 0 && (
          <span className="absolute -right-1 -top-1 grid min-w-5 place-items-center rounded-full bg-rose-600 px-1 text-[10px] font-bold leading-5 text-white">
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-[min(26rem,calc(100vw-2rem))] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl shadow-slate-900/15">
          <div className="flex items-center justify-between border-b border-slate-100 p-4">
            <div>
              <p className="text-sm font-semibold text-slate-950">Notifications</p>
              <p className="mt-0.5 text-[11px] text-slate-500">
                Refreshed at a safe 45-second interval
              </p>
            </div>
            <button
              type="button"
              disabled={unread === 0 || mutations.markAllRead.isPending}
              onClick={() => void mutations.markAllRead.mutateAsync()}
              className="inline-flex min-h-8 items-center gap-1.5 rounded-lg px-2 text-[11px] font-semibold text-blue-700 disabled:opacity-50"
            >
              <CheckCheck className="size-3.5" aria-hidden="true" />
              Mark all read
            </button>
          </div>
          <div className="max-h-[32rem] overflow-y-auto">
            {listQuery.isLoading && (
              <div
                aria-label="Loading notifications"
                className="h-40 animate-pulse bg-slate-50"
              />
            )}
            {listQuery.error && (
              <p role="alert" className="p-5 text-sm text-rose-700">
                Notifications could not be loaded.
              </p>
            )}
            {listQuery.data?.items.length === 0 && (
              <p className="p-8 text-center text-sm text-slate-500">
                No notifications.
              </p>
            )}
            <ul className="divide-y divide-slate-100">
              {listQuery.data?.items.map((notification) => {
                const Icon = severityIcon(notification.severity);
                return (
                  <li
                    key={notification.id}
                    className={notification.isRead ? 'bg-white' : 'bg-blue-50/50'}
                  >
                    <div className="flex gap-3 p-4">
                      <Icon
                        className={`mt-0.5 size-4 shrink-0 ${
                          notification.severity === 'CRITICAL' ||
                          notification.severity === 'ERROR'
                            ? 'text-rose-600'
                            : notification.severity === 'WARNING'
                              ? 'text-amber-600'
                              : 'text-blue-600'
                        }`}
                        aria-hidden="true"
                      />
                      <button
                        type="button"
                        className="min-w-0 flex-1 text-left"
                        onClick={() => void openNotification(notification)}
                      >
                        <span className="block text-xs font-semibold text-slate-950">
                          {notification.title}
                        </span>
                        <span className="mt-1 line-clamp-2 block text-[11px] leading-4 text-slate-600">
                          {notification.message}
                        </span>
                        <span className="mt-2 block text-[10px] text-slate-400">
                          {relativeTime(notification.createdAt)}
                        </span>
                      </button>
                      <button
                        type="button"
                        aria-label={`Dismiss ${notification.title}`}
                        onClick={() =>
                          void mutations.dismiss.mutateAsync(notification.id)
                        }
                        className="grid size-7 shrink-0 place-items-center rounded-lg text-slate-400 hover:bg-slate-100"
                      >
                        <X className="size-3.5" aria-hidden="true" />
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
          <div className="border-t border-slate-100 p-3 text-center">
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                navigate('/settings/notifications');
              }}
              className="text-xs font-semibold text-blue-700"
            >
              Notification settings
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
