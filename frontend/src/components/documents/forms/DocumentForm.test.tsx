import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '../../../providers/ToastProvider';
import { useAuthStore } from '../../../store/authStore';
import { superAdminSession } from '../../../test/authFixtures';
import type { DocumentDetail } from '../../../types/document';
import { DocumentForm } from './DocumentForm';

const department = {
  id: '11111111-1111-4111-8111-111111111111',
  code: 'HRM',
  name: 'Human Resource',
};
const otherDepartment = {
  id: '77777777-7777-4777-8777-777777777777',
  code: 'QMS',
  name: 'Quality Management',
};
const departmentSection = {
  id: '88888888-8888-4888-8888-888888888888',
  code: 'HRC',
  name: 'Human Resources Compliance',
  departmentId: department.id,
};
const documentType = {
  id: '22222222-2222-4222-8222-222222222222',
  code: 'POL',
  name: 'Policy',
  category: 'POLICY' as const,
  description: null,
  requiresSection: false,
  defaultValidationRuleId: '55555555-5555-4555-8555-555555555555',
  isActive: true,
  createdAt: '2026-07-25T10:00:00+08:00',
  updatedAt: '2026-07-25T10:00:00+08:00',
  createdBy: null,
  updatedBy: null,
};
const sectionDocumentType = {
  ...documentType,
  id: '99999999-9999-4999-8999-999999999999',
  code: 'SOP',
  name: 'Standard Operating Procedure',
  requiresSection: true,
  defaultValidationRuleId: null,
};
const manualValidationRule = {
  id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  code: 'POL-MANUAL',
  name: 'Policy Manual Selection',
  documentTypeId: documentType.id,
  isDefault: false,
};

vi.mock('../../../hooks/useDocumentFormOptions', () => ({
  useDocumentFormOptions: () => ({
    data: {
      defaultCompanyCode: 'BJM',
      departments: [department, otherDepartment],
      sections: [departmentSection],
      documentTypes: [documentType, sectionDocumentType],
      documentStatuses: [
        {
          id: '66666666-6666-4666-8666-666666666666',
          code: 'DRAFT',
          name: 'Draft',
          isInitial: true,
        },
      ],
      validationRules: [
        {
          id: '55555555-5555-4555-8555-555555555555',
          code: 'POL-DEFAULT',
          name: 'Policy Default',
          documentTypeId: documentType.id,
          isDefault: true,
        },
        manualValidationRule,
      ],
    },
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

const archivedDocument: DocumentDetail = {
  id: '33333333-3333-4333-8333-333333333333',
  companyCode: 'MTI',
  departmentId: department.id,
  sectionId: null,
  documentTypeId: documentType.id,
  documentNumber: '001',
  baseDocumentCode: 'MTI-HRM-POL-001',
  title: 'Archived Policy',
  department,
  section: null,
  documentType,
  currentRevision: null,
  isArchived: true,
  updatedAt: '2026-07-25T10:00:00+08:00',
  description: null,
  ownerDepartmentId: null,
  documentOwnerName: null,
  currentRevisionId: null,
  ownerDepartment: null,
  archivedAt: '2026-07-25T10:00:00+08:00',
  archivedBy: {
    id: '44444444-4444-4444-8444-444444444444',
    name: 'Document Controller',
  },
  archiveReason: 'No longer used.',
  createdBy: null,
  updatedBy: null,
  createdAt: '2026-07-20T10:00:00+08:00',
  revisions: [],
};

const sectionedDocument: DocumentDetail = {
  ...archivedDocument,
  id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  sectionId: departmentSection.id,
  documentTypeId: sectionDocumentType.id,
  baseDocumentCode: 'MTI-HRM-HRC-SOP-001',
  title: 'Section-controlled procedure',
  section: departmentSection,
  documentType: sectionDocumentType,
  isArchived: false,
  archivedAt: null,
  archivedBy: null,
  archiveReason: null,
};

const renderWithProviders = (children: ReactNode) => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>{children}</ToastProvider>
    </QueryClientProvider>,
  );
};

describe('DocumentForm archived state', () => {
  it('uses scoped backend defaults for a new document', async () => {
    useAuthStore.getState().setAuth(superAdminSession);
    renderWithProviders(
      <DocumentForm
        mode="create"
        isPending={false}
        onCancel={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByLabelText('Company Code')).toHaveValue('BJM');
    expect(screen.getByLabelText('Department')).toHaveValue('');
    expect(screen.getByLabelText('Document Type')).toHaveValue('');
    fireEvent.change(screen.getByLabelText('Document Type'), {
      target: { value: documentType.id },
    });

    await waitFor(() => {
      expect(screen.getByLabelText('Document Status')).toHaveValue(
        '66666666-6666-4666-8666-666666666666',
      );
      expect(screen.getByLabelText('Validation Rule')).toHaveValue(
        '55555555-5555-4555-8555-555555555555',
      );
    });
  });

  it('renders archived metadata read-only without a save action', () => {
    useAuthStore.getState().setAuth(superAdminSession);
    renderWithProviders(
      <DocumentForm
        mode="edit"
        document={archivedDocument}
        isPending={false}
        onCancel={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    expect(
      screen.getByText(/This document is archived. Its metadata is read-only/),
    ).toBeInTheDocument();
    expect(screen.getByLabelText('Document Title')).toBeDisabled();
    expect(
      screen.queryByRole('button', { name: 'Save Changes' }),
    ).not.toBeInTheDocument();
  });

  it('keeps a locked Department User department in the submitted payload', async () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      user: {
        ...superAdminSession.user,
        role: 'DEPARTMENT_USER',
        departmentId: department.id,
      },
      permissions: ['documents:view', 'documents:create'],
    });
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    renderWithProviders(
      <DocumentForm
        mode="create"
        isPending={false}
        onCancel={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    const departmentSelect = screen.getByRole('combobox', {
      name: /^Department/,
    });
    expect(departmentSelect).toBeDisabled();
    expect(departmentSelect).toHaveValue(department.id);

    fireEvent.change(screen.getByLabelText('Document Type'), {
      target: { value: documentType.id },
    });
    fireEvent.change(screen.getByLabelText('Document Number'), {
      target: { value: '001' },
    });
    fireEvent.change(screen.getByLabelText('Document Title'), {
      target: { value: 'Scoped Department Policy' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create Document' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          departmentId: department.id,
          documentTypeId: documentType.id,
        }),
      );
    });
  });

  it('clears and revalidates a stale section when the user changes department', async () => {
    useAuthStore.getState().setAuth(superAdminSession);
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    renderWithProviders(
      <DocumentForm
        mode="create"
        isPending={false}
        onCancel={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.change(screen.getByLabelText('Department'), {
      target: { value: department.id },
    });
    fireEvent.change(screen.getByLabelText('Document Type'), {
      target: { value: sectionDocumentType.id },
    });

    await screen.findByRole('option', {
      name: /HRC.*Human Resources Compliance/,
    });
    fireEvent.change(screen.getByLabelText('Section'), {
      target: { value: departmentSection.id },
    });
    expect(screen.getByRole('combobox', { name: /^Section/ })).toHaveValue(
      departmentSection.id,
    );

    fireEvent.change(screen.getByLabelText('Department'), {
      target: { value: otherDepartment.id },
    });

    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /^Section/ })).toHaveValue('');
      expect(
        screen.getByText('Section is required for this document type.'),
      ).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText('Document Number'), {
      target: { value: '002' },
    });
    fireEvent.change(screen.getByLabelText('Document Title'), {
      target: { value: 'Cross-department SOP' },
    });
    fireEvent.click(
      screen.getByRole('checkbox', {
        name: 'Create initial revision with this document',
      }),
    );
    fireEvent.click(screen.getByRole('button', { name: 'Create Document' }));

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('does not offer the document current section under another department', async () => {
    useAuthStore.getState().setAuth(superAdminSession);
    renderWithProviders(
      <DocumentForm
        mode="edit"
        document={sectionedDocument}
        isPending={false}
        onCancel={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByLabelText('Section')).toHaveValue(departmentSection.id);
    expect(
      screen.getByRole('option', {
        name: /HRC.*Human Resources Compliance/,
      }),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Department'), {
      target: { value: otherDepartment.id },
    });

    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /^Section/ })).toHaveValue('');
      expect(
        screen.queryByRole('option', {
          name: /HRC.*Human Resources Compliance/,
        }),
      ).not.toBeInTheDocument();
    });
  });

  it('preserves a manually selected validation rule on a same-type options rerender', async () => {
    useAuthStore.getState().setAuth(superAdminSession);
    renderWithProviders(
      <DocumentForm
        mode="create"
        isPending={false}
        onCancel={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText('Document Type'), {
      target: { value: documentType.id },
    });
    await waitFor(() => {
      expect(screen.getByLabelText('Validation Rule')).toHaveValue(
        documentType.defaultValidationRuleId,
      );
    });

    fireEvent.change(screen.getByLabelText('Validation Rule'), {
      target: { value: manualValidationRule.id },
    });
    expect(screen.getByLabelText('Validation Rule')).toHaveValue(
      manualValidationRule.id,
    );

    fireEvent.change(screen.getByLabelText('Company Code'), {
      target: { value: 'BJM_REFETCH' },
    });

    await waitFor(() => {
      expect(screen.getByLabelText('Validation Rule')).toHaveValue(
        manualValidationRule.id,
      );
    });
  });
});
