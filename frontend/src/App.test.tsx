import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import App from './App';
import { fetchHealth } from './api/health';

vi.mock('./api/health', () => ({
  fetchHealth: vi.fn(),
}));

const mockedFetchHealth = vi.mocked(fetchHealth);

const renderApp = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: Infinity,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  );
};

afterEach(() => {
  vi.clearAllMocks();
});

describe('landing page', () => {
  it('shows the application identity and a healthy backend response', async () => {
    mockedFetchHealth.mockResolvedValue({
      status: 'healthy',
      service: 'document-compliance-api',
    });

    renderApp();

    expect(
      screen.getByText(
        /Document Compliance & Multilingual Validation System creates one clear path/,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText('v1.0.0')).toBeInTheDocument();
    expect(await screen.findByText('Backend connected')).toBeInTheDocument();
    expect(screen.getByText('document-compliance-api')).toBeInTheDocument();
  });

  it('renders a friendly error state when the backend cannot be reached', async () => {
    mockedFetchHealth.mockRejectedValue(new Error('Network connection failed.'));

    renderApp();

    expect(await screen.findByText('Backend unavailable')).toBeInTheDocument();
    expect(screen.getByText('Network connection failed.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Check again' })).toBeInTheDocument();
  });
});
