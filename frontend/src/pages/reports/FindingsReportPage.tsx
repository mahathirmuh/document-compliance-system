import { Download, Search } from 'lucide-react';
import { useState } from 'react';

import { getApiErrorMessage } from '../../api/errors';
import { FindingsTable } from '../../components/compliance/FindingsTable';
import {
  Phase8ErrorAlert,
  Phase8FilterField,
  Phase8Loading,
  Phase8Pagination,
} from '../../components/compliance/Phase8TableUtilities';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { useDocumentFormOptions } from '../../hooks/useDocumentFormOptions';
import { useFindingsExport, useFindingsReport } from '../../hooks/useFindings';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import {
  findingSeverities,
  findingStatuses,
  type FindingListParams,
  type FindingSeverity,
  type FindingStatus,
} from '../../types/finding';
import { downloadFile } from '../../utils/downloadFile';

export function FindingsReportPage() {
  const user = useAuthStore((state) => state.user);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const departmentLocked = !hasPermission('compliance:view_all_departments');
  const [searchInput, setSearchInput] = useState('');
  const search = useDebouncedValue(searchInput.trim(), 350);
  const [departmentId, setDepartmentId] = useState(
    departmentLocked ? (user?.departmentId ?? '') : '',
  );
  const [severity, setSeverity] = useState<FindingSeverity | ''>('');
  const [status, setStatus] = useState<FindingStatus | ''>('');
  const [createdFrom, setCreatedFrom] = useState('');
  const [createdTo, setCreatedTo] = useState('');
  const [page, setPage] = useState(1);
  const optionsQuery = useDocumentFormOptions();
  const params: FindingListParams = {
    page,
    pageSize: 20,
    sortBy: 'severity',
    sortOrder: 'desc',
    ...(search ? { search } : {}),
    ...(departmentId ? { departmentId } : {}),
    ...(severity ? { severity } : {}),
    ...(status ? { status } : {}),
    ...(createdFrom ? { createdFrom } : {}),
    ...(createdTo ? { createdTo } : {}),
  };
  const query = useFindingsReport(params);
  const exportMutation = useFindingsExport();
  const { showToast } = useToast();

  const exportReport = async (format: 'xlsx' | 'json'): Promise<void> => {
    const filters = {
      sortBy: 'severity',
      sortOrder: 'desc' as const,
      ...(search ? { search } : {}),
      ...(departmentId ? { departmentId } : {}),
      ...(severity ? { severity } : {}),
      ...(status ? { status } : {}),
      ...(createdFrom ? { createdFrom } : {}),
      ...(createdTo ? { createdTo } : {}),
    };
    try {
      const result = await exportMutation.mutateAsync({ format, params: filters });
      downloadFile(result, `findings-report.${format}`);
      showToast({
        tone: 'success',
        title: `Findings report ${format.toUpperCase()} downloaded`,
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Findings report export failed',
        message: getApiErrorMessage(error, 'The report could not be downloaded.'),
      });
    }
  };

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Reports"
        title="Findings Report"
        description="Summarize finding workflow and severity while preserving API-enforced department scope."
        actions={
          hasPermission('findings:export') ? (
            <>
              {(['xlsx', 'json'] as const).map((format) => (
                <button
                  key={format}
                  type="button"
                  disabled={exportMutation.isPending}
                  onClick={() => void exportReport(format)}
                  className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 px-3 text-xs font-semibold uppercase text-slate-700 disabled:opacity-50"
                >
                  <Download className="size-4" aria-hidden="true" />
                  {format}
                </button>
              ))}
            </>
          ) : undefined
        }
      />
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
                placeholder="Code, document, or title"
                className="min-h-11 w-full rounded-xl border border-slate-300 pl-10 pr-3 text-sm"
              />
            </span>
          </Phase8FilterField>
          <Phase8FilterField label="Department">
            <select
              value={departmentId}
              disabled={departmentLocked}
              onChange={(event) => {
                setDepartmentId(event.target.value);
                setPage(1);
              }}
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
          <Phase8FilterField label="Severity">
            <select
              value={severity}
              onChange={(event) => {
                setSeverity(event.target.value as FindingSeverity | '');
                setPage(1);
              }}
              className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
            >
              <option value="">All severities</option>
              {findingSeverities.map((candidate) => (
                <option key={candidate} value={candidate}>
                  {candidate}
                </option>
              ))}
            </select>
          </Phase8FilterField>
          <Phase8FilterField label="Status">
            <select
              value={status}
              onChange={(event) => {
                setStatus(event.target.value as FindingStatus | '');
                setPage(1);
              }}
              className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
            >
              <option value="">All statuses</option>
              {findingStatuses.map((candidate) => (
                <option key={candidate} value={candidate}>
                  {candidate.replaceAll('_', ' ')}
                </option>
              ))}
            </select>
          </Phase8FilterField>
          <Phase8FilterField label="Created From">
            <input
              type="date"
              value={createdFrom}
              onChange={(event) => {
                setCreatedFrom(event.target.value);
                setPage(1);
              }}
              className="min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
            />
          </Phase8FilterField>
          <Phase8FilterField label="Created To">
            <input
              type="date"
              min={createdFrom || undefined}
              value={createdTo}
              onChange={(event) => {
                setCreatedTo(event.target.value);
                setPage(1);
              }}
              className="min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
            />
          </Phase8FilterField>
        </div>
      </section>

      {query.isLoading && <Phase8Loading label="Loading findings report" />}
      {query.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            query.error,
            'The findings report could not be loaded.',
          )}
          onRetry={() => void query.refetch()}
        />
      )}
      {query.data && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            {[
              ['Total Findings', query.data.summary.totalFindings],
              ['Open', query.data.summary.open],
              ['In Review', query.data.summary.inReview],
              ['Resolved', query.data.summary.resolved],
              ['Critical', query.data.summary.critical],
              ['Major', query.data.summary.major],
              ['Minor', query.data.summary.minor],
              ['False Positive', query.data.summary.falsePositive],
              ['Accepted Risk', query.data.summary.acceptedRisk],
            ].map(([label, value]) => (
              <div
                key={String(label)}
                className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
              >
                <p className="text-2xl font-semibold text-slate-950">
                  {Number(value).toLocaleString()}
                </p>
                <p className="mt-1 text-xs text-slate-500">{label}</p>
              </div>
            ))}
          </div>
          <div className="grid gap-5 xl:grid-cols-3">
            <ReportBars
              title="Findings by Department"
              items={query.data.summary.byDepartment}
            />
            <ReportBars title="Findings by Type" items={query.data.summary.byType} />
            <ReportBars
              title="Findings by Severity"
              items={query.data.summary.bySeverity.map((item) => ({
                label: item.label,
                count: item.count,
              }))}
            />
          </div>
          <FindingsTrendPanel items={query.data.summary.trend} />
          <FindingsTable findings={query.data.findings.items} />
          <Phase8Pagination
            page={page}
            totalItems={query.data.findings.totalItems}
            totalPages={query.data.findings.totalPages}
            label="findings"
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
}

export function FindingsTrendPanel({
  items,
}: {
  items: readonly { period: string; count: number }[];
}) {
  const maximum = Math.max(1, ...items.map((item) => item.count));
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-950">Findings Trend</h2>
      <p className="mt-1 text-xs text-slate-500">
        Finding volume for each reporting period returned by the scoped report.
      </p>
      {items.length > 0 ? (
        <div
          role="img"
          aria-label="Finding count trend by reporting period"
          className="mt-5 flex min-h-52 items-end gap-3 overflow-x-auto border-b border-slate-200 px-2 pt-4"
        >
          {items.map((item) => (
            <div
              key={item.period}
              className="flex min-w-16 flex-1 flex-col items-center justify-end"
            >
              <span className="mb-2 text-xs font-semibold text-slate-700">
                {item.count}
              </span>
              <div
                aria-label={`${item.period}: ${item.count} findings`}
                className="w-full max-w-16 rounded-t-lg bg-blue-600"
                style={{
                  height: `${Math.max(8, (item.count / maximum) * 144)}px`,
                }}
              />
              <span className="my-2 whitespace-nowrap text-[10px] text-slate-500">
                {item.period}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-4 rounded-xl bg-slate-50 py-10 text-center text-sm text-slate-500">
          No trend data.
        </p>
      )}
    </section>
  );
}

function ReportBars({
  items,
  title,
}: {
  title: string;
  items: readonly { label: string; count: number }[];
}) {
  const maximum = Math.max(1, ...items.map((item) => item.count));
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-950">{title}</h2>
      <div className="mt-4 space-y-3">
        {items.slice(0, 10).map((item) => (
          <div key={item.label}>
            <div className="flex justify-between gap-3 text-xs">
              <span className="truncate text-slate-600">{item.label}</span>
              <span className="font-semibold text-slate-700">{item.count}</span>
            </div>
            <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full bg-blue-600"
                style={{ width: `${(item.count / maximum) * 100}%` }}
              />
            </div>
          </div>
        ))}
        {items.length === 0 && (
          <p className="py-8 text-center text-sm text-slate-500">No report data.</p>
        )}
      </div>
    </section>
  );
}
