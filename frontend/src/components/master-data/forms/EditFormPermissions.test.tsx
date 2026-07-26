import { render, screen, waitFor, within } from '@testing-library/react';
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
  validateDocumentCode: true,
  validateLanguagePresence: true,
  validateLanguageCoverage: true,
  validateContainerCompleteness: false,
  validateTranslationGroups: true,
  validateCells: true,
  requiredLanguages: ['id', 'en', 'zh'],
  sectionAliasProfileId: null,
  sectionAliasProfile: null,
  minimumLanguageBlockCoverage: { id: 95, en: 95, zh: 95 },
  minimumLanguageCharacterCoverage: { id: 95, en: 95, zh: 95 },
  maximumUnknownBlockPercentage: 10,
  maximumMixedBlockPercentage: 20,
  documentCodeWeight: 10,
  languagePresenceWeight: 25,
  languageCoverageWeight: 15,
  sectionCompletenessWeight: 20,
  languageOrderWeight: 10,
  translationGroupWeight: 15,
  tableCompletenessWeight: 5,
  translationSimilarityWeight: 0,
  glossaryComplianceWeight: 0,
  qualityScoreMode: 'SEPARATE_QUALITY_SCORE',
  criticalFindingScoreCap: 69,
  majorFindingPenalty: 5,
  minorFindingPenalty: 1,
  compliantScore: 95,
  partiallyCompliantScore: 70,
  needsReviewScore: 50,
  failOnMissingRequiredLanguage: true,
  failOnMissingRequiredSection: false,
  failOnCriticalFinding: true,
  validationOptions: {},
  minimumComplianceScore: 95,
  partialComplianceScore: 70,
  isDefault: true,
  isActive: true,
};

describe('edit form status permissions', () => {
  it('offers every seeded canonical section and submits approval and distribution', async () => {
    const user = userEvent.setup();
    const submit = vi.fn().mockResolvedValue(undefined);
    render(
      <ValidationRuleForm
        validationRule={null}
        documentTypes={[]}
        isLoadingDocumentTypes={false}
        isPending={false}
        onCancel={vi.fn()}
        onSubmit={submit}
      />,
    );

    const requiredSections = screen.getByRole('group', {
      name: 'Required sections',
    });
    expect(
      within(requiredSections)
        .getAllByRole('checkbox')
        .map((checkbox) => (checkbox as HTMLInputElement).value),
    ).toEqual([
      'TITLE',
      'PURPOSE',
      'SCOPE',
      'DEFINITION',
      'REFERENCE',
      'RESPONSIBILITY',
      'PROCEDURE',
      'RECORDS',
      'ATTACHMENT',
      'REVISION_HISTORY',
      'APPROVAL',
      'DISTRIBUTION',
    ]);

    await user.type(screen.getByLabelText('Code'), 'PHASE8-SECTIONS');
    await user.type(screen.getByLabelText('Name'), 'Phase 8 canonical sections');
    await user.click(
      screen.getByRole('checkbox', { name: 'Validate required sections' }),
    );
    await user.click(
      within(requiredSections).getByRole('checkbox', { name: 'APPROVAL' }),
    );
    await user.click(
      within(requiredSections).getByRole('checkbox', { name: 'DISTRIBUTION' }),
    );
    await user.click(screen.getByRole('button', { name: 'Create validation rule' }));

    await waitFor(() =>
      expect(submit).toHaveBeenCalledWith(
        expect.objectContaining({
          requiredSections: expect.arrayContaining(['APPROVAL', 'DISTRIBUTION']),
        }),
      ),
    );
  });

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
