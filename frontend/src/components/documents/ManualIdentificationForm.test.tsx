import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useAuthStore } from '../../store/authStore';
import { superAdminSession } from '../../test/authFixtures';
import { uploadItemFixture } from '../../test/documentFileFixtures';
import { ManualIdentificationForm } from './ManualIdentificationForm';

vi.mock('../../hooks/useDocumentFormOptions', () => ({
  useDocumentFormOptions: () => ({
    data: {
      defaultCompanyCode: 'MTI',
      departments: [
        {
          id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
          code: 'HRM',
          name: 'Human Resources',
        },
      ],
      sections: [
        {
          id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
          departmentId: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
          code: 'IER',
          name: 'Industrial Relations',
        },
      ],
      documentTypes: [
        {
          id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
          code: 'SOP',
          name: 'Procedure',
          requiresSection: true,
          defaultValidationRuleId: null,
        },
      ],
      documentStatuses: [
        {
          id: 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
          code: 'DRAFT',
          name: 'Draft',
          isInitial: true,
        },
      ],
      validationRules: [],
    },
  }),
}));

vi.mock('../../hooks/useDocuments', () => ({
  useDocuments: () => ({
    data: {
      items: [
        {
          id: '22222222-2222-4222-8222-222222222222',
          baseDocumentCode: 'MTI-HRM-POL-001',
          title: 'Worker Policy',
        },
      ],
    },
    isLoading: false,
    error: null,
  }),
}));

vi.mock('../../hooks/useDocumentRevisions', () => ({
  useDocumentRevisions: () => ({
    data: [
      {
        id: '33333333-3333-4333-8333-333333333333',
        revisionCode: 'Rev.000',
        fullDocumentCode: 'MTI-HRM-POL-001_Rev.000',
      },
    ],
    isLoading: false,
  }),
}));

beforeEach(() => {
  useAuthStore.getState().setAuth(superAdminSession);
});

describe('ManualIdentificationForm', () => {
  it('validates conditional metadata when creating a document manually', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <ManualIdentificationForm
        item={{
          ...uploadItemFixture,
          identificationStatus: 'NOT_IDENTIFIED',
          proposedAction: 'MANUAL_REVIEW',
          parsedMetadata: null,
          matchedDocument: null,
          matchedRevision: null,
        }}
        initialAction="CREATE_DOCUMENT_AND_REVISION"
        isSubmitting={false}
        onBack={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Confirm Upload' }));
    expect(await screen.findByText('Department is required.')).toBeInTheDocument();
    expect(screen.getByText('Document type is required.')).toBeInTheDocument();
    expect(screen.getByText('Document number is required.')).toBeInTheDocument();
    expect(screen.getByText('Document title is required.')).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();

    fireEvent.change(screen.getByRole('combobox', { name: /Department/ }), {
      target: { value: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: /Document Type/ }), {
      target: { value: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: /Document Number/ }), {
      target: { value: '001' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: /Document Title/ }), {
      target: { value: 'Manual Policy' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: /Revision Code/ }), {
      target: { value: '0' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Confirm Upload' }));
    expect(
      await screen.findByText('Section is required for this document type.'),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByRole('combobox', { name: /Section/ }), {
      target: { value: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Confirm Upload' }));

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          action: 'CREATE_DOCUMENT_AND_REVISION',
          metadata: expect.objectContaining({
            title: 'Manual Policy',
            revisionCode: 'Rev.000',
            departmentId: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
            sectionId: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
          }),
        }),
      ),
    );
  });

  it('prefills and submits a title parsed from the filename', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const title =
      'Demin Plant - Reducing Reagent Mixing & Dosing 脱盐水-还原剂药剂配制 (4706)';
    render(
      <ManualIdentificationForm
        item={{
          ...uploadItemFixture,
          identificationStatus: 'IDENTIFIED',
          proposedAction: 'CREATE_DOCUMENT_AND_REVISION',
          matchedDocument: null,
          matchedRevision: null,
          parsedMetadata: {
            companyCode: 'MTI',
            departmentCode: 'HRM',
            sectionCode: 'IER',
            documentTypeCode: 'SOP',
            documentNumber: '900',
            title,
            revisionCode: 'Rev.000',
            baseDocumentCode: 'MTI-HRM-IER-SOP-900',
            fullDocumentCode: 'MTI-HRM-IER-SOP-900_Rev.000',
          },
        }}
        initialAction="CREATE_DOCUMENT_AND_REVISION"
        isSubmitting={false}
        onBack={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    expect(await screen.findByRole('textbox', { name: /Document Title/ })).toHaveValue(
      title,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Confirm Upload' }));

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          action: 'CREATE_DOCUMENT_AND_REVISION',
          metadata: expect.objectContaining({
            title,
            documentNumber: '900',
            revisionCode: 'Rev.000',
          }),
        }),
      ),
    );
  });

  it('submits an existing revision attachment with scoped target IDs', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <ManualIdentificationForm
        item={uploadItemFixture}
        initialAction="ATTACH_TO_EXISTING_REVISION"
        isSubmitting={false}
        onBack={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Confirm Upload' }));
    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          action: 'ATTACH_TO_EXISTING_REVISION',
          documentId: '22222222-2222-4222-8222-222222222222',
          revisionId: '33333333-3333-4333-8333-333333333333',
        }),
      ),
    );
  });

  it('supports the add-revision action with normalized revision metadata', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <ManualIdentificationForm
        item={{
          ...uploadItemFixture,
          proposedAction: 'ADD_NEW_REVISION',
          matchedRevision: null,
          parsedMetadata: {
            ...uploadItemFixture.parsedMetadata,
            revisionCode: '1',
            fullDocumentCode: 'MTI-HRM-POL-001_Rev.001',
          },
        }}
        initialAction="ADD_NEW_REVISION"
        isSubmitting={false}
        onBack={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Confirm Upload' }));
    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          action: 'ADD_NEW_REVISION',
          documentId: '22222222-2222-4222-8222-222222222222',
          metadata: expect.objectContaining({
            revisionCode: 'Rev.001',
            setAsCurrentRevision: true,
          }),
        }),
      ),
    );
  });

  it('requires explicit acknowledgement before submitting a duplicate file', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <ManualIdentificationForm
        item={{
          ...uploadItemFixture,
          identificationStatus: 'DUPLICATE_FILE',
          duplicateWarning: {
            message: 'An identical file already exists.',
            sameRevision: false,
            documentId: uploadItemFixture.matchedDocument?.id ?? null,
            revisionId: uploadItemFixture.matchedRevision?.id ?? null,
          },
        }}
        initialAction="ATTACH_TO_EXISTING_REVISION"
        isSubmitting={false}
        onBack={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Confirm Upload' }));
    expect(
      await screen.findByText('Acknowledge the duplicate warning before continuing.'),
    ).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();

    fireEvent.click(
      screen.getByRole('checkbox', {
        name: /Continue after reviewing duplicate warning/,
      }),
    );
    fireEvent.click(screen.getByRole('button', { name: 'Confirm Upload' }));

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          metadata: expect.objectContaining({ allowDuplicate: true }),
        }),
      ),
    );
  });

  it('does not offer or default to replacement without replace permission', () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      user: {
        ...superAdminSession.user,
        role: 'DEPARTMENT_USER',
        departmentId: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      },
      permissions: [
        'documents:view',
        'documents:create',
        'documents:update',
        'documents:upload',
      ],
    });

    render(
      <ManualIdentificationForm
        item={{
          ...uploadItemFixture,
          proposedAction: 'REPLACE_CURRENT_FILE',
        }}
        initialAction="REPLACE_CURRENT_FILE"
        isSubmitting={false}
        onBack={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    expect(
      screen.queryByRole('option', { name: 'Replace current file' }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Confirm action' })).toHaveValue('');
  });
});
