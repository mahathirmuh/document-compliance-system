import {
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  FileQuestion,
  Scale,
  SearchCheck,
  ShieldAlert,
} from 'lucide-react';
import { useState, type ReactNode } from 'react';

import { getApiErrorMessage } from '../../api/errors';
import {
  Phase8ErrorAlert,
  Phase8FilterField,
  Phase8Loading,
} from '../../components/compliance/Phase8TableUtilities';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { useComplianceOverview } from '../../hooks/useCompliance';
import { useDocumentFormOptions } from '../../hooks/useDocumentFormOptions';
import { useAuthStore } from '../../store/authStore';
import type { ComplianceBreakdownItem, ComplianceStatus } from '../../types/compliance';

export function ComplianceOverviewPage() {
  const user = useAuthStore((state) => state.user);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const departmentLocked = !hasPermission('compliance:view_all_departments');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [departmentId, setDepartmentId] = useState(
    departmentLocked ? (user?.departmentId ?? '') : '',
  );
  const [sectionId, setSectionId] = useState('');
  const [documentTypeId, setDocumentTypeId] = useState('');
  const [validationRuleId, setValidationRuleId] = useState('');
  const [complianceStatus, setComplianceStatus] = useState<ComplianceStatus | ''>('');
  const optionsQuery = useDocumentFormOptions();
  const query = useComplianceOverview({
    ...(dateFrom ? { dateFrom } : {}),
    ...(dateTo ? { dateTo } : {}),
    ...(departmentId ? { departmentId } : {}),
    ...(sectionId ? { sectionId } : {}),
    ...(documentTypeId ? { documentTypeId } : {}),
    ...(validationRuleId ? { validationRuleId } : {}),
    ...(complianceStatus ? { complianceStatus } : {}),
  });

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Compliance"
        title="Compliance Overview"
        description="A scope-aware view of multilingual structure, language coverage, compliance status, and open findings."
      />
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Phase8FilterField label="Date From">
            <input
              type="date"
              value={dateFrom}
              onChange={(event) => setDateFrom(event.target.value)}
              className="min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
            />
          </Phase8FilterField>
          <Phase8FilterField label="Date To">
            <input
              type="date"
              min={dateFrom || undefined}
              value={dateTo}
              onChange={(event) => setDateTo(event.target.value)}
              className="min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
            />
          </Phase8FilterField>
          <Phase8FilterField label="Department">
            <select
              value={departmentId}
              disabled={departmentLocked}
              onChange={(event) => setDepartmentId(event.target.value)}
              className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm disabled:bg-slate-100"
            >
              <option value="">
                {departmentLocked ? 'Assigned department only' : 'All departments'}
              </option>
              {(optionsQuery.data?.departments ?? []).map((department) => (
                <option key={department.id} value={department.id}>
                  {department.code} — {department.name}
                </option>
              ))}
            </select>
          </Phase8FilterField>
          <Phase8FilterField label="Section">
            <select
              value={sectionId}
              onChange={(event) => setSectionId(event.target.value)}
              className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
            >
              <option value="">All sections</option>
              {(optionsQuery.data?.sections ?? []).map((section) => (
                <option key={section.id} value={section.id}>
                  {section.code} — {section.name}
                </option>
              ))}
            </select>
          </Phase8FilterField>
          <Phase8FilterField label="Document Type">
            <select
              value={documentTypeId}
              onChange={(event) => setDocumentTypeId(event.target.value)}
              className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
            >
              <option value="">All document types</option>
              {(optionsQuery.data?.documentTypes ?? []).map((documentType) => (
                <option key={documentType.id} value={documentType.id}>
                  {documentType.code} — {documentType.name}
                </option>
              ))}
            </select>
          </Phase8FilterField>
          <Phase8FilterField label="Validation Rule">
            <select
              value={validationRuleId}
              onChange={(event) => setValidationRuleId(event.target.value)}
              className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
            >
              <option value="">All rules</option>
              {(optionsQuery.data?.validationRules ?? []).map((rule) => (
                <option key={rule.id} value={rule.id}>
                  {rule.code} — {rule.name}
                </option>
              ))}
            </select>
          </Phase8FilterField>
          <Phase8FilterField label="Compliance Status">
            <select
              value={complianceStatus}
              onChange={(event) =>
                setComplianceStatus(event.target.value as ComplianceStatus | '')
              }
              className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
            >
              <option value="">All statuses</option>
              {(
                [
                  'COMPLIANT',
                  'PARTIALLY_COMPLIANT',
                  'NON_COMPLIANT',
                  'NEEDS_REVIEW',
                  'NOT_EVALUATED',
                ] as const
              ).map((status) => (
                <option key={status} value={status}>
                  {status.replaceAll('_', ' ')}
                </option>
              ))}
            </select>
          </Phase8FilterField>
        </div>
        {departmentLocked && (
          <p className="mt-3 text-xs text-slate-500">
            Results are limited to your assigned department.
          </p>
        )}
      </section>

      {query.isLoading && <Phase8Loading label="Loading compliance overview" />}
      {query.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            query.error,
            'The compliance overview could not be loaded.',
          )}
          onRetry={() => void query.refetch()}
        />
      )}
      {query.data && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              icon={<ClipboardCheck className="size-5" />}
              label="Total Validated Documents"
              value={query.data.totalValidatedDocuments}
              tone="blue"
            />
            <MetricCard
              icon={<CheckCircle2 className="size-5" />}
              label="Compliant"
              value={query.data.compliant}
              tone="emerald"
            />
            <MetricCard
              icon={<Scale className="size-5" />}
              label="Partially Compliant"
              value={query.data.partiallyCompliant}
              tone="amber"
            />
            <MetricCard
              icon={<ShieldAlert className="size-5" />}
              label="Non-Compliant"
              value={query.data.nonCompliant}
              tone="rose"
            />
            <MetricCard
              icon={<SearchCheck className="size-5" />}
              label="Needs Review"
              value={query.data.needsReview}
              tone="violet"
            />
            <MetricCard
              icon={<FileQuestion className="size-5" />}
              label="Not Evaluated"
              value={query.data.notEvaluated}
              tone="slate"
            />
            <MetricCard
              icon={<AlertOctagon className="size-5" />}
              label="Open Critical Findings"
              value={query.data.openCriticalFindings}
              tone="rose"
            />
            <MetricCard
              icon={<AlertTriangle className="size-5" />}
              label="Open Major Findings"
              value={query.data.openMajorFindings}
              tone="orange"
            />
          </div>

          <div className="grid gap-5 xl:grid-cols-2">
            <BreakdownPanel
              title="Compliance by Department"
              items={query.data.byDepartment}
            />
            <BreakdownPanel
              title="Compliance by Document Type"
              items={query.data.byDocumentType}
            />
            <SimpleBars
              title="Findings by Severity"
              items={[
                { label: 'Critical', value: query.data.findingsBySeverity.critical },
                { label: 'Major', value: query.data.findingsBySeverity.major },
                { label: 'Minor', value: query.data.findingsBySeverity.minor },
                {
                  label: 'Information',
                  value: query.data.findingsBySeverity.information,
                },
              ]}
            />
            <SimpleBars
              title="Missing Languages"
              items={query.data.missingLanguages.map((item) => ({
                label:
                  item.languageCode === 'id'
                    ? 'Bahasa Indonesia'
                    : item.languageCode === 'en'
                      ? 'English'
                      : '中文 / Mandarin',
                value: item.count,
              }))}
            />
            <SimpleBars
              title="Missing Sections"
              items={query.data.missingSections.map((item) => ({
                label: item.canonicalCode,
                value: item.count,
              }))}
            />
            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-sm font-semibold text-slate-950">Compliance Trend</h2>
              <div className="mt-5 flex min-h-48 items-end gap-3 overflow-x-auto">
                {query.data.trend.map((item) => (
                  <div
                    key={item.period}
                    className="flex min-w-16 flex-1 flex-col items-center gap-2"
                  >
                    <span className="text-[10px] font-semibold text-slate-600">
                      {item.score.toFixed(1)}
                    </span>
                    <div className="flex h-32 w-full items-end rounded-lg bg-slate-50 px-2">
                      <div
                        className="w-full rounded-t-md bg-blue-600"
                        style={{ height: `${Math.max(2, Math.min(100, item.score))}%` }}
                      />
                    </div>
                    <span className="text-center text-[10px] text-slate-500">
                      {item.period}
                    </span>
                  </div>
                ))}
                {query.data.trend.length === 0 && (
                  <p className="self-center text-sm text-slate-500">
                    No trend data for this filter.
                  </p>
                )}
              </div>
            </section>
          </div>
        </>
      )}
    </div>
  );
}

const toneClasses = {
  blue: 'bg-blue-50 text-blue-700',
  emerald: 'bg-emerald-50 text-emerald-700',
  amber: 'bg-amber-50 text-amber-700',
  rose: 'bg-rose-50 text-rose-700',
  violet: 'bg-violet-50 text-violet-700',
  slate: 'bg-slate-100 text-slate-700',
  orange: 'bg-orange-50 text-orange-700',
} as const;

function MetricCard({
  icon,
  label,
  tone,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: number;
  tone: keyof typeof toneClasses;
}) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div
        className={`grid size-10 place-items-center rounded-xl ${toneClasses[tone]}`}
      >
        {icon}
      </div>
      <p className="mt-4 text-2xl font-semibold text-slate-950">
        {value.toLocaleString()}
      </p>
      <p className="mt-1 text-xs font-medium text-slate-500">{label}</p>
    </article>
  );
}

function BreakdownPanel({
  items,
  title,
}: {
  title: string;
  items: readonly ComplianceBreakdownItem[];
}) {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-950">{title}</h2>
      <div className="mt-4 space-y-4">
        {items.map((item) => (
          <div key={item.label}>
            <div className="flex justify-between gap-3 text-xs">
              <span className="font-medium text-slate-700">{item.label}</span>
              <span className="text-slate-500">{item.total}</span>
            </div>
            <div className="mt-2 flex h-2 overflow-hidden rounded-full bg-slate-100">
              {[
                ['bg-emerald-500', item.compliant],
                ['bg-amber-500', item.partiallyCompliant],
                ['bg-rose-500', item.nonCompliant],
                ['bg-violet-500', item.needsReview],
                ['bg-slate-400', item.notEvaluated],
              ].map(([className, count], index) => (
                <span
                  key={index}
                  className={String(className)}
                  style={{
                    width: `${
                      item.total > 0 ? (Number(count) / item.total) * 100 : 0
                    }%`,
                  }}
                />
              ))}
            </div>
          </div>
        ))}
        {items.length === 0 && (
          <p className="py-8 text-center text-sm text-slate-500">
            No breakdown data for this filter.
          </p>
        )}
      </div>
    </section>
  );
}

function SimpleBars({
  items,
  title,
}: {
  title: string;
  items: readonly { label: string; value: number }[];
}) {
  const maximum = Math.max(1, ...items.map((item) => item.value));
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-950">{title}</h2>
      <div className="mt-4 space-y-3">
        {items.map((item) => (
          <div
            key={item.label}
            className="grid grid-cols-[8rem_1fr_auto] items-center gap-3"
          >
            <span className="truncate text-xs text-slate-600">{item.label}</span>
            <span className="h-2 overflow-hidden rounded-full bg-slate-100">
              <span
                className="block h-full rounded-full bg-blue-600"
                style={{ width: `${(item.value / maximum) * 100}%` }}
              />
            </span>
            <span className="text-xs font-semibold text-slate-700">{item.value}</span>
          </div>
        ))}
        {items.length === 0 && (
          <p className="py-8 text-center text-sm text-slate-500">
            No data for this filter.
          </p>
        )}
      </div>
    </section>
  );
}
