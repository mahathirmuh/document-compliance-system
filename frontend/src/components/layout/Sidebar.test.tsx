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
      screen.queryByRole('link', { name: 'Add Document' }),
    ).not.toBeInTheDocument();
  });
});
