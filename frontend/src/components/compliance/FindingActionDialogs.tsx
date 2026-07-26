import { useEffect, useState, type ReactNode } from 'react';

import type {
  FindingAcceptRiskRequest,
  FindingAssignRequest,
  FindingFalsePositiveRequest,
  FindingReopenRequest,
  FindingResolveRequest,
  FindingReturnToOpenRequest,
  FindingReviewRequest,
} from '../../types/finding';

interface BaseDialogProps {
  isOpen: boolean;
  isPending: boolean;
  errorMessage?: string | null;
  onClose: () => void;
}

interface TextActionDialogProps extends BaseDialogProps {
  title: string;
  description: string;
  fieldLabel: string;
  confirmLabel: string;
  tone?: 'primary' | 'danger' | 'warning';
  onSubmit: (value: string) => void;
}

function TextActionDialog({
  confirmLabel,
  description,
  errorMessage,
  fieldLabel,
  isOpen,
  isPending,
  onClose,
  onSubmit,
  title,
  tone = 'primary',
}: TextActionDialogProps) {
  const [value, setValue] = useState('');
  const [validationMessage, setValidationMessage] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setValue('');
      setValidationMessage(null);
    }
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  const submit = (): void => {
    const trimmed = value.trim();
    if (!trimmed) {
      setValidationMessage(`${fieldLabel} is required.`);
      return;
    }
    onSubmit(trimmed);
  };

  const toneClass =
    tone === 'danger'
      ? 'bg-rose-700 hover:bg-rose-800'
      : tone === 'warning'
        ? 'bg-amber-600 hover:bg-amber-700'
        : 'bg-blue-700 hover:bg-blue-800';

  return (
    <DialogShell title={title} description={description} onClose={onClose}>
      <label className="block text-xs font-semibold text-slate-700">
        {fieldLabel}
        <textarea
          autoFocus
          rows={5}
          maxLength={2000}
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
            setValidationMessage(null);
          }}
          className="mt-1.5 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
        />
      </label>
      {(validationMessage || errorMessage) && (
        <p role="alert" className="mt-2 text-xs text-rose-700">
          {validationMessage ?? errorMessage}
        </p>
      )}
      <DialogActions
        confirmLabel={confirmLabel}
        isPending={isPending}
        toneClass={toneClass}
        onClose={onClose}
        onSubmit={submit}
      />
    </DialogShell>
  );
}

export function ReviewFindingDialog({
  onSubmit,
  ...props
}: BaseDialogProps & { onSubmit: (payload: FindingReviewRequest) => void }) {
  return (
    <TextActionDialog
      {...props}
      title="Start finding review"
      description="Record why this finding is being moved to In Review."
      fieldLabel="Review comment"
      confirmLabel="Start Review"
      onSubmit={(comment) => onSubmit({ comment })}
    />
  );
}

export function ResolveFindingDialog({
  onSubmit,
  ...props
}: BaseDialogProps & { onSubmit: (payload: FindingResolveRequest) => void }) {
  return (
    <TextActionDialog
      {...props}
      title="Resolve finding"
      description="Explain the verified corrective action. Resolution does not modify the source file."
      fieldLabel="Resolution comment"
      confirmLabel="Resolve"
      onSubmit={(comment) => onSubmit({ comment })}
    />
  );
}

export function ReturnToOpenFindingDialog({
  onSubmit,
  ...props
}: BaseDialogProps & {
  onSubmit: (payload: FindingReturnToOpenRequest) => void;
}) {
  return (
    <TextActionDialog
      {...props}
      title="Return finding to open"
      description="Record why this reviewed finding needs to return to the Open queue."
      fieldLabel="Return-to-open comment"
      confirmLabel="Return to Open"
      tone="warning"
      onSubmit={(comment) => onSubmit({ comment })}
    />
  );
}

export function FalsePositiveDialog({
  onSubmit,
  ...props
}: BaseDialogProps & {
  onSubmit: (payload: FindingFalsePositiveRequest) => void;
}) {
  return (
    <TextActionDialog
      {...props}
      title="Mark as false positive"
      description="This audited action requires a finding-specific reason."
      fieldLabel="False-positive reason"
      confirmLabel="Mark False Positive"
      tone="warning"
      onSubmit={(reason) => onSubmit({ reason })}
    />
  );
}

export function ReopenFindingDialog({
  onSubmit,
  ...props
}: BaseDialogProps & { onSubmit: (payload: FindingReopenRequest) => void }) {
  return (
    <TextActionDialog
      {...props}
      title="Reopen finding"
      description="Explain why this finding requires renewed attention."
      fieldLabel="Reopen reason"
      confirmLabel="Reopen"
      tone="warning"
      onSubmit={(reason) => onSubmit({ reason })}
    />
  );
}

export function AcceptRiskDialog({
  errorMessage,
  isOpen,
  isPending,
  onClose,
  onSubmit,
}: BaseDialogProps & {
  onSubmit: (payload: FindingAcceptRiskRequest) => void;
}) {
  const [reason, setReason] = useState('');
  const [expiryDate, setExpiryDate] = useState('');
  const [validationMessage, setValidationMessage] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setReason('');
      setExpiryDate('');
      setValidationMessage(null);
    }
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  const submit = (): void => {
    if (!reason.trim() || !expiryDate) {
      setValidationMessage('Risk reason and expiry date are required.');
      return;
    }
    onSubmit({ reason: reason.trim(), expiryDate });
  };

  return (
    <DialogShell
      title="Accept finding risk"
      description="Document the temporary exception and a mandatory expiry date."
      onClose={onClose}
    >
      <label className="block text-xs font-semibold text-slate-700">
        Risk reason
        <textarea
          autoFocus
          rows={4}
          maxLength={2000}
          value={reason}
          onChange={(event) => {
            setReason(event.target.value);
            setValidationMessage(null);
          }}
          className="mt-1.5 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
        />
      </label>
      <label className="mt-4 block text-xs font-semibold text-slate-700">
        Expiry date
        <input
          type="date"
          value={expiryDate}
          onChange={(event) => {
            setExpiryDate(event.target.value);
            setValidationMessage(null);
          }}
          className="mt-1.5 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
        />
      </label>
      {(validationMessage || errorMessage) && (
        <p role="alert" className="mt-2 text-xs text-rose-700">
          {validationMessage ?? errorMessage}
        </p>
      )}
      <DialogActions
        confirmLabel="Accept Risk"
        isPending={isPending}
        toneClass="bg-amber-600 hover:bg-amber-700"
        onClose={onClose}
        onSubmit={submit}
      />
    </DialogShell>
  );
}

export function AssignFindingDialog({
  errorMessage,
  isOpen,
  isPending,
  onClose,
  onSubmit,
}: BaseDialogProps & {
  onSubmit: (payload: FindingAssignRequest) => void;
}) {
  const [assignedTo, setAssignedTo] = useState('');
  const [validationMessage, setValidationMessage] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setAssignedTo('');
      setValidationMessage(null);
    }
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  const submit = (): void => {
    if (!assignedTo.trim()) {
      setValidationMessage('Assignee is required.');
      return;
    }
    onSubmit({ assignedTo: assignedTo.trim() });
  };

  return (
    <DialogShell
      title="Assign finding"
      description="Enter the user identifier supplied by your organization."
      onClose={onClose}
    >
      <label className="block text-xs font-semibold text-slate-700">
        Assignee user ID
        <input
          autoFocus
          value={assignedTo}
          onChange={(event) => {
            setAssignedTo(event.target.value);
            setValidationMessage(null);
          }}
          className="mt-1.5 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
        />
      </label>
      {(validationMessage || errorMessage) && (
        <p role="alert" className="mt-2 text-xs text-rose-700">
          {validationMessage ?? errorMessage}
        </p>
      )}
      <DialogActions
        confirmLabel="Assign"
        isPending={isPending}
        toneClass="bg-blue-700 hover:bg-blue-800"
        onClose={onClose}
        onSubmit={submit}
      />
    </DialogShell>
  );
}

function DialogShell({
  children,
  description,
  onClose,
  title,
}: {
  title: string;
  description: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <div
      className="fixed inset-0 z-[100] grid place-items-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="finding-action-title"
    >
      <button
        type="button"
        aria-label="Close finding action"
        onClick={onClose}
        className="absolute inset-0 bg-slate-950/50 backdrop-blur-sm"
      />
      <div className="relative w-full max-w-lg rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl">
        <h2 id="finding-action-title" className="text-lg font-semibold text-slate-950">
          {title}
        </h2>
        <p className="mt-1 text-sm leading-6 text-slate-600">{description}</p>
        <div className="mt-5">{children}</div>
      </div>
    </div>
  );
}

function DialogActions({
  confirmLabel,
  isPending,
  onClose,
  onSubmit,
  toneClass,
}: {
  confirmLabel: string;
  isPending: boolean;
  toneClass: string;
  onClose: () => void;
  onSubmit: () => void;
}) {
  return (
    <div className="mt-6 flex justify-end gap-3">
      <button
        type="button"
        onClick={onClose}
        disabled={isPending}
        className="min-h-10 rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700 disabled:opacity-50"
      >
        Cancel
      </button>
      <button
        type="button"
        onClick={onSubmit}
        disabled={isPending}
        className={`min-h-10 rounded-xl px-4 text-sm font-semibold text-white disabled:opacity-50 ${toneClass}`}
      >
        {isPending ? 'Working…' : confirmLabel}
      </button>
    </div>
  );
}
