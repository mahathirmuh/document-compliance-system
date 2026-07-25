import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { physicalFileFixture } from '../../test/documentFileFixtures';
import { supportedDocumentMimeTypes } from '../../types/documentFile';
import { DeleteDocumentFileDialog } from './DeleteDocumentFileDialog';
import { ReplaceDocumentFileDialog } from './ReplaceDocumentFileDialog';

const replacement = new File(['replacement'], 'replacement.pdf', {
  type: supportedDocumentMimeTypes.pdf,
});

describe('ReplaceDocumentFileDialog', () => {
  it('requires a replacement file and reason before submitting', async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    render(
      <ReplaceDocumentFileDialog
        file={physicalFileFixture}
        revisionStatus="DRAFT"
        isPending={false}
        onClose={vi.fn()}
        onConfirm={onConfirm}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Replace File' }));
    expect(
      await screen.findByText('Replacement reason is required.'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Select a replacement PDF, DOCX, or XLSX.'),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Browse document files'), {
      target: { files: [replacement] },
    });
    fireEvent.change(screen.getByRole('textbox', { name: /Reason/ }), {
      target: { value: 'Corrected controlled copy.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Replace File' }));

    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledWith(
        replacement,
        'Corrected controlled copy.',
        expect.any(Function),
      );
    });
  });

  it('requires acknowledgement for a final revision replacement', () => {
    render(
      <ReplaceDocumentFileDialog
        file={physicalFileFixture}
        revisionStatus="FINAL"
        isPending={false}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    expect(screen.getByText('Sensitive revision replacement')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Replace File' })).toBeDisabled();
    fireEvent.click(
      screen.getByLabelText(/I understand the existing file remains in history/),
    );
    expect(screen.getByRole('button', { name: 'Replace File' })).toBeEnabled();
  });
});

describe('DeleteDocumentFileDialog', () => {
  it('requires an audit reason and uses soft-delete language', async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    render(
      <DeleteDocumentFileDialog
        file={physicalFileFixture}
        isPending={false}
        onClose={vi.fn()}
        onConfirm={onConfirm}
      />,
    );

    expect(
      screen.getByText(
        'File will be removed from active storage but retained in file history.',
      ),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Remove File' }));
    expect(await screen.findByText('Deletion reason is required.')).toBeInTheDocument();
    expect(onConfirm).not.toHaveBeenCalled();

    fireEvent.change(screen.getByRole('textbox', { name: /Reason/ }), {
      target: { value: 'Wrong physical copy.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Remove File' }));
    await waitFor(() => expect(onConfirm).toHaveBeenCalledWith('Wrong physical copy.'));
  });
});
