import { ChevronDown, ChevronUp } from 'lucide-react';
import { useMemo, useState } from 'react';

import type { RevisionChange } from '../../types/revisionComparison';

const maximumPreviewCharacters = 600;
const maximumDiffTokens = 220;

interface DiffToken {
  value: string;
  kind: 'same' | 'added' | 'removed';
}

const tokenize = (value: string): string[] =>
  value
    .split(/(\s+|[.,;:!?()[\]{}])/)
    .filter(Boolean)
    .slice(0, maximumDiffTokens);

const calculateDiff = (base: string, target: string): DiffToken[] => {
  const left = tokenize(base);
  const right = tokenize(target);
  const rows = left.length + 1;
  const columns = right.length + 1;
  const matrix = Array.from({ length: rows }, () => Array<number>(columns).fill(0));
  for (let leftIndex = left.length - 1; leftIndex >= 0; leftIndex -= 1) {
    for (let rightIndex = right.length - 1; rightIndex >= 0; rightIndex -= 1) {
      matrix[leftIndex]![rightIndex] =
        left[leftIndex] === right[rightIndex]
          ? 1 + (matrix[leftIndex + 1]?.[rightIndex + 1] ?? 0)
          : Math.max(
              matrix[leftIndex + 1]?.[rightIndex] ?? 0,
              matrix[leftIndex]?.[rightIndex + 1] ?? 0,
            );
    }
  }
  const result: DiffToken[] = [];
  let leftIndex = 0;
  let rightIndex = 0;
  while (leftIndex < left.length || rightIndex < right.length) {
    if (
      leftIndex < left.length &&
      rightIndex < right.length &&
      left[leftIndex] === right[rightIndex]
    ) {
      result.push({ value: left[leftIndex] ?? '', kind: 'same' });
      leftIndex += 1;
      rightIndex += 1;
    } else if (
      rightIndex < right.length &&
      (leftIndex >= left.length ||
        (matrix[leftIndex]?.[rightIndex + 1] ?? 0) >=
          (matrix[leftIndex + 1]?.[rightIndex] ?? 0))
    ) {
      result.push({ value: right[rightIndex] ?? '', kind: 'added' });
      rightIndex += 1;
    } else {
      result.push({ value: left[leftIndex] ?? '', kind: 'removed' });
      leftIndex += 1;
    }
  }
  return result;
};

const bounded = (value: string): string =>
  value.length > maximumPreviewCharacters
    ? `${value.slice(0, maximumPreviewCharacters).trimEnd()}…`
    : value;

export function RevisionDiff({ change }: { change: RevisionChange }) {
  const [expanded, setExpanded] = useState(false);
  const base = change.baseTextSnapshot ?? '';
  const target = change.targetTextSnapshot ?? '';
  const modifiedDiff = useMemo(
    () =>
      change.changeType === 'MODIFIED' || change.changeType === 'MOVED'
        ? calculateDiff(base, target)
        : [],
    [base, change.changeType, target],
  );
  const long =
    base.length > maximumPreviewCharacters || target.length > maximumPreviewCharacters;

  return (
    <article className="rounded-2xl border border-slate-200 bg-white">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`rounded-full px-2.5 py-1 text-[10px] font-semibold ${changeTypeStyle(change.changeType)}`}
          >
            {change.changeType}
          </span>
          <span className="text-xs font-semibold text-slate-900">
            {change.sectionName ?? change.entityType.replaceAll('_', ' ')}
          </span>
          {change.languageCode && (
            <span className="text-[10px] uppercase text-slate-500">
              {change.languageCode}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 text-[10px] text-slate-500">
          <span>
            Alignment{' '}
            {change.alignmentConfidence === null
              ? '—'
              : `${(change.alignmentConfidence * 100).toFixed(1)}%`}
          </span>
          <span>
            Similarity{' '}
            {change.textSimilarity === null
              ? '—'
              : `${(change.textSimilarity * 100).toFixed(1)}%`}
          </span>
        </div>
      </header>
      <div className="grid divide-y divide-slate-200 lg:grid-cols-2 lg:divide-x lg:divide-y-0">
        <DiffPanel
          label="Base Revision"
          reference={change.sourceReferenceBase}
          text={expanded ? base : bounded(base)}
          tokens={
            change.changeType === 'MODIFIED' || change.changeType === 'MOVED'
              ? modifiedDiff.filter((token) => token.kind !== 'added')
              : undefined
          }
          emptyLabel="Content not present in base revision"
          tone={change.changeType === 'REMOVED' ? 'removed' : 'neutral'}
        />
        <DiffPanel
          label="Target Revision"
          reference={change.sourceReferenceTarget}
          text={expanded ? target : bounded(target)}
          tokens={
            change.changeType === 'MODIFIED' || change.changeType === 'MOVED'
              ? modifiedDiff.filter((token) => token.kind !== 'removed')
              : undefined
          }
          emptyLabel="Content not present in target revision"
          tone={change.changeType === 'ADDED' ? 'added' : 'neutral'}
        />
      </div>
      {long && (
        <button
          type="button"
          onClick={() => setExpanded((current) => !current)}
          className="flex min-h-10 w-full items-center justify-center gap-1.5 border-t border-slate-200 text-xs font-semibold text-blue-700"
        >
          {expanded ? (
            <ChevronUp className="size-4" aria-hidden="true" />
          ) : (
            <ChevronDown className="size-4" aria-hidden="true" />
          )}
          {expanded ? 'Collapse detail' : 'Open full bounded detail'}
        </button>
      )}
    </article>
  );
}

function DiffPanel({
  emptyLabel,
  label,
  reference,
  text,
  tokens,
  tone,
}: {
  label: string;
  reference: string | null;
  text: string;
  tokens: readonly DiffToken[] | undefined;
  emptyLabel: string;
  tone: 'neutral' | 'added' | 'removed';
}) {
  return (
    <section className="min-w-0 p-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-xs font-semibold text-slate-950">{label}</h3>
        <span className="max-w-56 truncate text-[10px] text-slate-500">
          {reference ?? 'No source reference'}
        </span>
      </div>
      <p
        className={`mt-3 whitespace-pre-wrap break-words rounded-xl p-3 text-xs leading-5 ${
          tone === 'added'
            ? 'bg-emerald-50 text-emerald-950'
            : tone === 'removed'
              ? 'bg-rose-50 text-rose-950'
              : 'bg-slate-50 text-slate-700'
        }`}
      >
        {tokens && tokens.length > 0
          ? tokens.map((token, index) => (
              <span
                key={`${token.kind}-${index}`}
                className={
                  token.kind === 'added'
                    ? 'bg-emerald-200 text-emerald-950'
                    : token.kind === 'removed'
                      ? 'bg-rose-200 text-rose-950 line-through decoration-rose-500'
                      : undefined
                }
              >
                {token.value}
              </span>
            ))
          : text || emptyLabel}
      </p>
    </section>
  );
}

const changeTypeStyle = (changeType: RevisionChange['changeType']): string => {
  switch (changeType) {
    case 'ADDED':
      return 'bg-emerald-100 text-emerald-800';
    case 'REMOVED':
      return 'bg-rose-100 text-rose-800';
    case 'MODIFIED':
      return 'bg-amber-100 text-amber-800';
    case 'MOVED':
    case 'SPLIT':
    case 'MERGED':
      return 'bg-violet-100 text-violet-800';
    case 'UNCHANGED':
      return 'bg-slate-100 text-slate-600';
  }
};
