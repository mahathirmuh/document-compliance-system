import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';

import { CancelExtractionDialog } from './CancelExtractionDialog';
import { ContainerNavigator } from './ContainerNavigator';
import { ExtractedBlockViewer } from './ExtractedBlockViewer';
import { ExtractedTableViewer } from './ExtractedTableViewer';
import { ExtractionProgress } from './ExtractionProgress';
import { ExtractionStatusBadge } from './ExtractionStatusBadge';
import { ExtractionHistoryTable } from './ExtractionHistoryTable';
import { ReExtractionDialog } from './ReExtractionDialog';
import { SafeHighlight } from './SafeHighlight';
import {
  extractedBlocks,
  extractedTable,
  extractionHistoryItem,
  extractionIds,
  extractionRun,
  pdfContainers,
  queuedExtractionJob,
} from '../../test/extractionFixtures';
import type { ExtractedBlock } from '../../types/extractedContent';

describe('Phase 6 extraction components', () => {
  it('renders every job state with accessible progress', () => {
    render(
      <>
        <ExtractionStatusBadge status="PARTIALLY_COMPLETED" />
        <ExtractionProgress
          status="EXTRACTING"
          progress={45.4}
          currentStage="Extracting page 9 of 20"
        />
      </>,
    );

    expect(screen.getByText('Partially Completed')).toBeInTheDocument();
    expect(screen.getByText('Extracting page 9 of 20')).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '45');
  });

  it('navigates PDF pages and DOCX logical parts', () => {
    const onSelect = vi.fn();
    render(
      <ContainerNavigator
        containers={[
          ...pdfContainers,
          {
            ...pdfContainers[0]!,
            id: 'dddddddd-1111-4111-8111-111111111111',
            containerType: 'DOCX_HEADER',
            name: 'default-header',
          },
          {
            ...pdfContainers[0]!,
            id: 'eeeeeeee-1111-4111-8111-111111111111',
            containerType: 'XLSX_WORKSHEET',
            containerIndex: 3,
            name: null,
            title: null,
          },
          {
            ...pdfContainers[0]!,
            id: 'ffffffff-1111-4111-8111-111111111111',
            containerType: 'DOCX_FOOTER',
            containerIndex: 2,
            name: null,
            title: null,
          },
        ]}
        selectedId={pdfContainers[0]!.id}
        onSelect={onSelect}
      />,
    );

    expect(screen.getByRole('button', { name: /Page 1/ })).toHaveAttribute(
      'aria-current',
      'page',
    );
    fireEvent.click(screen.getByRole('button', { name: /Page 2/ }));
    expect(onSelect).toHaveBeenCalledWith(pdfContainers[1]);
    expect(screen.getByRole('button', { name: /default-header/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Worksheet 3/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Footer 2/ })).toBeInTheDocument();
  });

  it('highlights search text as React fragments without creating source HTML', () => {
    const { container } = render(
      <p>
        <SafeHighlight
          text="<script>alert(1)</script> document control"
          query="document"
        />
      </p>,
    );

    expect(screen.getByText('document')).toHaveRole('mark');
    expect(screen.getByText(/<script>alert\(1\)<\/script>/)).toBeInTheDocument();
    expect(container.querySelector('script')).toBeNull();
  });

  it('renders DOCX headings, source references, and structured tables', () => {
    const { container } = render(
      <>
        <ExtractedBlockViewer
          blocks={extractedBlocks}
          extractorType="DOCX"
          highlightQuery="control"
        />
        <ExtractedTableViewer tables={[extractedTable]} />
      </>,
    );

    expect(screen.getAllByText('Heading 1')).toHaveLength(2);
    expect(screen.getByText('PDF:page=1:block=1')).toBeInTheDocument();
    expect(screen.getByText('Code')).toBeInTheDocument();
    expect(screen.getByText('Title')).toBeInTheDocument();
    expect(container.querySelector('script')).toBeNull();
  });

  it('renders only returned table rows and identifies a truncated inline preview', () => {
    render(
      <ExtractedTableViewer
        tables={[
          {
            ...extractedTable,
            rowCount: 1_000_000,
            metadata: {
              cellsTruncated: true,
              totalCells: 2_000_000,
            },
            cells: [
              {
                ...extractedTable.cells[0]!,
                rowIndex: 999_999,
              },
            ],
          },
        ]}
      />,
    );

    expect(screen.getAllByRole('row')).toHaveLength(1);
    expect(screen.getByText('Code')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent(
      `Showing 1 of ${(2_000_000).toLocaleString()} table cells`,
    );
  });

  it('renders XLSX coordinates, formulas, cached values, and merged indicators', () => {
    const cell: ExtractedBlock = {
      ...extractedBlocks[0]!,
      blockType: 'FORMULA',
      sourceReference: 'XLSX:sheet=Register:cell=A4',
      text: '=SUM(A1:A3)',
      styleName: null,
      headingLevel: null,
      metadata: {
        coordinate: 'A4',
        formula: '=SUM(A1:A3)',
        cachedValue: 42,
        isMerged: true,
      },
    };
    render(<ExtractedBlockViewer blocks={[cell]} extractorType="XLSX" />);

    expect(screen.getByText('A4')).toBeInTheDocument();
    expect(screen.getAllByText('=SUM(A1:A3)')).toHaveLength(2);
    expect(screen.getByText('Cached: 42')).toBeInTheDocument();
    expect(screen.getByText('Merged')).toBeInTheDocument();
  });

  it('validates a required re-extraction reason before submission', async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    render(
      <ReExtractionDialog
        isOpen
        run={extractionRun}
        isPending={false}
        onClose={vi.fn()}
        onConfirm={onConfirm}
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Queue Re-extraction' }));
    expect(
      await screen.findByText('Re-extraction reason is required.'),
    ).toBeInTheDocument();
    expect(onConfirm).not.toHaveBeenCalled();

    await userEvent.type(
      screen.getByRole('textbox', { name: /Reason/ }),
      'Extractor configuration updated.',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Queue Re-extraction' }));
    expect(onConfirm).toHaveBeenCalledWith('Extractor configuration updated.');
  });

  it('explains checkpoint cancellation and confirms the selected job', async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    render(
      <CancelExtractionDialog
        job={queuedExtractionJob}
        isPending={false}
        onCancel={vi.fn()}
        onConfirm={onConfirm}
      />,
    );

    expect(screen.getByText(/next safe checkpoint/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Request Cancellation' }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it('renders read-only extraction history with export and latest re-extraction', async () => {
    const onExport = vi.fn();
    const onReextract = vi.fn();
    render(
      <MemoryRouter>
        <ExtractionHistoryTable
          runs={[extractionHistoryItem]}
          documentId={extractionIds.document}
          revisionId={extractionIds.revision}
          canExport
          canReextract
          onExport={onExport}
          onReextract={onReextract}
        />
      </MemoryRouter>,
    );

    expect(screen.getAllByText('Latest')).toHaveLength(2);
    await userEvent.click(screen.getByRole('button', { name: 'json' }));
    await userEvent.click(screen.getByRole('button', { name: 'Re-extract' }));
    expect(onExport).toHaveBeenCalledWith(extractionHistoryItem, 'json');
    expect(onReextract).toHaveBeenCalledWith(extractionHistoryItem);
  });
});
