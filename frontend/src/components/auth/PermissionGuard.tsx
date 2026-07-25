import type { ReactNode } from 'react';
import { Navigate } from 'react-router';

import { useAuthStore } from '../../store/authStore';
import type { Permission } from '../../types/auth';

interface PermissionGuardProps {
  permission: Permission;
  children: ReactNode;
  fallback?: ReactNode;
}

export function PermissionGuard({
  permission,
  children,
  fallback,
}: PermissionGuardProps) {
  const hasPermission = useAuthStore((state) => state.hasPermission);

  if (!hasPermission(permission)) {
    return fallback ?? <Navigate to="/unauthorized" replace />;
  }

  return children;
}
