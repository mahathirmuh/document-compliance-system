import { Search } from 'lucide-react';
import { useState } from 'react';

import type {
  GlossaryLanguageCode,
  GlossaryProfile,
  GlossaryTestMatchRequest,
  GlossaryTestMatchResult,
} from '../../types/glossary';

export function GlossaryMatchTester({
  isPending,
  onTest,
  profiles,
  results,
}: {
  profiles: readonly GlossaryProfile[];
  results: readonly GlossaryTestMatchResult[];
  isPending: boolean;
  onTest: (payload: GlossaryTestMatchRequest) => Promise<void>;
}) {
  const [text, setText] = useState('');
  const [languageCode, setLanguageCode] = useState<GlossaryLanguageCode>('id');
  const [profileId, setProfileId] = useState('');
  const effectiveProfileId = profileId || profiles[0]?.id || '';
  return (
    <div className="space-y-5">
      <form
        className="rounded-2xl border border-slate-200 bg-white p-5"
        onSubmit={(event) => {
          event.preventDefault();
          if (text.trim() && effectiveProfileId) {
            void onTest({
              text: text.trim(),
              languageCode,
              profileIds: [effectiveProfileId],
            });
          }
        }}
      >
        <h2 className="text-sm font-semibold text-slate-950">Glossary Match Tester</h2>
        <p className="mt-1 text-xs text-slate-500">
          Test matching rules without creating a validation run or changing a source
          document.
        </p>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <label className="text-xs font-semibold text-slate-700 md:col-span-3">
            Text
            <textarea
              required
              value={text}
              onChange={(event) => setText(event.target.value)}
              className="mt-1.5 min-h-28 w-full rounded-xl border border-slate-300 p-3 text-sm"
            />
          </label>
          <label className="text-xs font-semibold text-slate-700">
            Language
            <select
              value={languageCode}
              onChange={(event) =>
                setLanguageCode(event.target.value as GlossaryLanguageCode)
              }
              className="mt-1.5 min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
            >
              <option value="id">Indonesian</option>
              <option value="en">English</option>
              <option value="zh">Chinese</option>
            </select>
          </label>
          <label className="text-xs font-semibold text-slate-700">
            Glossary Profile
            <select
              value={effectiveProfileId}
              onChange={(event) => setProfileId(event.target.value)}
              className="mt-1.5 min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
            >
              <option value="">Select profile</option>
              {profiles.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.code} — {profile.name}
                </option>
              ))}
            </select>
          </label>
          <button
            type="submit"
            disabled={!text.trim() || !effectiveProfileId || isPending}
            className="mt-auto inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white disabled:opacity-50"
          >
            <Search className="size-4" aria-hidden="true" />
            {isPending ? 'Matching…' : 'Test Match'}
          </button>
        </div>
      </form>

      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
        <table className="min-w-[75rem] divide-y divide-slate-200">
          <thead className="bg-slate-50">
            <tr>
              {[
                'Matched Concept',
                'Matched Term',
                'Language',
                'Match Type',
                'Preferred',
                'Forbidden',
                'Variant',
                'Position',
                'Exception',
              ].map((heading) => (
                <th
                  key={heading}
                  className="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-500"
                >
                  {heading}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {results.map((result, index) => (
              <tr key={`${result.glossaryTermId}-${result.startOffset}-${index}`}>
                <td className="px-4 py-3 text-xs font-semibold text-slate-900">
                  {result.conceptName}
                </td>
                <td className="px-4 py-3 text-xs text-slate-700">
                  {result.matchedText}
                </td>
                <td className="px-4 py-3 text-xs uppercase text-slate-600">
                  {result.languageCode}
                </td>
                <td className="px-4 py-3 text-xs text-slate-600">{result.matchType}</td>
                <td className="px-4 py-3 text-xs">
                  {result.isPreferred ? 'Yes' : 'No'}
                </td>
                <td className="px-4 py-3 text-xs text-rose-700">
                  {result.isForbidden ? 'Yes' : 'No'}
                </td>
                <td className="px-4 py-3 text-xs text-slate-600">
                  {result.glossaryVariantId ? result.matchedText : '—'}
                </td>
                <td className="px-4 py-3 text-xs text-slate-600">
                  {result.startOffset}–{result.endOffset}
                </td>
                <td className="px-4 py-3 text-xs text-slate-600">
                  {result.exceptionApplied
                    ? (result.exceptionType?.replaceAll('_', ' ') ?? 'Applied')
                    : 'None'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {results.length === 0 && (
          <p className="p-8 text-center text-sm text-slate-500">
            Run a test to inspect glossary matches.
          </p>
        )}
      </div>
    </div>
  );
}
