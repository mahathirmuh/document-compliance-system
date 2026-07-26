import { Search } from 'lucide-react';
import { useState } from 'react';
import { Link, useSearchParams } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import {
  LanguageComplianceTable,
  LanguageOrderFilters,
  LanguageOrderGroupTable,
  SectionDetailDialog,
  SectionComplianceTable,
} from '../../components/compliance/ComplianceDataViews';
import {
  emptyLanguageOrderFilters,
  type LanguageOrderFiltersValue,
} from '../../components/compliance/languageOrderFilters';
import {
  Phase8ErrorAlert,
  Phase8Loading,
  Phase8Pagination,
} from '../../components/compliance/Phase8TableUtilities';
import { ComplianceStatusBadge } from '../../components/compliance/ComplianceStatusBadge';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import {
  useComplianceRun,
  useComplianceSummary,
  useDetectedSections,
  useTranslationGroups,
} from '../../hooks/useCompliance';
import { useFindings } from '../../hooks/useFindings';
import type {
  DetectedSection,
  TranslationGroupListParams,
} from '../../types/compliance';

export type ComplianceAnalysisMode = 'languages' | 'sections' | 'language-order';

const pageContent: Record<
  ComplianceAnalysisMode,
  { title: string; description: string }
> = {
  languages: {
    title: 'Language Compliance',
    description:
      'Review required-language presence, block coverage, character coverage, confidence, and related findings.',
  },
  sections: {
    title: 'Section Compliance',
    description:
      'Review canonical section matches, required languages, completeness, order, and confidence.',
  },
  'language-order': {
    title: 'Language Order',
    description:
      'Review structurally grouped content for expected ID → EN → ZH order and group completeness.',
  },
};

export function ComplianceRunAnalysisPage({ mode }: { mode: ComplianceAnalysisMode }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const runId = searchParams.get('runId');
  const [runInput, setRunInput] = useState(runId ?? '');
  const [sectionPage, setSectionPage] = useState(1);
  const [sectionPageSize, setSectionPageSize] = useState(20);
  const [groupPage, setGroupPage] = useState(1);
  const [groupPageSize, setGroupPageSize] = useState(20);
  const [groupFilterDraft, setGroupFilterDraft] = useState<LanguageOrderFiltersValue>({
    ...emptyLanguageOrderFilters,
  });
  const [groupFilters, setGroupFilters] = useState<LanguageOrderFiltersValue>({
    ...emptyLanguageOrderFilters,
  });
  const [selectedSection, setSelectedSection] = useState<DetectedSection | null>(null);
  const runQuery = useComplianceRun(runId);
  const summaryQuery = useComplianceSummary(mode === 'languages' ? runId : null);
  const sectionsQuery = useDetectedSections(mode === 'sections' ? runId : null, {
    page: sectionPage,
    pageSize: sectionPageSize,
  });
  const sectionOptionsQuery = useDetectedSections(
    mode === 'language-order' ? runId : null,
    { page: 1, pageSize: 100 },
  );
  const groupParams: TranslationGroupListParams = {
    page: groupPage,
    pageSize: groupPageSize,
    ...(groupFilters.completeness === 'COMPLETE'
      ? { isComplete: true }
      : groupFilters.completeness === 'INCOMPLETE'
        ? { isComplete: false }
        : {}),
    ...(groupFilters.orderInvalidOnly ? { isOrderValid: false } : {}),
    ...(groupFilters.lowConfidenceOnly ? { lowConfidence: true } : {}),
    ...(groupFilters.detectedSectionId
      ? { detectedSectionId: groupFilters.detectedSectionId }
      : {}),
    ...(groupFilters.containerId ? { containerId: groupFilters.containerId } : {}),
  };
  const groupsQuery = useTranslationGroups(
    mode === 'language-order' ? runId : null,
    groupParams,
  );
  const relatedGroupsQuery = useTranslationGroups(
    selectedSection ? runId : null,
    {
      page: 1,
      pageSize: 100,
      ...(selectedSection ? { detectedSectionId: selectedSection.id } : {}),
    },
    { enabled: selectedSection !== null },
  );
  const relatedFindingsQuery = useFindings(
    {
      page: 1,
      pageSize: 100,
      ...(runId ? { complianceRunId: runId } : {}),
      ...(selectedSection ? { detectedSectionId: selectedSection.id } : {}),
    },
    { enabled: runId !== null && selectedSection !== null },
  );
  const content = pageContent[mode];
  const activeQuery =
    mode === 'languages'
      ? summaryQuery
      : mode === 'sections'
        ? sectionsQuery
        : groupsQuery;

  const selectRun = (): void => {
    const trimmed = runInput.trim();
    setSectionPage(1);
    setGroupPage(1);
    setSelectedSection(null);
    setSearchParams(trimmed ? { runId: trimmed } : {});
  };

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Compliance"
        title={content.title}
        description={content.description}
      />
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <label className="block max-w-2xl text-xs font-semibold text-slate-700">
          Compliance Run ID
          <span className="mt-1.5 flex gap-2">
            <span className="relative flex-1">
              <Search
                className="pointer-events-none absolute left-3 top-3.5 size-4 text-slate-400"
                aria-hidden="true"
              />
              <input
                value={runInput}
                onChange={(event) => setRunInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    selectRun();
                  }
                }}
                placeholder="Select a run from Validation History or enter its ID"
                className="min-h-11 w-full rounded-xl border border-slate-300 pl-10 pr-3 text-sm"
              />
            </span>
            <button
              type="button"
              onClick={selectRun}
              className="min-h-11 rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white"
            >
              Open Run
            </button>
          </span>
        </label>
      </section>

      {!runId && (
        <section className="rounded-3xl border border-dashed border-slate-300 bg-white p-10 text-center">
          <h2 className="text-base font-semibold text-slate-900">
            Choose a compliance run
          </h2>
          <p className="mt-2 text-sm text-slate-500">
            Open a completed validation run to inspect this view.
          </p>
          <Link
            to="/documents/validation-history"
            className="mt-5 inline-flex min-h-10 items-center rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white"
          >
            Validation History
          </Link>
        </section>
      )}
      {runId && (runQuery.isLoading || activeQuery.isLoading) && (
        <Phase8Loading label={`Loading ${content.title.toLowerCase()}`} />
      )}
      {runId && (runQuery.error || activeQuery.error) && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            runQuery.error ?? activeQuery.error,
            `${content.title} could not be loaded.`,
          )}
          onRetry={() => {
            void runQuery.refetch();
            void activeQuery.refetch();
          }}
        />
      )}
      {runQuery.data && (
        <section className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-semibold text-slate-950">
              {runQuery.data.document?.baseDocumentCode ?? runQuery.data.documentId}
              {runQuery.data.revision
                ? ` · ${runQuery.data.revision.revisionCode}`
                : ''}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Rule{' '}
              {runQuery.data.validationRule?.name ?? runQuery.data.validationRuleId}
              {' · '}
              Score {runQuery.data.complianceScore?.toFixed(1) ?? '—'}
            </p>
          </div>
          <ComplianceStatusBadge status={runQuery.data.complianceStatus} />
        </section>
      )}
      {mode === 'languages' && summaryQuery.data && (
        <LanguageComplianceTable summary={summaryQuery.data} />
      )}
      {mode === 'sections' && sectionsQuery.data && (
        <>
          <SectionComplianceTable
            sections={sectionsQuery.data.items}
            onViewDetails={setSelectedSection}
            {...(runQuery.data
              ? {
                  documentId: runQuery.data.documentId,
                  revisionId: runQuery.data.documentRevisionId,
                  extractionRunId: runQuery.data.extractionRunId,
                }
              : {})}
          />
          <Phase8Pagination
            page={sectionsQuery.data.page}
            pageSize={sectionsQuery.data.pageSize}
            totalItems={sectionsQuery.data.totalItems}
            totalPages={sectionsQuery.data.totalPages}
            label="detected sections"
            onPageChange={setSectionPage}
            onPageSizeChange={(pageSize) => {
              setSectionPage(1);
              setSectionPageSize(pageSize);
            }}
          />
        </>
      )}
      {mode === 'language-order' && groupsQuery.data && (
        <>
          <LanguageOrderFilters
            value={groupFilterDraft}
            sections={sectionOptionsQuery.data?.items ?? []}
            onChange={setGroupFilterDraft}
            onApply={() => {
              setGroupPage(1);
              setGroupFilters({
                ...groupFilterDraft,
                containerId: groupFilterDraft.containerId.trim(),
              });
            }}
            onReset={() => {
              const reset = { ...emptyLanguageOrderFilters };
              setGroupPage(1);
              setGroupFilterDraft(reset);
              setGroupFilters(reset);
            }}
          />
          <LanguageOrderGroupTable
            groups={groupsQuery.data.items}
            sections={sectionOptionsQuery.data?.items ?? []}
          />
          <Phase8Pagination
            page={groupsQuery.data.page}
            pageSize={groupsQuery.data.pageSize}
            totalItems={groupsQuery.data.totalItems}
            totalPages={groupsQuery.data.totalPages}
            label="translation groups"
            onPageChange={setGroupPage}
            onPageSizeChange={(pageSize) => {
              setGroupPage(1);
              setGroupPageSize(pageSize);
            }}
          />
        </>
      )}
      <SectionDetailDialog
        section={selectedSection}
        findings={relatedFindingsQuery.data?.items ?? []}
        groups={relatedGroupsQuery.data?.items ?? []}
        isLoadingRelated={
          relatedFindingsQuery.isLoading || relatedGroupsQuery.isLoading
        }
        onClose={() => setSelectedSection(null)}
        {...(runQuery.data
          ? {
              documentId: runQuery.data.documentId,
              revisionId: runQuery.data.documentRevisionId,
              extractionRunId: runQuery.data.extractionRunId,
            }
          : {})}
      />
    </div>
  );
}
