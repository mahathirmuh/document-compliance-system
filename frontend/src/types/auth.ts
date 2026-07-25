export const userRoles = [
  'SUPER_ADMIN',
  'DOCUMENT_CONTROLLER',
  'REVIEWER',
  'DEPARTMENT_USER',
  'AUDITOR',
  'VIEWER',
] as const;

export type UserRole = (typeof userRoles)[number];

export const permissions = [
  'dashboard:view',
  'documents:view',
  'documents:create',
  'documents:update',
  'documents:delete',
  'documents:archive',
  'documents:restore',
  'documents:export',
  'documents:import',
  'documents:view_all_departments',
  'documents:manage_revisions',
  'documents:validate',
  'documents:assign_reviewer',
  'findings:view',
  'findings:update',
  'findings:resolve',
  'master_data:view',
  'master_data:create',
  'master_data:update',
  'master_data:delete',
  'reports:view',
  'reports:export',
  'users:view',
  'users:create',
  'users:update',
  'users:disable',
  'audit_logs:view',
  'settings:view',
  'settings:update',
] as const;

export type Permission = (typeof permissions)[number];

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  departmentId: string | null;
  isActive: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface AuthSession {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  expiresIn: number;
  user: AuthUser;
  permissions: Permission[];
}

export type LoginResponse = AuthSession;

export interface RefreshTokenResponse {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  expiresIn: number;
  user?: AuthUser;
  permissions?: Permission[];
}

export interface CurrentUserResponse {
  user: AuthUser;
  permissions: Permission[];
}

export interface ApiErrorDetail {
  field: string | null;
  message: string;
}

export interface ApiResponse<TData> {
  success: boolean;
  message: string;
  data: TData;
  errors: ApiErrorDetail[] | null;
}
