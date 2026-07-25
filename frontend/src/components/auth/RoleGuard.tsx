import type { ReactNode } from 'react';
import { Navigate } from 'react-router';

import { useAuthStore } from '../../store/authStore';
import type { UserRole } from '../../types/auth';

interface RoleGuardProps {
  roles: readonly UserRole[];
  children: ReactNode;
  fallback?: ReactNode;
}

export function RoleGuard({ roles, children, fallback }: RoleGuardProps) {
  const hasRole = useAuthStore((state) => state.hasRole);

  if (!hasRole(roles)) {
    return fallback ?? <Navigate to="/unauthorized" replace />;
  }

  return children;
}
