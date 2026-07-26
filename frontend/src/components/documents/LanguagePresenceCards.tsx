import { Languages } from 'lucide-react';

import { getPresenceClass, presenceLabels } from './languageDisplay';
import type {
  LanguageCode,
  LanguagePresenceStatus,
  LanguageSummary,
} from '../../types/languageDetection';
import { languageLabels } from '../../types/languageDetection';

const formatPercent = (value: number): string => `${value.toFixed(1)}%`;

export function LanguagePresenceCards({ summary }: { summary: LanguageSummary }) {
  const cards = (
    [
      [
        'id',
        summary.languagePresence.id,
        summary.indonesianBlocks,
        summary.indonesianCharacters,
      ],
      [
        'en',
        summary.languagePresence.en,
        summary.englishBlocks,
        summary.englishCharacters,
      ],
      [
        'zh',
        summary.languagePresence.zh,
        summary.chineseBlocks,
        summary.chineseCharacters,
      ],
    ] as const
  ).map(([languageCode, status, blockCount, characterCount]) => ({
    languageCode,
    status,
    blockCount,
    characterCount,
    blockCoverage: summary.coverage.blockCoverage[languageCode],
    characterCoverage: summary.coverage.characterCoverage[languageCode],
    averageConfidence: summary.averageConfidenceByLanguage[languageCode],
  }));
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      {cards.map((item) => (
        <PresenceCard key={item.languageCode} presence={item} />
      ))}
    </div>
  );
}

function PresenceCard({
  presence,
}: {
  presence: {
    languageCode: Extract<LanguageCode, 'id' | 'en' | 'zh'>;
    status: LanguagePresenceStatus;
    blockCount: number;
    characterCount: number;
    blockCoverage: number;
    characterCoverage: number;
    averageConfidence: number | null;
  };
}) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Languages className="size-4 text-slate-500" aria-hidden="true" />
          <h3 className="text-sm font-semibold text-slate-950">
            {languageLabels[presence.languageCode]}
          </h3>
        </div>
        <span
          className={`rounded-full px-2.5 py-1 text-[10px] font-semibold ${getPresenceClass(
            presence.status,
          )}`}
        >
          {presenceLabels[presence.status]}
        </span>
      </div>
      <dl className="mt-5 grid grid-cols-2 gap-4 text-xs">
        <Metric label="Blocks" value={presence.blockCount.toLocaleString()} />
        <Metric label="Characters" value={presence.characterCount.toLocaleString()} />
        <Metric label="Block Coverage" value={formatPercent(presence.blockCoverage)} />
        <Metric
          label="Character Coverage"
          value={formatPercent(presence.characterCoverage)}
        />
        <Metric
          label="Average Confidence"
          value={
            presence.averageConfidence === null
              ? 'Not available'
              : `${Math.round(presence.averageConfidence * 100)}%`
          }
        />
      </dl>
    </article>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className="mt-1 font-semibold text-slate-900">{value}</dd>
    </div>
  );
}
