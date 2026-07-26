import { X } from 'lucide-react';
import { useEffect, useState } from 'react';

import type {
  GlossaryLanguageCode,
  GlossaryProfile,
  GlossaryProfileCreate,
  GlossaryScopeType,
  GlossarySeverity,
  GlossaryTerm,
  GlossaryTermCreate,
  GlossaryTermType,
  GlossaryTranslation,
  GlossaryTranslationCreate,
  GlossaryVariantCreate,
  GlossaryVariantType,
} from '../../types/glossary';

const inputClass =
  'mt-1.5 min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm';
const checkboxClass = 'size-4 rounded border-slate-300 text-blue-700';

export function GlossaryProfileDialog({
  isPending,
  onClose,
  onSubmit,
  open,
  profile,
}: {
  open: boolean;
  profile: GlossaryProfile | null;
  isPending: boolean;
  onClose: () => void;
  onSubmit: (payload: GlossaryProfileCreate) => Promise<void>;
}) {
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [scopeType, setScopeType] = useState<GlossaryScopeType>('GLOBAL');
  const [departmentId, setDepartmentId] = useState('');
  const [documentTypeId, setDocumentTypeId] = useState('');
  const [isDefault, setIsDefault] = useState(false);

  useEffect(() => {
    setCode(profile?.code ?? '');
    setName(profile?.name ?? '');
    setDescription(profile?.description ?? '');
    setScopeType(profile?.scopeType ?? 'GLOBAL');
    setDepartmentId(profile?.departmentId ?? '');
    setDocumentTypeId(profile?.documentTypeId ?? '');
    setIsDefault(profile?.isDefault ?? false);
  }, [profile, open]);

  if (!open) {
    return null;
  }
  const requiresDepartment =
    scopeType === 'DEPARTMENT' || scopeType === 'DEPARTMENT_DOCUMENT_TYPE';
  const requiresDocumentType =
    scopeType === 'DOCUMENT_TYPE' || scopeType === 'DEPARTMENT_DOCUMENT_TYPE';
  const valid =
    code.trim() &&
    name.trim() &&
    (!requiresDepartment || departmentId.trim()) &&
    (!requiresDocumentType || documentTypeId.trim());

  return (
    <DialogFrame
      title={profile ? 'Edit glossary profile' : 'Create glossary profile'}
      onClose={onClose}
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (!valid) {
            return;
          }
          void onSubmit({
            code: code.trim().toUpperCase(),
            name: name.trim(),
            description: description.trim() || null,
            scopeType,
            departmentId: requiresDepartment ? departmentId.trim() : null,
            documentTypeId: requiresDocumentType ? documentTypeId.trim() : null,
            isDefault,
            isActive: profile?.isActive ?? true,
          });
        }}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Profile Code">
            <input
              required
              maxLength={50}
              value={code}
              onChange={(event) => setCode(event.target.value)}
              className={inputClass}
            />
          </Field>
          <Field label="Profile Name">
            <input
              required
              maxLength={200}
              value={name}
              onChange={(event) => setName(event.target.value)}
              className={inputClass}
            />
          </Field>
          <Field label="Scope Type">
            <select
              value={scopeType}
              onChange={(event) =>
                setScopeType(event.target.value as GlossaryScopeType)
              }
              className={inputClass}
            >
              {(
                [
                  'GLOBAL',
                  'DEPARTMENT',
                  'DOCUMENT_TYPE',
                  'DEPARTMENT_DOCUMENT_TYPE',
                ] as const
              ).map((scope) => (
                <option key={scope} value={scope}>
                  {scope.replaceAll('_', ' ')}
                </option>
              ))}
            </select>
          </Field>
          {requiresDepartment && (
            <Field label="Department ID">
              <input
                required
                value={departmentId}
                onChange={(event) => setDepartmentId(event.target.value)}
                className={inputClass}
              />
            </Field>
          )}
          {requiresDocumentType && (
            <Field label="Document Type ID">
              <input
                required
                value={documentTypeId}
                onChange={(event) => setDocumentTypeId(event.target.value)}
                className={inputClass}
              />
            </Field>
          )}
          <label className="flex items-center gap-2 self-end pb-3 text-sm font-semibold text-slate-700">
            <input
              type="checkbox"
              checked={isDefault}
              onChange={(event) => setIsDefault(event.target.checked)}
              className={checkboxClass}
            />
            Default for this scope
          </label>
        </div>
        <Field label="Description">
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            className={`${inputClass} min-h-24 py-3`}
          />
        </Field>
        <DialogActions
          isPending={isPending}
          submitLabel={profile ? 'Save Profile' : 'Create Profile'}
          onClose={onClose}
          disabled={!valid}
        />
      </form>
    </DialogFrame>
  );
}

interface TranslationDraft {
  termText: string;
  isPreferred: boolean;
  isForbidden: boolean;
  isRequired: boolean;
  priority: string;
  usageNote: string;
  exampleText: string;
}

const emptyTranslation = (): TranslationDraft => ({
  termText: '',
  isPreferred: true,
  isForbidden: false,
  isRequired: false,
  priority: '100',
  usageNote: '',
  exampleText: '',
});

const translationFrom = (
  translation: GlossaryTranslation | undefined,
): TranslationDraft =>
  translation
    ? {
        termText: translation.termText,
        isPreferred: translation.isPreferred,
        isForbidden: translation.isForbidden,
        isRequired: translation.isRequired,
        priority: String(translation.priority),
        usageNote: translation.usageNote ?? '',
        exampleText: translation.exampleText ?? '',
      }
    : emptyTranslation();

export interface GlossaryTermFormSubmission {
  term: GlossaryTermCreate;
  translations: Readonly<
    Partial<Record<GlossaryLanguageCode, GlossaryTranslationCreate>>
  >;
  variant: {
    languageCode: GlossaryLanguageCode;
    payload: GlossaryVariantCreate;
  } | null;
}

export function GlossaryTermDialog({
  isPending,
  onClose,
  onSubmit,
  open,
  profiles,
  term,
}: {
  open: boolean;
  term: GlossaryTerm | null;
  profiles: readonly GlossaryProfile[];
  isPending: boolean;
  onClose: () => void;
  onSubmit: (submission: GlossaryTermFormSubmission) => Promise<void>;
}) {
  const [profileId, setProfileId] = useState('');
  const [termCode, setTermCode] = useState('');
  const [conceptName, setConceptName] = useState('');
  const [description, setDescription] = useState('');
  const [termType, setTermType] = useState<GlossaryTermType>('PREFERRED');
  const [severity, setSeverity] = useState<GlossarySeverity>('MINOR');
  const [isCaseSensitive, setIsCaseSensitive] = useState(false);
  const [matchWholeWord, setMatchWholeWord] = useState(true);
  const [allowInflection, setAllowInflection] = useState(false);
  const [isRegex, setIsRegex] = useState(false);
  const [notes, setNotes] = useState('');
  const [translations, setTranslations] = useState<
    Record<GlossaryLanguageCode, TranslationDraft>
  >({
    id: emptyTranslation(),
    en: emptyTranslation(),
    zh: emptyTranslation(),
  });
  const [variantText, setVariantText] = useState('');
  const [variantLanguage, setVariantLanguage] = useState<GlossaryLanguageCode>('id');
  const [variantType, setVariantType] = useState<GlossaryVariantType>('SYNONYM');
  const [variantAllowed, setVariantAllowed] = useState(true);

  useEffect(() => {
    setProfileId(term?.glossaryProfileId ?? profiles[0]?.id ?? '');
    setTermCode(term?.termCode ?? '');
    setConceptName(term?.conceptName ?? '');
    setDescription(term?.description ?? '');
    setTermType(term?.termType ?? 'PREFERRED');
    setSeverity(term?.severity ?? 'MINOR');
    setIsCaseSensitive(term?.isCaseSensitive ?? false);
    setMatchWholeWord(term?.matchWholeWord ?? true);
    setAllowInflection(term?.allowInflection ?? false);
    setIsRegex(term?.isRegex ?? false);
    setNotes(term?.notes ?? '');
    setTranslations({
      id: translationFrom(
        term?.translations.find((translation) => translation.languageCode === 'id'),
      ),
      en: translationFrom(
        term?.translations.find((translation) => translation.languageCode === 'en'),
      ),
      zh: translationFrom(
        term?.translations.find((translation) => translation.languageCode === 'zh'),
      ),
    });
    setVariantText('');
    setVariantLanguage('id');
    setVariantType('SYNONYM');
    setVariantAllowed(true);
  }, [open, profiles, term]);

  if (!open) {
    return null;
  }
  const populatedTranslations = Object.values(translations).filter(
    (translation) => translation.termText.trim().length > 0,
  );
  const hasTranslationConflict = populatedTranslations.some(
    (translation) => translation.isPreferred && translation.isForbidden,
  );
  const hasInvalidPriority = populatedTranslations.some((translation) => {
    const priority = Number(translation.priority);
    return !Number.isInteger(priority) || priority < 0 || priority > 1_000_000;
  });
  const variantTargetMissing =
    Boolean(variantText.trim()) && !translations[variantLanguage].termText.trim();
  const valid =
    profileId &&
    termCode.trim() &&
    conceptName.trim() &&
    (populatedTranslations.length > 0 || Boolean(term)) &&
    !hasTranslationConflict &&
    !hasInvalidPriority &&
    !variantTargetMissing;

  const updateTranslation = (
    language: GlossaryLanguageCode,
    update: Partial<TranslationDraft>,
  ): void => {
    setTranslations((current) => ({
      ...current,
      [language]: { ...current[language], ...update },
    }));
  };

  return (
    <DialogFrame
      title={term ? 'Edit glossary term' : 'Create glossary term'}
      onClose={onClose}
      wide
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (!valid) {
            return;
          }
          const translationPayloads: Partial<
            Record<GlossaryLanguageCode, GlossaryTranslationCreate>
          > = {};
          (['id', 'en', 'zh'] as const).forEach((languageCode) => {
            const draft = translations[languageCode];
            if (draft.termText.trim()) {
              translationPayloads[languageCode] = {
                languageCode,
                termText: draft.termText.trim(),
                isPreferred: draft.isPreferred,
                isForbidden: draft.isForbidden,
                isRequired: draft.isRequired,
                priority: Number(draft.priority) || 0,
                usageNote: draft.usageNote.trim() || null,
                exampleText: draft.exampleText.trim() || null,
                isActive: true,
              };
            }
          });
          void onSubmit({
            term: {
              glossaryProfileId: profileId,
              termCode: termCode.trim().toUpperCase(),
              conceptName: conceptName.trim(),
              description: description.trim() || null,
              termType,
              severity,
              isCaseSensitive,
              matchWholeWord,
              allowInflection,
              isRegex,
              isActive: term?.isActive ?? true,
              notes: notes.trim() || null,
            },
            translations: translationPayloads,
            variant: variantText.trim()
              ? {
                  languageCode: variantLanguage,
                  payload: {
                    variantText: variantText.trim(),
                    variantType,
                    isAllowed: variantAllowed,
                    isActive: true,
                  },
                }
              : null,
          });
        }}
      >
        <section>
          <h3 className="text-sm font-semibold text-slate-950">General</h3>
          <div className="mt-3 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <Field label="Term Code">
              <input
                required
                value={termCode}
                onChange={(event) => setTermCode(event.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label="Concept Name">
              <input
                required
                value={conceptName}
                onChange={(event) => setConceptName(event.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label="Profile">
              <select
                required
                value={profileId}
                onChange={(event) => setProfileId(event.target.value)}
                className={inputClass}
              >
                <option value="">Select profile</option>
                {profiles.map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.code} — {profile.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Term Type">
              <select
                value={termType}
                onChange={(event) =>
                  setTermType(event.target.value as GlossaryTermType)
                }
                className={inputClass}
              >
                {(
                  [
                    'PREFERRED',
                    'REQUIRED',
                    'FORBIDDEN',
                    'REFERENCE',
                    'ABBREVIATION',
                  ] as const
                ).map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Severity">
              <select
                value={severity}
                onChange={(event) =>
                  setSeverity(event.target.value as GlossarySeverity)
                }
                className={inputClass}
              >
                {(['CRITICAL', 'MAJOR', 'MINOR', 'INFO'] as const).map((candidate) => (
                  <option key={candidate} value={candidate}>
                    {candidate}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Description">
              <input
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                className={inputClass}
              />
            </Field>
          </div>
        </section>

        <section className="mt-6">
          <h3 className="text-sm font-semibold text-slate-950">Matching</h3>
          <div className="mt-3 flex flex-wrap gap-5 rounded-2xl bg-slate-50 p-4">
            {[
              ['Case Sensitive', isCaseSensitive, setIsCaseSensitive],
              ['Whole Word', matchWholeWord, setMatchWholeWord],
              ['Allow Inflection', allowInflection, setAllowInflection],
              ['Regex', isRegex, setIsRegex],
            ].map(([label, checked, setter]) => (
              <label
                key={String(label)}
                className="flex items-center gap-2 text-xs font-semibold text-slate-700"
              >
                <input
                  type="checkbox"
                  checked={Boolean(checked)}
                  onChange={(event) =>
                    (setter as (value: boolean) => void)(event.target.checked)
                  }
                  className={checkboxClass}
                />
                {String(label)}
              </label>
            ))}
          </div>
          {isRegex && (
            <p className="mt-2 text-xs text-amber-700">
              Regex is validated and runtime-limited by the server.
            </p>
          )}
        </section>

        <section className="mt-6">
          <h3 className="text-sm font-semibold text-slate-950">Translations</h3>
          <div className="mt-3 grid gap-4 xl:grid-cols-3">
            {(
              [
                ['id', 'Indonesian'],
                ['en', 'English'],
                ['zh', 'Chinese'],
              ] as const
            ).map(([language, label]) => {
              const draft = translations[language];
              return (
                <fieldset
                  key={language}
                  className="rounded-2xl border border-slate-200 p-4"
                >
                  <legend className="px-2 text-xs font-semibold text-slate-900">
                    {label}
                  </legend>
                  <Field label="Term Text">
                    <input
                      value={draft.termText}
                      onChange={(event) =>
                        updateTranslation(language, {
                          termText: event.target.value,
                        })
                      }
                      className={inputClass}
                    />
                  </Field>
                  <div className="mt-3 grid grid-cols-3 gap-2">
                    {(
                      [
                        ['Preferred', 'isPreferred'],
                        ['Forbidden', 'isForbidden'],
                        ['Required', 'isRequired'],
                      ] as const
                    ).map(([candidateLabel, field]) => (
                      <label
                        key={field}
                        className="flex items-center gap-1.5 text-[10px] font-semibold text-slate-600"
                      >
                        <input
                          type="checkbox"
                          checked={draft[field]}
                          onChange={(event) =>
                            updateTranslation(language, {
                              [field]: event.target.checked,
                            })
                          }
                          className={checkboxClass}
                        />
                        {candidateLabel}
                      </label>
                    ))}
                  </div>
                  <Field label="Priority">
                    <input
                      type="number"
                      min={0}
                      max={1_000_000}
                      step={1}
                      value={draft.priority}
                      onChange={(event) =>
                        updateTranslation(language, {
                          priority: event.target.value,
                        })
                      }
                      className={inputClass}
                    />
                  </Field>
                  <Field label="Usage Note">
                    <input
                      value={draft.usageNote}
                      onChange={(event) =>
                        updateTranslation(language, {
                          usageNote: event.target.value,
                        })
                      }
                      className={inputClass}
                    />
                  </Field>
                  <Field label="Example">
                    <input
                      value={draft.exampleText}
                      onChange={(event) =>
                        updateTranslation(language, {
                          exampleText: event.target.value,
                        })
                      }
                      className={inputClass}
                    />
                  </Field>
                </fieldset>
              );
            })}
          </div>
        </section>

        <section className="mt-6">
          <h3 className="text-sm font-semibold text-slate-950">Variants</h3>
          <div className="mt-3 grid gap-4 rounded-2xl bg-slate-50 p-4 md:grid-cols-4">
            <Field label="Variant">
              <input
                value={variantText}
                onChange={(event) => setVariantText(event.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label="Language">
              <select
                value={variantLanguage}
                onChange={(event) =>
                  setVariantLanguage(event.target.value as GlossaryLanguageCode)
                }
                className={inputClass}
              >
                <option value="id">Indonesian</option>
                <option value="en">English</option>
                <option value="zh">Chinese</option>
              </select>
            </Field>
            <Field label="Type">
              <select
                value={variantType}
                onChange={(event) =>
                  setVariantType(event.target.value as GlossaryVariantType)
                }
                className={inputClass}
              >
                {(
                  [
                    'SYNONYM',
                    'ABBREVIATION',
                    'SPELLING',
                    'LEGACY',
                    'FORBIDDEN_VARIANT',
                  ] as const
                ).map((type) => (
                  <option key={type} value={type}>
                    {type.replaceAll('_', ' ')}
                  </option>
                ))}
              </select>
            </Field>
            <label className="flex items-center gap-2 self-end pb-3 text-xs font-semibold text-slate-700">
              <input
                type="checkbox"
                checked={variantAllowed}
                onChange={(event) => setVariantAllowed(event.target.checked)}
                className={checkboxClass}
              />
              Allowed
            </label>
          </div>
        </section>

        <Field label="Notes">
          <textarea
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            className={`${inputClass} min-h-20 py-3`}
          />
        </Field>
        {(hasTranslationConflict || hasInvalidPriority || variantTargetMissing) && (
          <div
            role="alert"
            className="mt-4 rounded-xl bg-rose-50 p-3 text-xs text-rose-800"
          >
            {hasTranslationConflict &&
              'A translation cannot be both preferred and forbidden. '}
            {hasInvalidPriority &&
              'Translation priority must be a whole number from 0 to 1,000,000. '}
            {variantTargetMissing &&
              'Add a translation for the selected variant language first.'}
          </div>
        )}
        <DialogActions
          isPending={isPending}
          submitLabel={term ? 'Save Term' : 'Create Term'}
          onClose={onClose}
          disabled={!valid}
        />
      </form>
    </DialogFrame>
  );
}

function DialogFrame({
  children,
  onClose,
  title,
  wide = false,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4"
    >
      <div
        className={`max-h-[94vh] w-full overflow-y-auto rounded-3xl bg-white p-6 shadow-2xl ${wide ? 'max-w-6xl' : 'max-w-2xl'}`}
      >
        <header className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="grid size-10 place-items-center rounded-xl hover:bg-slate-100"
          >
            <X className="size-5" aria-hidden="true" />
          </button>
        </header>
        <div className="mt-5">{children}</div>
      </div>
    </div>
  );
}

function Field({ children, label }: { label: string; children: React.ReactNode }) {
  return (
    <label className="mt-3 block text-xs font-semibold text-slate-700">
      {label}
      {children}
    </label>
  );
}

function DialogActions({
  disabled,
  isPending,
  onClose,
  submitLabel,
}: {
  isPending: boolean;
  submitLabel: string;
  onClose: () => void;
  disabled: boolean;
}) {
  return (
    <div className="mt-6 flex justify-end gap-2 border-t border-slate-200 pt-5">
      <button
        type="button"
        onClick={onClose}
        className="min-h-10 rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700"
      >
        Cancel
      </button>
      <button
        type="submit"
        disabled={disabled || isPending}
        className="min-h-10 rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white disabled:opacity-50"
      >
        {isPending ? 'Saving…' : submitLabel}
      </button>
    </div>
  );
}
