import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';

import { supportedDocumentMimeTypes } from '../../types/documentFile';
import { FileDropzone } from './FileDropzone';

function DropzoneHarness({
  maximumSize,
  multiple = false,
}: {
  maximumSize?: number;
  multiple?: boolean;
}) {
  const [files, setFiles] = useState<File[]>([]);
  return (
    <FileDropzone
      files={files}
      onFilesChange={setFiles}
      {...(maximumSize === undefined ? {} : { maximumSize })}
      maximumFiles={multiple ? 5 : 1}
      multiple={multiple}
    />
  );
}

const select = (file: File, maximumSize?: number) => {
  render(<DropzoneHarness {...(maximumSize === undefined ? {} : { maximumSize })} />);
  fireEvent.change(screen.getByLabelText('Browse document files'), {
    target: { files: [file] },
  });
};

describe('FileDropzone', () => {
  it.each([
    ['PDF', 'policy.pdf', supportedDocumentMimeTypes.pdf],
    ['DOCX', 'policy.docx', supportedDocumentMimeTypes.docx],
    ['XLSX', 'register.xlsx', supportedDocumentMimeTypes.xlsx],
  ])('accepts a supported %s file', (_, name, type) => {
    select(new File(['valid'], name, { type }));

    expect(screen.getByText(name)).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it.each([
    [
      'presentation.pptx',
      'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    ],
    ['photo.jpg', 'image/jpeg'],
  ])('rejects unsupported file %s', (name, type) => {
    select(new File(['invalid'], name, { type }));

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Only PDF, DOCX, and XLSX files are supported.',
    );
    expect(screen.queryByText(name, { selector: 'p' })).not.toBeInTheDocument();
  });

  it('rejects a file larger than the configured maximum', () => {
    select(new File(['12345'], 'oversized.pdf', { type: 'application/pdf' }), 4);

    expect(screen.getByRole('alert')).toHaveTextContent('File exceeds the 4 B limit.');
  });

  it('supports multiple selection and removal from the keyboard-accessible control', () => {
    render(<DropzoneHarness multiple />);
    const input = screen.getByLabelText('Browse document files');
    fireEvent.change(input, {
      target: {
        files: [
          new File(['one'], 'one.pdf', { type: supportedDocumentMimeTypes.pdf }),
          new File(['two'], 'two.docx', { type: supportedDocumentMimeTypes.docx }),
        ],
      },
    });

    expect(
      screen.getByRole('button', { name: 'Select document file' }),
    ).toHaveAttribute('tabindex', '0');
    expect(screen.getByText('one.pdf')).toBeInTheDocument();
    expect(screen.getByText('two.docx')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Remove one.pdf' }));
    expect(screen.queryByText('one.pdf')).not.toBeInTheDocument();
  });
});
