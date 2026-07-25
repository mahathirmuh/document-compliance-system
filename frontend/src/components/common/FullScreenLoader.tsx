import { LoaderCircle } from 'lucide-react';

import { ApplicationMark } from './ApplicationMark';

interface FullScreenLoaderProps {
  message?: string;
}

export function FullScreenLoader({
  message = 'Preparing your workspace...',
}: FullScreenLoaderProps) {
  return (
    <div
      className="grid min-h-screen place-items-center bg-slate-50 px-6"
      role="status"
      aria-live="polite"
    >
      <div className="flex flex-col items-center text-center">
        <ApplicationMark />
        <LoaderCircle
          className="mt-8 size-6 animate-spin text-blue-600"
          aria-hidden="true"
        />
        <p className="mt-3 text-sm font-medium text-slate-600">{message}</p>
      </div>
    </div>
  );
}
