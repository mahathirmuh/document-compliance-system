import { describe, expect, it } from 'vitest';

import { filterNavigationItems, navigationItems } from './navigation';
import type { Permission, UserRole } from '../types/auth';

const labels = (permissions: Permission[], role: UserRole = 'DEPARTMENT_USER') =>
  filterNavigationItems(navigationItems, permissions, role).flatMap((item) => [
    item.label,
    ...(item.children?.map((child) => child.label) ?? []),
  ]);

describe('Phase 10 navigation permissions', () => {
  it('shows department-safe sync menus without exposing configuration', () => {
    const visible = labels([
      'documents:view',
      'sharepoint:view',
      'sharepoint:push',
      'sharepoint:view_history',
      'notifications:view',
      'notifications:update_preferences',
    ]);
    expect(visible).toContain('SharePoint Sync Queue');
    expect(visible).toContain('SharePoint Sync History');
    expect(visible).toContain('Notification Settings');
    expect(visible).not.toContain('Folder Mappings');
    expect(visible).not.toContain('SharePoint Conflicts');
    expect(visible).not.toContain('Administration');
  });

  it('shows conflict review to an auditor but no mutation configuration', () => {
    const visible = labels(
      [
        'sharepoint:view',
        'sharepoint:view_history',
        'sharepoint:view_conflicts',
        'sharepoint:view_all_departments',
      ],
      'AUDITOR',
    );
    expect(visible).toContain('SharePoint Conflicts');
    expect(visible).not.toContain('Sync Profiles');
    expect(visible).not.toContain('Notification Rules');
  });

  it('shows administration modules only to an authorized super admin', () => {
    const visible = labels(
      [
        'sharepoint:view',
        'sharepoint:configure',
        'notifications:manage_templates',
        'notifications:manage_rules',
        'notifications:view_deliveries',
        'system_health:view',
        'background_jobs:manage',
        'retention_policies:manage',
      ],
      'SUPER_ADMIN',
    );
    expect(visible).toEqual(
      expect.arrayContaining([
        'Integrations',
        'Folder Mappings',
        'Metadata Mappings',
        'Sync Profiles',
        'Graph Subscriptions',
        'Administration',
        'Notification Templates',
        'Notification Rules',
        'Notification Deliveries',
        'System Health',
        'Background Jobs',
        'Retention Policies',
      ]),
    );
  });
});
