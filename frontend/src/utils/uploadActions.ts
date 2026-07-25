import type { Permission } from '../types/auth';
import type { UploadProposedAction } from '../types/documentUpload';

export const uploadActionLabels: Record<UploadProposedAction, string> = {
  ATTACH_TO_EXISTING_REVISION: 'Attach to existing revision',
  CREATE_DOCUMENT_AND_REVISION: 'Create document and first revision',
  ADD_NEW_REVISION: 'Add as a new revision',
  REPLACE_CURRENT_FILE: 'Replace current file',
  MANUAL_REVIEW: 'Select metadata manually',
  SKIP: 'Skip file',
};

const actionPermissions: Partial<Record<UploadProposedAction, Permission>> = {
  CREATE_DOCUMENT_AND_REVISION: 'documents:create',
  ADD_NEW_REVISION: 'documents:update',
  REPLACE_CURRENT_FILE: 'documents:replace_file',
};

export const isUploadActionAllowed = (
  action: UploadProposedAction,
  permissions: readonly Permission[],
): boolean => {
  const requiredPermission = actionPermissions[action];
  return !requiredPermission || permissions.includes(requiredPermission);
};
