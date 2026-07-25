import { Power } from 'lucide-react';

interface EntityStatusToggleProps {
  isActive: boolean;
  disabled?: boolean;
  onClick: () => void;
}

export function EntityStatusToggle({
  disabled = false,
  isActive,
  onClick,
}: EntityStatusToggleProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`inline-flex min-h-9 items-center gap-1.5 rounded-lg px-2.5 text-xs font-semibold transition focus-visible:outline focus-visible:outline-2 disabled:cursor-not-allowed disabled:opacity-50 ${
        isActive
          ? 'text-rose-700 hover:bg-rose-50 focus-visible:outline-rose-600'
          : 'text-emerald-700 hover:bg-emerald-50 focus-visible:outline-emerald-600'
      }`}
    >
      <Power className="size-3.5" aria-hidden="true" />
      {isActive ? 'Deactivate' : 'Activate'}
    </button>
  );
}
