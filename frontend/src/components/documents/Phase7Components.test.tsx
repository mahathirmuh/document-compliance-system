import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';

import {
  languageBlocks,
  languageSummary,
  ocrBlocks,
  ocrPage,
  ocrRun,
  phase7Ids,
} from '../../test/phase7Fixtures';
import { LanguageBadge } from './LanguageBadge';
import { LanguageBlockTable } from './LanguageBlockTable';
import { LanguageCoveragePanel } from './LanguageCoveragePanel';
import { LanguagePresenceCards } from './LanguagePresenceCards';
import { OCRPageViewer } from './OCRPageViewer';
import { OCRProgress } from './OCRProgress';
import { RedetectLanguageDialog } from './RedetectLanguageDialog';
import { ReOCRDialog } from './ReOCRDialog';
import { StartOCRDialog } from './StartOCRDialog';

describe('Phase 7 OCR components', () => {
  it('renders accessible OCR progress and current page stage', () => {
    render(
      <OCRProgress
        status="RECOGNISING"
        progress={63}
        currentStage="Recognising page 2 of 3 using Chinese OCR"
      />,
    );

    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '63');
    expect(
      screen.getByText('Recognising page 2 of 3 using Chinese OCR'),
    ).toBeInTheDocument();
  });

  it('shows OCR provenance, rotation, bounding box, and low-confidence filter', async () => {
    const onFilter = vi.fn();
    const { rerender } = render(
      <OCRPageViewer
        page={ocrPage}
        blocks={ocrBlocks}
        confidenceFilter="ALL"
        lowConfidenceThreshold={ocrRun.lowConfidenceThreshold}
        reviewConfidenceThreshold={ocrRun.reviewConfidenceThreshold}
        onConfidenceFilterChange={onFilter}
      />,
    );

    expect(screen.getByText('Raw OCR text')).toBeInTheDocument();
    expect(screen.getByText('90°')).toBeInTheDocument();
    expect(screen.getAllByText('Source: OCR')).toHaveLength(2);
    await userEvent.click(screen.getAllByText('Bounding box and polygon')[0]!);
    expect(screen.getAllByText(/"width": 400/)).toHaveLength(2);

    await userEvent.selectOptions(screen.getByLabelText('OCR confidence'), 'LOW');
    expect(onFilter).toHaveBeenCalledWith('LOW');
    rerender(
      <OCRPageViewer
        page={ocrPage}
        blocks={ocrBlocks}
        confidenceFilter="LOW"
        lowConfidenceThreshold={ocrRun.lowConfidenceThreshold}
        reviewConfidenceThreshold={ocrRun.reviewConfidenceThreshold}
        onConfidenceFilterChange={onFilter}
      />,
    );
    const blockSection = screen.getByText('OCR blocks').closest('section');
    expect(blockSection).not.toBeNull();
    expect(within(blockSection!).getByText('Document control')).toBeInTheDocument();
    expect(within(blockSection!).queryByText('文件控制程序')).not.toBeInTheDocument();
    expect(within(blockSection!).getByText(/Low Confidence/)).toBeInTheDocument();
  });

  it('requires a re-OCR reason and submits page/profile choices', async () => {
    const onConfirm = vi.fn();
    render(
      <ReOCRDialog
        isOpen
        isPending={false}
        run={ocrRun}
        onClose={vi.fn()}
        onConfirm={onConfirm}
      />,
    );

    expect(screen.getByRole('button', { name: 'Queue Re-OCR' })).toBeDisabled();
    await userEvent.type(screen.getByLabelText('Pages (optional)'), '4, 5');
    await userEvent.selectOptions(
      screen.getByLabelText('Language profile'),
      'CHINESE_SIMPLIFIED',
    );
    await userEvent.selectOptions(screen.getByLabelText('Preprocessing'), 'AGGRESSIVE');
    await userEvent.type(
      screen.getByLabelText('Reason'),
      'Low confidence on Chinese pages.',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Queue Re-OCR' }));

    expect(onConfirm).toHaveBeenCalledWith({
      reason: 'Low confidence on Chinese pages.',
      pageNumbers: [4, 5],
      languageProfile: 'CHINESE_SIMPLIFIED',
      preprocessingProfile: 'AGGRESSIVE',
    });
  });

  it('queues only an explicitly configured PDF OCR request', async () => {
    const onConfirm = vi.fn();
    render(
      <StartOCRDialog
        isOpen
        filename="scan.pdf"
        documentFileId={phase7Ids.file}
        extractionRunId={phase7Ids.extractionRun}
        allowForce
        isPending={false}
        onClose={vi.fn()}
        onConfirm={onConfirm}
      />,
    );

    await userEvent.type(screen.getByLabelText('Manual pages (optional)'), '2, 5');
    await userEvent.click(screen.getByText('Force selected pages'));
    await userEvent.click(screen.getByRole('button', { name: 'Queue OCR' }));

    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({
        documentFileId: phase7Ids.file,
        extractionRunId: phase7Ids.extractionRun,
        pageNumbers: [2, 5],
        force: true,
      }),
    );
  });
});

describe('Phase 7 language result components', () => {
  it('renders target language presence and the preliminary disclaimer', () => {
    render(
      <>
        <LanguagePresenceCards summary={languageSummary} />
        <LanguageCoveragePanel coverage={languageSummary.coverage} />
      </>,
    );

    expect(screen.getAllByText('Bahasa Indonesia').length).toBeGreaterThan(0);
    expect(screen.getAllByText('English').length).toBeGreaterThan(0);
    expect(screen.getAllByText('中文 / Mandarin').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Present')).toHaveLength(2);
    expect(screen.getByText('Insufficient Evidence')).toBeInTheDocument();
    expect(screen.getByText('91%')).toBeInTheDocument();
    expect(screen.getByText('84%')).toBeInTheDocument();
    expect(screen.getByText('Not available')).toBeInTheDocument();
    expect(
      screen.getByText(/does not represent translation equivalence/),
    ).toBeInTheDocument();
  });

  it.each([
    ['id', 'ID · Bahasa Indonesia'],
    ['en', 'EN · English'],
    ['zh', 'ZH · 中文 / Mandarin'],
    ['mixed', 'Mixed'],
    ['unknown', 'Unknown'],
    ['other', 'Other'],
  ] as const)('renders the %s language category with a text label', (code, label) => {
    render(<LanguageBadge code={code} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it('keeps OCR confidence separate from language confidence', async () => {
    render(
      <MemoryRouter>
        <LanguageBlockTable
          blocks={languageBlocks}
          sourceContext={{
            documentId: phase7Ids.document,
            revisionId: phase7Ids.revision,
            extractionRunId: phase7Ids.extractionRun,
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText('Language 96%')).toBeInTheDocument();
    expect(screen.getByText('OCR 94%')).toBeInTheDocument();
    expect(screen.getByText('Language 78%')).toBeInTheDocument();
    expect(
      screen.getAllByRole('link', { name: 'Open Source Container' })[0],
    ).toHaveAttribute(
      'href',
      expect.stringContaining(
        `/documents/${phase7Ids.document}/revisions/${phase7Ids.revision}/extracted-content?`,
      ),
    );
    await userEvent.click(screen.getAllByRole('button', { name: 'View Detail' })[0]!);
    const detailDialog = screen.getByRole('dialog', { name: 'Language result detail' });
    expect(
      within(detailDialog).getByText('Language result detail'),
    ).toBeInTheDocument();
    expect(within(detailDialog).getByText('OCR:page=2:block=1')).toBeInTheDocument();
  });

  it('requires an audit reason before language re-detection', async () => {
    const onConfirm = vi.fn();
    render(
      <RedetectLanguageDialog
        isOpen
        isPending={false}
        onClose={vi.fn()}
        onConfirm={onConfirm}
      />,
    );

    expect(screen.getByRole('button', { name: 'Queue Re-detection' })).toBeDisabled();
    await userEvent.type(
      screen.getByLabelText('Reason'),
      'Language model configuration updated.',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Queue Re-detection' }));
    expect(onConfirm).toHaveBeenCalledWith('Language model configuration updated.');
  });
});
