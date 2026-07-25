import { forwardRef, type InputHTMLAttributes } from 'react';

type PercentageInputProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  'min' | 'max' | 'type'
>;

export const PercentageInput = forwardRef<HTMLInputElement, PercentageInputProps>(
  ({ className = '', ...props }, ref) => (
    <div className="relative">
      <input
        {...props}
        ref={ref}
        type="number"
        min={0}
        max={100}
        className={`min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3.5 pr-9 text-sm text-slate-950 outline-none transition focus:border-blue-600 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-100 ${className}`}
      />
      <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-xs font-semibold text-slate-400">
        %
      </span>
    </div>
  ),
);

PercentageInput.displayName = 'PercentageInput';
