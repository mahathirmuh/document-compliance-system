import { ExternalLink, X } from 'lucide-react';
import { Link } from 'react-router';

import { ConsistencyBadge, SimilarityCategoryBadge } from './SimilarityCategoryBadge';
import type { TranslationSimilarityResult } from '../../types/similarity';

const languageNames = {
  id: 'Indonesian',
  en: 'English',
  zh: 'Chinese',
} as const;

const displayScore = (value: number | null | undefined): string =>
  value == null ? 'Not evaluated' : `${(value * 100).toFixed(1)}%`;

function DetailValues({ details }: { details: Readonly<Record<string, unknown>> }) {
  const entries = Object.entries(details);
  if (entries.length === 0) {
    return <span className="text-slate-500">No extracted values</span>;
  }
  return (
    <span className="text-slate-700">
      {entries
        .slice(0, 8)
        .map(([key, value]) => `${key}: ${displayDetailValue(value)}`)
        .join(' · ')}
    </span>
  );
}

const displayDetailValue = (value: unknown): string => {
  if (Array.isArray(value)) {
    const displayed = value
      .slice(0, 20)
      .map((item) => String(item).slice(0, 100))
      .join(', ');
    return value.length > 20 ? `${displayed}, …` : displayed || 'None';
  }
  if (value === null || value === undefined) {
    return 'None';
  }
  if (typeof value === 'object') {
    return '[structured detail]';
  }
  return String(value).slice(0, 300);
};

export function SimilarityDetailDialog({
  documentId,
  onClose,
  open,
  result,
  revisionId,
}: {
  result: TranslationSimilarityResult | null;
  open: boolean;
  onClose: () => void;
  documentId?: string;
  revisionId?: string;
}) {
  if (!open || !result) {
    return null;
  }

  const navigationPath =
    documentId && revisionId
      ? `/documents/${documentId}/revisions/${revisionId}/extracted-content`
      : documentId
        ? `/documents/${documentId}/extracted-content`
        : null;

  const sourceLanguage = result.sourceLanguage ?? result.sourceLanguageCode;
  const targetLanguage = result.targetLanguage ?? result.targetLanguageCode;
  const consistency = [
    [
      'Numbers extracted',
      result.numberStatus ?? result.numberConsistencyStatus,
      result.numberDetails,
    ],
    [
      'Dates extracted',
      result.dateStatus ?? result.dateConsistencyStatus,
      result.dateDetails,
    ],
    [
      'Measurements extracted',
      result.measurementStatus ?? result.measurementConsistencyStatus,
      result.measurementDetails,
    ],
    [
      'References extracted',
      result.referenceStatus ?? result.referenceConsistencyStatus,
      result.referenceDetails,
    ],
    [
      'Negation signals',
      result.negationStatus ?? result.negationConsistencyStatus,
      result.negationDetails,
    ],
  ] as const;
  const findingCount =
    result.findingCount ??
    (typeof result.metrics.findingCount === 'number' ? result.metrics.findingCount : 0);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="similarity-detail-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4"
    >
      <div className="max-h-[92vh] w-full max-w-5xl overflow-y-auto rounded-3xl bg-white shadow-2xl">
        <header className="sticky top-0 z-10 flex items-start justify-between border-b border-slate-200 bg-white px-5 py-4 sm:px-7">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-violet-700">
              Translation group detail
            </p>
            <h2
              id="similarity-detail-title"
              className="mt-1 text-lg font-semibold text-slate-950"
            >
              {languageNames[sourceLanguage]} ↔ {languageNames[targetLanguage]}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close similarity detail"
            className="grid size-10 place-items-center rounded-xl text-slate-500 hover:bg-slate-100"
          >
            <X className="size-5" aria-hidden="true" />
          </button>
        </header>

        <div className="space-y-6 p-5 sm:p-7">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Metric
              label="Similarity score"
              value={displayScore(result.similarityScore)}
            />
            <Metric
              label="Confidence"
              value={displayScore(result.confidenceScore ?? result.confidence)}
            />
            <Metric
              label="Structural group confidence"
              value={displayScore(result.structuralGroupConfidence)}
            />
            <Metric label="OCR confidence" value={displayScore(result.ocrConfidence)} />
            <Metric
              label="Length ratio"
              value={result.lengthRatio?.toFixed(2) ?? 'Not evaluated'}
            />
            <Metric
              label="Chunks evaluated"
              value={String(
                result.chunkCount ?? result.chunkCountSource + result.chunkCountTarget,
              )}
            />
            <Metric label="Related findings" value={String(findingCount)} />
            <div className="rounded-2xl bg-slate-50 p-4">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                Category
              </p>
              <div className="mt-2">
                <SimilarityCategoryBadge category={result.similarityCategory} />
              </div>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <TextPanel
              label={`${languageNames[sourceLanguage]} source text`}
              text={result.sourceTextSnippet}
            />
            <TextPanel
              label={`${languageNames[targetLanguage]} target text`}
              text={result.targetTextSnippet}
            />
          </div>

          <section>
            <h3 className="text-sm font-semibold text-slate-950">
              Consistency analysis
            </h3>
            <div className="mt-3 divide-y divide-slate-100 rounded-2xl border border-slate-200">
              {consistency.map(([label, status, details]) => (
                <div
                  key={label}
                  className="grid gap-2 px-4 py-3 text-xs sm:grid-cols-[12rem_5rem_1fr] sm:items-center"
                >
                  <span className="font-semibold text-slate-800">{label}</span>
                  <ConsistencyBadge label={label} status={status} />
                  <DetailValues details={details} />
                </div>
              ))}
            </div>
          </section>

          <section className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 p-4">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Source navigation
              </h3>
              <p className="mt-2 text-sm text-slate-800">
                {result.sourceReference ?? 'No source reference available'}
              </p>
              {navigationPath && (
                <Link
                  to={navigationPath}
                  className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-blue-700"
                >
                  Open extracted content
                  <ExternalLink className="size-3.5" aria-hidden="true" />
                </Link>
              )}
            </div>
            <div className="rounded-2xl border border-slate-200 p-4">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Related findings
              </h3>
              <p className="mt-2 text-sm text-slate-800">
                {(result.relatedFindingIds?.length ?? 0) > 0
                  ? result.relatedFindingIds.slice(0, 20).join(', ')
                  : 'No related finding'}
              </p>
            </div>
          </section>

          <p className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-900">
            Similarity is an automated review signal and does not guarantee that both
            texts have identical legal or technical meaning.
          </p>
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-slate-50 p-4">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
        {label}
      </p>
      <p className="mt-2 text-sm font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function TextPanel({
  label,
  text,
}: {
  label: string;
  text: string | null | undefined;
}) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-slate-50/50 p-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        {label}
      </h3>
      <p className="mt-3 max-h-72 overflow-y-auto whitespace-pre-wrap break-words text-sm leading-6 text-slate-800">
        {text || 'Text unavailable'}
      </p>
    </section>
  );
}
