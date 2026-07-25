import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '../../providers/ToastProvider';
import { useAuthStore } from '../../store/authStore';
import { superAdminSession } from '../../test/authFixtures';
import { physicalFileFixture } from '../../test/documentFileFixtures';
import { UploadHistoryPage } from './UploadHistoryPage';

const historyHook = vi.hoisted(() => vi.fn());

vi.mock('../../hooks/useDocumentFileHistory', () => ({
  useDocumentFileHistory: (params: object) => historyHook(params),
}));

vi.mock('../../hooks/useDocumentFormOptions', () => ({
  useDocumentFormOptions: () => ({
    data: {
      departments: [
        {
          id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
          code: 'HRM',
          name: 'Human Resources',
        },
      ],
    },
  }),
}));

const renderPage = () => {
  historyHook.mockReturnValue({
    isLoading: false,
    error: null,
    data: {
      items: [physicalFileFixture],
      page: 1,
      pageSize: 20,
      totalItems: 1,
      totalPages: 1,
    },
  });
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ToastProvider>
          <UploadHistoryPage />
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

describe('UploadHistoryPage', () => {
  it('locks a Department User to their department and shows scoped history', () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      user: {
        ...superAdminSession.user,
        role: 'DEPARTMENT_USER',
        departmentId: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      },
      permissions: [
        'documents:view',
        'documents:download',
        'documents:view_file_history',
      ],
    });
    renderPage();

    expect(screen.getByLabelText('Department')).toBeDisabled();
    expect(screen.getByLabelText('Department')).toHaveValue(
      'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    );
    expect(screen.getByText(physicalFileFixture.originalFilename)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Download' })).toBeInTheDocument();
    expect(historyHook).toHaveBeenCalledWith(
      expect.objectContaining({
        departmentId: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      }),
    );
  });

  it('locks a Reviewer without cross-department permission to their department', () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      user: {
        ...superAdminSession.user,
        role: 'REVIEWER',
        departmentId: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      },
      permissions: [
        'documents:view',
        'documents:download',
        'documents:view_file_history',
      ],
    });
    renderPage();

    expect(screen.getByLabelText('Department')).toBeDisabled();
    expect(screen.getByLabelText('Department')).toHaveValue(
      'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    );
    expect(historyHook).toHaveBeenCalledWith(
      expect.objectContaining({
        departmentId: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      }),
    );
  });

  it('shows a locked unassigned state without implying global access', () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      user: {
        ...superAdminSession.user,
        role: 'REVIEWER',
        departmentId: null,
      },
      permissions: ['documents:view', 'documents:view_file_history'],
    });
    renderPage();

    expect(screen.getByLabelText('Department')).toBeDisabled();
    expect(screen.getByLabelText('Department')).toHaveDisplayValue(
      'No department assigned',
    );
  });

  it('keeps the department filter editable when permission grants global scope', () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      user: {
        ...superAdminSession.user,
        role: 'REVIEWER',
        departmentId: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      },
      permissions: [
        'documents:view',
        'documents:view_file_history',
        'documents:view_all_departments',
      ],
    });
    renderPage();

    expect(screen.getByLabelText('Department')).toBeEnabled();
    expect(screen.getByLabelText('Department')).toHaveDisplayValue(
      'All accessible departments',
    );
  });

  it('hides download and mutation controls without their permissions', () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      permissions: ['documents:view', 'documents:view_file_history'],
    });
    renderPage();

    expect(screen.queryByRole('button', { name: 'Download' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Replace' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Remove' })).not.toBeInTheDocument();
    expect(screen.getByText('Available')).toBeInTheDocument();
  });

  it('sends a date-only end boundary for server timezone handling', () => {
    useAuthStore.getState().setAuth(superAdminSession);
    renderPage();

    fireEvent.change(screen.getByLabelText('Uploaded To'), {
      target: { value: '2026-07-25' },
    });

    expect(historyHook).toHaveBeenLastCalledWith(
      expect.objectContaining({
        uploadedTo: '2026-07-25',
      }),
    );
  });
});
