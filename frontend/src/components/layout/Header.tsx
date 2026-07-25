import {
  ChevronDown,
  LogOut,
  Menu,
  PanelLeft,
  ShieldCheck,
  UserRound,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router';

import { authApi } from '../../api/authApi';
import { getRouteTitle } from '../../config/routes';
import { useAuthStore } from '../../store/authStore';
import { useUiStore } from '../../store/uiStore';
import { formatRole, getInitials } from '../../utils/formatters';

export function Header() {
  const user = useAuthStore((state) => state.user);
  const refreshToken = useAuthStore((state) => state.refreshToken);
  const clearAuth = useAuthStore((state) => state.clearAuth);
  const toggleSidebar = useUiStore((state) => state.toggleSidebar);
  const toggleMobileSidebar = useUiStore((state) => state.toggleMobileSidebar);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const { pathname } = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    const closeOnOutsideClick = (event: MouseEvent): void => {
      if (
        menuRef.current &&
        event.target instanceof Node &&
        !menuRef.current.contains(event.target)
      ) {
        setIsMenuOpen(false);
      }
    };
    const closeOnEscape = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') {
        setIsMenuOpen(false);
      }
    };

    document.addEventListener('mousedown', closeOnOutsideClick);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('mousedown', closeOnOutsideClick);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, []);

  if (!user) {
    return null;
  }

  const logout = async (): Promise<void> => {
    setIsLoggingOut(true);
    clearAuth();
    try {
      if (refreshToken) {
        await authApi.logout(refreshToken);
      }
    } catch {
      // Local cleanup must still complete when the backend is unavailable.
    } finally {
      navigate('/login', { replace: true });
    }
  };

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/90 backdrop-blur-xl">
      <div className="flex h-20 items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <div className="flex min-w-0 items-center gap-3">
          <button
            type="button"
            onClick={toggleMobileSidebar}
            className="grid size-10 shrink-0 place-items-center rounded-xl border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:bg-slate-50 hover:text-slate-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600 lg:hidden"
            aria-label="Open navigation"
          >
            <Menu className="size-5" aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={toggleSidebar}
            className="hidden size-10 shrink-0 place-items-center rounded-xl border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:bg-slate-50 hover:text-slate-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600 lg:grid"
            aria-label="Toggle sidebar"
          >
            <PanelLeft className="size-5" aria-hidden="true" />
          </button>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-slate-950 sm:text-base">
              {getRouteTitle(pathname)}
            </p>
            <p className="mt-0.5 hidden text-xs text-slate-500 sm:block">
              Document Compliance System
            </p>
          </div>
        </div>

        <div className="relative" ref={menuRef}>
          <button
            type="button"
            onClick={() => setIsMenuOpen((open) => !open)}
            className="flex min-h-11 items-center gap-2 rounded-xl border border-slate-200 bg-white p-1.5 pr-2.5 text-left shadow-sm transition hover:border-slate-300 hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600 sm:gap-3 sm:pr-3.5"
            aria-expanded={isMenuOpen}
            aria-haspopup="menu"
          >
            <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-blue-700 text-xs font-bold text-white">
              {getInitials(user.name)}
            </span>
            <span className="hidden min-w-0 sm:block">
              <span className="block max-w-40 truncate text-xs font-semibold text-slate-900">
                {user.name}
              </span>
              <span className="mt-0.5 block text-[10px] font-medium text-slate-500">
                {formatRole(user.role)}
              </span>
            </span>
            <ChevronDown
              className={`size-3.5 text-slate-400 transition-transform ${
                isMenuOpen ? 'rotate-180' : ''
              }`}
              aria-hidden="true"
            />
          </button>

          {isMenuOpen && (
            <div
              className="absolute right-0 mt-2 w-[min(20rem,calc(100vw-2rem))] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl shadow-slate-900/15"
              role="menu"
            >
              <div className="border-b border-slate-100 p-4">
                <div className="flex items-center gap-2 text-xs font-semibold text-slate-500">
                  <UserRound className="size-3.5" aria-hidden="true" />
                  Profile
                </div>
                <p className="mt-3 truncate text-sm font-semibold text-slate-950">
                  {user.name}
                </p>
                <p className="mt-1 truncate text-xs text-slate-500">{user.email}</p>
                <span className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-2.5 py-1 text-[10px] font-semibold text-blue-700">
                  <ShieldCheck className="size-3" aria-hidden="true" />
                  {formatRole(user.role)}
                </span>
              </div>
              <div className="p-2">
                <button
                  type="button"
                  role="menuitem"
                  disabled={isLoggingOut}
                  onClick={() => void logout()}
                  className="flex min-h-10 w-full items-center gap-2.5 rounded-xl px-3 text-sm font-medium text-rose-600 transition hover:bg-rose-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-rose-500 disabled:opacity-60"
                >
                  <LogOut className="size-4" aria-hidden="true" />
                  {isLoggingOut ? 'Signing out...' : 'Sign out'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
