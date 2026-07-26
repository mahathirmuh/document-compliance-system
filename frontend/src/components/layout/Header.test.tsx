import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router';
import { describe, expect, it, vi } from 'vitest';

import { authApi } from '../../api/authApi';
import { useAuthStore } from '../../store/authStore';
import { superAdminSession } from '../../test/authFixtures';
import { Header } from './Header';

vi.mock('../../api/authApi', () => ({
  authApi: {
    login: vi.fn(),
    refreshToken: vi.fn(),
    logout: vi.fn(),
    getCurrentUser: vi.fn(),
  },
}));

vi.mock('../notifications/NotificationCentre', () => ({
  NotificationCentre: () => null,
}));

describe('Header logout', () => {
  it('clears local auth state even when the backend request fails', async () => {
    vi.mocked(authApi.logout).mockRejectedValue(new Error('Offline'));
    useAuthStore.getState().setAuth(superAdminSession);
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route path="/dashboard" element={<Header />} />
          <Route path="/login" element={<p>Signed out locally</p>} />
        </Routes>
      </MemoryRouter>,
    );

    await user.click(screen.getByRole('button', { name: /System Administrator/ }));
    await user.click(screen.getByRole('menuitem', { name: 'Sign out' }));

    expect(await screen.findByText('Signed out locally')).toBeInTheDocument();
    await waitFor(() => {
      expect(useAuthStore.getState().isAuthenticated).toBe(false);
      expect(useAuthStore.getState().accessToken).toBeNull();
      expect(useAuthStore.getState().refreshToken).toBeNull();
    });
  });
});
