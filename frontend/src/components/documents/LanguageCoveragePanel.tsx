import type {
  LanguageCode,
  LanguageCoverage,
  LanguageCoverageValues,
} from '../../types/languageDetection';
import { languageLabels } from '../../types/languageDetection';

import { languageClasses } from './languageDisplay';

const displayedLanguages: readonly LanguageCode[] = [
  'id',
  'en',
  'zh',
  'mixed',
  'unknown',
  'other',
];

export function LanguageCoveragePanel({ coverage }: { coverage: LanguageCoverage }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-950">Preliminary Coverage</h2>
      <p className="mt-2 rounded-xl border border-blue-200 bg-blue-50 p-3 text-xs leading-5 text-blue-800">
        {coverage.disclaimer}
      </p>
      <div className="mt-5 grid gap-6 lg:grid-cols-2">
        <CoverageGroup title="Block coverage" values={coverage.blockCoverage} />
        <CoverageGroup title="Character coverage" values={coverage.characterCoverage} />
      </div>
    </section>
  );
}

function CoverageGroup({
  title,
  values,
}: {
  title: string;
  values: LanguageCoverageValues;
}) {
  return (
    <div>
      <h3 className="text-xs font-semibold text-slate-800">{title}</h3>
      <ul className="mt-3 space-y-3">
        {displayedLanguages.map((code) => {
          const value = values[code];
          return (
            <li key={code}>
              <div className="mb-1 flex items-center justify-between gap-3 text-[11px]">
                <span className="font-semibold text-slate-700">
                  {languageLabels[code]}
                </span>
                <span className="tabular-nums text-slate-500">{value.toFixed(1)}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                <div
                  className={`h-full rounded-full ring-0 ${languageClasses[code]
                    .split(' ')
                    .find((className) => className.startsWith('bg-'))}`}
                  style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
                />
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
