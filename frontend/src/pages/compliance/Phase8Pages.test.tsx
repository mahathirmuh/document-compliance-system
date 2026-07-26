import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ValidationQueuePage } from '../documents/ValidationQueuePage';
import { ValidationHistoryPage } from '../documents/ValidationHistoryPage';
import { ToastProvider } from '../../providers/ToastProvider';
import { useAuthStore } from '../../store/authStore';
import { superAdminSession } from '../../test/authFixtures';
import {
  complianceJob,
  complianceRun,
  finding,
  findingListItem,
  phase8Ids,
} from '../../test/phase8Fixtures';
import { FindingDetailPage } from './FindingDetailPage';
import { FindingsPage } from './FindingsPage';

const complianceJobsHook = vi.hoisted(() => vi.fn());
const cancelCompliance = vi.hoisted(() => ({
  mutateAsync: vi.fn(),
  isPending: false,
}));
const findingsHook = vi.hoisted(() => vi.fn());
const findingHook = vi.hoisted(() => vi.fn());
const findingsExport = vi.hoisted(() => ({
  mutateAsync: vi.fn(),
  isPending: false,
}));
const findingActions = vi.hoisted(() => ({
  createManual: { mutateAsync: vi.fn(), isPending: false },
  update: { mutateAsync: vi.fn(), isPending: false },
  review: { mutateAsync: vi.fn(), isPending: false },
  resolve: { mutateAsync: vi.fn(), isPending: false },
  returnToOpen: { mutateAsync: vi.fn(), isPending: false },
  reopen: { mutateAsync: vi.fn(), isPending: false },
  falsePositive: { mutateAsync: vi.fn(), isPending: false },
  acceptRisk: { mutateAsync: vi.fn(), isPending: false },
  assign: { mutateAsync: vi.fn(), isPending: false },
  bulkAction: { mutateAsync: vi.fn(), isPending: false },
}));
const complianceRunHook = vi.hoisted(() => vi.fn());
const complianceMutations = vi.hoisted(() => ({
  export: { mutateAsync: vi.fn(), isPending: false },
  revalidate: { mutateAsync: vi.fn(), isPending: false },
}));

vi.mock('../../hooks/useComplianceJobs', () => ({
  useComplianceJobs: (params: object, options: object) =>
    complianceJobsHook(params, options),
  useCancelComplianceJob: () => cancelCompliance,
}));

vi.mock('../../hooks/useFindings', () => ({
  useFindings: (params: object) => findingsHook(params),
  useFinding: (id: string | null) => findingHook(id),
  useFindingsExport: () => findingsExport,
}));

vi.mock('../../hooks/useFindingActions', () => ({
  useFindingActions: () => findingActions,
}));

vi.mock('../../hooks/useCompliance', () => ({
  useComplianceRun: (id: string | null) => complianceRunHook(id),
  useComplianceMutations: () => complianceMutations,
}));

vi.mock('../../hooks/useDocumentFormOptions', () => ({
  useDocumentFormOptions: () => ({
    data: {
      departments: [
        {
          id: 'department-id',
          code: 'HRM',
          name: 'Human Resources',
        },
      ],
      validationRules: [
        {
          id: phase8Ids.rule,
          code: 'SOP-3LANG',
          name: 'SOP Three-Language Rule',
        },
      ],
    },
  }),
}));

const renderPage = (page: React.ReactNode, route = '/') =>
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={[route]}>
        <ToastProvider>{page}</ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );

describe('Phase 8 queue and findings pages', () => {
  beforeEach(() => {
    useAuthStore.getState().setAuth(superAdminSession);
    cancelCompliance.mutateAsync.mockReset();
    findingsExport.mutateAsync.mockReset();
    complianceMutations.export.mutateAsync.mockReset();
    complianceMutations.revalidate.mutateAsync.mockReset();
    Object.values(findingActions).forEach((mutation) =>
      mutation.mutateAsync.mockReset(),
    );
    complianceJobsHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        items: [complianceJob],
        page: 1,
        pageSize: 20,
        totalItems: 1,
        totalPages: 1,
      },
      refetch: vi.fn(),
    });
    findingsHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        items: [findingListItem],
        page: 1,
        pageSize: 20,
        totalItems: 1,
        totalPages: 1,
      },
      refetch: vi.fn(),
    });
    findingHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: finding,
      refetch: vi.fn(),
    });
    complianceRunHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: complianceRun,
      refetch: vi.fn(),
    });
  });

  it('shows live validation progress and confirms safe cancellation', async () => {
    cancelCompliance.mutateAsync.mockResolvedValue({
      ...complianceJob,
      status: 'CANCEL_REQUESTED',
    });
    renderPage(<ValidationQueuePage />);

    expect(screen.getByText('45%')).toBeInTheDocument();
    expect(screen.getAllByText('VALIDATING LANGUAGES').length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(
      screen.getByRole('dialog', { name: 'Cancel compliance validation?' }),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Request Cancellation' }));
    expect(cancelCompliance.mutateAsync).toHaveBeenCalledWith(phase8Ids.job);
  });

  it('locks validation queue scope to a department user', () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      user: {
        ...superAdminSession.user,
        role: 'DEPARTMENT_USER',
        departmentId: 'department-id',
      },
      permissions: ['compliance:view', 'compliance:validate'],
    });
    renderPage(<ValidationQueuePage />);

    expect(screen.getByLabelText('Department')).toBeDisabled();
    expect(complianceJobsHook).toHaveBeenCalledWith(
      expect.objectContaining({ departmentId: 'department-id' }),
      { pollActive: true },
    );
  });

  it('delegates validation history compliance status filtering to the server', async () => {
    const historyJob = {
      ...complianceJob,
      status: 'COMPLETED' as const,
      progress: 100,
      currentStage: 'COMPLETED',
      completedAt: '2026-07-26T08:01:00+08:00',
      resultSummary: {
        runId: phase8Ids.run,
        complianceStatus: 'NON_COMPLIANT' as const,
        complianceScore: 61,
        totalFindings: 5,
        criticalFindings: 1,
        majorFindings: 2,
        minorFindings: 2,
      },
    };
    complianceJobsHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        items: [historyJob],
        page: 1,
        pageSize: 20,
        totalItems: 41,
        totalPages: 3,
      },
      refetch: vi.fn(),
    });
    renderPage(<ValidationHistoryPage />);

    await userEvent.selectOptions(
      screen.getByLabelText('Compliance Status'),
      'COMPLIANT',
    );

    expect(complianceJobsHook).toHaveBeenLastCalledWith(
      expect.objectContaining({ complianceStatus: 'COMPLIANT' }),
      undefined,
    );
    expect(screen.getByText('MTI-HRM-SOP-0042')).toBeInTheDocument();
    expect(screen.getByText(/41 validation jobs/)).toBeInTheDocument();
  });

  it('passes finding filters to the backend hook', async () => {
    renderPage(<FindingsPage />);

    await userEvent.selectOptions(screen.getByLabelText('Severity'), 'MAJOR');
    await userEvent.selectOptions(screen.getByLabelText('Status'), 'OPEN');

    expect(findingsHook).toHaveBeenLastCalledWith(
      expect.objectContaining({ severity: 'MAJOR', status: 'OPEN' }),
    );
    expect(screen.getByText('MISSING_TRANSLATION_GROUP_CHINESE')).toBeInTheDocument();
  });

  it('creates a manual finding with required source identifiers', async () => {
    findingActions.createManual.mutateAsync.mockResolvedValue(finding);
    renderPage(<FindingsPage />);

    await userEvent.click(screen.getByRole('button', { name: 'Manual Finding' }));
    await userEvent.type(screen.getByLabelText('Document ID'), phase8Ids.document);
    await userEvent.type(screen.getByLabelText('Revision ID'), phase8Ids.revision);
    await userEvent.type(screen.getByLabelText('Document file ID'), phase8Ids.file);
    await userEvent.type(screen.getByLabelText('Title'), 'Unclear table heading');
    await userEvent.type(
      screen.getByLabelText('Description'),
      'The multilingual table heading needs manual review.',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Create Finding' }));

    expect(findingActions.createManual.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        documentId: phase8Ids.document,
        documentRevisionId: phase8Ids.revision,
        documentFileId: phase8Ids.file,
        severity: 'MAJOR',
        title: 'Unclear table heading',
      }),
    );
  });

  it('sends selected findings through one authoritative bulk assignment', async () => {
    findingActions.bulkAction.mutateAsync.mockResolvedValue({
      action: 'ASSIGN',
      processedCount: 1,
      findingIds: [phase8Ids.finding],
    });
    renderPage(<FindingsPage />);

    await userEvent.click(
      screen.getByRole('checkbox', {
        name: `Select ${findingListItem.title}`,
      }),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Assign' }));
    await userEvent.type(screen.getByLabelText('Assignee user ID'), 'reviewer-id');
    await userEvent.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Assign' }),
    );

    expect(findingActions.bulkAction.mutateAsync).toHaveBeenCalledTimes(1);
    expect(findingActions.bulkAction.mutateAsync).toHaveBeenCalledWith({
      action: 'ASSIGN',
      findingIds: [phase8Ids.finding],
      assignedTo: 'reviewer-id',
    });
    expect(findingActions.assign.mutateAsync).not.toHaveBeenCalled();
  });

  it('reviews an open finding through the reasoned action dialog', async () => {
    findingActions.review.mutateAsync.mockResolvedValue({
      ...finding,
      status: 'IN_REVIEW',
    });
    renderPage(
      <Routes>
        <Route path="/compliance/findings/:findingId" element={<FindingDetailPage />} />
      </Routes>,
      `/compliance/findings/${phase8Ids.finding}`,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Start Review' }));
    await userEvent.type(
      screen.getByLabelText('Review comment'),
      'Confirmed during document review.',
    );
    await userEvent.click(
      within(screen.getByRole('dialog')).getByRole('button', {
        name: 'Start Review',
      }),
    );

    expect(findingActions.review.mutateAsync).toHaveBeenCalledWith({
      findingId: phase8Ids.finding,
      payload: { comment: 'Confirmed during document review.' },
    });
  });

  it('does not offer invalid transitions for a resolved finding', () => {
    findingHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: { ...finding, status: 'RESOLVED' },
      refetch: vi.fn(),
    });
    renderPage(
      <Routes>
        <Route path="/compliance/findings/:findingId" element={<FindingDetailPage />} />
      </Routes>,
      `/compliance/findings/${phase8Ids.finding}`,
    );

    expect(screen.getByRole('button', { name: 'Reopen' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Resolve' })).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Mark False Positive' }),
    ).not.toBeInTheDocument();
  });

  it('uses the compliance run immutable extraction source in finding links', () => {
    renderPage(
      <Routes>
        <Route path="/compliance/findings/:findingId" element={<FindingDetailPage />} />
      </Routes>,
      `/compliance/findings/${phase8Ids.finding}`,
    );

    expect(complianceRunHook).toHaveBeenCalledWith(phase8Ids.run);
    const sourceLink = screen.getByRole('link', { name: 'Open Source' });
    expect(sourceLink).toHaveAttribute(
      'href',
      expect.stringContaining(`runId=${phase8Ids.extraction}`),
    );
    expect(sourceLink).toHaveAttribute(
      'href',
      expect.stringContaining('sourceReference=DOCX%3Abody%3Ap%3D4-5'),
    );
  });

  it('guards risk acceptance with resolve permission, not update permission', () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      user: {
        ...superAdminSession.user,
        role: 'DEPARTMENT_USER',
        departmentId: 'department-id',
      },
      permissions: ['findings:view', 'findings:update'],
    });
    const { unmount } = renderPage(
      <Routes>
        <Route path="/compliance/findings/:findingId" element={<FindingDetailPage />} />
      </Routes>,
      `/compliance/findings/${phase8Ids.finding}`,
    );
    expect(
      screen.queryByRole('button', { name: 'Accept Risk' }),
    ).not.toBeInTheDocument();
    unmount();

    useAuthStore.getState().setAuth({
      ...superAdminSession,
      user: { ...superAdminSession.user, role: 'REVIEWER' },
      permissions: ['findings:view', 'findings:resolve'],
    });
    renderPage(
      <Routes>
        <Route path="/compliance/findings/:findingId" element={<FindingDetailPage />} />
      </Routes>,
      `/compliance/findings/${phase8Ids.finding}`,
    );
    expect(screen.getByRole('button', { name: 'Accept Risk' })).toBeInTheDocument();
  });

  it('returns an in-review finding to open with a mandatory comment', async () => {
    findingHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: { ...finding, status: 'IN_REVIEW' },
      refetch: vi.fn(),
    });
    findingActions.returnToOpen.mutateAsync.mockResolvedValue({
      ...finding,
      status: 'OPEN',
    });
    renderPage(
      <Routes>
        <Route path="/compliance/findings/:findingId" element={<FindingDetailPage />} />
      </Routes>,
      `/compliance/findings/${phase8Ids.finding}`,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Return to Open' }));
    await userEvent.type(
      screen.getByLabelText('Return-to-open comment'),
      'Additional source review is required.',
    );
    await userEvent.click(
      within(screen.getByRole('dialog')).getByRole('button', {
        name: 'Return to Open',
      }),
    );

    expect(findingActions.returnToOpen.mutateAsync).toHaveBeenCalledWith({
      findingId: phase8Ids.finding,
      payload: { comment: 'Additional source review is required.' },
    });
  });
});
