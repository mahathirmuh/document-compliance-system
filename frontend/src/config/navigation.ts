import {
  Archive,
  Building2,
  Database,
  FileClock,
  FilePlus2,
  FileUp,
  Files,
  FileType2,
  Layers3,
  LayoutDashboard,
  ShieldCheck,
  Workflow,
  PackageOpen,
  type LucideIcon,
} from 'lucide-react';

import type { Permission, UserRole } from '../types/auth';

export interface NavigationItem {
  label: string;
  path?: string;
  icon: LucideIcon;
  permission?: Permission;
  roles?: readonly UserRole[];
  children?: readonly NavigationItem[];
}

export const navigationItems: readonly NavigationItem[] = [
  {
    label: 'Dashboard',
    path: '/dashboard',
    icon: LayoutDashboard,
    permission: 'dashboard:view',
  },
  {
    label: 'Documents',
    path: '/documents',
    icon: Files,
    permission: 'documents:view',
    children: [
      {
        label: 'Document Register',
        path: '/documents',
        icon: Files,
        permission: 'documents:view',
      },
      {
        label: 'Add Document',
        path: '/documents/new',
        icon: FilePlus2,
        permission: 'documents:create',
      },
      {
        label: 'Upload Document',
        path: '/documents/upload',
        icon: FileUp,
        permission: 'documents:upload',
      },
      {
        label: 'Batch Upload',
        path: '/documents/batch-upload',
        icon: PackageOpen,
        permission: 'documents:batch_upload',
      },
      {
        label: 'Upload History',
        path: '/documents/upload-history',
        icon: FileClock,
        permission: 'documents:view_file_history',
      },
      {
        label: 'Archived Documents',
        path: '/documents/archived',
        icon: Archive,
        permission: 'documents:view',
      },
    ],
  },
  {
    label: 'Master Data',
    path: '/master-data',
    icon: Database,
    permission: 'master_data:view',
    children: [
      {
        label: 'Overview',
        path: '/master-data',
        icon: Database,
        permission: 'master_data:view',
      },
      {
        label: 'Departments',
        path: '/master-data/departments',
        icon: Building2,
        permission: 'master_data:view',
      },
      {
        label: 'Sections',
        path: '/master-data/sections',
        icon: Layers3,
        permission: 'master_data:view',
      },
      {
        label: 'Document Types',
        path: '/master-data/document-types',
        icon: FileType2,
        permission: 'master_data:view',
      },
      {
        label: 'Document Statuses',
        path: '/master-data/document-statuses',
        icon: Workflow,
        permission: 'master_data:view',
      },
      {
        label: 'Validation Rules',
        path: '/master-data/validation-rules',
        icon: ShieldCheck,
        permission: 'master_data:view',
      },
    ],
  },
];

export const filterNavigationItems = (
  items: readonly NavigationItem[],
  grantedPermissions: readonly Permission[],
  role: UserRole | undefined,
): NavigationItem[] =>
  items.flatMap((item) => {
    const hasPermission =
      item.permission === undefined || grantedPermissions.includes(item.permission);
    const hasRole =
      item.roles === undefined || (role !== undefined && item.roles.includes(role));

    if (!hasPermission || !hasRole) {
      return [];
    }

    const children = item.children
      ? filterNavigationItems(item.children, grantedPermissions, role)
      : undefined;

    return [
      {
        ...item,
        ...(children === undefined ? {} : { children }),
      },
    ];
  });
