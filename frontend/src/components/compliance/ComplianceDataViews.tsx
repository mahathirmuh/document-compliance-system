import { ExternalLink, X } from 'lucide-react';
import { Link } from 'react-router';

import type { LanguageOrderFiltersValue } from './languageOrderFilters';
import type { FindingListItem } from '../../types/finding';
import type {
  ComplianceSummary,
  DetectedSection,
  LanguageComplianceMetric,
  RequiredLanguageCode,
  TranslationGroup,
} from '../../types/compliance';

const languageLabels: Record<RequiredLanguageCode, string> = {
  id: 'Bahasa Indonesia',
  en: 'English',
  zh: '中文 / Mandarin',
};

const presenceLabels = {
  PRESENT: 'Detected',
  NOT_PRESENT: 'Missing',
  INSUFFICIENT_EVIDENCE: 'Insufficient Evidence',
  MIXED_ONLY: 'Mixed Only',
} as const;

const languageRows = (summary: ComplianceSummary): LanguageComplianceMetric[] =>
  summary.languageMetrics ??
  summary.requiredLanguages.map((languageCode) => ({
    languageCode,
    presence: summary.languagePresence[languageCode],
    blockCoverage: summary.languageCoverage[languageCode],
    characterCoverage: summary.languageCoverage[languageCode],
    minimumBlockCoverage: null,
    minimumCharacterCoverage: null,
    averageConfidence: null,
    findingCount: 0,
  }));

const formatPercent = (value: number | null): string =>
  value === null ? '—' : `${value.toFixed(1)}%`;

export function LanguageComplianceTable({ summary }: { summary: ComplianceSummary }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
      <div className="overflow-x-auto">
        <table className="min-w-[62rem] divide-y divide-slate-200">
          <thead className="bg-slate-50">
            <tr>
              {[
                'Required Language',
                'Presence',
                'Block Coverage',
                'Character Coverage',
                'Minimum Required',
                'Average Confidence',
                'Findings',
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
            {languageRows(summary).map((metric) => {
              const belowCoverage =
                (metric.minimumBlockCoverage !== null &&
                  metric.blockCoverage < metric.minimumBlockCoverage) ||
                (metric.minimumCharacterCoverage !== null &&
                  metric.characterCoverage < metric.minimumCharacterCoverage);
              return (
                <tr key={metric.languageCode}>
                  <td className="px-4 py-3 text-sm font-semibold text-slate-900">
                    {languageLabels[metric.languageCode]}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2.5 py-1 text-[10px] font-semibold ${
                        metric.presence === 'PRESENT'
                          ? 'bg-emerald-50 text-emerald-700'
                          : metric.presence === 'NOT_PRESENT'
                            ? 'bg-rose-50 text-rose-700'
                            : 'bg-amber-50 text-amber-700'
                      }`}
                    >
                      {presenceLabels[metric.presence]}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-700">
                    {formatPercent(metric.blockCoverage)}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-700">
                    {formatPercent(metric.characterCoverage)}
                    {belowCoverage && (
                      <span className="ml-2 rounded bg-rose-50 px-1.5 py-0.5 text-[10px] font-semibold text-rose-700">
                        Below Coverage
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-600">
                    {metric.minimumBlockCoverage === null &&
                    metric.minimumCharacterCoverage === null
                      ? 'Rule snapshot'
                      : `${formatPercent(metric.minimumBlockCoverage)} blocks / ${formatPercent(metric.minimumCharacterCoverage)} chars`}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-600">
                    {metric.averageConfidence === null
                      ? '—'
                      : `${(metric.averageConfidence * 100).toFixed(1)}%`}
                  </td>
                  <td className="px-4 py-3 text-xs font-semibold text-slate-700">
                    {metric.findingCount}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function LanguageOrderFilters({
  onApply,
  onChange,
  onReset,
  sections,
  value,
}: {
  value: LanguageOrderFiltersValue;
  sections: readonly Pick<DetectedSection, 'id' | 'canonicalCode' | 'headingText'>[];
  onChange: (value: LanguageOrderFiltersValue) => void;
  onApply: () => void;
  onReset: () => void;
}) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <label className="text-xs font-semibold text-slate-700">
          Complete / Incomplete
          <select
            value={value.completeness}
            onChange={(event) =>
              onChange({
                ...value,
                completeness: event.target
                  .value as LanguageOrderFiltersValue['completeness'],
              })
            }
            className="mt-1.5 min-h-10 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
          >
            <option value="ALL">All groups</option>
            <option value="COMPLETE">Complete</option>
            <option value="INCOMPLETE">Incomplete</option>
          </select>
        </label>
        <label className="text-xs font-semibold text-slate-700">
          Section
          <select
            value={value.detectedSectionId}
            onChange={(event) =>
              onChange({ ...value, detectedSectionId: event.target.value })
            }
            className="mt-1.5 min-h-10 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
          >
            <option value="">All loaded sections</option>
            {sections.map((section) => (
              <option key={section.id} value={section.id}>
                {section.canonicalCode} · {section.headingText}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs font-semibold text-slate-700">
          Container
          <input
            value={value.containerId}
            onChange={(event) =>
              onChange({ ...value, containerId: event.target.value })
            }
            placeholder="Exact container ID"
            className="mt-1.5 min-h-10 w-full rounded-xl border border-slate-300 px-3 text-sm"
          />
        </label>
        <label className="flex min-h-10 items-center gap-2 self-end rounded-xl border border-slate-200 px-3 text-xs font-semibold text-slate-700">
          <input
            type="checkbox"
            checked={value.orderInvalidOnly}
            onChange={(event) =>
              onChange({ ...value, orderInvalidOnly: event.target.checked })
            }
          />
          Order Invalid only
        </label>
        <label className="flex min-h-10 items-center gap-2 self-end rounded-xl border border-slate-200 px-3 text-xs font-semibold text-slate-700">
          <input
            type="checkbox"
            checked={value.lowConfidenceOnly}
            onChange={(event) =>
              onChange({ ...value, lowConfidenceOnly: event.target.checked })
            }
          />
          Low Confidence only
        </label>
      </div>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-slate-500">
          Filters are applied by the server across the complete compliance run.
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onReset}
            className="min-h-9 rounded-lg border border-slate-300 px-3 text-xs font-semibold text-slate-700"
          >
            Reset
          </button>
          <button
            type="button"
            onClick={onApply}
            className="min-h-9 rounded-lg bg-blue-700 px-4 text-xs font-semibold text-white"
          >
            Apply Filters
          </button>
        </div>
      </div>
    </section>
  );
}

const presenceCell = (
  section: DetectedSection,
  languageCode: RequiredLanguageCode,
): string => {
  const result = section.languageResults.find(
    (candidate) => candidate.languageCode === languageCode,
  );
  const presence = result?.presenceStatus ?? section.languagePresence[languageCode];
  return presence ? presenceLabels[presence] : 'Not evaluated';
};

export function SectionComplianceTable({
  documentId,
  extractionRunId,
  onViewDetails,
  revisionId,
  sections,
}: {
  sections: readonly DetectedSection[];
  documentId?: string | null;
  revisionId?: string | null;
  extractionRunId?: string | null;
  onViewDetails?: (section: DetectedSection) => void;
}) {
  const sourceBase =
    documentId && revisionId
      ? `/documents/${documentId}/revisions/${revisionId}/extracted-content`
      : null;
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
      <div className="overflow-x-auto">
        <table className="min-w-[82rem] divide-y divide-slate-200">
          <thead className="bg-slate-50">
            <tr>
              {[
                'Order',
                'Canonical Section',
                'Detected Heading',
                'Heading Language',
                'Required',
                'Indonesia',
                'English',
                'Chinese',
                'Complete',
                'Match Confidence',
                'Findings',
                'Source',
                'Details',
              ].map((heading) => (
                <th
                  key={heading}
                  className="whitespace-nowrap px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-500"
                >
                  {heading}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {sections.map((section) => (
              <tr key={section.id}>
                <td className="px-4 py-3 text-xs text-slate-600">
                  {section.sectionOrder}
                </td>
                <td className="px-4 py-3 font-mono text-xs font-semibold text-slate-900">
                  {section.canonicalCode}
                </td>
                <td className="max-w-xs px-4 py-3 text-xs text-slate-700">
                  {section.headingText}
                </td>
                <td className="px-4 py-3 text-xs uppercase text-slate-600">
                  {section.headingLanguageCode}
                </td>
                <td className="px-4 py-3 text-xs text-slate-600">
                  {section.isRequired ? 'Yes' : 'No'}
                </td>
                {(['id', 'en', 'zh'] as const).map((languageCode) => (
                  <td key={languageCode} className="px-4 py-3 text-xs text-slate-600">
                    {presenceCell(section, languageCode)}
                  </td>
                ))}
                <td className="px-4 py-3">
                  <span
                    className={`rounded-full px-2 py-1 text-[10px] font-semibold ${
                      section.isComplete
                        ? 'bg-emerald-50 text-emerald-700'
                        : 'bg-rose-50 text-rose-700'
                    }`}
                  >
                    {section.isComplete ? 'Complete' : 'Incomplete'}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-slate-600">
                  {(section.matchConfidence * 100).toFixed(1)}%
                </td>
                <td className="px-4 py-3 text-xs font-semibold text-slate-700">
                  {section.findingCount}
                </td>
                <td className="px-4 py-3">
                  {sourceBase ? (
                    <Link
                      to={`${sourceBase}?${new URLSearchParams({
                        ...(extractionRunId ? { runId: extractionRunId } : {}),
                        ...(section.containerId
                          ? { containerId: section.containerId }
                          : {}),
                        ...(section.headingBlockId
                          ? { blockId: section.headingBlockId }
                          : {}),
                        ...(section.headingText
                          ? { sourceSearch: section.headingText }
                          : {}),
                      }).toString()}`}
                      className="inline-flex items-center gap-1 text-xs font-semibold text-blue-700"
                    >
                      Open <ExternalLink className="size-3" aria-hidden="true" />
                    </Link>
                  ) : (
                    <span className="text-xs text-slate-400">
                      {section.containerId ?? '—'}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {onViewDetails && (
                    <button
                      type="button"
                      onClick={() => onViewDetails(section)}
                      className="min-h-8 whitespace-nowrap rounded-lg border border-blue-200 bg-blue-50 px-2.5 text-xs font-semibold text-blue-700"
                    >
                      View details
                      <span className="sr-only"> for {section.canonicalCode}</span>
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {sections.length === 0 && (
        <p className="px-5 py-10 text-center text-sm text-slate-500">
          No sections were detected for this run.
        </p>
      )}
    </div>
  );
}

export function SectionDetailDialog({
  documentId,
  extractionRunId,
  findings,
  groups,
  isLoadingRelated = false,
  onClose,
  revisionId,
  section,
}: {
  section: DetectedSection | null;
  documentId?: string | null;
  revisionId?: string | null;
  extractionRunId?: string | null;
  findings: readonly FindingListItem[];
  groups: readonly TranslationGroup[];
  isLoadingRelated?: boolean;
  onClose: () => void;
}) {
  if (!section) {
    return null;
  }
  const sourceBase =
    documentId && revisionId
      ? `/documents/${documentId}/revisions/${revisionId}/extracted-content`
      : null;
  const sourceUrl = sourceBase
    ? `${sourceBase}?${new URLSearchParams({
        ...(extractionRunId ? { runId: extractionRunId } : {}),
        ...(section.containerId ? { containerId: section.containerId } : {}),
        ...(section.headingBlockId ? { blockId: section.headingBlockId } : {}),
        ...(section.headingText ? { sourceSearch: section.headingText } : {}),
      }).toString()}`
    : null;
  const relatedFindings = findings.filter(
    (finding) => finding.detectedSectionId === section.id,
  );
  const relatedGroups = groups.filter(
    (group) => group.detectedSectionId === section.id,
  );

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Section details: ${section.canonicalCode}`}
      className="fixed inset-0 z-[100] overflow-y-auto bg-slate-950/50 p-4 backdrop-blur-sm"
    >
      <div className="mx-auto my-4 max-w-5xl rounded-3xl bg-white shadow-2xl">
        <header className="flex items-start justify-between gap-4 border-b border-slate-200 p-5 sm:p-6">
          <div>
            <p className="font-mono text-xs font-semibold text-blue-700">
              {section.canonicalCode}
            </p>
            <h2 className="mt-1 text-xl font-semibold text-slate-950">
              Section Details
            </h2>
            <p className="mt-1 text-sm text-slate-500">{section.headingText}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close section details"
            className="grid size-10 shrink-0 place-items-center rounded-full border border-slate-200 text-slate-600"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </header>
        <div className="space-y-6 p-5 sm:p-6">
          <section>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-slate-950">Source metadata</h3>
              {sourceUrl && (
                <Link
                  to={sourceUrl}
                  className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-blue-200 bg-blue-50 px-3 text-xs font-semibold text-blue-700"
                >
                  Open source block
                  <ExternalLink className="size-3.5" aria-hidden="true" />
                </Link>
              )}
            </div>
            <dl className="mt-3 grid gap-3 rounded-2xl bg-slate-50 p-4 sm:grid-cols-2 lg:grid-cols-4">
              {[
                ['Container', section.containerId],
                ['Heading block', section.headingBlockId],
                ['Start block', section.startBlockId],
                ['End block', section.endBlockId],
                ['Heading language', section.headingLanguageCode],
                ['Match type', section.matchType],
                ['Match confidence', `${(section.matchConfidence * 100).toFixed(1)}%`],
                ['Section order', String(section.sectionOrder)],
              ].map(([label, value]) => (
                <div key={label}>
                  <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                    {label}
                  </dt>
                  <dd className="mt-1 break-all text-xs font-medium text-slate-800">
                    {value || '—'}
                  </dd>
                </div>
              ))}
            </dl>
          </section>

          <section>
            <h3 className="text-sm font-semibold text-slate-950">
              Per-language metrics
            </h3>
            <div className="mt-3 overflow-x-auto rounded-2xl border border-slate-200">
              <table className="min-w-[48rem] divide-y divide-slate-200">
                <thead className="bg-slate-50">
                  <tr>
                    {[
                      'Language',
                      'Presence',
                      'Blocks',
                      'Characters',
                      'Coverage',
                      'Confidence',
                      'Block range',
                    ].map((heading) => (
                      <th
                        key={heading}
                        className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-500"
                      >
                        {heading}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {section.languageResults.map((result) => (
                    <tr key={result.id}>
                      <td className="px-3 py-2 text-xs font-semibold text-slate-800">
                        {languageLabels[result.languageCode]}
                      </td>
                      <td className="px-3 py-2 text-xs text-slate-600">
                        {presenceLabels[result.presenceStatus]}
                      </td>
                      <td className="px-3 py-2 text-xs text-slate-600">
                        {result.blockCount}
                      </td>
                      <td className="px-3 py-2 text-xs text-slate-600">
                        {result.characterCount}
                      </td>
                      <td className="px-3 py-2 text-xs text-slate-600">
                        {formatPercent(result.coveragePercentage)}
                      </td>
                      <td className="px-3 py-2 text-xs text-slate-600">
                        {result.averageConfidence === null
                          ? '—'
                          : `${(result.averageConfidence * 100).toFixed(1)}%`}
                      </td>
                      <td className="px-3 py-2 font-mono text-[11px] text-slate-600">
                        {result.firstBlockId ?? '—'} → {result.lastBlockId ?? '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {section.languageResults.length === 0 && (
                <p className="px-4 py-8 text-center text-sm text-slate-500">
                  No per-language metrics were persisted for this section.
                </p>
              )}
            </div>
          </section>

          <div className="grid gap-6 lg:grid-cols-2">
            <section>
              <h3 className="text-sm font-semibold text-slate-950">
                Related findings ({relatedFindings.length})
              </h3>
              <div className="mt-3 space-y-2">
                {relatedFindings.map((finding) => (
                  <Link
                    key={finding.id}
                    to={`/compliance/findings/${finding.id}`}
                    className="block rounded-xl border border-slate-200 p-3 hover:border-blue-300"
                  >
                    <span className="text-xs font-semibold text-slate-900">
                      {finding.findingCode}
                    </span>
                    <span className="mt-1 block text-xs text-slate-600">
                      {finding.severity} · {finding.status} · {finding.title}
                    </span>
                  </Link>
                ))}
                {!isLoadingRelated && relatedFindings.length === 0 && (
                  <p className="rounded-xl bg-slate-50 p-3 text-xs text-slate-500">
                    No findings are linked to this section.
                  </p>
                )}
              </div>
            </section>
            <section>
              <h3 className="text-sm font-semibold text-slate-950">
                Related translation groups ({relatedGroups.length})
              </h3>
              <div className="mt-3 space-y-2">
                {relatedGroups.map((group) => (
                  <div
                    key={group.id}
                    className="rounded-xl border border-slate-200 p-3"
                  >
                    <p className="text-xs font-semibold text-slate-900">
                      Group #{group.groupIndex} · {group.groupType.replaceAll('_', ' ')}
                    </p>
                    <p className="mt-1 break-all text-xs text-slate-600">
                      {group.sourceReference}
                    </p>
                    <p className="mt-1 text-[11px] text-slate-500">
                      {group.isComplete ? 'Complete' : 'Incomplete'} ·{' '}
                      {group.isOrderValid ? 'Order valid' : 'Order invalid'} ·{' '}
                      {(group.confidence * 100).toFixed(1)}% confidence
                    </p>
                  </div>
                ))}
                {!isLoadingRelated && relatedGroups.length === 0 && (
                  <p className="rounded-xl bg-slate-50 p-3 text-xs text-slate-500">
                    No translation groups are linked to this section.
                  </p>
                )}
              </div>
            </section>
          </div>
          {isLoadingRelated && (
            <p className="text-xs font-semibold text-blue-700">
              Loading related findings and translation groups…
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

const orderLabel = (languages: readonly RequiredLanguageCode[]): string =>
  languages.map((code) => code.toUpperCase()).join(' → ') || '—';

export function LanguageOrderGroupTable({
  groups,
  sections = [],
}: {
  groups: readonly TranslationGroup[];
  sections?: readonly Pick<DetectedSection, 'id' | 'canonicalCode'>[];
}) {
  const sectionCodes = new Map(
    sections.map((section) => [section.id, section.canonicalCode] as const),
  );
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
      <div className="overflow-x-auto">
        <table className="min-w-[74rem] divide-y divide-slate-200">
          <thead className="bg-slate-50">
            <tr>
              {[
                'Group',
                'Section',
                'Source Reference',
                'Expected Order',
                'Actual Order',
                'Complete',
                'Order Valid',
                'Confidence',
                'Findings',
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
            {groups.map((group) => (
              <tr key={group.id}>
                <td className="px-4 py-3 text-xs font-semibold text-slate-900">
                  #{group.groupIndex} · {group.groupType.replaceAll('_', ' ')}
                </td>
                <td className="px-4 py-3 font-mono text-xs text-slate-600">
                  {group.sectionCode ??
                    (group.detectedSectionId
                      ? (sectionCodes.get(group.detectedSectionId) ??
                        group.detectedSectionId)
                      : '—')}
                </td>
                <td className="max-w-xs break-all px-4 py-3 text-xs text-slate-600">
                  {group.sourceReference}
                </td>
                <td className="px-4 py-3 text-xs text-slate-700">
                  {orderLabel(group.expectedLanguages)}
                </td>
                <td className="px-4 py-3 text-xs text-slate-700">
                  {orderLabel(group.actualLanguageOrder ?? group.languageOrder)}
                </td>
                <td className="px-4 py-3">
                  <ResultBadge
                    value={group.isComplete}
                    positive="Complete"
                    negative="Incomplete"
                  />
                </td>
                <td className="px-4 py-3">
                  <ResultBadge
                    value={group.isOrderValid}
                    positive="Valid"
                    negative="Invalid"
                  />
                </td>
                <td className="px-4 py-3 text-xs text-slate-600">
                  {(group.confidence * 100).toFixed(1)}%
                  {group.confidence < 0.65 && (
                    <span className="ml-2 text-[10px] font-semibold text-amber-700">
                      Low confidence
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-xs font-semibold text-slate-700">
                  {group.findingCount}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {groups.length === 0 && (
        <p className="px-5 py-10 text-center text-sm text-slate-500">
          No structural translation groups were evaluated.
        </p>
      )}
      <p className="border-t border-slate-100 bg-slate-50 px-4 py-3 text-xs leading-5 text-slate-500">
        Groups use document position and structure. Phase 8 does not evaluate semantic
        translation equivalence.
      </p>
    </div>
  );
}

function ResultBadge({
  negative,
  positive,
  value,
}: {
  value: boolean;
  positive: string;
  negative: string;
}) {
  return (
    <span
      className={`rounded-full px-2 py-1 text-[10px] font-semibold ${
        value ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'
      }`}
    >
      {value ? positive : negative}
    </span>
  );
}
