import { Check, Copy } from 'lucide-react';
import { useState } from 'react';

import { useToast } from '../../providers/useToast';

interface DocumentCodeFieldProps {
  code: string;
  label?: string;
  className?: string;
}

export function DocumentCodeField({
  className = '',
  code,
  label = 'Copy document code',
}: DocumentCodeFieldProps) {
  const [copied, setCopied] = useState(false);
  const { showToast } = useToast();

  const copyCode = async (): Promise<void> => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      showToast({ tone: 'success', title: 'Document code copied' });
      window.setTimeout(() => setCopied(false), 1_500);
    } catch {
      showToast({
        tone: 'error',
        title: 'Document code could not be copied',
      });
    }
  };

  return (
    <span className={`inline-flex min-w-0 items-center gap-1.5 ${className}`}>
      <span className="truncate font-mono text-xs font-semibold text-slate-900">
        {code}
      </span>
      <button
        type="button"
        onClick={() => void copyCode()}
        aria-label={label}
        className="grid size-7 shrink-0 place-items-center rounded-lg text-slate-400 transition hover:bg-slate-100 hover:text-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
      >
        {copied ? (
          <Check className="size-3.5 text-emerald-600" aria-hidden="true" />
        ) : (
          <Copy className="size-3.5" aria-hidden="true" />
        )}
      </button>
    </span>
  );
}
