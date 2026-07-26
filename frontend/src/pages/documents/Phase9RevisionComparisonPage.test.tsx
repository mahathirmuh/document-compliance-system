import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '../../providers/ToastProvider';
import { useAuthStore } from '../../store/authStore';
import { superAdminSession } from '../../test/authFixtures';
import { RevisionComparisonPage } from './RevisionComparisonPage';

const comparisonState = vi.hoisted(() => ({
  job: null as object | null,
  comparison: null as object | null,
  summary: null as object | null,
  changes: {
    items: [],
    page: 1,
    pageSize: 50,
    totalItems: 0,
    totalPages: 0,
  } as object,
  sections: { comparisonId: 'comparison-id', items: [] } as object,
  languages: {
    comparisonId: 'comparison-id',
    items: [],
    groupsAdded: 0,
    groupsRemoved: 0,
    groupsModified: 0,
  } as object,
  findings: {
    comparisonId: 'comparison-id',
    items: [],
    summary: {},
  } as object,
}));
const comparisonMutations = vi.hoisted(() => ({
  start: { mutateAsync: vi.fn(), isPending: false },
  cancel: { mutateAsync: vi.fn(), isPending: false },
  export: { mutateAsync: vi.fn(), isPending: false },
}));
const downloadFile = vi.hoisted(() => vi.fn());

vi.mock('../../hooks/useDocuments', () => ({
  useDocuments: () => ({
    data: {
      items: [
        {
          id: 'document-id',
          baseDocumentCode: 'SOP-HSE-001',
          title: 'Safety Procedure',
        },
      ],
    },
    isLoading: false,
    error: null,
  }),
}));

vi.mock('../../hooks/useDocumentRevisions', () => ({
  useDocumentRevisions: (documentId: string | null) => ({
    data: documentId
      ? [
          { id: 'revision-1', revisionCode: 'R01', isCurrent: false },
          { id: 'revision-2', revisionCode: 'R02', isCurrent: true },
        ]
      : [],
    isLoading: false,
    error: null,
  }),
}));

vi.mock('../../hooks/useDocumentFiles', () => ({
  useRevisionFiles: (_documentId: string | null, revisionId: string | null) => ({
    data: revisionId
      ? [
          {
            id: `${revisionId}-file`,
            isCurrent: true,
            fileStatus: 'AVAILABLE',
          },
        ]
      : [],
    isLoading: false,
    error: null,
  }),
}));

vi.mock('../../hooks/useRevisionComparison', () => ({
  useRevisionComparisonJob: () => ({
    data: comparisonState.job,
    isLoading: false,
    error: null,
  }),
  useRevisionComparison: () => ({
    data: comparisonState.comparison,
    isLoading: false,
    error: null,
  }),
  useRevisionComparisonSummary: () => ({
    data: comparisonState.summary,
    isLoading: false,
    error: null,
  }),
  useRevisionChanges: () => ({
    data: comparisonState.changes,
    isLoading: false,
    error: null,
  }),
  useRevisionSectionChanges: () => ({
    data: comparisonState.sections,
    isLoading: false,
    error: null,
  }),
  useRevisionLanguageChanges: () => ({
    data: comparisonState.languages,
    isLoading: false,
    error: null,
  }),
  useRevisionFindingChanges: () => ({
    data: comparisonState.findings,
    isLoading: false,
    error: null,
  }),
  useRevisionComparisonMutations: () => comparisonMutations,
}));

vi.mock('../../utils/downloadFile', () => ({
  downloadFile,
}));

const timestamp = '2026-07-26T01:00:00Z';

const renderPage = (route = '/') =>
  render(
    <MemoryRouter initialEntries={[route]}>
      <ToastProvider>
        <RevisionComparisonPage />
      </ToastProvider>
    </MemoryRouter>,
  );

describe('Phase 9 revision comparison page', () => {
  beforeEach(() => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      permissions: [
        'revision_comparison:view',
        'revision_comparison:run',
        'revision_comparison:export',
      ],
    });
    comparisonState.job = null;
    comparisonState.comparison = null;
    comparisonState.summary = null;
    comparisonState.changes = {
      items: [],
      page: 1,
      pageSize: 50,
      totalItems: 0,
      totalPages: 0,
    };
    comparisonState.sections = { comparisonId: 'comparison-id', items: [] };
    comparisonState.languages = {
      comparisonId: 'comparison-id',
      items: [],
      groupsAdded: 0,
      groupsRemoved: 0,
      groupsModified: 0,
    };
    comparisonState.findings = {
      comparisonId: 'comparison-id',
      items: [],
      summary: {},
    };
    comparisonMutations.start.mutateAsync.mockReset();
    comparisonMutations.cancel.mutateAsync.mockReset();
    comparisonMutations.export.mutateAsync.mockReset();
    downloadFile.mockReset();
  });

  it('blocks selecting the same revision as both comparison sides', async () => {
    renderPage();

    await userEvent.selectOptions(
      screen.getByLabelText('Select Document'),
      'document-id',
    );
    await userEvent.selectOptions(
      screen.getByLabelText('Select Base Revision'),
      'revision-1',
    );
    await userEvent.selectOptions(
      screen.getByLabelText('Select Target Revision'),
      'revision-1',
    );

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Base and target revision must be different',
    );
    expect(screen.getByRole('button', { name: 'Run Comparison' })).toBeDisabled();
  });

  it('runs only two ready revisions belonging to the selected document', async () => {
    comparisonMutations.start.mutateAsync.mockResolvedValue({
      jobId: 'job-id',
      status: 'QUEUED',
      progress: 0,
      comparisonId: null,
      reusedExistingResult: false,
    });
    renderPage();

    await userEvent.selectOptions(
      screen.getByLabelText('Select Document'),
      'document-id',
    );
    await userEvent.selectOptions(
      screen.getByLabelText('Select Base Revision'),
      'revision-1',
    );
    await userEvent.selectOptions(
      screen.getByLabelText('Select Target Revision'),
      'revision-2',
    );
    expect(screen.getAllByText(/ready/i)).toHaveLength(2);
    await userEvent.click(screen.getByRole('button', { name: 'Run Comparison' }));

    expect(comparisonMutations.start.mutateAsync).toHaveBeenCalledWith({
      documentId: 'document-id',
      baseRevisionId: 'revision-1',
      targetRevisionId: 'revision-2',
      force: false,
    });
  });

  it('renders summary, language regression, compliance, finding, and export results', async () => {
    comparisonState.comparison = {
      id: 'comparison-id',
      classification: 'REGRESSED',
      complianceScoreChange: -4.5,
      similarityScoreChange: -0.08,
      newFindings: 2,
      removedFindings: 1,
      severityChangeCount: 1,
      addedTranslationGroups: 1,
      removedTranslationGroups: 2,
      modifiedTranslationGroups: 3,
      summary: { glossaryViolationChange: 2 },
    };
    comparisonState.summary = {
      comparisonId: 'comparison-id',
      classification: 'REGRESSED',
      totalChanges: 12,
      added: 3,
      removed: 2,
      modified: 5,
      moved: 2,
      unchanged: 8,
      complianceScoreChange: -4.5,
      similarityScoreChange: -0.08,
      newFindings: 2,
      noLongerReproduced: 1,
      summary: {},
      warnings: [],
    };
    comparisonState.languages = {
      comparisonId: 'comparison-id',
      items: [
        {
          languageCode: 'zh',
          baseCount: 10,
          targetCount: 6,
          baseCoverage: 92,
          targetCoverage: 70,
          coverageChange: -22,
          additions: 0,
          removals: 4,
          modifications: 1,
          basePresence: true,
          targetPresence: true,
          regression: true,
          fixedMissingLanguage: false,
        },
      ],
      groupsAdded: 1,
      groupsRemoved: 2,
      groupsModified: 3,
    };
    comparisonState.findings = {
      comparisonId: 'comparison-id',
      items: [
        {
          findingKey: 'finding-key',
          findingCode: 'GLOSSARY_FORBIDDEN_TERM',
          baseSeverity: 'MINOR',
          targetSeverity: 'MAJOR',
          comparisonStatus: 'SEVERITY_INCREASED',
          baseStatus: 'OPEN',
          targetStatus: 'OPEN',
          section: 'Safety',
          language: 'zh',
          location: 'DOCX:body:p=8',
        },
      ],
      summary: { SEVERITY_INCREASED: 1 },
    };
    const exported = {
      blob: new Blob(['comparison']),
      fileName: 'comparison.pdf',
    };
    comparisonMutations.export.mutateAsync.mockResolvedValue(exported);

    renderPage(
      '/?documentId=document-id&baseRevisionId=revision-1&targetRevisionId=revision-2&comparisonId=comparison-id',
    );

    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('REGRESSED')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Languages' }));
    expect(screen.getByText('92.00%')).toBeInTheDocument();
    expect(screen.getByText('-22.00 pp')).toBeInTheDocument();
    expect(screen.getByText('Yes')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Compliance' }));
    expect(screen.getAllByText('-4.50')).toHaveLength(2);
    await userEvent.click(screen.getByRole('button', { name: 'Findings' }));
    expect(screen.getByText('GLOSSARY_FORBIDDEN_TERM')).toBeInTheDocument();
    expect(screen.getByText('SEVERITY INCREASED')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'pdf' }));
    expect(comparisonMutations.export.mutateAsync).toHaveBeenCalledWith({
      comparisonId: 'comparison-id',
      format: 'pdf',
    });
    expect(downloadFile).toHaveBeenCalledWith(exported, 'revision_comparison.pdf');
  });

  it('shows worker progress and cancellation for an active comparison', async () => {
    comparisonState.job = {
      id: 'job-id',
      status: 'COMPARING_CONTENT',
      progress: 55,
      currentStage: 'COMPARING_CONTENT',
      resultSummary: null,
      errorMessage: null,
      requestedAt: timestamp,
    };
    comparisonMutations.cancel.mutateAsync.mockResolvedValue({
      ...comparisonState.job,
      status: 'CANCEL_REQUESTED',
    });

    renderPage('/?documentId=document-id&jobId=job-id');

    expect(screen.getByText('55%')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(comparisonMutations.cancel.mutateAsync).toHaveBeenCalledWith('job-id');
  });
});
