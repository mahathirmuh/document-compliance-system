import { ChevronRight, Home } from 'lucide-react';
import { Link, useLocation } from 'react-router';

import { getRouteBreadcrumbs } from '../../config/routes';

export function Breadcrumb() {
  const { pathname } = useLocation();
  const items = getRouteBreadcrumbs(pathname);

  return (
    <nav aria-label="Breadcrumb">
      <ol className="flex items-center gap-1.5 text-xs text-slate-500">
        <li>
          <Link
            to="/dashboard"
            className="inline-flex items-center gap-1.5 rounded-md transition hover:text-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
          >
            <Home className="size-3.5" aria-hidden="true" />
            Home
          </Link>
        </li>
        {items.map((item, index) => (
          <li key={`${item.label}-${index}`} className="flex items-center gap-1.5">
            <ChevronRight className="size-3.5 text-slate-300" aria-hidden="true" />
            {item.path ? (
              <Link
                to={item.path}
                className="rounded-md transition hover:text-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
              >
                {item.label}
              </Link>
            ) : (
              <span className="font-medium text-slate-700" aria-current="page">
                {item.label}
              </span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
