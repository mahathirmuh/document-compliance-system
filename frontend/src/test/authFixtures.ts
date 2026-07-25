import type { AuthSession } from '../types/auth';

export const superAdminSession: AuthSession = {
  accessToken: 'test-access-token',
  refreshToken: 'test-refresh-token',
  tokenType: 'bearer',
  expiresIn: 900,
  user: {
    id: '69e87427-d98e-4a62-b787-b1c07362b11e',
    name: 'System Administrator',
    email: 'admin@example.com',
    role: 'SUPER_ADMIN',
    departmentId: null,
    isActive: true,
  },
  permissions: [
    'dashboard:view',
    'documents:view',
    'documents:create',
    'documents:update',
    'documents:archive',
    'documents:restore',
    'documents:export',
    'documents:import',
    'documents:view_all_departments',
    'documents:manage_revisions',
    'master_data:view',
    'master_data:create',
    'master_data:update',
    'master_data:delete',
    'users:view',
    'settings:view',
  ],
};
