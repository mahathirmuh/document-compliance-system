import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { filterNavigationItems, navigationItems } from '../config/navigation';
import { useAuthStore } from '../store/authStore';
import { superAdminSession } from '../test/authFixtures';
import type { GlossaryImportPreview, GlossaryProfile } from '../types/glossary';
import type { RevisionChange } from '../types/revisionComparison';
import type { TranslationSimilarityResult } from '../types/similarity';
import { GlossaryProfileDialog, GlossaryTermDialog } from './glossary/GlossaryForms';
import { GlossaryImportPanel } from './glossary/GlossaryImportPanel';
import { GlossaryMatchTester } from './glossary/GlossaryMatchTester';
import { AdvancedReportBuilder } from './reports/AdvancedReportBuilder';
import { RevisionDiff } from './revision-comparison/RevisionDiff';
import { SimilarityDetailDialog } from './similarity/SimilarityDetailDialog';

vi.mock('../hooks/useDocumentFormOptions', () => ({
  useDocumentFormOptions: () => ({
    data: {
      departments: [
        {
          id: 'department-id',
          code: 'HRM',
          name: 'Human Resources',
        },
      ],
      documentTypes: [{ id: 'document-type-id', code: 'SOP', name: 'Procedure' }],
      validationRules: [{ id: 'rule-id', code: 'TRILINGUAL', name: 'Trilingual Rule' }],
    },
  }),
}));

vi.mock('../hooks/useGlossary', () => ({
  useGlossaryProfiles: () => ({
    data: {
      items: [
        {
          id: 'profile-id',
          code: 'HSE',
          name: 'Health and Safety',
        },
      ],
    },
  }),
}));

const timestamp = '2026-07-26T01:00:00Z';

const similarityResult: TranslationSimilarityResult = {
  id: 'result-id',
  similarityRunId: 'run-id',
  translationGroupId: 'group-id',
  detectedSectionId: 'section-id',
  containerId: 'body',
  sourceReference: 'DOCX:body:p=4',
  sourceLanguageCode: 'id',
  targetLanguageCode: 'en',
  sourceMemberId: 'member-id',
  targetMemberId: 'member-en',
  sourceTextHash: 'a'.repeat(64),
  targetTextHash: 'b'.repeat(64),
  sourceTextSnippet: 'Peralatan pelindung wajib digunakan.',
  targetTextSnippet: 'Protective equipment may be used.',
  similarityScore: 0.41,
  similarityCategory: 'LOW',
  confidence: 0.88,
  structuralGroupConfidence: 0.92,
  ocrConfidence: null,
  analysisStatus: 'COMPLETED',
  sourceCharacterCount: 38,
  targetCharacterCount: 33,
  lengthRatio: 0.87,
  numberConsistencyStatus: 'MATCH',
  dateConsistencyStatus: 'NOT_APPLICABLE',
  measurementConsistencyStatus: 'NOT_APPLICABLE',
  referenceConsistencyStatus: 'MATCH',
  negationConsistencyStatus: 'POSSIBLE_NEGATION_MISMATCH',
  numberDetails: { source: ['1'], target: ['1'] },
  dateDetails: {},
  measurementDetails: {},
  referenceDetails: {},
  negationDetails: { source: ['wajib'], target: ['may'] },
  chunkCountSource: 1,
  chunkCountTarget: 1,
  findingCount: 2,
  relatedFindingIds: ['finding-1', 'finding-2'],
  metrics: {},
  warnings: [],
  createdAt: timestamp,
};

const revisionChange: RevisionChange = {
  id: 'change-id',
  revisionComparisonId: 'comparison-id',
  changeType: 'MODIFIED',
  entityType: 'PARAGRAPH',
  baseContainerId: 'body',
  targetContainerId: 'body',
  baseSectionId: 'section-id',
  targetSectionId: 'section-id',
  baseTranslationGroupId: 'group-id',
  targetTranslationGroupId: 'group-id',
  baseBlockId: 'block-1',
  targetBlockId: 'block-2',
  sectionName: 'Safety',
  languageCode: 'en',
  sourceReferenceBase: 'DOCX:body:p=4',
  sourceReferenceTarget: 'DOCX:body:p=5',
  baseTextSnapshot:
    '<img src=x onerror=alert(1)> Protective equipment is recommended. '.repeat(12),
  targetTextSnapshot:
    '<script>alert(1)</script> Protective equipment is mandatory. '.repeat(12),
  textSimilarity: 0.76,
  structuralSimilarity: 0.95,
  alignmentConfidence: 0.91,
  characterChangeCount: 34,
  wordChangeCount: 4,
  metadata: {},
  createdAt: timestamp,
};

const profile: GlossaryProfile = {
  id: 'profile-id',
  code: 'HSE',
  name: 'Health and Safety',
  description: null,
  scopeType: 'GLOBAL',
  departmentId: null,
  documentTypeId: null,
  isDefault: true,
  isActive: true,
  version: 1,
  termCount: 1,
  createdBy: 'user-id',
  updatedBy: 'user-id',
  createdAt: timestamp,
  updatedAt: timestamp,
};

describe('Phase 9 reusable components', () => {
  beforeEach(() => {
    useAuthStore.getState().setAuth(superAdminSession);
  });

  it('renders low similarity, consistency evidence, bounded text, and disclaimer', () => {
    render(
      <MemoryRouter>
        <SimilarityDetailDialog
          open
          result={similarityResult}
          documentId="document-id"
          revisionId="revision-id"
          onClose={vi.fn()}
        />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole('dialog', { name: 'Indonesian ↔ English' }),
    ).toBeInTheDocument();
    expect(screen.getByText('LOW')).toBeInTheDocument();
    expect(screen.getByText('41.0%')).toBeInTheDocument();
    expect(
      screen.getByText('Peralatan pelindung wajib digunakan.'),
    ).toBeInTheDocument();
    expect(
      screen.getByTitle(/Negation signals: POSSIBLE NEGATION MISMATCH/),
    ).toHaveTextContent('CHECK');
    expect(screen.getByText('finding-1, finding-2')).toBeInTheDocument();
    expect(
      screen.getByText(/does not guarantee that both texts have identical/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /Open extracted content/ }),
    ).toHaveAttribute(
      'href',
      '/documents/document-id/revisions/revision-id/extracted-content',
    );
  });

  it('renders a side-by-side bounded diff without interpreting raw HTML', async () => {
    const { container } = render(<RevisionDiff change={revisionChange} />);

    expect(screen.getByText('Base Revision')).toBeInTheDocument();
    expect(screen.getByText('Target Revision')).toBeInTheDocument();
    expect(screen.getByText('MODIFIED')).toBeInTheDocument();
    expect(container.querySelector('img')).toBeNull();
    expect(container.querySelector('script')).toBeNull();
    expect(
      screen.getByRole('button', { name: 'Open full bounded detail' }),
    ).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole('button', { name: 'Open full bounded detail' }),
    );
    expect(screen.getByRole('button', { name: 'Collapse detail' })).toBeInTheDocument();
    expect(container.querySelector('script')).toBeNull();
  });

  it('confirms only the workbook that was previewed and preserves UPSERT mode', async () => {
    const preview: GlossaryImportPreview = {
      valid: true,
      totalRows: 1,
      validRows: 1,
      invalidRows: 0,
      sheets: [
        {
          sheet: 'Terms',
          totalRows: 1,
          validRows: 1,
          invalidRows: 0,
        },
      ],
      issues: [],
      preview: {},
      warnings: [],
    };
    const onPreview = vi.fn().mockResolvedValue(undefined);
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    const file = new File(['workbook'], 'glossary.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
    render(
      <GlossaryImportPanel
        preview={preview}
        previewPending={false}
        confirmPending={false}
        onPreview={onPreview}
        onConfirm={onConfirm}
        onDownloadTemplate={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    const confirm = screen.getByRole('button', { name: 'Confirm Import' });
    expect(confirm).toBeDisabled();
    await userEvent.upload(screen.getByLabelText('Import workbook'), file);
    await userEvent.click(screen.getByRole('button', { name: 'Preview Import' }));
    await waitFor(() => expect(onPreview).toHaveBeenCalledWith(file));
    await waitFor(() => expect(confirm).toBeEnabled());
    await userEvent.selectOptions(screen.getByLabelText('Import mode'), 'UPSERT');
    await userEvent.click(confirm);
    expect(onConfirm).toHaveBeenCalledWith(file, 'UPSERT');
  });

  it('creates a scoped glossary profile with normalized values', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <GlossaryProfileDialog
        open
        profile={null}
        isPending={false}
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    await userEvent.type(screen.getByLabelText('Profile Code'), ' hse ');
    await userEvent.type(screen.getByLabelText('Profile Name'), 'Health and Safety');
    await userEvent.selectOptions(screen.getByLabelText('Scope Type'), 'DEPARTMENT');
    await userEvent.type(screen.getByLabelText('Department ID'), 'department-id');
    await userEvent.click(screen.getByRole('button', { name: 'Create Profile' }));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        code: 'HSE',
        name: 'Health and Safety',
        scopeType: 'DEPARTMENT',
        departmentId: 'department-id',
        documentTypeId: null,
      }),
    );
  });

  it('creates multilingual translations and a variant in one term submission', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <GlossaryTermDialog
        open
        term={null}
        profiles={[profile]}
        isPending={false}
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    await userEvent.type(screen.getByLabelText('Term Code'), 'apd');
    await userEvent.type(screen.getByLabelText('Concept Name'), 'Alat Pelindung Diri');
    const termInputs = screen.getAllByLabelText('Term Text');
    await userEvent.type(termInputs[0]!, 'alat pelindung diri');
    await userEvent.type(termInputs[1]!, 'personal protective equipment');
    await userEvent.type(termInputs[2]!, '个人防护装备');
    await userEvent.type(screen.getByLabelText('Variant'), 'APD');
    await userEvent.click(screen.getByRole('button', { name: 'Create Term' }));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        term: expect.objectContaining({
          glossaryProfileId: 'profile-id',
          termCode: 'APD',
        }),
        translations: expect.objectContaining({
          id: expect.objectContaining({
            termText: 'alat pelindung diri',
            isPreferred: true,
          }),
          en: expect.objectContaining({
            termText: 'personal protective equipment',
          }),
          zh: expect.objectContaining({ termText: '个人防护装备' }),
        }),
        variant: {
          languageCode: 'id',
          payload: expect.objectContaining({
            variantText: 'APD',
            variantType: 'SYNONYM',
          }),
        },
      }),
    );
  });

  it('blocks contradictory preferred and forbidden translations', async () => {
    render(
      <GlossaryTermDialog
        open
        term={null}
        profiles={[profile]}
        isPending={false}
        onClose={vi.fn()}
        onSubmit={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    await userEvent.type(screen.getByLabelText('Term Code'), 'apd');
    await userEvent.type(screen.getByLabelText('Concept Name'), 'Protection');
    await userEvent.type(
      screen.getAllByLabelText('Term Text')[0]!,
      'alat pelindung diri',
    );
    await userEvent.click(screen.getAllByLabelText('Forbidden')[0]!);

    expect(screen.getByRole('alert')).toHaveTextContent(
      'cannot be both preferred and forbidden',
    );
    expect(screen.getByRole('button', { name: 'Create Term' })).toBeDisabled();
  });

  it('submits glossary test text and exposes an applied exception type', async () => {
    const onTest = vi.fn().mockResolvedValue(undefined);
    render(
      <GlossaryMatchTester
        profiles={[profile]}
        isPending={false}
        onTest={onTest}
        results={[
          {
            glossaryTermId: 'term-id',
            glossaryTranslationId: 'translation-id',
            glossaryVariantId: null,
            termCode: 'APD',
            conceptName: 'Alat Pelindung Diri',
            languageCode: 'id',
            matchedText: 'APD',
            normalisedMatchedText: 'apd',
            matchType: 'EXACT',
            isPreferred: true,
            isForbidden: false,
            isAllowedVariant: false,
            startOffset: 0,
            endOffset: 3,
            exceptionApplied: true,
            exceptionId: 'exception-id',
            exceptionType: 'IGNORE_TERM',
          },
        ]}
      />,
    );

    await userEvent.type(screen.getByLabelText('Text'), 'APD wajib digunakan.');
    await userEvent.click(screen.getByRole('button', { name: 'Test Match' }));
    expect(onTest).toHaveBeenCalledWith({
      text: 'APD wajib digunakan.',
      languageCode: 'id',
      profileIds: ['profile-id'],
    });
    expect(screen.getByText('IGNORE TERM')).toBeInTheDocument();
  });

  it('locks a department user report scope and generates one selected format', async () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      user: {
        ...superAdminSession.user,
        role: 'DEPARTMENT_USER',
        departmentId: 'department-id',
      },
      permissions: ['advanced_reports:view', 'advanced_reports:export'],
    });
    const onGenerate = vi.fn().mockResolvedValue(undefined);
    render(
      <AdvancedReportBuilder
        canGenerate
        canSaveSchedule={false}
        isGenerating={false}
        isSavingSchedule={false}
        onGenerate={onGenerate}
        onSaveSchedule={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(screen.getByLabelText('Department')).toBeDisabled();
    expect(
      screen.getByText('Department scope is locked to your assigned department.'),
    ).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText('Report Name'), 'Department quality');
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: 'Output Format' }),
      'json',
    );
    await userEvent.selectOptions(
      screen.getByLabelText('Compliance Status'),
      'NON_COMPLIANT',
    );
    await userEvent.selectOptions(screen.getByLabelText('Language Pair'), 'id-en');
    await userEvent.selectOptions(
      screen.getByLabelText('Glossary Profile'),
      'profile-id',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Generate' }));

    expect(onGenerate).toHaveBeenCalledWith(
      expect.objectContaining({
        reportName: 'Department quality',
        outputFormat: 'json',
        filters: expect.objectContaining({
          departmentIds: ['department-id'],
          complianceStatuses: ['NON_COMPLIANT'],
          languagePairs: ['id-en'],
          glossaryProfileIds: ['profile-id'],
        }),
      }),
    );
    expect(
      screen.queryByRole('button', { name: 'Save Schedule' }),
    ).not.toBeInTheDocument();
  });

  it('shows Phase 9 navigation only for granted permissions', () => {
    const filtered = filterNavigationItems(
      navigationItems,
      ['similarity:view'],
      'VIEWER',
    );
    const documents = filtered.find((item) => item.label === 'Documents');
    const compliance = filtered.find((item) => item.label === 'Compliance');

    expect(documents?.path).toBe('/documents/similarity-queue');
    expect(documents?.children?.map((item) => item.label)).toEqual([
      'Similarity Queue',
      'Similarity History',
    ]);
    expect(compliance?.path).toBe('/compliance/translation-similarity');
    expect(compliance?.children?.map((item) => item.label)).toEqual([
      'Translation Similarity',
    ]);
    expect(filtered.some((item) => item.label === 'Reports')).toBe(false);
  });
});
