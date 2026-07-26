import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';

import {
  LanguageComplianceTable,
  LanguageOrderFilters,
  LanguageOrderGroupTable,
  SectionDetailDialog,
  SectionComplianceTable,
} from './ComplianceDataViews';
import {
  emptyLanguageOrderFilters,
  type LanguageOrderFiltersValue,
} from './languageOrderFilters';
import type { DetectedSection } from '../../types/compliance';
import { ComplianceScorePanel } from './ComplianceScorePanel';
import { ComplianceStatusBadge } from './ComplianceStatusBadge';
import { FalsePositiveDialog } from './FalsePositiveDialog';
import { ResolveFindingDialog } from './ResolveFindingDialog';
import {
  complianceSummary,
  detectedSection,
  findingListItem,
  phase8Ids,
  scoreBreakdown,
  translationGroup,
} from '../../test/phase8Fixtures';

describe('Phase 8 compliance components', () => {
  it('shows score breakdown, text status, and Needs Review reasons', () => {
    render(
      <ComplianceScorePanel
        score={82.5}
        status="NEEDS_REVIEW"
        breakdown={scoreBreakdown}
        reasons={['Low grouping confidence requires manual review.']}
      />,
    );

    expect(screen.getByText('82.5')).toBeInTheDocument();
    expect(screen.getByText('Needs Review')).toBeInTheDocument();
    expect(screen.getByText('Language presence')).toBeInTheDocument();
    expect(
      screen.getByText('Low grouping confidence requires manual review.'),
    ).toBeInTheDocument();
  });

  it.each([
    ['COMPLIANT', 'Compliant'],
    ['PARTIALLY_COMPLIANT', 'Partially Compliant'],
    ['NON_COMPLIANT', 'Non-Compliant'],
    ['NEEDS_REVIEW', 'Needs Review'],
    ['NOT_EVALUATED', 'Not Evaluated'],
  ] as const)('renders %s with a stable text label', (status, label) => {
    render(<ComplianceStatusBadge status={status} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it('renders missing-language coverage and section completeness evidence', () => {
    render(
      <MemoryRouter>
        <LanguageComplianceTable summary={complianceSummary} />
        <SectionComplianceTable
          sections={[detectedSection]}
          documentId="document-id"
          revisionId="revision-id"
        />
      </MemoryRouter>,
    );

    expect(screen.getByText('中文 / Mandarin')).toBeInTheDocument();
    expect(screen.getAllByText('Missing').length).toBeGreaterThan(0);
    expect(screen.getByText('Below Coverage')).toBeInTheDocument();
    expect(screen.getByText('PURPOSE')).toBeInTheDocument();
    expect(screen.getByText('Incomplete')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open' })).toHaveAttribute(
      'href',
      expect.stringContaining('/extracted-content'),
    );
  });

  it('shows incomplete structural groups without a semantic-similarity claim', () => {
    render(<LanguageOrderGroupTable groups={[translationGroup]} />);

    expect(screen.getByText(/PARAGRAPH GROUP/)).toBeInTheDocument();
    expect(screen.getByText('ID → EN → ZH')).toBeInTheDocument();
    expect(screen.getByText('Incomplete')).toBeInTheDocument();
    expect(
      screen.getByText(/does not evaluate semantic translation equivalence/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/translations have the same meaning/i),
    ).not.toBeInTheDocument();
  });

  it('collects all language-order server filters before applying them', async () => {
    const applied = vi.fn();
    function FilterHarness() {
      const [filters, setFilters] = useState<LanguageOrderFiltersValue>({
        ...emptyLanguageOrderFilters,
      });
      return (
        <LanguageOrderFilters
          value={filters}
          sections={[detectedSection]}
          onChange={setFilters}
          onApply={() => applied(filters)}
          onReset={() => setFilters({ ...emptyLanguageOrderFilters })}
        />
      );
    }
    render(<FilterHarness />);

    await userEvent.selectOptions(
      screen.getByLabelText('Complete / Incomplete'),
      'INCOMPLETE',
    );
    await userEvent.selectOptions(screen.getByLabelText('Section'), phase8Ids.section);
    await userEvent.type(screen.getByLabelText('Container'), 'container-42');
    await userEvent.click(screen.getByLabelText('Order Invalid only'));
    await userEvent.click(screen.getByLabelText('Low Confidence only'));
    await userEvent.click(screen.getByRole('button', { name: 'Apply Filters' }));

    expect(applied).toHaveBeenCalledWith({
      completeness: 'INCOMPLETE',
      detectedSectionId: phase8Ids.section,
      containerId: 'container-42',
      orderInvalidOnly: true,
      lowConfidenceOnly: true,
    });
    expect(
      screen.getByText(/applied by the server across the complete compliance run/i),
    ).toBeInTheDocument();
  });

  it('opens bounded section details with source, language, finding, and group data', async () => {
    const sectionWithMetrics = {
      ...detectedSection,
      languageResults: [
        {
          id: 'section-language-id',
          detectedSectionId: detectedSection.id,
          languageCode: 'id' as const,
          presenceStatus: 'PRESENT' as const,
          blockCount: 4,
          characterCount: 240,
          coveragePercentage: 37.5,
          averageConfidence: 0.97,
          firstBlockId: 'block-2',
          lastBlockId: 'block-5',
          metrics: {},
          createdAt: detectedSection.createdAt,
        },
      ],
    };
    function DetailHarness() {
      const [section, setSection] = useState<DetectedSection | null>(null);
      return (
        <MemoryRouter>
          <SectionComplianceTable
            sections={[sectionWithMetrics]}
            documentId={phase8Ids.document}
            revisionId={phase8Ids.revision}
            onViewDetails={setSection}
          />
          <SectionDetailDialog
            section={section}
            documentId={phase8Ids.document}
            revisionId={phase8Ids.revision}
            findings={[findingListItem]}
            groups={[translationGroup]}
            onClose={() => setSection(null)}
          />
        </MemoryRouter>
      );
    }
    render(<DetailHarness />);

    await userEvent.click(
      screen.getByRole('button', { name: 'View details for PURPOSE' }),
    );

    expect(
      screen.getByRole('dialog', { name: 'Section details: PURPOSE' }),
    ).toBeInTheDocument();
    expect(screen.getByText('body')).toBeInTheDocument();
    expect(screen.getAllByText('block-1').length).toBeGreaterThan(0);
    expect(screen.getByText('240')).toBeInTheDocument();
    expect(screen.getByText('37.5%')).toBeInTheDocument();
    expect(screen.getByText('MISSING_TRANSLATION_GROUP_CHINESE')).toBeInTheDocument();
    expect(screen.getByText(/Group #1/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Open source block/ })).toHaveAttribute(
      'href',
      expect.stringContaining('blockId=block-1'),
    );
  });

  it('requires a finding-specific resolution comment', async () => {
    const onSubmit = vi.fn();
    render(
      <ResolveFindingDialog
        isOpen
        isPending={false}
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Resolve' }));
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Resolution comment is required.',
    );
    expect(onSubmit).not.toHaveBeenCalled();

    await userEvent.type(
      screen.getByLabelText('Resolution comment'),
      'Chinese content was added in Rev.003.',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Resolve' }));
    expect(onSubmit).toHaveBeenCalledWith({
      comment: 'Chinese content was added in Rev.003.',
    });
  });

  it('requires a reason before marking a false positive', async () => {
    const onSubmit = vi.fn();
    render(
      <FalsePositiveDialog
        isOpen
        isPending={false}
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Mark False Positive' }));
    expect(screen.getByRole('alert')).toHaveTextContent(
      'False-positive reason is required.',
    );
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
