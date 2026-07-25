import { ChevronLeft, X } from 'lucide-react';
import { NavLink } from 'react-router';

import { ApplicationMark } from '../common/ApplicationMark';
import {
  filterNavigationItems,
  navigationItems,
  type NavigationItem,
} from '../../config/navigation';
import { appConfig } from '../../config/app';
import { useAuthStore } from '../../store/authStore';
import { useUiStore } from '../../store/uiStore';

export function Sidebar() {
  const permissions = useAuthStore((state) => state.permissions);
  const role = useAuthStore((state) => state.user?.role);
  const isCollapsed = useUiStore((state) => state.isSidebarCollapsed);
  const isMobileOpen = useUiStore((state) => state.isMobileSidebarOpen);
  const closeMobile = useUiStore((state) => state.closeMobileSidebar);
  const toggleSidebar = useUiStore((state) => state.toggleSidebar);
  const visibleNavigation = filterNavigationItems(navigationItems, permissions, role);

  return (
    <>
      {isMobileOpen && (
        <button
          type="button"
          aria-label="Close navigation"
          onClick={closeMobile}
          className="fixed inset-0 z-40 bg-slate-950/45 backdrop-blur-sm lg:hidden"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-50 flex flex-col border-r border-white/10 bg-slate-950 text-white shadow-2xl shadow-slate-950/20 transition-[width,transform] duration-300 ${
          isCollapsed ? 'lg:w-20' : 'lg:w-72'
        } w-72 ${
          isMobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
        aria-label="Primary navigation"
      >
        <div className="flex h-20 items-center justify-between border-b border-white/10 px-5">
          <ApplicationMark compact={isCollapsed} tone="dark" />
          <button
            type="button"
            onClick={closeMobile}
            className="grid size-9 place-items-center rounded-xl text-slate-400 transition hover:bg-white/10 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400 lg:hidden"
            aria-label="Close sidebar"
          >
            <X className="size-5" aria-hidden="true" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-6">
          {!isCollapsed && (
            <p className="mb-3 px-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">
              Workspace
            </p>
          )}
          <ul className="space-y-1.5">
            {visibleNavigation.map((item) => (
              <NavigationEntry
                key={item.label}
                item={item}
                isCollapsed={isCollapsed}
                closeMobile={closeMobile}
              />
            ))}
          </ul>
        </nav>

        <div className="border-t border-white/10 p-4">
          {!isCollapsed && (
            <div className="mb-3 rounded-xl bg-white/[0.05] px-3.5 py-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                Application
              </p>
              <p className="mt-1 text-xs font-medium text-slate-300">
                Version {appConfig.version}
              </p>
            </div>
          )}
          <button
            type="button"
            onClick={toggleSidebar}
            className="hidden min-h-10 w-full items-center justify-center gap-2 rounded-xl text-xs font-semibold text-slate-400 transition hover:bg-white/[0.07] hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400 lg:flex"
            aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            <ChevronLeft
              className={`size-4 transition-transform ${
                isCollapsed ? 'rotate-180' : ''
              }`}
              aria-hidden="true"
            />
            {!isCollapsed && <span>Collapse sidebar</span>}
          </button>
        </div>
      </aside>
    </>
  );
}

function NavigationEntry({
  closeMobile,
  isCollapsed,
  item,
}: {
  item: NavigationItem;
  isCollapsed: boolean;
  closeMobile: () => void;
}) {
  const Icon = item.icon;

  return (
    <li>
      {item.path && (
        <NavLink
          to={item.path}
          end={item.path === '/dashboard'}
          title={isCollapsed ? item.label : undefined}
          onClick={closeMobile}
          className={({ isActive }) =>
            `group flex min-h-11 items-center rounded-xl text-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400 ${
              isCollapsed ? 'justify-center px-2' : 'gap-3 px-3.5'
            } ${
              isActive
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-950/30'
                : 'text-slate-400 hover:bg-white/[0.07] hover:text-white'
            }`
          }
        >
          <Icon className="size-[1.15rem] shrink-0" aria-hidden="true" />
          {!isCollapsed && <span>{item.label}</span>}
        </NavLink>
      )}
      {!isCollapsed && item.children && item.children.length > 0 && (
        <ul
          className="ml-5 mt-1.5 space-y-1 border-l border-white/10 pl-3"
          aria-label={`${item.label} navigation`}
        >
          {item.children.map((child) => {
            const ChildIcon = child.icon;
            return (
              <li key={child.label}>
                {child.path && (
                  <NavLink
                    to={child.path}
                    end={child.path === item.path}
                    onClick={closeMobile}
                    className={({ isActive }) =>
                      `flex min-h-9 items-center gap-2.5 rounded-lg px-3 text-xs font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400 ${
                        isActive
                          ? 'bg-white/10 text-white'
                          : 'text-slate-500 hover:bg-white/[0.06] hover:text-slate-200'
                      }`
                    }
                  >
                    <ChildIcon className="size-3.5 shrink-0" aria-hidden="true" />
                    <span>{child.label}</span>
                  </NavLink>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </li>
  );
}
