import type { LucideIcon } from 'lucide-react';
import { X } from 'lucide-react';
import { useState, type ReactNode } from 'react';

const statusTone = (status: string): string => {
  const normalized = status.toUpperCase();
  if (
    [
      'CONNECTED',
      'COMPLETED',
      'DELIVERED',
      'SENT',
      'HEALTHY',
      'ACTIVE',
      'SYNCED',
    ].includes(normalized)
  ) {
    return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
  }
  if (
    [
      'DEGRADED',
      'PARTIALLY_COMPLETED',
      'EXPIRING',
      'RETRYING',
      'RETRY_SCHEDULED',
      'WARNING',
      'CONFLICT',
    ].includes(normalized)
  ) {
    return 'bg-amber-50 text-amber-800 ring-amber-200';
  }
  if (
    [
      'FAILED',
      'UNHEALTHY',
      'AUTHENTICATION_FAILED',
      'PERMISSION_DENIED',
      'RENEWAL_FAILED',
      'CRITICAL',
      'ERROR',
      'DEAD_LETTER',
    ].includes(normalized)
  ) {
    return 'bg-rose-50 text-rose-700 ring-rose-200';
  }
  if (['DISABLED', 'CANCELLED', 'SKIPPED', 'UNKNOWN'].includes(normalized)) {
    return 'bg-slate-100 text-slate-600 ring-slate-200';
  }
  return 'bg-blue-50 text-blue-700 ring-blue-200';
};

export function Phase10StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ring-1 ring-inset ${statusTone(status)}`}
    >
      {status.replaceAll('_', ' ')}
    </span>
  );
}

export function Phase10Cell({
  children,
  strong = false,
}: {
  children: ReactNode;
  strong?: boolean;
}) {
  return (
    <td
      className={`px-4 py-3 text-xs ${strong ? 'font-semibold text-slate-950' : 'text-slate-600'}`}
    >
      {children}
    </td>
  );
}

export function Phase10Action({
  disabled,
  icon: Icon,
  label,
  onClick,
  tone = 'default',
}: {
  label: string;
  icon?: LucideIcon;
  onClick: () => void;
  disabled?: boolean;
  tone?: 'default' | 'danger' | 'primary';
}) {
  const toneClass =
    tone === 'danger'
      ? 'border-rose-200 text-rose-700 hover:bg-rose-50'
      : tone === 'primary'
        ? 'border-blue-200 text-blue-700 hover:bg-blue-50'
        : 'border-slate-200 text-slate-700 hover:bg-slate-50';
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      aria-label={label}
      title={label}
      className={`inline-flex min-h-9 items-center gap-1.5 rounded-lg border px-2.5 text-[11px] font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${toneClass}`}
    >
      {Icon && <Icon className="size-3.5" aria-hidden="true" />}
      {label}
    </button>
  );
}

export function Phase10Empty({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
      {children}
    </p>
  );
}

export function Phase10Dialog({
  children,
  description,
  label,
  onClose,
  open,
  title,
  width = 'max-w-3xl',
}: {
  open: boolean;
  label: string;
  title: string;
  description?: string;
  onClose: () => void;
  children: ReactNode;
  width?: string;
}) {
  if (!open) {
    return null;
  }
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={label}
      className="fixed inset-0 z-50 grid place-items-center overflow-y-auto bg-slate-950/55 p-4"
    >
      <div className={`my-8 w-full ${width} rounded-3xl bg-white shadow-2xl`}>
        <div className="flex items-start justify-between gap-4 border-b border-slate-100 p-6">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
            {description && (
              <p className="mt-1 text-xs leading-5 text-slate-500">{description}</p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid size-9 shrink-0 place-items-center rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50"
            aria-label="Close"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>
        <div className="p-6">{children}</div>
      </div>
    </div>
  );
}

export function ReasonDialog({
  confirmLabel,
  description,
  isPending,
  onClose,
  onConfirm,
  open,
  title,
}: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  isPending: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => Promise<void>;
}) {
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  if (!open) {
    return null;
  }
  return (
    <Phase10Dialog
      open
      label={title}
      title={title}
      description={description}
      onClose={onClose}
      width="max-w-lg"
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (reason.trim().length < 5) {
            setError('Enter an audit reason of at least 5 characters.');
            return;
          }
          setError('');
          void onConfirm(reason.trim());
        }}
      >
        <label className="text-xs font-semibold text-slate-700">
          Audit reason
          <textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            rows={4}
            className="mt-2 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
          />
        </label>
        {error && (
          <p role="alert" className="mt-2 text-xs text-rose-700">
            {error}
          </p>
        )}
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="min-h-10 rounded-xl border border-slate-300 px-4 text-xs font-semibold"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isPending}
            className="min-h-10 rounded-xl bg-blue-700 px-4 text-xs font-semibold text-white disabled:opacity-50"
          >
            {isPending ? 'Working…' : confirmLabel}
          </button>
        </div>
      </form>
    </Phase10Dialog>
  );
}

export const phase10InputClass =
  'min-h-10 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100';

export const phase10TextareaClass =
  'w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100';
