import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { uploadItemFixture } from '../../test/documentFileFixtures';
import { FileIdentificationPreview } from './FileIdentificationPreview';

describe('FileIdentificationPreview', () => {
  it('shows identified metadata, proposed action, and the register match', () => {
    render(<FileIdentificationPreview item={uploadItemFixture} />);

    expect(screen.getByText('Identified')).toBeInTheDocument();
    expect(screen.getByText('MTI-HRM-POL-001_Rev.000')).toBeInTheDocument();
    expect(screen.getByText('Worker Policy')).toBeInTheDocument();
    expect(
      screen.getByText('Proposed: Attach to existing revision'),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(uploadItemFixture.sha256Hash ?? ''),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Copy full SHA-256 hash' }),
    ).toBeInTheDocument();
  });

  it('shows duplicate and validation warnings without exposing another document', () => {
    render(
      <FileIdentificationPreview
        item={{
          ...uploadItemFixture,
          identificationStatus: 'DUPLICATE_FILE',
          proposedAction: 'MANUAL_REVIEW',
          matchedDocument: null,
          matchedRevision: null,
          duplicateWarning: {
            message: 'Duplicate file already exists.',
            sameRevision: false,
          },
          warnings: ['Manual review is required.'],
          errors: ['Target could not be selected automatically.'],
        }}
      />,
    );

    expect(screen.getByText('Duplicate')).toBeInTheDocument();
    expect(screen.getByText('Duplicate content detected')).toBeInTheDocument();
    expect(screen.getByText('Duplicate file already exists.')).toBeInTheDocument();
    expect(
      screen.getByText(
        'No existing register record was exposed within your department scope.',
      ),
    ).toBeInTheDocument();
  });
});
