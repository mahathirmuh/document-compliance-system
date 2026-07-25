import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';

import { useAuthStore } from '../../store/authStore';
import { superAdminSession } from '../../test/authFixtures';
import { Sidebar } from './Sidebar';

const renderSidebar = () =>
  render(
    <MemoryRouter>
      <Sidebar />
    </MemoryRouter>,
  );

describe('Sidebar', () => {
  it('shows Dashboard when the user has its permission', () => {
    useAuthStore.getState().setAuth(superAdminSession);
    renderSidebar();

    expect(screen.getByRole('link', { name: 'Dashboard' })).toBeInTheDocument();
  });

  it('shows the nested Master Data menu when view permission is granted', () => {
    useAuthStore.getState().setAuth(superAdminSession);
    renderSidebar();

    expect(screen.getByRole('link', { name: 'Master Data' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Overview' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Departments' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Sections' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Validation Rules' })).toBeInTheDocument();
  });

  it('shows document children according to their individual permissions', () => {
    useAuthStore.getState().setAuth(superAdminSession);
    renderSidebar();

    expect(screen.getByRole('link', { name: 'Documents' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Document Register' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Add Document' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Upload Document' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Batch Upload' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Extraction Queue' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'OCR Queue' })).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'Language Detection' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'Extraction History' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'OCR History' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Upload History' })).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'Archived Documents' }),
    ).toBeInTheDocument();
  });

  it('hides navigation the user is not permitted to access', () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      permissions: ['documents:view'],
      user: {
        ...superAdminSession.user,
        role: 'VIEWER',
      },
    });
    renderSidebar();

    expect(screen.queryByRole('link', { name: 'Dashboard' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Master Data' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Documents' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Document Register' })).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'Archived Documents' }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('link', { name: 'Upload Document' }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('link', { name: 'Add Document' }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('link', { name: 'Batch Upload' }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('link', { name: 'Upload History' }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('link', { name: 'Extraction Queue' }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('link', { name: 'Extraction History' }),
    ).not.toBeInTheDocument();
  });

  it('shows each upload menu only for its dedicated permission', () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      permissions: ['documents:view', 'documents:upload'],
    });
    renderSidebar();

    expect(screen.getByRole('link', { name: 'Upload Document' })).toBeInTheDocument();
    expect(
      screen.queryByRole('link', { name: 'Batch Upload' }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('link', { name: 'Upload History' }),
    ).not.toBeInTheDocument();
  });

  it('shows extraction menus only for their dedicated permissions', () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      permissions: ['documents:view', 'documents:view_extraction_history'],
    });
    renderSidebar();

    expect(
      screen.queryByRole('link', { name: 'Extraction Queue' }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'Extraction History' }),
    ).toBeInTheDocument();
  });

  it('shows OCR and language menus only for their dedicated permissions', () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      permissions: [
        'documents:view',
        'documents:view_ocr_history',
        'documents:view_language_results',
      ],
    });
    renderSidebar();

    expect(screen.queryByRole('link', { name: 'OCR Queue' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'OCR History' })).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'Language Detection' }),
    ).toBeInTheDocument();
  });
});
