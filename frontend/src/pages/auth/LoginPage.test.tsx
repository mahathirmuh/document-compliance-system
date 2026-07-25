import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { authApi } from '../../api/authApi';
import { useAuthStore } from '../../store/authStore';
import { superAdminSession } from '../../test/authFixtures';
import { LoginPage } from './LoginPage';

vi.mock('../../api/authApi', () => ({
  authApi: {
    login: vi.fn(),
    refreshToken: vi.fn(),
    logout: vi.fn(),
    getCurrentUser: vi.fn(),
  },
}));

const mockedLogin = vi.mocked(authApi.login);

const renderLogin = () =>
  render(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/dashboard" element={<p>Dashboard opened</p>} />
      </Routes>
    </MemoryRouter>,
  );

describe('LoginPage', () => {
  beforeEach(() => {
    useAuthStore.setState({ isInitializing: false });
  });

  it('validates the email format and required password', async () => {
    const user = userEvent.setup();
    renderLogin();

    await user.type(
      screen.getByRole('textbox', { name: 'Email address' }),
      'not-an-email',
    );
    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(await screen.findByText('Enter a valid email address.')).toBeInTheDocument();
    expect(screen.getByText('Password is required.')).toBeInTheDocument();
    expect(mockedLogin).not.toHaveBeenCalled();
  });

  it('stores a valid session and opens the dashboard', async () => {
    mockedLogin.mockResolvedValue(superAdminSession);
    const user = userEvent.setup();
    renderLogin();

    await user.type(
      screen.getByRole('textbox', { name: 'Email address' }),
      'admin@example.com',
    );
    await user.type(screen.getByLabelText('Password'), 'Admin123');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(await screen.findByText('Dashboard opened')).toBeInTheDocument();
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(useAuthStore.getState().user?.email).toBe('admin@example.com');
  });
});
