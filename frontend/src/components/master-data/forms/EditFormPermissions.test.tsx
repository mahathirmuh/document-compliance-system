import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import type { Department } from '../../../types/department';
import type { ValidationRule } from '../../../types/validationRule';
import { DepartmentForm } from './DepartmentForm';
import { ValidationRuleForm } from './ValidationRuleForm';

const timestamps = {
  createdAt: '2026-07-25T01:00:00Z',
  updatedAt: '2026-07-25T01:00:00Z',
  createdBy: null,
  updatedBy: null,
};

const department: Department = {
  ...timestamps,
  id: '4a1d9d61-4dd2-4056-90f2-97d897e831ec',
  code: 'HRM',
  name: 'Human Resource',
  description: null,
  isActive: true,
};

const validationRule: ValidationRule = {
  ...timestamps,
  id: '80f71846-d42d-4ab6-8f77-71a5af560508',
  code: 'DEFAULT-3LANG',
  name: 'Default Three-Language Validation',
  description: null,
  documentTypeId: null,
  requiredIndonesian: true,
  requiredEnglish: true,
  requiredChinese: true,
  minimumIndonesianCoverage: 95,
  minimumEnglishCoverage: 95,
  minimumChineseCoverage: 95,
  validateLanguageOrder: true,
  languageOrder: ['id', 'en', 'zh'],
  validateSections: false,
  requiredSections: ['TITLE', 'PURPOSE'],
  validateTables: false,
  minimumComplianceScore: 95,
  partialComplianceScore: 70,
  isDefault: true,
  isActive: true,
};

describe('edit form status permissions', () => {
  it('preserves department status so edits cannot bypass the row action', async () => {
    const user = userEvent.setup();
    const submit = vi.fn().mockResolvedValue(undefined);
    render(
      <DepartmentForm
        department={department}
        isPending={false}
        onCancel={vi.fn()}
        onSubmit={submit}
      />,
    );

    const active = screen.getByRole('checkbox', {
      name: /Active and available for selection/i,
    });
    await user.click(active);
    expect(active).toBeChecked();
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() =>
      expect(submit).toHaveBeenCalledWith(expect.objectContaining({ isActive: true })),
    );
  });

  it('preserves default and active flags during Validation Rule edits', async () => {
    const user = userEvent.setup();
    const submit = vi.fn().mockResolvedValue(undefined);
    render(
      <ValidationRuleForm
        validationRule={validationRule}
        documentTypes={[]}
        isLoadingDocumentTypes={false}
        isPending={false}
        onCancel={vi.fn()}
        onSubmit={submit}
      />,
    );

    const defaultRule = screen.getByRole('checkbox', { name: /Default rule/i });
    const active = screen.getByRole('checkbox', {
      name: /^Active \(use the row action/i,
    });
    await user.click(defaultRule);
    await user.click(active);
    expect(defaultRule).toBeChecked();
    expect(active).toBeChecked();
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() =>
      expect(submit).toHaveBeenCalledWith(
        expect.objectContaining({ isDefault: true, isActive: true }),
      ),
    );
  });
});
