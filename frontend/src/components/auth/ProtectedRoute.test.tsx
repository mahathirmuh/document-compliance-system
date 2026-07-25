import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { describe, expect, it } from 'vitest';

import { useAuthStore } from '../../store/authStore';
import { superAdminSession } from '../../test/authFixtures';
import { ProtectedRoute } from './ProtectedRoute';

const renderProtectedRoute = () =>
  render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <Routes>
        <Route path="/login" element={<p>Sign in required</p>} />
        <Route element={<ProtectedRoute />}>
          <Route path="/dashboard" element={<p>Protected dashboard</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );

describe('ProtectedRoute', () => {
  it('redirects an unauthenticated visitor to login', () => {
    useAuthStore.setState({ isInitializing: false });
    renderProtectedRoute();

    expect(screen.getByText('Sign in required')).toBeInTheDocument();
    expect(screen.queryByText('Protected dashboard')).not.toBeInTheDocument();
  });

  it('allows an authenticated user to open the dashboard', () => {
    useAuthStore.getState().setAuth(superAdminSession);
    renderProtectedRoute();

    expect(screen.getByText('Protected dashboard')).toBeInTheDocument();
  });
});
