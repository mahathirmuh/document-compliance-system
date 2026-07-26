import { Archive, Download, Edit3, Plus, RotateCcw, Search } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import {
  Phase8ErrorAlert,
  Phase8FilterField,
  Phase8Loading,
  Phase8Pagination,
} from '../../components/compliance/Phase8TableUtilities';
import {
  GlossaryProfileDialog,
  GlossaryTermDialog,
  type GlossaryTermFormSubmission,
} from '../../components/glossary/GlossaryForms';
import { GlossaryImportPanel } from '../../components/glossary/GlossaryImportPanel';
import { GlossaryMatchTester } from '../../components/glossary/GlossaryMatchTester';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import {
  useGlossaryExceptions,
  useGlossaryMutations,
  useGlossaryProfiles,
  useGlossaryTerms,
} from '../../hooks/useGlossary';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import {
  glossaryExceptionScopeTypes,
  glossaryExceptionTypes,
  glossaryTermTypes,
  type GlossaryExceptionCreate,
  type GlossaryExceptionScopeType,
  type GlossaryExceptionType,
  type GlossaryImportPreview,
  type GlossaryLanguageCode,
  type GlossaryProfile,
  type GlossaryProfileCreate,
  type GlossaryTerm,
  type GlossaryTermType,
  type GlossaryTestMatchResult,
  type GlossaryTranslation,
} from '../../types/glossary';
import { downloadFile } from '../../utils/downloadFile';
import { formatDate, formatDateTime } from '../../utils/formatters';

type GlossaryTab =
  | 'profiles'
  | 'terms'
  | 'translations'
  | 'variants'
  | 'exceptions'
  | 'import'
  | 'export'
  | 'tester';

const tabs: readonly [GlossaryTab, string][] = [
  ['profiles', 'Glossary Profiles'],
  ['terms', 'Terms'],
  ['translations', 'Translations'],
  ['variants', 'Variants'],
  ['exceptions', 'Exceptions'],
  ['import', 'Import'],
  ['export', 'Export'],
  ['tester', 'Match Tester'],
];

export function GlossaryPage() {
  const { glossaryId } = useParams();
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canCreate = hasPermission('glossary:create');
  const canUpdate = hasPermission('glossary:update');
  const canArchive = hasPermission('glossary:delete');
  const canImport = hasPermission('glossary:import');
  const canExport = hasPermission('glossary:export');
  const canManageExceptions = hasPermission('glossary:manage_exceptions');
  const [tab, setTab] = useState<GlossaryTab>(glossaryId ? 'terms' : 'profiles');
  const [searchInput, setSearchInput] = useState('');
  const search = useDebouncedValue(searchInput.trim(), 350);
  const [profileId, setProfileId] = useState(glossaryId ?? '');
  const [languageCode, setLanguageCode] = useState<GlossaryLanguageCode | ''>('');
  const [termType, setTermType] = useState<GlossaryTermType | ''>('');
  const [activeFilter, setActiveFilter] = useState<'all' | 'active' | 'inactive'>(
    'active',
  );
  const [page, setPage] = useState(1);
  const [profileDialog, setProfileDialog] = useState<GlossaryProfile | 'create' | null>(
    null,
  );
  const [termDialog, setTermDialog] = useState<GlossaryTerm | 'create' | null>(null);
  const [importPreview, setImportPreview] = useState<GlossaryImportPreview | null>(
    null,
  );
  const [matchResults, setMatchResults] = useState<readonly GlossaryTestMatchResult[]>(
    [],
  );
  const mutations = useGlossaryMutations();
  const { showToast } = useToast();

  useEffect(() => {
    if (glossaryId) {
      setProfileId(glossaryId);
      setTab('terms');
    }
  }, [glossaryId]);

  const commonParams = {
    page,
    pageSize: 50,
    ...(search ? { search } : {}),
    ...(profileId ? { profileId } : {}),
    ...(languageCode ? { languageCode } : {}),
    ...(termType ? { termType } : {}),
    ...(activeFilter === 'active' ? { isActive: true } : {}),
    ...(activeFilter === 'inactive' ? { isActive: false } : {}),
  };
  const profilesQuery = useGlossaryProfiles({
    page: 1,
    pageSize: 100,
    ...(search && tab === 'profiles' ? { search } : {}),
    ...(activeFilter === 'active' ? { isActive: true } : {}),
    ...(activeFilter === 'inactive' ? { isActive: false } : {}),
  });
  const termsQuery = useGlossaryTerms(commonParams);
  const exceptionsQuery = useGlossaryExceptions(commonParams);
  const profiles = profilesQuery.data?.items ?? [];
  const terms = useMemo(() => termsQuery.data?.items ?? [], [termsQuery.data?.items]);

  const translations = useMemo(
    () =>
      terms.flatMap((term) =>
        term.translations.map((translation) => ({ term, translation })),
      ),
    [terms],
  );
  const variants = useMemo(
    () =>
      translations.flatMap(({ term, translation }) =>
        (translation.variants ?? []).map((variant) => ({
          term,
          translation,
          variant,
        })),
      ),
    [translations],
  );

  const saveProfile = async (payload: GlossaryProfileCreate): Promise<void> => {
    try {
      if (profileDialog && profileDialog !== 'create') {
        await mutations.updateProfile.mutateAsync({
          profileId: profileDialog.id,
          payload,
        });
      } else {
        await mutations.createProfile.mutateAsync(payload);
      }
      showToast({
        tone: 'success',
        title:
          profileDialog === 'create'
            ? 'Glossary profile created'
            : 'Glossary profile updated',
      });
      setProfileDialog(null);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Glossary profile could not be saved',
        message: getApiErrorMessage(error, 'Review the scope and code.'),
      });
    }
  };

  const saveTerm = async (submission: GlossaryTermFormSubmission): Promise<void> => {
    try {
      const editingTerm = termDialog && termDialog !== 'create' ? termDialog : null;
      const { glossaryProfileId: _profileId, ...updatePayload } = submission.term;
      void _profileId;
      const savedTerm = editingTerm
        ? await mutations.updateTerm.mutateAsync({
            termId: editingTerm.id,
            payload: updatePayload,
          })
        : await mutations.createTerm.mutateAsync(submission.term);
      const resolvedTranslations = new Map<GlossaryLanguageCode, GlossaryTranslation>();
      for (const languageCode of ['id', 'en', 'zh'] as const) {
        const payload = submission.translations[languageCode];
        if (!payload) {
          continue;
        }
        const existing = editingTerm?.translations.find(
          (translation) => translation.languageCode === languageCode,
        );
        const savedTranslation = existing
          ? await mutations.updateTranslation.mutateAsync({
              translationId: existing.id,
              payload,
            })
          : await mutations.addTranslation.mutateAsync({
              termId: savedTerm.id,
              payload,
            });
        resolvedTranslations.set(languageCode, savedTranslation);
      }
      if (submission.variant) {
        const translation =
          resolvedTranslations.get(submission.variant.languageCode) ??
          editingTerm?.translations.find(
            (candidate) => candidate.languageCode === submission.variant?.languageCode,
          );
        if (translation) {
          await mutations.addVariant.mutateAsync({
            translationId: translation.id,
            payload: submission.variant.payload,
          });
        }
      }
      showToast({
        tone: 'success',
        title: editingTerm ? 'Glossary term updated' : 'Glossary term created',
      });
      setTermDialog(null);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Glossary term could not be saved',
        message: getApiErrorMessage(
          error,
          'Review translations, regex, and duplicate term codes.',
        ),
      });
    }
  };

  const changeArchiveState = async (
    entity: GlossaryProfile | GlossaryTerm,
    kind: 'profile' | 'term',
  ): Promise<void> => {
    try {
      if (kind === 'profile') {
        if (entity.isActive) {
          await mutations.archiveProfile.mutateAsync(entity.id);
        } else {
          await mutations.restoreProfile.mutateAsync(entity.id);
        }
      } else if (entity.isActive) {
        await mutations.archiveTerm.mutateAsync(entity.id);
      } else {
        await mutations.restoreTerm.mutateAsync(entity.id);
      }
      showToast({
        tone: 'success',
        title: `${kind === 'profile' ? 'Profile' : 'Term'} ${
          entity.isActive ? 'archived' : 'restored'
        }`,
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Glossary state could not be changed',
        message: getApiErrorMessage(error, 'Refresh and try again.'),
      });
    }
  };

  const runExport = async (format: 'json' | 'xlsx'): Promise<void> => {
    try {
      const result = await mutations.export.mutateAsync({
        format,
        params: {
          ...(profileId ? { profileIds: [profileId] } : {}),
          ...(activeFilter !== 'active' ? { includeInactive: true } : {}),
        },
      });
      downloadFile(result, `glossary_export.${format}`);
      showToast({ tone: 'success', title: `Glossary ${format.toUpperCase()} ready` });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Glossary export failed',
        message: getApiErrorMessage(error, 'Try again.'),
      });
    }
  };

  const isLoading = profilesQuery.isLoading || termsQuery.isLoading;
  const queryError = profilesQuery.error ?? termsQuery.error;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <MasterDataPageHeader
          eyebrow="Master Data"
          title="Glossary"
          description="Manage scoped concepts, Indonesian/English/Chinese translations, allowed variants, audited exceptions, and validation imports."
        />
        <div className="flex flex-wrap gap-2">
          {canCreate && (
            <>
              <button
                type="button"
                onClick={() => {
                  setProfileDialog('create');
                  setTab('profiles');
                }}
                className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-4 text-xs font-semibold text-blue-700"
              >
                <Plus className="size-4" aria-hidden="true" />
                New Profile
              </button>
              <button
                type="button"
                onClick={() => {
                  setTermDialog('create');
                  setTab('terms');
                }}
                disabled={profiles.length === 0}
                className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-blue-700 px-4 text-xs font-semibold text-white disabled:opacity-50"
              >
                <Plus className="size-4" aria-hidden="true" />
                New Term
              </button>
            </>
          )}
        </div>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white px-3">
        <div className="flex min-w-max">
          {tabs.map(([candidate, label]) => {
            const hidden =
              (candidate === 'import' && !canImport) ||
              (candidate === 'export' && !canExport) ||
              (candidate === 'exceptions' && !hasPermission('glossary:view'));
            if (hidden) {
              return null;
            }
            return (
              <button
                key={candidate}
                type="button"
                onClick={() => setTab(candidate)}
                className={`min-h-12 border-b-2 px-4 text-xs font-semibold ${
                  tab === candidate
                    ? 'border-blue-700 text-blue-700'
                    : 'border-transparent text-slate-500 hover:text-slate-900'
                }`}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>

      {!['import', 'export', 'tester'].includes(tab) && (
        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            <Phase8FilterField label="Search">
              <span className="relative block">
                <Search
                  className="pointer-events-none absolute left-3 top-3.5 size-4 text-slate-400"
                  aria-hidden="true"
                />
                <input
                  value={searchInput}
                  onChange={(event) => {
                    setSearchInput(event.target.value);
                    setPage(1);
                  }}
                  placeholder="Code, concept, or term"
                  className="min-h-11 w-full rounded-xl border border-slate-300 pl-10 pr-3 text-sm"
                />
              </span>
            </Phase8FilterField>
            <FilterSelect
              label="Profile"
              value={profileId}
              onChange={(value) => {
                setProfileId(value);
                setPage(1);
              }}
              options={[
                ['', 'All profiles'],
                ...profiles.map(
                  (profile) =>
                    [profile.id, `${profile.code} — ${profile.name}`] as const,
                ),
              ]}
            />
            <FilterSelect
              label="Language"
              value={languageCode}
              onChange={(value) => {
                setLanguageCode(value as GlossaryLanguageCode | '');
                setPage(1);
              }}
              options={[
                ['', 'All languages'],
                ['id', 'Indonesian'],
                ['en', 'English'],
                ['zh', 'Chinese'],
              ]}
            />
            <FilterSelect
              label="Term Type"
              value={termType}
              onChange={(value) => {
                setTermType(value as GlossaryTermType | '');
                setPage(1);
              }}
              options={[
                ['', 'All types'],
                ...glossaryTermTypes.map(
                  (type) => [type, type.replaceAll('_', ' ')] as const,
                ),
              ]}
            />
            <FilterSelect
              label="Status"
              value={activeFilter}
              onChange={(value) => {
                setActiveFilter(value as 'all' | 'active' | 'inactive');
                setPage(1);
              }}
              options={[
                ['all', 'All'],
                ['active', 'Active'],
                ['inactive', 'Inactive'],
              ]}
            />
          </div>
        </section>
      )}

      {isLoading && !['import', 'export', 'tester'].includes(tab) && (
        <Phase8Loading label="Loading glossary" />
      )}
      {queryError && !['import', 'export', 'tester'].includes(tab) && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(queryError, 'Glossary data could not be loaded.')}
          onRetry={() => {
            void profilesQuery.refetch();
            void termsQuery.refetch();
          }}
        />
      )}

      {!isLoading && !queryError && tab === 'profiles' && (
        <ProfilesTable
          profiles={profiles}
          canUpdate={canUpdate}
          canArchive={canArchive}
          onEdit={setProfileDialog}
          onArchive={(profile) => void changeArchiveState(profile, 'profile')}
        />
      )}
      {!isLoading && !queryError && tab === 'terms' && (
        <>
          <TermsTable
            terms={terms}
            profiles={profiles}
            canUpdate={canUpdate}
            canArchive={canArchive}
            onEdit={setTermDialog}
            onArchive={(term) => void changeArchiveState(term, 'term')}
          />
          {termsQuery.data && (
            <Phase8Pagination
              page={page}
              pageSize={50}
              totalItems={termsQuery.data.totalItems}
              totalPages={termsQuery.data.totalPages}
              label="glossary terms"
              onPageChange={setPage}
            />
          )}
        </>
      )}
      {!isLoading && !queryError && tab === 'translations' && (
        <TranslationsTable rows={translations} />
      )}
      {!isLoading && !queryError && tab === 'variants' && (
        <VariantsTable rows={variants} />
      )}
      {tab === 'exceptions' && (
        <ExceptionsPanel
          canManage={canManageExceptions}
          terms={terms}
          exceptions={exceptionsQuery.data?.items ?? []}
          pending={mutations.createException.isPending}
          onCreate={async (payload) => {
            try {
              await mutations.createException.mutateAsync(payload);
              showToast({ tone: 'success', title: 'Glossary exception created' });
            } catch (error: unknown) {
              showToast({
                tone: 'error',
                title: 'Exception could not be created',
                message: getApiErrorMessage(
                  error,
                  'A reason and valid scope are required.',
                ),
              });
            }
          }}
          onDeactivate={async (exceptionId) => {
            try {
              await mutations.deactivateException.mutateAsync(exceptionId);
              showToast({ tone: 'success', title: 'Exception deactivated' });
            } catch (error: unknown) {
              showToast({
                tone: 'error',
                title: 'Exception could not be deactivated',
                message: getApiErrorMessage(error, 'Try again.'),
              });
            }
          }}
        />
      )}
      {tab === 'import' && canImport && (
        <GlossaryImportPanel
          preview={importPreview}
          previewPending={mutations.previewImport.isPending}
          confirmPending={mutations.confirmImport.isPending}
          onDownloadTemplate={async () => {
            const result = await mutations.template.mutateAsync();
            downloadFile(result, 'glossary_import_template.xlsx');
          }}
          onPreview={async (file) => {
            try {
              setImportPreview(await mutations.previewImport.mutateAsync(file));
            } catch (error: unknown) {
              showToast({
                tone: 'error',
                title: 'Import preview failed',
                message: getApiErrorMessage(error, 'Use a valid XLSX template.'),
              });
              throw error;
            }
          }}
          onConfirm={async (file, mode) => {
            try {
              const result = await mutations.confirmImport.mutateAsync({
                file,
                mode,
              });
              showToast({
                tone: 'success',
                title: 'Glossary imported',
                message: `${result.created.terms ?? 0} terms and ${
                  result.created.translations ?? 0
                } translations created.`,
              });
              setImportPreview(null);
            } catch (error: unknown) {
              showToast({
                tone: 'error',
                title: 'Glossary import failed',
                message: getApiErrorMessage(error, 'Run preview again.'),
              });
            }
          }}
        />
      )}
      {tab === 'export' && canExport && (
        <section className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-950">Export Glossary</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Export follows the selected profile, active-state selection, and your
            authorized department scope. Exceptions outside your scope are excluded.
          </p>
          <div className="mt-5 flex gap-3">
            {(['xlsx', 'json'] as const).map((format) => (
              <button
                key={format}
                type="button"
                onClick={() => void runExport(format)}
                disabled={mutations.export.isPending}
                className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 px-4 text-xs font-semibold uppercase text-slate-700 disabled:opacity-50"
              >
                <Download className="size-4" aria-hidden="true" />
                {format}
              </button>
            ))}
          </div>
        </section>
      )}
      {tab === 'tester' && (
        <GlossaryMatchTester
          profiles={profiles}
          results={matchResults}
          isPending={mutations.testMatch.isPending}
          onTest={async (payload) => {
            try {
              setMatchResults(await mutations.testMatch.mutateAsync(payload));
            } catch (error: unknown) {
              showToast({
                tone: 'error',
                title: 'Glossary match test failed',
                message: getApiErrorMessage(error, 'Review the test text and profile.'),
              });
            }
          }}
        />
      )}

      <GlossaryProfileDialog
        open={profileDialog !== null}
        profile={profileDialog === 'create' ? null : profileDialog}
        isPending={
          mutations.createProfile.isPending || mutations.updateProfile.isPending
        }
        onClose={() => setProfileDialog(null)}
        onSubmit={saveProfile}
      />
      <GlossaryTermDialog
        open={termDialog !== null}
        term={termDialog === 'create' ? null : termDialog}
        profiles={profiles}
        isPending={
          mutations.createTerm.isPending ||
          mutations.updateTerm.isPending ||
          mutations.addTranslation.isPending ||
          mutations.updateTranslation.isPending ||
          mutations.addVariant.isPending
        }
        onClose={() => setTermDialog(null)}
        onSubmit={saveTerm}
      />
    </div>
  );
}

function ProfilesTable({
  canArchive,
  canUpdate,
  onArchive,
  onEdit,
  profiles,
}: {
  profiles: readonly GlossaryProfile[];
  canUpdate: boolean;
  canArchive: boolean;
  onEdit: (profile: GlossaryProfile) => void;
  onArchive: (profile: GlossaryProfile) => void;
}) {
  return (
    <TableShell empty={profiles.length === 0} emptyLabel="No glossary profiles found.">
      <table className="min-w-[75rem] divide-y divide-slate-200">
        <thead className="bg-slate-50">
          <HeaderRow
            headings={[
              'Code',
              'Name',
              'Scope',
              'Department',
              'Document Type',
              'Default',
              'Version',
              'Status',
              'Updated',
              'Actions',
            ]}
          />
        </thead>
        <tbody className="divide-y divide-slate-100">
          {profiles.map((profile) => (
            <tr key={profile.id}>
              <Cell strong>{profile.code}</Cell>
              <Cell>{profile.name}</Cell>
              <Cell>{profile.scopeType.replaceAll('_', ' ')}</Cell>
              <Cell>{profile.departmentId ?? '—'}</Cell>
              <Cell>{profile.documentTypeId ?? '—'}</Cell>
              <Cell>{profile.isDefault ? 'Yes' : 'No'}</Cell>
              <Cell>{profile.version}</Cell>
              <Cell>{profile.isActive ? 'Active' : 'Inactive'}</Cell>
              <Cell>{formatDateTime(profile.updatedAt)}</Cell>
              <td className="px-4 py-3">
                <div className="flex gap-1">
                  {canUpdate && (
                    <ActionButton
                      label="Edit"
                      icon={Edit3}
                      onClick={() => onEdit(profile)}
                    />
                  )}
                  {canArchive && (
                    <ActionButton
                      label={profile.isActive ? 'Archive' : 'Restore'}
                      icon={profile.isActive ? Archive : RotateCcw}
                      onClick={() => onArchive(profile)}
                    />
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableShell>
  );
}

function TermsTable({
  canArchive,
  canUpdate,
  onArchive,
  onEdit,
  profiles,
  terms,
}: {
  terms: readonly GlossaryTerm[];
  profiles: readonly GlossaryProfile[];
  canUpdate: boolean;
  canArchive: boolean;
  onEdit: (term: GlossaryTerm) => void;
  onArchive: (term: GlossaryTerm) => void;
}) {
  return (
    <TableShell empty={terms.length === 0} emptyLabel="No glossary terms found.">
      <table className="min-w-[85rem] divide-y divide-slate-200">
        <thead className="bg-slate-50">
          <HeaderRow
            headings={[
              'Term Code',
              'Concept',
              'Profile',
              'Type',
              'Severity',
              'Indonesian',
              'English',
              'Chinese',
              'Matching',
              'Status',
              'Actions',
            ]}
          />
        </thead>
        <tbody className="divide-y divide-slate-100">
          {terms.map((term) => (
            <tr key={term.id} className="align-top">
              <Cell strong>{term.termCode}</Cell>
              <Cell>{term.conceptName}</Cell>
              <Cell>
                {profiles.find((profile) => profile.id === term.glossaryProfileId)
                  ?.code ?? term.glossaryProfileId}
              </Cell>
              <Cell>{term.termType}</Cell>
              <Cell>{term.severity}</Cell>
              {(['id', 'en', 'zh'] as const).map((language) => (
                <Cell key={language}>
                  {term.translations
                    .filter((translation) => translation.languageCode === language)
                    .map((translation) => translation.termText)
                    .join(', ') || '—'}
                </Cell>
              ))}
              <Cell>
                {[
                  term.isCaseSensitive && 'Case',
                  term.matchWholeWord && 'Whole word',
                  term.allowInflection && 'Inflection',
                  term.isRegex && 'Regex',
                ]
                  .filter(Boolean)
                  .join(', ') || 'Default'}
              </Cell>
              <Cell>{term.isActive ? 'Active' : 'Inactive'}</Cell>
              <td className="px-4 py-3">
                <div className="flex gap-1">
                  {canUpdate && (
                    <ActionButton
                      label="Edit"
                      icon={Edit3}
                      onClick={() => onEdit(term)}
                    />
                  )}
                  {canArchive && (
                    <ActionButton
                      label={term.isActive ? 'Archive' : 'Restore'}
                      icon={term.isActive ? Archive : RotateCcw}
                      onClick={() => onArchive(term)}
                    />
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableShell>
  );
}

function TranslationsTable({
  rows,
}: {
  rows: readonly { term: GlossaryTerm; translation: GlossaryTranslation }[];
}) {
  return (
    <TableShell empty={rows.length === 0} emptyLabel="No translations found.">
      <table className="min-w-[80rem] divide-y divide-slate-200">
        <thead className="bg-slate-50">
          <HeaderRow
            headings={[
              'Concept',
              'Term Code',
              'Language',
              'Term Text',
              'Preferred',
              'Forbidden',
              'Required',
              'Priority',
              'Usage Note',
              'Example',
              'Status',
            ]}
          />
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map(({ term, translation }) => (
            <tr key={translation.id}>
              <Cell strong>{term.conceptName}</Cell>
              <Cell>{term.termCode}</Cell>
              <Cell>{translation.languageCode.toUpperCase()}</Cell>
              <Cell>{translation.termText}</Cell>
              <Cell>{translation.isPreferred ? 'Yes' : 'No'}</Cell>
              <Cell>{translation.isForbidden ? 'Yes' : 'No'}</Cell>
              <Cell>{translation.isRequired ? 'Yes' : 'No'}</Cell>
              <Cell>{translation.priority}</Cell>
              <Cell>{translation.usageNote ?? '—'}</Cell>
              <Cell>{translation.exampleText ?? '—'}</Cell>
              <Cell>{translation.isActive ? 'Active' : 'Inactive'}</Cell>
            </tr>
          ))}
        </tbody>
      </table>
    </TableShell>
  );
}

function VariantsTable({
  rows,
}: {
  rows: readonly {
    term: GlossaryTerm;
    translation: GlossaryTranslation;
    variant: NonNullable<GlossaryTranslation['variants']>[number];
  }[];
}) {
  return (
    <TableShell empty={rows.length === 0} emptyLabel="No variants found.">
      <table className="min-w-[70rem] divide-y divide-slate-200">
        <thead className="bg-slate-50">
          <HeaderRow
            headings={[
              'Concept',
              'Language',
              'Preferred Term',
              'Variant',
              'Type',
              'Allowed',
              'Status',
              'Updated',
            ]}
          />
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map(({ term, translation, variant }) => (
            <tr key={variant.id}>
              <Cell strong>{term.conceptName}</Cell>
              <Cell>{translation.languageCode.toUpperCase()}</Cell>
              <Cell>{translation.termText}</Cell>
              <Cell>{variant.variantText}</Cell>
              <Cell>{variant.variantType.replaceAll('_', ' ')}</Cell>
              <Cell>{variant.isAllowed ? 'Yes' : 'No'}</Cell>
              <Cell>{variant.isActive ? 'Active' : 'Inactive'}</Cell>
              <Cell>{formatDateTime(variant.updatedAt)}</Cell>
            </tr>
          ))}
        </tbody>
      </table>
    </TableShell>
  );
}

function ExceptionsPanel({
  canManage,
  exceptions,
  onCreate,
  onDeactivate,
  pending,
  terms,
}: {
  terms: readonly GlossaryTerm[];
  exceptions: ReturnType<typeof useGlossaryExceptions>['data'] extends
    { items: infer TItems } | undefined
    ? TItems extends readonly (infer TItem)[]
      ? readonly TItem[]
      : never
    : never;
  canManage: boolean;
  pending: boolean;
  onCreate: (payload: GlossaryExceptionCreate) => Promise<void>;
  onDeactivate: (exceptionId: string) => Promise<void>;
}) {
  const [termId, setTermId] = useState('');
  const [scopeType, setScopeType] = useState<GlossaryExceptionScopeType>('GLOBAL');
  const [scopeId, setScopeId] = useState('');
  const [languageCode, setLanguageCode] = useState<GlossaryLanguageCode | ''>('');
  const [exceptionType, setExceptionType] =
    useState<GlossaryExceptionType>('ALLOW_VARIANT');
  const [reason, setReason] = useState('');
  const [effectiveFrom, setEffectiveFrom] = useState('');
  const [effectiveTo, setEffectiveTo] = useState('');

  return (
    <div className="space-y-5">
      {canManage && (
        <form
          className="rounded-2xl border border-slate-200 bg-white p-5"
          onSubmit={(event) => {
            event.preventDefault();
            if (
              !termId ||
              !reason.trim() ||
              (scopeType !== 'GLOBAL' && !scopeId.trim()) ||
              (effectiveFrom && effectiveTo && effectiveFrom > effectiveTo)
            ) {
              return;
            }
            const scopeTarget = scopeId.trim() || null;
            const scoped: Partial<GlossaryExceptionCreate> =
              scopeType === 'DEPARTMENT'
                ? { departmentId: scopeTarget }
                : scopeType === 'DOCUMENT'
                  ? { documentId: scopeTarget }
                  : scopeType === 'DOCUMENT_REVISION'
                    ? { documentRevisionId: scopeTarget }
                    : scopeType === 'DOCUMENT_FILE'
                      ? { documentFileId: scopeTarget }
                      : scopeType === 'SECTION'
                        ? { sectionDefinitionId: scopeTarget }
                        : {};
            void onCreate({
              glossaryTermId: termId,
              scopeType,
              ...scoped,
              languageCode: languageCode || null,
              exceptionType,
              reason: reason.trim(),
              effectiveFrom: effectiveFrom || null,
              effectiveTo: effectiveTo || null,
              isActive: true,
            }).then(() => setReason(''));
          }}
        >
          <h2 className="text-sm font-semibold text-slate-950">
            Add Glossary Exception
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Reason is required and every scope change is audited.
          </p>
          <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <FilterSelect
              label="Term"
              value={termId}
              onChange={setTermId}
              options={[
                ['', 'Select term'],
                ...terms.map(
                  (term) =>
                    [term.id, `${term.termCode} — ${term.conceptName}`] as const,
                ),
              ]}
            />
            <FilterSelect
              label="Exception Type"
              value={exceptionType}
              onChange={(value) => setExceptionType(value as GlossaryExceptionType)}
              options={glossaryExceptionTypes.map(
                (type) => [type, type.replaceAll('_', ' ')] as const,
              )}
            />
            <FilterSelect
              label="Scope"
              value={scopeType}
              onChange={(value) => setScopeType(value as GlossaryExceptionScopeType)}
              options={glossaryExceptionScopeTypes.map(
                (scope) => [scope, scope.replaceAll('_', ' ')] as const,
              )}
            />
            {scopeType !== 'GLOBAL' && (
              <Phase8FilterField label="Scope Target ID">
                <input
                  required
                  value={scopeId}
                  onChange={(event) => setScopeId(event.target.value)}
                  className="min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
                />
              </Phase8FilterField>
            )}
            <FilterSelect
              label="Language"
              value={languageCode}
              onChange={(value) => setLanguageCode(value as GlossaryLanguageCode | '')}
              options={[
                ['', 'All languages'],
                ['id', 'Indonesian'],
                ['en', 'English'],
                ['zh', 'Chinese'],
              ]}
            />
            <Phase8FilterField label="Effective From">
              <input
                type="date"
                value={effectiveFrom}
                onChange={(event) => setEffectiveFrom(event.target.value)}
                className="min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
              />
            </Phase8FilterField>
            <Phase8FilterField label="Effective To">
              <input
                type="date"
                min={effectiveFrom || undefined}
                value={effectiveTo}
                onChange={(event) => setEffectiveTo(event.target.value)}
                className="min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
              />
            </Phase8FilterField>
            <Phase8FilterField label="Reason">
              <input
                required
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                className="min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
              />
            </Phase8FilterField>
          </div>
          <button
            type="submit"
            disabled={
              !termId ||
              !reason.trim() ||
              (scopeType !== 'GLOBAL' && !scopeId.trim()) ||
              Boolean(effectiveFrom && effectiveTo && effectiveFrom > effectiveTo) ||
              pending
            }
            className="mt-4 min-h-10 rounded-xl bg-blue-700 px-4 text-xs font-semibold text-white disabled:opacity-50"
          >
            Add Exception
          </button>
        </form>
      )}
      <TableShell empty={exceptions.length === 0} emptyLabel="No exceptions found.">
        <table className="min-w-[85rem] divide-y divide-slate-200">
          <thead className="bg-slate-50">
            <HeaderRow
              headings={[
                'Term',
                'Type',
                'Scope',
                'Language',
                'Reason',
                'Effective From',
                'Effective To',
                'Status',
                'Created',
                'Actions',
              ]}
            />
          </thead>
          <tbody className="divide-y divide-slate-100">
            {exceptions.map((exception) => (
              <tr key={exception.id}>
                <Cell strong>
                  {terms.find((term) => term.id === exception.glossaryTermId)
                    ?.termCode ??
                    exception.termCode ??
                    exception.glossaryTermId}
                </Cell>
                <Cell>{exception.exceptionType.replaceAll('_', ' ')}</Cell>
                <Cell>{exception.scopeType.replaceAll('_', ' ')}</Cell>
                <Cell>{exception.languageCode?.toUpperCase() ?? 'All'}</Cell>
                <Cell>{exception.reason}</Cell>
                <Cell>{formatDate(exception.effectiveFrom)}</Cell>
                <Cell>{formatDate(exception.effectiveTo)}</Cell>
                <Cell>{exception.isActive ? 'Active' : 'Inactive'}</Cell>
                <Cell>{formatDateTime(exception.createdAt)}</Cell>
                <td className="px-4 py-3">
                  {canManage && exception.isActive && (
                    <button
                      type="button"
                      onClick={() => void onDeactivate(exception.id)}
                      className="text-xs font-semibold text-amber-700"
                    >
                      Deactivate
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableShell>
    </div>
  );
}

function FilterSelect({
  label,
  onChange,
  options,
  value,
}: {
  label: string;
  value: string;
  options: readonly (readonly [string, string])[];
  onChange: (value: string) => void;
}) {
  return (
    <Phase8FilterField label={label}>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
      >
        {options.map(([optionValue, labelText]) => (
          <option key={optionValue || 'all'} value={optionValue}>
            {labelText}
          </option>
        ))}
      </select>
    </Phase8FilterField>
  );
}

function TableShell({
  children,
  empty,
  emptyLabel,
}: {
  children: React.ReactNode;
  empty: boolean;
  emptyLabel: string;
}) {
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
      <div className="overflow-x-auto">{children}</div>
      {empty && <p className="p-10 text-center text-sm text-slate-500">{emptyLabel}</p>}
    </div>
  );
}

function HeaderRow({ headings }: { headings: readonly string[] }) {
  return (
    <tr>
      {headings.map((heading) => (
        <th
          key={heading}
          className="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-500"
        >
          {heading}
        </th>
      ))}
    </tr>
  );
}

function Cell({
  children,
  strong = false,
}: {
  children: React.ReactNode;
  strong?: boolean;
}) {
  return (
    <td
      className={`max-w-64 px-4 py-3 text-xs ${
        strong ? 'font-semibold text-slate-900' : 'text-slate-600'
      }`}
    >
      {children}
    </td>
  );
}

function ActionButton({
  icon: Icon,
  label,
  onClick,
}: {
  icon: typeof Edit3;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold text-blue-700 hover:bg-blue-50"
    >
      <Icon className="size-3.5" aria-hidden="true" />
      {label}
    </button>
  );
}
