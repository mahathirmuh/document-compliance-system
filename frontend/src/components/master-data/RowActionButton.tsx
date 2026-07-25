import type { LucideIcon } from 'lucide-react';

interface RowActionButtonProps {
  icon: LucideIcon;
  label: string;
  onClick: () => void;
  disabled?: boolean;
}

export function RowActionButton({
  disabled = false,
  icon: Icon,
  label,
  onClick,
}: RowActionButtonProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-2.5 text-xs font-semibold text-blue-700 transition hover:bg-blue-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-50"
    >
      <Icon className="size-3.5" aria-hidden="true" />
      {label}
    </button>
  );
}
