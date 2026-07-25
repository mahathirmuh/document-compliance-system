import { X } from 'lucide-react';
import { useEffect, type PropsWithChildren, type ReactNode } from 'react';

interface MasterDataFormDrawerProps extends PropsWithChildren {
  isOpen: boolean;
  title: string;
  description?: string;
  onClose: () => void;
  footer?: ReactNode;
  size?: 'default' | 'wide';
}

export function MasterDataFormDrawer({
  children,
  description,
  footer,
  isOpen,
  onClose,
  size = 'default',
  title,
}: MasterDataFormDrawerProps) {
  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const closeOnEscape = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') {
        onClose();
      }
    };
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [isOpen, onClose]);

  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-[80]" role="dialog" aria-modal="true">
      <button
        type="button"
        aria-label="Close drawer"
        className="absolute inset-0 bg-slate-950/45 backdrop-blur-sm"
        onClick={onClose}
      />
      <section
        className={`absolute inset-y-0 right-0 flex w-full flex-col bg-white shadow-2xl ${
          size === 'wide' ? 'max-w-3xl' : 'max-w-xl'
        }`}
      >
        <header className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-5 sm:px-7">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
            {description && (
              <p className="mt-1 text-sm leading-5 text-slate-500">{description}</p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="grid size-9 shrink-0 place-items-center rounded-xl text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
          >
            <X className="size-5" aria-hidden="true" />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-5 py-6 sm:px-7">{children}</div>
        {footer && (
          <footer className="border-t border-slate-200 bg-slate-50 px-5 py-4 sm:px-7">
            {footer}
          </footer>
        )}
      </section>
    </div>
  );
}
