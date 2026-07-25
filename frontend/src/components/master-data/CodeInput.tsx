import { forwardRef, type InputHTMLAttributes } from 'react';

type CodeInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'maxLength'> & {
  maxLength?: number;
};

export const CodeInput = forwardRef<HTMLInputElement, CodeInputProps>(
  ({ className = '', maxLength = 20, onChange, ...props }, ref) => (
    <input
      {...props}
      ref={ref}
      maxLength={maxLength}
      autoComplete="off"
      spellCheck={false}
      onChange={(event) => {
        event.currentTarget.value = event.currentTarget.value.trimStart().toUpperCase();
        onChange?.(event);
      }}
      className={`min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3.5 text-sm font-semibold uppercase tracking-wide text-slate-950 outline-none transition placeholder:font-normal placeholder:normal-case placeholder:tracking-normal placeholder:text-slate-400 focus:border-blue-600 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-100 ${className}`}
    />
  ),
);

CodeInput.displayName = 'CodeInput';
