import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  complianceRun,
  detectedSection,
  phase8Ids,
  translationGroup,
} from '../../test/phase8Fixtures';
import { ComplianceRunAnalysisPage } from './ComplianceRunAnalysisPage';

const runHook = vi.hoisted(() => vi.fn());
const summaryHook = vi.hoisted(() => vi.fn());
const sectionsHook = vi.hoisted(() => vi.fn());
const groupsHook = vi.hoisted(() => vi.fn());
const findingsHook = vi.hoisted(() => vi.fn());

vi.mock('../../hooks/useCompliance', () => ({
  useComplianceRun: (runId: string | null) => runHook(runId),
  useComplianceSummary: (runId: string | null) => summaryHook(runId),
  useDetectedSections: (runId: string | null, params: object, options?: object) =>
    sectionsHook(runId, params, options),
  useTranslationGroups: (runId: string | null, params: object, options?: object) =>
    groupsHook(runId, params, options),
}));

vi.mock('../../hooks/useFindings', () => ({
  useFindings: (params: object, options: object) => findingsHook(params, options),
}));

const page = <TItem,>(
  items: TItem[],
  overrides: Partial<{
    page: number;
    pageSize: number;
    totalItems: number;
    totalPages: number;
  }> = {},
) => ({
  items,
  page: 1,
  pageSize: 20,
  totalItems: items.length,
  totalPages: 1,
  ...overrides,
});

describe('ComplianceRunAnalysisPage server pagination and filters', () => {
  beforeEach(() => {
    runHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: complianceRun,
      refetch: vi.fn(),
    });
    summaryHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: null,
      refetch: vi.fn(),
    });
    sectionsHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: page([detectedSection]),
      refetch: vi.fn(),
    });
    groupsHook.mockImplementation(
      (runId: string | null, params: { page?: number; pageSize?: number }) => ({
        isLoading: false,
        error: null,
        data:
          runId === null
            ? undefined
            : page([translationGroup], {
                page: params.page ?? 1,
                pageSize: params.pageSize ?? 20,
                totalItems: 41,
                totalPages: 3,
              }),
        refetch: vi.fn(),
      }),
    );
    findingsHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: page([]),
      refetch: vi.fn(),
    });
  });

  it('sends all language-order filters and page changes to the backend hook', async () => {
    render(
      <MemoryRouter
        initialEntries={[`/compliance/language-order?runId=${phase8Ids.run}`]}
      >
        <ComplianceRunAnalysisPage mode="language-order" />
      </MemoryRouter>,
    );

    await userEvent.selectOptions(
      screen.getByLabelText('Complete / Incomplete'),
      'INCOMPLETE',
    );
    await userEvent.selectOptions(screen.getByLabelText('Section'), phase8Ids.section);
    await userEvent.type(screen.getByLabelText('Container'), 'container-id');
    await userEvent.click(screen.getByLabelText('Order Invalid only'));
    await userEvent.click(screen.getByLabelText('Low Confidence only'));
    await userEvent.click(screen.getByRole('button', { name: 'Apply Filters' }));

    await waitFor(() =>
      expect(groupsHook).toHaveBeenCalledWith(
        phase8Ids.run,
        expect.objectContaining({
          page: 1,
          pageSize: 20,
          isComplete: false,
          isOrderValid: false,
          lowConfidence: true,
          detectedSectionId: phase8Ids.section,
          containerId: 'container-id',
        }),
        undefined,
      ),
    );

    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(groupsHook).toHaveBeenCalledWith(
      phase8Ids.run,
      expect.objectContaining({ page: 2, pageSize: 20 }),
      undefined,
    );
    expect(screen.getByText(/Page 2 of 3/)).toBeInTheDocument();
  });

  it('loads exact bounded finding and group data when section details open', async () => {
    render(
      <MemoryRouter initialEntries={[`/compliance/sections?runId=${phase8Ids.run}`]}>
        <ComplianceRunAnalysisPage mode="sections" />
      </MemoryRouter>,
    );

    await userEvent.click(
      screen.getByRole('button', { name: 'View details for PURPOSE' }),
    );

    expect(groupsHook).toHaveBeenCalledWith(
      phase8Ids.run,
      {
        page: 1,
        pageSize: 100,
        detectedSectionId: phase8Ids.section,
      },
      { enabled: true },
    );
    expect(findingsHook).toHaveBeenCalledWith(
      {
        page: 1,
        pageSize: 100,
        complianceRunId: phase8Ids.run,
        detectedSectionId: phase8Ids.section,
      },
      { enabled: true },
    );
    expect(
      screen.getByRole('dialog', { name: 'Section details: PURPOSE' }),
    ).toBeInTheDocument();
  });
});
