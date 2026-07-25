import { Outlet } from 'react-router';

import { Breadcrumb } from './Breadcrumb';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { useUiStore } from '../../store/uiStore';

export function AppLayout() {
  const isSidebarCollapsed = useUiStore((state) => state.isSidebarCollapsed);

  return (
    <div className="min-h-screen bg-slate-50">
      <Sidebar />
      <div
        className={`min-h-screen transition-[padding] duration-300 ${
          isSidebarCollapsed ? 'lg:pl-20' : 'lg:pl-72'
        }`}
      >
        <Header />
        <main className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Breadcrumb />
          <div className="mt-5">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
