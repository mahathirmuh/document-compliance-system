import { Files } from 'lucide-react';

interface ApplicationMarkProps {
  compact?: boolean;
  tone?: 'dark' | 'light';
}

export function ApplicationMark({
  compact = false,
  tone = 'light',
}: ApplicationMarkProps) {
  const isDark = tone === 'dark';

  return (
    <div className="flex items-center gap-3">
      <div
        className="relative grid size-10 shrink-0 place-items-center overflow-hidden rounded-xl bg-gradient-to-br from-blue-600 to-blue-900 text-white shadow-lg shadow-blue-900/20"
        aria-hidden="true"
      >
        <div className="absolute -right-2 -top-2 size-6 rounded-full bg-cyan-300/20" />
        <Files className="relative size-5" strokeWidth={1.8} />
      </div>
      {!compact && (
        <div className="min-w-0">
          <p
            className={`truncate text-sm font-semibold tracking-tight ${
              isDark ? 'text-white' : 'text-slate-950'
            }`}
          >
            Document Compliance
          </p>
          <p
            className={`truncate text-[11px] font-medium uppercase tracking-[0.16em] ${
              isDark ? 'text-slate-400' : 'text-slate-500'
            }`}
          >
            Multilingual validation
          </p>
        </div>
      )}
    </div>
  );
}
