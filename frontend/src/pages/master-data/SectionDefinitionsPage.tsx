import { Beaker, Download, Pencil, Plus, Power, Search, Upload } from 'lucide-react';
import { useEffect, useState, type FormEvent } from 'react';

import { getApiErrorMessage } from '../../api/errors';
import {
  Phase8ErrorAlert,
  Phase8FilterField,
  Phase8Loading,
  Phase8Pagination,
} from '../../components/compliance/Phase8TableUtilities';
import { ActiveStatusBadge } from '../../components/master-data/ActiveStatusBadge';
import { ConfirmationDialog } from '../../components/master-data/ConfirmationDialog';
import { MasterDataFormDrawer } from '../../components/master-data/MasterDataFormDrawer';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import {
  useSectionAliases,
  useSectionAliasProfiles,
  useSectionDefinitionMutations,
  useSectionDefinitions,
} from '../../hooks/useSectionDefinitions';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type { ImportMode } from '../../types/masterData';
import {
  sectionAliasLanguages,
  sectionAliasMatchTypes,
  type SectionAlias,
  type SectionAliasCreate,
  type SectionAliasLanguage,
  type SectionAliasProfile,
  type SectionAliasProfileCreate,
  type SectionDefinition,
  type SectionDefinitionCreate,
} from '../../types/sectionDefinition';
import { downloadFile } from '../../utils/downloadFile';

type DrawerState =
  | { type: 'profile'; item: SectionAliasProfile | null }
  | { type: 'definition'; item: SectionDefinition | null }
  | { type: 'alias'; item: SectionAlias | null }
  | null;

type StatusTarget =
  | { type: 'profile'; item: SectionAliasProfile }
  | { type: 'definition'; item: SectionDefinition }
  | { type: 'alias'; item: SectionAlias }
  | null;

export function SectionDefinitionsPage() {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canConfigure = hasPermission('compliance:configure_rules');
  const [profilePage, setProfilePage] = useState(1);
  const [selectedProfileId, setSelectedProfileId] = useState('');
  const [definitionPage, setDefinitionPage] = useState(1);
  const [selectedDefinitionId, setSelectedDefinitionId] = useState('');
  const [aliasPage, setAliasPage] = useState(1);
  const [languageCode, setLanguageCode] = useState<SectionAliasLanguage | ''>('');
  const [aliasSearch, setAliasSearch] = useState('');
  const [drawer, setDrawer] = useState<DrawerState>(null);
  const [statusTarget, setStatusTarget] = useState<StatusTarget>(null);
  const [importOpen, setImportOpen] = useState(false);
  const profilesQuery = useSectionAliasProfiles({
    page: profilePage,
    pageSize: 20,
    sortBy: 'code',
    sortOrder: 'asc',
  });
  const profileId =
    selectedProfileId ||
    profilesQuery.data?.items.find((profile) => profile.isDefault)?.id ||
    profilesQuery.data?.items[0]?.id ||
    '';
  const definitionsQuery = useSectionDefinitions({
    page: definitionPage,
    pageSize: 50,
    sortBy: 'displayOrder',
    sortOrder: 'asc',
    ...(profileId ? { profileId } : {}),
  });
  const definitionId =
    selectedDefinitionId || definitionsQuery.data?.items[0]?.id || '';
  const aliasesQuery = useSectionAliases({
    page: aliasPage,
    pageSize: 50,
    sortBy: 'priority',
    sortOrder: 'desc',
    ...(profileId ? { profileId } : {}),
    ...(definitionId ? { sectionDefinitionId: definitionId } : {}),
    ...(languageCode ? { languageCode } : {}),
    ...(aliasSearch.trim() ? { search: aliasSearch.trim() } : {}),
  });
  const mutations = useSectionDefinitionMutations();
  const { showToast } = useToast();

  useEffect(() => {
    if (
      selectedDefinitionId &&
      !definitionsQuery.data?.items.some(
        (definition) => definition.id === selectedDefinitionId,
      )
    ) {
      setSelectedDefinitionId('');
    }
  }, [definitionsQuery.data?.items, selectedDefinitionId]);

  const changeStatus = async (): Promise<void> => {
    if (!statusTarget) {
      return;
    }
    try {
      if (statusTarget.type === 'profile') {
        await (statusTarget.item.isActive
          ? mutations.deactivateProfile.mutateAsync(statusTarget.item.id)
          : mutations.activateProfile.mutateAsync(statusTarget.item.id));
      } else if (statusTarget.type === 'definition') {
        await (statusTarget.item.isActive
          ? mutations.deactivateDefinition.mutateAsync(statusTarget.item.id)
          : mutations.activateDefinition.mutateAsync(statusTarget.item.id));
      } else {
        await (statusTarget.item.isActive
          ? mutations.deactivateAlias.mutateAsync(statusTarget.item.id)
          : mutations.activateAlias.mutateAsync(statusTarget.item.id));
      }
      showToast({ tone: 'success', title: 'Status updated' });
      setStatusTarget(null);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Status could not be updated',
        message: getApiErrorMessage(error, 'Review dependent section aliases.'),
      });
    }
  };

  const exportDefinitions = async (): Promise<void> => {
    try {
      const result = await mutations.export.mutateAsync(profileId || undefined);
      downloadFile(result, 'section-definitions.xlsx');
      showToast({ tone: 'success', title: 'Section definitions exported' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Section definitions export failed',
        message: getApiErrorMessage(error, 'The workbook could not be downloaded.'),
      });
    }
  };

  const selectedProfile =
    profilesQuery.data?.items.find((profile) => profile.id === profileId) ?? null;
  const selectedDefinition =
    definitionsQuery.data?.items.find((definition) => definition.id === definitionId) ??
    null;

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Master Data"
        title="Section Definitions"
        description="Manage canonical sections and Indonesian, English, Mandarin, or language-neutral heading aliases with confidence-aware matching."
        actions={
          <>
            <button
              type="button"
              onClick={() => void exportDefinitions()}
              disabled={mutations.export.isPending}
              className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 px-3.5 text-sm font-semibold text-slate-700 disabled:opacity-50"
            >
              <Download className="size-4" aria-hidden="true" />
              Export XLSX
            </button>
            {canConfigure && (
              <button
                type="button"
                onClick={() => setImportOpen(true)}
                className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-3.5 text-sm font-semibold text-blue-700"
              >
                <Upload className="size-4" aria-hidden="true" />
                Import XLSX
              </button>
            )}
          </>
        }
      />
      {!canConfigure && (
        <p className="rounded-2xl border border-blue-200 bg-blue-50 p-4 text-xs leading-5 text-blue-800">
          You have read-only access. Changes require the compliance:configure_rules
          permission.
        </p>
      )}
      {profilesQuery.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            profilesQuery.error,
            'Section alias profiles could not be loaded.',
          )}
          onRetry={() => void profilesQuery.refetch()}
        />
      )}
      {profilesQuery.isLoading && <Phase8Loading label="Loading section definitions" />}
      {profilesQuery.data && (
        <div className="grid gap-5 xl:grid-cols-[17rem_minmax(0,0.85fr)_minmax(0,1.15fr)]">
          <section className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-sm font-semibold text-slate-950">Profiles</h2>
              {canConfigure && (
                <button
                  type="button"
                  onClick={() => setDrawer({ type: 'profile', item: null })}
                  aria-label="Add profile"
                  className="grid size-8 place-items-center rounded-lg bg-blue-50 text-blue-700"
                >
                  <Plus className="size-4" aria-hidden="true" />
                </button>
              )}
            </div>
            <div className="mt-4 space-y-2">
              {profilesQuery.data.items.map((profile) => (
                <button
                  key={profile.id}
                  type="button"
                  onClick={() => {
                    setSelectedProfileId(profile.id);
                    setSelectedDefinitionId('');
                    setDefinitionPage(1);
                    setAliasPage(1);
                  }}
                  className={`w-full rounded-xl border p-3 text-left ${
                    profile.id === profileId
                      ? 'border-blue-300 bg-blue-50'
                      : 'border-slate-200 hover:bg-slate-50'
                  }`}
                >
                  <span className="flex items-start justify-between gap-2">
                    <span>
                      <span className="block font-mono text-[10px] font-semibold text-slate-500">
                        {profile.code}
                      </span>
                      <span className="mt-1 block text-xs font-semibold text-slate-900">
                        {profile.name}
                      </span>
                    </span>
                    {profile.isDefault && (
                      <span className="rounded bg-amber-50 px-1.5 py-0.5 text-[9px] font-semibold text-amber-700">
                        Default
                      </span>
                    )}
                  </span>
                  <span className="mt-2 flex items-center justify-between">
                    <ActiveStatusBadge isActive={profile.isActive} />
                    {canConfigure && (
                      <span className="flex gap-1">
                        <span
                          role="button"
                          tabIndex={0}
                          aria-label={`Edit ${profile.name}`}
                          onClick={(event) => {
                            event.stopPropagation();
                            setDrawer({ type: 'profile', item: profile });
                          }}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter') {
                              event.stopPropagation();
                              setDrawer({ type: 'profile', item: profile });
                            }
                          }}
                          className="grid size-7 place-items-center rounded text-slate-500 hover:bg-white"
                        >
                          <Pencil className="size-3.5" />
                        </span>
                        <span
                          role="button"
                          tabIndex={0}
                          aria-label={`${profile.isActive ? 'Deactivate' : 'Activate'} ${profile.name}`}
                          onClick={(event) => {
                            event.stopPropagation();
                            setStatusTarget({ type: 'profile', item: profile });
                          }}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter') {
                              event.stopPropagation();
                              setStatusTarget({ type: 'profile', item: profile });
                            }
                          }}
                          className="grid size-7 place-items-center rounded text-slate-500 hover:bg-white"
                        >
                          <Power className="size-3.5" />
                        </span>
                      </span>
                    )}
                  </span>
                </button>
              ))}
            </div>
            <div className="mt-4">
              <Phase8Pagination
                page={profilePage}
                totalItems={profilesQuery.data.totalItems}
                totalPages={profilesQuery.data.totalPages}
                label="profiles"
                onPageChange={setProfilePage}
              />
            </div>
          </section>

          <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
            <header className="flex items-center justify-between gap-3 border-b border-slate-200 p-4">
              <div>
                <h2 className="text-sm font-semibold text-slate-950">
                  Canonical Sections
                </h2>
                <p className="mt-1 text-xs text-slate-500">
                  {selectedProfile?.name ?? 'Select a profile'}
                </p>
              </div>
              {canConfigure && profileId && (
                <button
                  type="button"
                  onClick={() => setDrawer({ type: 'definition', item: null })}
                  className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-blue-700 px-3 text-xs font-semibold text-white"
                >
                  <Plus className="size-3.5" aria-hidden="true" />
                  Add
                </button>
              )}
            </header>
            {definitionsQuery.error && (
              <div className="p-4">
                <Phase8ErrorAlert
                  message={getApiErrorMessage(
                    definitionsQuery.error,
                    'Canonical sections could not be loaded.',
                  )}
                />
              </div>
            )}
            <div className="max-h-[46rem] overflow-y-auto">
              {definitionsQuery.data?.items.map((definition) => (
                <button
                  key={definition.id}
                  type="button"
                  onClick={() => {
                    setSelectedDefinitionId(definition.id);
                    setAliasPage(1);
                  }}
                  className={`flex w-full items-start justify-between gap-3 border-b border-slate-100 p-4 text-left ${
                    definition.id === definitionId ? 'bg-blue-50' : 'hover:bg-slate-50'
                  }`}
                >
                  <span>
                    <span className="font-mono text-xs font-semibold text-slate-900">
                      {definition.canonicalCode}
                    </span>
                    <span className="mt-1 block text-xs text-slate-600">
                      {definition.displayName} · Order {definition.displayOrder}
                    </span>
                    <span className="mt-2 flex gap-2 text-[9px] font-semibold uppercase">
                      {definition.isRequiredDefault && (
                        <span className="rounded bg-amber-50 px-1.5 py-0.5 text-amber-700">
                          Required
                        </span>
                      )}
                      {definition.isRepeatable && (
                        <span className="rounded bg-violet-50 px-1.5 py-0.5 text-violet-700">
                          Repeatable
                        </span>
                      )}
                      <ActiveStatusBadge isActive={definition.isActive} />
                    </span>
                  </span>
                  {canConfigure && (
                    <span className="flex gap-1">
                      <span
                        role="button"
                        tabIndex={0}
                        aria-label={`Edit ${definition.canonicalCode}`}
                        onClick={(event) => {
                          event.stopPropagation();
                          setDrawer({ type: 'definition', item: definition });
                        }}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter') {
                            setDrawer({ type: 'definition', item: definition });
                          }
                        }}
                        className="grid size-8 place-items-center rounded-lg text-slate-500 hover:bg-white"
                      >
                        <Pencil className="size-3.5" />
                      </span>
                      <span
                        role="button"
                        tabIndex={0}
                        aria-label={`${definition.isActive ? 'Deactivate' : 'Activate'} ${definition.canonicalCode}`}
                        onClick={(event) => {
                          event.stopPropagation();
                          setStatusTarget({ type: 'definition', item: definition });
                        }}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter') {
                            setStatusTarget({ type: 'definition', item: definition });
                          }
                        }}
                        className="grid size-8 place-items-center rounded-lg text-slate-500 hover:bg-white"
                      >
                        <Power className="size-3.5" />
                      </span>
                    </span>
                  )}
                </button>
              ))}
              {definitionsQuery.data?.items.length === 0 && (
                <p className="p-8 text-center text-sm text-slate-500">
                  No canonical sections in this profile.
                </p>
              )}
            </div>
            {definitionsQuery.data && (
              <div className="p-4">
                <Phase8Pagination
                  page={definitionPage}
                  totalItems={definitionsQuery.data.totalItems}
                  totalPages={definitionsQuery.data.totalPages}
                  label="sections"
                  onPageChange={setDefinitionPage}
                />
              </div>
            )}
          </section>

          <section className="space-y-5">
            <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
              <header className="border-b border-slate-200 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h2 className="text-sm font-semibold text-slate-950">Aliases</h2>
                    <p className="mt-1 font-mono text-xs text-slate-500">
                      {selectedDefinition?.canonicalCode ?? 'Select a section'}
                    </p>
                  </div>
                  {canConfigure && definitionId && (
                    <button
                      type="button"
                      onClick={() => setDrawer({ type: 'alias', item: null })}
                      className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-blue-700 px-3 text-xs font-semibold text-white"
                    >
                      <Plus className="size-3.5" aria-hidden="true" />
                      Add Alias
                    </button>
                  )}
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <Phase8FilterField label="Language">
                    <select
                      value={languageCode}
                      onChange={(event) => {
                        setLanguageCode(
                          event.target.value as SectionAliasLanguage | '',
                        );
                        setAliasPage(1);
                      }}
                      className="min-h-10 w-full rounded-xl border border-slate-300 bg-white px-3 text-xs"
                    >
                      <option value="">All languages</option>
                      {sectionAliasLanguages.map((candidate) => (
                        <option key={candidate} value={candidate}>
                          {candidate.toUpperCase()}
                        </option>
                      ))}
                    </select>
                  </Phase8FilterField>
                  <Phase8FilterField label="Search">
                    <span className="relative block">
                      <Search
                        className="absolute left-3 top-3 size-3.5 text-slate-400"
                        aria-hidden="true"
                      />
                      <input
                        value={aliasSearch}
                        onChange={(event) => {
                          setAliasSearch(event.target.value);
                          setAliasPage(1);
                        }}
                        className="min-h-10 w-full rounded-xl border border-slate-300 pl-9 pr-3 text-xs"
                      />
                    </span>
                  </Phase8FilterField>
                </div>
              </header>
              {aliasesQuery.error && (
                <div className="p-4">
                  <Phase8ErrorAlert
                    message={getApiErrorMessage(
                      aliasesQuery.error,
                      'Section aliases could not be loaded.',
                    )}
                  />
                </div>
              )}
              <div className="overflow-x-auto">
                <table className="min-w-[42rem] divide-y divide-slate-200">
                  <thead className="bg-slate-50">
                    <tr>
                      {[
                        'Language',
                        'Alias',
                        'Match',
                        'Priority',
                        'Status',
                        'Actions',
                      ].map((heading) => (
                        <th
                          key={heading}
                          className="px-3 py-2.5 text-left text-[9px] font-semibold uppercase tracking-wide text-slate-500"
                        >
                          {heading}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {aliasesQuery.data?.items.map((alias) => (
                      <tr key={alias.id}>
                        <td className="px-3 py-3 text-xs font-semibold uppercase text-slate-600">
                          {alias.languageCode}
                        </td>
                        <td className="max-w-xs break-words px-3 py-3 text-xs text-slate-800">
                          {alias.aliasText}
                        </td>
                        <td className="px-3 py-3 text-[10px] text-slate-600">
                          {alias.matchType}
                          {alias.isRegex ? ' · Regex' : ''}
                        </td>
                        <td className="px-3 py-3 text-xs text-slate-600">
                          {alias.priority}
                        </td>
                        <td className="px-3 py-3">
                          <ActiveStatusBadge isActive={alias.isActive} />
                        </td>
                        <td className="px-3 py-3">
                          {canConfigure && (
                            <span className="flex gap-1">
                              <button
                                type="button"
                                onClick={() =>
                                  setDrawer({ type: 'alias', item: alias })
                                }
                                aria-label={`Edit alias ${alias.aliasText}`}
                                className="grid size-8 place-items-center rounded-lg text-slate-500 hover:bg-slate-100"
                              >
                                <Pencil className="size-3.5" aria-hidden="true" />
                              </button>
                              <button
                                type="button"
                                onClick={() =>
                                  setStatusTarget({ type: 'alias', item: alias })
                                }
                                aria-label={`${alias.isActive ? 'Deactivate' : 'Activate'} alias ${alias.aliasText}`}
                                className="grid size-8 place-items-center rounded-lg text-slate-500 hover:bg-slate-100"
                              >
                                <Power className="size-3.5" aria-hidden="true" />
                              </button>
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {aliasesQuery.data?.items.length === 0 && (
                <p className="p-8 text-center text-sm text-slate-500">
                  No aliases match this selection.
                </p>
              )}
              {aliasesQuery.data && (
                <div className="p-4">
                  <Phase8Pagination
                    page={aliasPage}
                    totalItems={aliasesQuery.data.totalItems}
                    totalPages={aliasesQuery.data.totalPages}
                    label="aliases"
                    onPageChange={setAliasPage}
                  />
                </div>
              )}
            </div>
            <SectionMatchTester profileId={profileId || null} />
          </section>
        </div>
      )}

      <MasterDataFormDrawer
        isOpen={drawer !== null}
        onClose={() => setDrawer(null)}
        title={
          drawer?.type === 'profile'
            ? `${drawer.item ? 'Edit' : 'Add'} Alias Profile`
            : drawer?.type === 'definition'
              ? `${drawer.item ? 'Edit' : 'Add'} Canonical Section`
              : `${drawer?.item ? 'Edit' : 'Add'} Section Alias`
        }
        description="Changes are validated and audited by the backend."
      >
        {drawer?.type === 'profile' && (
          <ProfileForm item={drawer.item} onDone={() => setDrawer(null)} />
        )}
        {drawer?.type === 'definition' && profileId && (
          <DefinitionForm
            profileId={profileId}
            item={drawer.item}
            onDone={() => setDrawer(null)}
          />
        )}
        {drawer?.type === 'alias' && definitionId && (
          <AliasForm
            definitionId={definitionId}
            item={drawer.item}
            onDone={() => setDrawer(null)}
          />
        )}
      </MasterDataFormDrawer>

      <ConfirmationDialog
        isOpen={statusTarget !== null}
        title={`${statusTarget?.item.isActive ? 'Deactivate' : 'Activate'} item?`}
        message="Existing compliance runs keep their saved rule snapshots. New validations use the updated active configuration."
        confirmLabel={statusTarget?.item.isActive ? 'Deactivate' : 'Activate'}
        tone={statusTarget?.item.isActive ? 'danger' : 'primary'}
        isPending={
          mutations.activateProfile.isPending ||
          mutations.deactivateProfile.isPending ||
          mutations.activateDefinition.isPending ||
          mutations.deactivateDefinition.isPending ||
          mutations.activateAlias.isPending ||
          mutations.deactivateAlias.isPending
        }
        onCancel={() => setStatusTarget(null)}
        onConfirm={() => void changeStatus()}
      />
      <SectionDefinitionImportDialog
        isOpen={importOpen}
        {...(profileId ? { profileId } : {})}
        onClose={() => setImportOpen(false)}
      />
    </div>
  );
}

function SectionMatchTester({ profileId }: { profileId: string | null }) {
  const [headingText, setHeadingText] = useState('');
  const mutations = useSectionDefinitionMutations();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const test = async (): Promise<void> => {
    if (!headingText.trim()) {
      setErrorMessage('Enter a heading to test.');
      return;
    }
    setErrorMessage(null);
    try {
      await mutations.testMatch.mutateAsync({
        headingText: headingText.trim(),
        profileId,
      });
    } catch (error: unknown) {
      setErrorMessage(getApiErrorMessage(error, 'The heading could not be tested.'));
    }
  };

  const result = mutations.testMatch.data;
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center gap-2">
        <Beaker className="size-4 text-violet-700" aria-hidden="true" />
        <h2 className="text-sm font-semibold text-slate-950">Match Tester</h2>
      </div>
      <label className="mt-4 block text-xs font-semibold text-slate-700">
        Heading
        <input
          value={headingText}
          onChange={(event) => setHeadingText(event.target.value)}
          placeholder="2. TANGGUNG JAWAB"
          className="mt-1.5 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
        />
      </label>
      <button
        type="button"
        onClick={() => void test()}
        disabled={mutations.testMatch.isPending}
        className="mt-3 min-h-10 rounded-xl bg-violet-700 px-4 text-sm font-semibold text-white disabled:opacity-50"
      >
        {mutations.testMatch.isPending ? 'Testing…' : 'Test Heading Match'}
      </button>
      {errorMessage && (
        <p role="alert" className="mt-3 text-xs text-rose-700">
          {errorMessage}
        </p>
      )}
      {result && (
        <dl className="mt-4 grid gap-3 rounded-2xl bg-slate-50 p-4 sm:grid-cols-2">
          <ResultItem
            label="Canonical"
            value={result.canonicalCode ?? 'No confident match'}
          />
          <ResultItem
            label="Language"
            value={result.languageCode?.toUpperCase() ?? '—'}
          />
          <ResultItem label="Match Type" value={result.matchType ?? '—'} />
          <ResultItem
            label="Confidence"
            value={`${(result.confidence * 100).toFixed(1)}%`}
          />
          {result.requiresReview && (
            <p className="text-xs font-semibold text-amber-700 sm:col-span-2">
              Manual review is recommended for this low-confidence match.
            </p>
          )}
        </dl>
      )}
    </section>
  );
}

function ResultItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] font-semibold uppercase text-slate-500">{label}</dt>
      <dd className="mt-1 text-sm font-semibold text-slate-900">{value}</dd>
    </div>
  );
}

function ProfileForm({
  item,
  onDone,
}: {
  item: SectionAliasProfile | null;
  onDone: () => void;
}) {
  const [code, setCode] = useState(item?.code ?? '');
  const [name, setName] = useState(item?.name ?? '');
  const [description, setDescription] = useState(item?.description ?? '');
  const [isDefault, setIsDefault] = useState(item?.isDefault ?? false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const mutations = useSectionDefinitionMutations();
  const { showToast } = useToast();

  const submit = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    if (!code.trim() || !name.trim()) {
      setErrorMessage('Code and name are required.');
      return;
    }
    const payload: SectionAliasProfileCreate = {
      code: code.trim().toUpperCase(),
      name: name.trim(),
      description: description.trim() || null,
      isDefault,
      isActive: item?.isActive ?? true,
    };
    try {
      if (item) {
        await mutations.updateProfile.mutateAsync({ id: item.id, payload });
      } else {
        await mutations.createProfile.mutateAsync(payload);
      }
      showToast({ tone: 'success', title: `Profile ${item ? 'updated' : 'created'}` });
      onDone();
    } catch (error: unknown) {
      setErrorMessage(getApiErrorMessage(error, 'The profile could not be saved.'));
    }
  };

  return (
    <form onSubmit={(event) => void submit(event)} className="space-y-4">
      <FormInput label="Code" value={code} onChange={setCode} />
      <FormInput label="Name" value={name} onChange={setName} />
      <FormTextarea label="Description" value={description} onChange={setDescription} />
      <CheckField label="Default profile" checked={isDefault} onChange={setIsDefault} />
      <FormActions
        errorMessage={errorMessage}
        isPending={
          mutations.createProfile.isPending || mutations.updateProfile.isPending
        }
        onCancel={onDone}
      />
    </form>
  );
}

function DefinitionForm({
  item,
  onDone,
  profileId,
}: {
  profileId: string;
  item: SectionDefinition | null;
  onDone: () => void;
}) {
  const [canonicalCode, setCanonicalCode] = useState(item?.canonicalCode ?? '');
  const [displayName, setDisplayName] = useState(item?.displayName ?? '');
  const [description, setDescription] = useState(item?.description ?? '');
  const [displayOrder, setDisplayOrder] = useState(String(item?.displayOrder ?? 1));
  const [isRequiredDefault, setRequiredDefault] = useState(
    item?.isRequiredDefault ?? false,
  );
  const [isRepeatable, setRepeatable] = useState(item?.isRepeatable ?? false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const mutations = useSectionDefinitionMutations();
  const { showToast } = useToast();

  const submit = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    const order = Number(displayOrder);
    if (
      !canonicalCode.trim() ||
      !displayName.trim() ||
      !Number.isInteger(order) ||
      order < 0
    ) {
      setErrorMessage('Canonical code, display name, and a valid order are required.');
      return;
    }
    const payload: SectionDefinitionCreate = {
      profileId,
      canonicalCode: canonicalCode.trim().toUpperCase(),
      displayName: displayName.trim(),
      description: description.trim() || null,
      displayOrder: order,
      isRequiredDefault,
      isRepeatable,
      isActive: item?.isActive ?? true,
    };
    try {
      if (item) {
        await mutations.updateDefinition.mutateAsync({
          id: item.id,
          payload: {
            canonicalCode: canonicalCode.trim().toUpperCase(),
            displayName: displayName.trim(),
            description: description.trim() || null,
            displayOrder: order,
            isRequiredDefault,
            isRepeatable,
            isActive: item.isActive,
          },
        });
      } else {
        await mutations.createDefinition.mutateAsync(payload);
      }
      showToast({
        tone: 'success',
        title: `Canonical section ${item ? 'updated' : 'created'}`,
      });
      onDone();
    } catch (error: unknown) {
      setErrorMessage(
        getApiErrorMessage(error, 'The canonical section could not be saved.'),
      );
    }
  };

  return (
    <form onSubmit={(event) => void submit(event)} className="space-y-4">
      <FormInput
        label="Canonical Code"
        value={canonicalCode}
        onChange={setCanonicalCode}
      />
      <FormInput label="Display Name" value={displayName} onChange={setDisplayName} />
      <FormTextarea label="Description" value={description} onChange={setDescription} />
      <FormInput
        label="Display Order"
        type="number"
        value={displayOrder}
        onChange={setDisplayOrder}
      />
      <CheckField
        label="Required by default"
        checked={isRequiredDefault}
        onChange={setRequiredDefault}
      />
      <CheckField
        label="Repeatable section"
        checked={isRepeatable}
        onChange={setRepeatable}
      />
      <FormActions
        errorMessage={errorMessage}
        isPending={
          mutations.createDefinition.isPending || mutations.updateDefinition.isPending
        }
        onCancel={onDone}
      />
    </form>
  );
}

function AliasForm({
  definitionId,
  item,
  onDone,
}: {
  definitionId: string;
  item: SectionAlias | null;
  onDone: () => void;
}) {
  const [languageCode, setLanguageCode] = useState<SectionAliasLanguage>(
    item?.languageCode ?? 'id',
  );
  const [aliasText, setAliasText] = useState(item?.aliasText ?? '');
  const [matchType, setMatchType] = useState(item?.matchType ?? 'EXACT');
  const [priority, setPriority] = useState(String(item?.priority ?? 100));
  const [isRegex, setRegex] = useState(item?.isRegex ?? false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const mutations = useSectionDefinitionMutations();
  const { showToast } = useToast();

  const submit = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    const parsedPriority = Number(priority);
    if (!aliasText.trim() || !Number.isInteger(parsedPriority) || parsedPriority < 0) {
      setErrorMessage('Alias text and a non-negative priority are required.');
      return;
    }
    const payload: SectionAliasCreate = {
      sectionDefinitionId: definitionId,
      languageCode,
      aliasText: aliasText.trim(),
      matchType,
      priority: parsedPriority,
      isRegex,
      isActive: item?.isActive ?? true,
    };
    try {
      if (item) {
        await mutations.updateAlias.mutateAsync({
          id: item.id,
          payload: {
            languageCode,
            aliasText: aliasText.trim(),
            matchType,
            priority: parsedPriority,
            isRegex,
            isActive: item.isActive,
          },
        });
      } else {
        await mutations.createAlias.mutateAsync(payload);
      }
      showToast({ tone: 'success', title: `Alias ${item ? 'updated' : 'created'}` });
      onDone();
    } catch (error: unknown) {
      setErrorMessage(getApiErrorMessage(error, 'The alias could not be saved.'));
    }
  };

  return (
    <form onSubmit={(event) => void submit(event)} className="space-y-4">
      <label className="block text-xs font-semibold text-slate-700">
        Language
        <select
          value={languageCode}
          onChange={(event) =>
            setLanguageCode(event.target.value as SectionAliasLanguage)
          }
          className="mt-1.5 min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
        >
          {sectionAliasLanguages.map((candidate) => (
            <option key={candidate} value={candidate}>
              {candidate.toUpperCase()}
            </option>
          ))}
        </select>
      </label>
      <FormInput label="Alias Text" value={aliasText} onChange={setAliasText} />
      <label className="block text-xs font-semibold text-slate-700">
        Match Type
        <select
          value={matchType}
          onChange={(event) =>
            setMatchType(event.target.value as (typeof sectionAliasMatchTypes)[number])
          }
          className="mt-1.5 min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
        >
          {sectionAliasMatchTypes.map((candidate) => (
            <option key={candidate} value={candidate}>
              {candidate}
            </option>
          ))}
        </select>
      </label>
      <FormInput
        label="Priority"
        type="number"
        value={priority}
        onChange={setPriority}
      />
      <CheckField label="Regular expression" checked={isRegex} onChange={setRegex} />
      {isRegex && (
        <p className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-800">
          Regex aliases are validated for length and unsafe complexity by the backend.
        </p>
      )}
      <FormActions
        errorMessage={errorMessage}
        isPending={mutations.createAlias.isPending || mutations.updateAlias.isPending}
        onCancel={onDone}
      />
    </form>
  );
}

function SectionDefinitionImportDialog({
  isOpen,
  profileId,
  onClose,
}: {
  isOpen: boolean;
  profileId?: string;
  onClose: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<ImportMode>('CREATE_ONLY');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const mutations = useSectionDefinitionMutations();
  const { showToast } = useToast();

  useEffect(() => {
    if (isOpen) {
      setFile(null);
      setMode('CREATE_ONLY');
      setErrorMessage(null);
      mutations.previewImport.reset();
    }
  }, [isOpen, mutations.previewImport]);

  if (!isOpen) {
    return null;
  }

  const preview = async (): Promise<void> => {
    if (!file) {
      setErrorMessage('Choose an XLSX workbook.');
      return;
    }
    try {
      await mutations.previewImport.mutateAsync({
        file,
        ...(profileId ? { profileId } : {}),
      });
    } catch (error: unknown) {
      setErrorMessage(
        getApiErrorMessage(error, 'The workbook could not be previewed.'),
      );
    }
  };

  const confirm = async (): Promise<void> => {
    const importToken = mutations.previewImport.data?.importToken;
    if (!importToken) {
      return;
    }
    try {
      const result = await mutations.confirmImport.mutateAsync({ importToken, mode });
      showToast({
        tone: 'success',
        title: 'Section aliases imported',
        message: `${result.created} created, ${result.updated} updated, ${result.skipped} skipped.`,
      });
      onClose();
    } catch (error: unknown) {
      setErrorMessage(getApiErrorMessage(error, 'The import could not be confirmed.'));
    }
  };

  const previewData = mutations.previewImport.data;
  return (
    <div
      className="fixed inset-0 z-[100] grid place-items-center overflow-y-auto bg-slate-950/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="section-import-title"
    >
      <div className="my-6 w-full max-w-4xl rounded-3xl bg-white p-6 shadow-2xl">
        <h2 id="section-import-title" className="text-lg font-semibold text-slate-950">
          Import Section Definitions
        </h2>
        <p className="mt-1 text-sm text-slate-600">
          Workbook sheets must be named Section Definitions and Section Aliases.
        </p>
        {!previewData && (
          <label className="mt-5 block rounded-2xl border border-dashed border-slate-300 p-5 text-xs font-semibold text-slate-700">
            XLSX workbook
            <input
              type="file"
              accept=".xlsx"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              className="mt-3 block w-full text-sm"
            />
          </label>
        )}
        {previewData && (
          <>
            <div className="mt-5 grid gap-3 sm:grid-cols-5">
              {[
                ['Definitions', previewData.definitions],
                ['Aliases', previewData.aliases],
                ['Valid', previewData.validRows],
                ['Invalid', previewData.invalidRows],
                ['Duplicate', previewData.duplicateRows],
              ].map(([label, value]) => (
                <div key={String(label)} className="rounded-xl bg-slate-50 p-3">
                  <p className="text-lg font-semibold text-slate-900">{value}</p>
                  <p className="text-[10px] uppercase text-slate-500">{label}</p>
                </div>
              ))}
            </div>
            <div className="mt-4 max-h-72 overflow-auto rounded-xl border border-slate-200">
              <table className="min-w-full divide-y divide-slate-200">
                <thead className="bg-slate-50">
                  <tr>
                    {['Sheet', 'Row', 'Status', 'Errors'].map((heading) => (
                      <th
                        key={heading}
                        className="px-3 py-2 text-left text-[10px] font-semibold uppercase text-slate-500"
                      >
                        {heading}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {previewData.rows.slice(0, 200).map((row) => (
                    <tr key={`${row.sheetName}-${row.rowNumber}`}>
                      <td className="px-3 py-2 text-xs text-slate-600">
                        {row.sheetName}
                      </td>
                      <td className="px-3 py-2 text-xs text-slate-600">
                        {row.rowNumber}
                      </td>
                      <td className="px-3 py-2 text-xs font-semibold text-slate-700">
                        {row.status}
                      </td>
                      <td className="px-3 py-2 text-xs text-rose-700">
                        {row.errors.join('; ') || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <label className="mt-4 block text-xs font-semibold text-slate-700">
              Import mode
              <select
                value={mode}
                onChange={(event) => setMode(event.target.value as ImportMode)}
                className="mt-1.5 min-h-11 w-full max-w-xs rounded-xl border border-slate-300 bg-white px-3 text-sm"
              >
                <option value="CREATE_ONLY">Create only</option>
                <option value="UPSERT">Create and update</option>
              </select>
            </label>
          </>
        )}
        {errorMessage && (
          <p role="alert" className="mt-3 text-xs text-rose-700">
            {errorMessage}
          </p>
        )}
        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="min-h-10 rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void (previewData ? confirm() : preview())}
            disabled={
              mutations.previewImport.isPending ||
              mutations.confirmImport.isPending ||
              (previewData?.invalidRows ?? 0) > 0
            }
            className="min-h-10 rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white disabled:opacity-50"
          >
            {mutations.previewImport.isPending
              ? 'Previewing…'
              : mutations.confirmImport.isPending
                ? 'Importing…'
                : previewData
                  ? 'Confirm Import'
                  : 'Preview'}
          </button>
        </div>
      </div>
    </div>
  );
}

function FormInput({
  label,
  onChange,
  type = 'text',
  value,
}: {
  label: string;
  value: string;
  type?: 'text' | 'number';
  onChange: (value: string) => void;
}) {
  return (
    <label className="block text-xs font-semibold text-slate-700">
      {label}
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1.5 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
      />
    </label>
  );
}

function FormTextarea({
  label,
  onChange,
  value,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block text-xs font-semibold text-slate-700">
      {label}
      <textarea
        rows={4}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1.5 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
      />
    </label>
  );
}

function CheckField({
  checked,
  label,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-3 text-sm font-medium text-slate-700">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="size-4 rounded border-slate-300"
      />
      {label}
    </label>
  );
}

function FormActions({
  errorMessage,
  isPending,
  onCancel,
}: {
  errorMessage: string | null;
  isPending: boolean;
  onCancel: () => void;
}) {
  return (
    <>
      {errorMessage && (
        <p role="alert" className="text-xs text-rose-700">
          {errorMessage}
        </p>
      )}
      <div className="flex justify-end gap-3 border-t border-slate-200 pt-4">
        <button
          type="button"
          onClick={onCancel}
          disabled={isPending}
          className="min-h-10 rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={isPending}
          className="min-h-10 rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white disabled:opacity-50"
        >
          {isPending ? 'Saving…' : 'Save'}
        </button>
      </div>
    </>
  );
}
