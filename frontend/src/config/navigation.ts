import {
  Archive,
  Building2,
  Database,
  FileClock,
  FileSearch,
  FilePlus2,
  FileUp,
  Files,
  FileType2,
  Layers3,
  LayoutDashboard,
  Languages,
  ShieldCheck,
  Workflow,
  PackageOpen,
  ScanSearch,
  BarChart3,
  type LucideIcon,
} from 'lucide-react';

import type { Permission, UserRole } from '../types/auth';

export interface NavigationItem {
  label: string;
  path?: string;
  icon: LucideIcon;
  permission?: Permission;
  anyPermissions?: readonly Permission[];
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
    anyPermissions: ['documents:view', 'similarity:view', 'revision_comparison:view'],
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
        label: 'Extraction Queue',
        path: '/documents/extraction-queue',
        icon: ScanSearch,
        permission: 'documents:extract',
      },
      {
        label: 'OCR Queue',
        path: '/documents/ocr-queue',
        icon: ScanSearch,
        permission: 'documents:ocr',
      },
      {
        label: 'Language Detection',
        path: '/documents/language-detection',
        icon: Languages,
        permission: 'documents:view_language_results',
      },
      {
        label: 'Validation Queue',
        path: '/documents/validation-queue',
        icon: ShieldCheck,
        permission: 'compliance:view',
      },
      {
        label: 'Similarity Queue',
        path: '/documents/similarity-queue',
        icon: Languages,
        permission: 'similarity:view',
      },
      {
        label: 'Revision Comparison',
        path: '/documents/revision-comparison',
        icon: Workflow,
        permission: 'revision_comparison:view',
      },
      {
        label: 'Extraction History',
        path: '/documents/extraction-history',
        icon: FileSearch,
        permission: 'documents:view_extraction_history',
      },
      {
        label: 'OCR History',
        path: '/documents/ocr-history',
        icon: FileSearch,
        permission: 'documents:view_ocr_history',
      },
      {
        label: 'Validation History',
        path: '/documents/validation-history',
        icon: FileClock,
        permission: 'compliance:view',
      },
      {
        label: 'Similarity History',
        path: '/documents/similarity-history',
        icon: FileClock,
        permission: 'similarity:view',
      },
      {
        label: 'Archived Documents',
        path: '/documents/archived',
        icon: Archive,
        permission: 'documents:view',
      },
      {
        label: 'Upload History',
        path: '/documents/upload-history',
        icon: FileClock,
        permission: 'documents:view_file_history',
      },
    ],
  },
  {
    label: 'Master Data',
    path: '/master-data',
    icon: Database,
    permission: 'master_data:view',
    anyPermissions: ['master_data:view', 'glossary:view'],
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
      {
        label: 'Section Definitions',
        path: '/master-data/section-definitions',
        icon: Layers3,
        permission: 'master_data:view',
      },
      {
        label: 'Glossary',
        path: '/master-data/glossary',
        icon: Languages,
        permission: 'glossary:view',
      },
    ],
  },
  {
    label: 'Compliance',
    path: '/compliance',
    icon: ShieldCheck,
    permission: 'compliance:view',
    anyPermissions: ['compliance:view', 'similarity:view', 'glossary:view'],
    children: [
      {
        label: 'Compliance Overview',
        path: '/compliance',
        icon: LayoutDashboard,
        permission: 'compliance:view',
      },
      {
        label: 'Language Compliance',
        path: '/compliance/languages',
        icon: Languages,
        permission: 'compliance:view',
      },
      {
        label: 'Translation Similarity',
        path: '/compliance/translation-similarity',
        icon: Languages,
        permission: 'similarity:view',
      },
      {
        label: 'Section Compliance',
        path: '/compliance/sections',
        icon: Layers3,
        permission: 'compliance:view',
      },
      {
        label: 'Language Order',
        path: '/compliance/language-order',
        icon: Workflow,
        permission: 'compliance:view',
      },
      {
        label: 'Glossary Compliance',
        path: '/compliance/glossary',
        icon: ShieldCheck,
        permission: 'glossary:view',
      },
      {
        label: 'Findings',
        path: '/compliance/findings',
        icon: FileSearch,
        permission: 'findings:view',
      },
      {
        label: 'Review Findings',
        path: '/compliance/findings/review',
        icon: ShieldCheck,
        permission: 'findings:review',
      },
    ],
  },
  {
    label: 'Reports',
    path: '/reports/compliance',
    icon: BarChart3,
    permission: 'reports:view',
    anyPermissions: ['reports:view', 'advanced_reports:view'],
    children: [
      {
        label: 'Compliance Report',
        path: '/reports/compliance',
        icon: BarChart3,
        permission: 'reports:view',
      },
      {
        label: 'Findings Report',
        path: '/reports/findings',
        icon: FileSearch,
        permission: 'reports:view',
      },
      {
        label: 'Translation Similarity',
        path: '/reports/translation-similarity',
        icon: Languages,
        permission: 'advanced_reports:view',
      },
      {
        label: 'Glossary Compliance',
        path: '/reports/glossary-compliance',
        icon: ShieldCheck,
        permission: 'advanced_reports:view',
      },
      {
        label: 'Revision Changes',
        path: '/reports/revision-changes',
        icon: Workflow,
        permission: 'advanced_reports:view',
      },
      {
        label: 'Advanced Analytics',
        path: '/reports/advanced-analytics',
        icon: BarChart3,
        permission: 'advanced_reports:view',
      },
      {
        label: 'Report Snapshots',
        path: '/reports/snapshots',
        icon: FileClock,
        permission: 'advanced_reports:view',
      },
      {
        label: 'Report Schedules',
        path: '/reports/schedules',
        icon: FileClock,
        permission: 'advanced_reports:configure',
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
      (item.permission === undefined &&
        (item.anyPermissions === undefined ||
          item.anyPermissions.some((permission) =>
            grantedPermissions.includes(permission),
          ))) ||
      (item.permission !== undefined &&
        (grantedPermissions.includes(item.permission) ||
          item.anyPermissions?.some((permission) =>
            grantedPermissions.includes(permission),
          ) === true));
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
        ...(item.permission !== undefined &&
        !grantedPermissions.includes(item.permission) &&
        children?.[0]?.path
          ? { path: children[0].path }
          : {}),
        ...(children === undefined ? {} : { children }),
      },
    ];
  });
