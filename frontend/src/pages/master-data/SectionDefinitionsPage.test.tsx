import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '../../providers/ToastProvider';
import { useAuthStore } from '../../store/authStore';
import { superAdminSession } from '../../test/authFixtures';
import type {
  SectionAlias,
  SectionAliasProfile,
  SectionDefinition,
} from '../../types/sectionDefinition';
import { SectionDefinitionsPage } from './SectionDefinitionsPage';

const profile: SectionAliasProfile = {
  id: 'profile-id',
  code: 'DEFAULT-3LANG',
  name: 'Default Three-Language Section Profile',
  description: null,
  isDefault: true,
  isActive: true,
  createdBy: null,
  updatedBy: null,
  createdAt: '2026-07-26T08:00:00+08:00',
  updatedAt: '2026-07-26T08:00:00+08:00',
};

const definition: SectionDefinition = {
  id: 'definition-id',
  profileId: profile.id,
  canonicalCode: 'RESPONSIBILITY',
  displayName: 'Responsibility',
  description: null,
  displayOrder: 6,
  isRequiredDefault: true,
  isRepeatable: false,
  isActive: true,
  createdBy: null,
  updatedBy: null,
  createdAt: '2026-07-26T08:00:00+08:00',
  updatedAt: '2026-07-26T08:00:00+08:00',
};

const alias: SectionAlias = {
  id: 'alias-id',
  sectionDefinitionId: definition.id,
  canonicalCode: definition.canonicalCode,
  languageCode: 'id',
  aliasText: 'Tanggung Jawab',
  normalisedAlias: 'tanggung jawab',
  matchType: 'EXACT',
  priority: 100,
  isRegex: false,
  isActive: true,
  createdBy: null,
  updatedBy: null,
  createdAt: '2026-07-26T08:00:00+08:00',
  updatedAt: '2026-07-26T08:00:00+08:00',
};

const sectionMutations = vi.hoisted(() => ({
  createProfile: { mutateAsync: vi.fn(), isPending: false },
  updateProfile: { mutateAsync: vi.fn(), isPending: false },
  activateProfile: { mutateAsync: vi.fn(), isPending: false },
  deactivateProfile: { mutateAsync: vi.fn(), isPending: false },
  createDefinition: { mutateAsync: vi.fn(), isPending: false },
  updateDefinition: { mutateAsync: vi.fn(), isPending: false },
  activateDefinition: { mutateAsync: vi.fn(), isPending: false },
  deactivateDefinition: { mutateAsync: vi.fn(), isPending: false },
  createAlias: { mutateAsync: vi.fn(), isPending: false },
  updateAlias: { mutateAsync: vi.fn(), isPending: false },
  activateAlias: { mutateAsync: vi.fn(), isPending: false },
  deactivateAlias: { mutateAsync: vi.fn(), isPending: false },
  testMatch: {
    mutateAsync: vi.fn(),
    isPending: false,
    data: {
      matched: true,
      sectionDefinitionId: 'definition-id',
      canonicalCode: 'RESPONSIBILITY',
      displayName: 'Responsibility',
      languageCode: 'id',
      matchType: 'EXACT',
      confidence: 1,
      normalisedHeading: 'tanggung jawab',
      requiresReview: false,
    },
  },
  previewImport: {
    mutateAsync: vi.fn(),
    isPending: false,
    data: undefined,
    reset: vi.fn(),
  },
  confirmImport: { mutateAsync: vi.fn(), isPending: false },
  export: { mutateAsync: vi.fn(), isPending: false },
}));
const profilesHook = vi.hoisted(() => vi.fn());
const definitionsHook = vi.hoisted(() => vi.fn());
const aliasesHook = vi.hoisted(() => vi.fn());

vi.mock('../../hooks/useSectionDefinitions', () => ({
  useSectionAliasProfiles: (params: object) => profilesHook(params),
  useSectionDefinitions: (params: object) => definitionsHook(params),
  useSectionAliases: (params: object) => aliasesHook(params),
  useSectionDefinitionMutations: () => sectionMutations,
}));

const renderPage = () =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <ToastProvider>
          <SectionDefinitionsPage />
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );

describe('Section definitions management', () => {
  beforeEach(() => {
    useAuthStore.getState().setAuth(superAdminSession);
    Object.values(sectionMutations).forEach((mutation) => {
      mutation.mutateAsync.mockReset();
    });
    profilesHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        items: [profile],
        page: 1,
        pageSize: 20,
        totalItems: 1,
        totalPages: 1,
      },
      refetch: vi.fn(),
    });
    definitionsHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        items: [definition],
        page: 1,
        pageSize: 50,
        totalItems: 1,
        totalPages: 1,
      },
    });
    aliasesHook.mockReturnValue({
      isLoading: false,
      error: null,
      data: {
        items: [alias],
        page: 1,
        pageSize: 50,
        totalItems: 1,
        totalPages: 1,
      },
    });
  });

  it('renders profiles, canonical sections, aliases, and the heading matcher', async () => {
    renderPage();

    expect(screen.getAllByText(profile.name).length).toBeGreaterThan(0);
    expect(screen.getAllByText('RESPONSIBILITY').length).toBeGreaterThan(0);
    expect(screen.getByText('Tanggung Jawab')).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText('Heading'), '2. TANGGUNG JAWAB');
    await userEvent.click(screen.getByRole('button', { name: 'Test Heading Match' }));

    expect(sectionMutations.testMatch.mutateAsync).toHaveBeenCalledWith({
      headingText: '2. TANGGUNG JAWAB',
      profileId: profile.id,
    });
    expect(screen.getByText('100.0%')).toBeInTheDocument();
  });

  it('creates an Indonesian exact alias through the real mutation hook', async () => {
    sectionMutations.createAlias.mutateAsync.mockResolvedValue(alias);
    renderPage();

    await userEvent.click(screen.getByRole('button', { name: 'Add Alias' }));
    const drawer = screen.getByRole('dialog');
    await userEvent.selectOptions(within(drawer).getByLabelText('Language'), 'id');
    await userEvent.type(
      within(drawer).getByLabelText('Alias Text'),
      'Penanggung Jawab',
    );
    await userEvent.selectOptions(within(drawer).getByLabelText('Match Type'), 'EXACT');
    await userEvent.click(within(drawer).getByRole('button', { name: 'Save' }));

    expect(sectionMutations.createAlias.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        sectionDefinitionId: definition.id,
        languageCode: 'id',
        aliasText: 'Penanggung Jawab',
        matchType: 'EXACT',
      }),
    );
  });

  it('keeps configuration read-only without configure permission', () => {
    useAuthStore.getState().setAuth({
      ...superAdminSession,
      permissions: ['master_data:view'],
    });
    renderPage();

    expect(screen.getByText(/read-only access/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Add Alias' })).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Import XLSX' }),
    ).not.toBeInTheDocument();
  });
});
