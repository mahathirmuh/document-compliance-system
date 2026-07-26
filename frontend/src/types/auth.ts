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
  'documents:upload',
  'documents:download',
  'documents:replace_file',
  'documents:delete_file',
  'documents:batch_upload',
  'documents:view_file_history',
  'documents:extract',
  'documents:reextract',
  'documents:view_extracted_content',
  'documents:export_extracted_content',
  'documents:view_extraction_history',
  'documents:cancel_extraction',
  'documents:ocr',
  'documents:reocr',
  'documents:view_ocr_results',
  'documents:view_ocr_history',
  'documents:cancel_ocr',
  'documents:detect_language',
  'documents:redetect_language',
  'documents:view_language_results',
  'documents:export_language_results',
  'documents:review_language_result',
  'documents:validate',
  'documents:assign_reviewer',
  'compliance:view',
  'compliance:validate',
  'compliance:revalidate',
  'compliance:view_all_departments',
  'compliance:export',
  'compliance:configure_rules',
  'findings:view',
  'findings:create_manual',
  'findings:update',
  'findings:review',
  'findings:resolve',
  'findings:reopen',
  'findings:false_positive',
  'findings:export',
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
  code?: string;
}

export interface ApiResponse<TData> {
  success: boolean;
  message: string;
  data: TData;
  errors: ApiErrorDetail[] | null;
}
