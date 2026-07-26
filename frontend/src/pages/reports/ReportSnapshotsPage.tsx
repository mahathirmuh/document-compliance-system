import { Download, Eye, RefreshCw, Trash2 } from 'lucide-react';
import { useState } from 'react';

import { getApiErrorMessage } from '../../api/errors';
import {
  Phase8ErrorAlert,
  Phase8FilterField,
  Phase8Loading,
  Phase8Pagination,
} from '../../components/compliance/Phase8TableUtilities';
import { ConfirmationDialog } from '../../components/master-data/ConfirmationDialog';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import {
  useAdvancedReportMutations,
  useReportSnapshots,
} from '../../hooks/useAdvancedReports';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import {
  advancedReportTypes,
  type AdvancedReportType,
  type ReportSnapshot,
  type ReportSnapshotStatus,
} from '../../types/advancedReporting';
import { downloadFile } from '../../utils/downloadFile';
import { formatDateTime } from '../../utils/formatters';

export function ReportSnapshotsPage() {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const [page, setPage] = useState(1);
  const [reportType, setReportType] = useState<AdvancedReportType | ''>('');
  const [status, setStatus] = useState<ReportSnapshotStatus | ''>('');
  const [format, setFormat] = useState('');
  const [filterTarget, setFilterTarget] = useState<ReportSnapshot | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ReportSnapshot | null>(null);
  const query = useReportSnapshots({
    page,
    pageSize: 20,
    ...(reportType ? { reportType } : {}),
    ...(status ? { status } : {}),
    ...(format ? { format: format as 'xlsx' | 'json' | 'pdf' } : {}),
  });
  const mutations = useAdvancedReportMutations();
  const { showToast } = useToast();

  const download = async (snapshot: ReportSnapshot): Promise<void> => {
    try {
      const result = await mutations.download.mutateAsync(snapshot.id);
      downloadFile(result, `${snapshot.reportName}.${snapshot.fileFormat}`);
      showToast({ tone: 'success', title: 'Report download started' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Snapshot could not be downloaded',
        message: getApiErrorMessage(
          error,
          'It may have expired or be outside your scope.',
        ),
      });
    }
  };

  const regenerate = async (snapshot: ReportSnapshot): Promise<void> => {
    try {
      await mutations.generate.mutateAsync({
        reportType: snapshot.reportType,
        reportName: snapshot.reportName,
        filters: snapshot.filters,
        outputFormat: snapshot.fileFormat,
        includeCharts: true,
        includeDetailedTables: true,
      });
      showToast({ tone: 'success', title: 'Report regeneration queued' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Report could not be regenerated',
        message: getApiErrorMessage(error, 'Review the saved filters.'),
      });
    }
  };

  const remove = async (): Promise<void> => {
    if (!deleteTarget) {
      return;
    }
    try {
      await mutations.deleteSnapshot.mutateAsync(deleteTarget.id);
      setDeleteTarget(null);
      showToast({
        tone: 'success',
        title: 'Report snapshot deleted',
        message: 'The snapshot was soft-deleted and is no longer downloadable.',
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Snapshot could not be deleted',
        message: getApiErrorMessage(error, 'Refresh and try again.'),
      });
    }
  };

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Reports"
        title="Report Snapshots"
        description="Manage generated files stored behind authenticated download endpoints and explicit retention status."
      />
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="grid gap-4 sm:grid-cols-3">
          <FilterSelect
            label="Report Type"
            value={reportType}
            onChange={(value) => {
              setReportType(value as AdvancedReportType | '');
              setPage(1);
            }}
            options={[
              ['', 'All report types'],
              ...advancedReportTypes.map(
                (type) => [type, type.replaceAll('_', ' ')] as const,
              ),
            ]}
          />
          <FilterSelect
            label="Status"
            value={status}
            onChange={(value) => {
              setStatus(value as ReportSnapshotStatus | '');
              setPage(1);
            }}
            options={[
              ['', 'All statuses'],
              ...(
                ['GENERATING', 'AVAILABLE', 'FAILED', 'EXPIRED', 'DELETED'] as const
              ).map((candidate) => [candidate, candidate] as const),
            ]}
          />
          <FilterSelect
            label="Format"
            value={format}
            onChange={(value) => {
              setFormat(value);
              setPage(1);
            }}
            options={[
              ['', 'All formats'],
              ['xlsx', 'XLSX'],
              ['json', 'JSON'],
              ['pdf', 'PDF'],
            ]}
          />
        </div>
      </section>

      {query.isLoading && <Phase8Loading label="Loading report snapshots" />}
      {query.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            query.error,
            'Report snapshots could not be loaded.',
          )}
          onRetry={() => void query.refetch()}
        />
      )}
      {query.data && (
        <>
          <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
            <table className="min-w-[88rem] divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  {[
                    'Generated At',
                    'Report Name',
                    'Report Type',
                    'Format',
                    'Generated By',
                    'Size',
                    'Status',
                    'Expires At',
                    'Actions',
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
                {query.data.items.map((snapshot) => (
                  <tr key={snapshot.id}>
                    <Cell>
                      {snapshot.generatedAt
                        ? formatDateTime(snapshot.generatedAt)
                        : '—'}
                    </Cell>
                    <Cell strong>{snapshot.reportName}</Cell>
                    <Cell>{snapshot.reportType.replaceAll('_', ' ')}</Cell>
                    <Cell>{snapshot.fileFormat.toUpperCase()}</Cell>
                    <Cell>{formatUser(snapshot.generatedBy)}</Cell>
                    <Cell>{formatFileSize(snapshot.fileSize)}</Cell>
                    <Cell>{snapshot.status}</Cell>
                    <Cell>
                      {snapshot.expiresAt ? formatDateTime(snapshot.expiresAt) : '—'}
                    </Cell>
                    <td className="px-4 py-3">
                      <div className="flex min-w-max gap-1">
                        {snapshot.status === 'AVAILABLE' &&
                          hasPermission('advanced_reports:export') && (
                            <Action
                              label="Download"
                              icon={Download}
                              onClick={() => void download(snapshot)}
                            />
                          )}
                        {hasPermission('advanced_reports:export') && (
                          <Action
                            label="Regenerate"
                            icon={RefreshCw}
                            onClick={() => void regenerate(snapshot)}
                          />
                        )}
                        <Action
                          label="View Filter"
                          icon={Eye}
                          onClick={() => setFilterTarget(snapshot)}
                        />
                        {hasPermission('advanced_reports:export') &&
                          snapshot.status !== 'DELETED' && (
                            <Action
                              label="Delete"
                              icon={Trash2}
                              onClick={() => setDeleteTarget(snapshot)}
                            />
                          )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {query.data.items.length === 0 && (
              <p className="p-10 text-center text-sm text-slate-500">
                No report snapshots match these filters.
              </p>
            )}
          </div>
          <Phase8Pagination
            page={page}
            totalItems={query.data.totalItems}
            totalPages={query.data.totalPages}
            label="report snapshots"
            onPageChange={setPage}
          />
        </>
      )}
      {filterTarget && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Report filter snapshot"
          className="fixed inset-0 z-50 grid place-items-center bg-slate-950/50 p-4"
        >
          <div className="w-full max-w-2xl rounded-3xl bg-white p-6 shadow-2xl">
            <h2 className="text-lg font-semibold text-slate-950">
              {filterTarget.reportName}
            </h2>
            <dl className="mt-5 grid gap-3 sm:grid-cols-2">
              {Object.entries(filterTarget.filters).map(([key, value]) => (
                <div key={key} className="rounded-xl bg-slate-50 p-3">
                  <dt className="text-[10px] font-semibold uppercase text-slate-500">
                    {key.replaceAll(/([A-Z])/g, ' $1')}
                  </dt>
                  <dd className="mt-1 break-words text-xs text-slate-800">
                    {Array.isArray(value)
                      ? value.join(', ')
                      : typeof value === 'boolean'
                        ? value
                          ? 'Yes'
                          : 'No'
                        : String(value)}
                  </dd>
                </div>
              ))}
            </dl>
            <button
              type="button"
              onClick={() => setFilterTarget(null)}
              className="mt-5 min-h-10 rounded-xl bg-slate-900 px-4 text-sm font-semibold text-white"
            >
              Close
            </button>
          </div>
        </div>
      )}
      <ConfirmationDialog
        isOpen={deleteTarget !== null}
        title="Delete report snapshot?"
        message="This performs a soft delete or protected storage move. The generated file will no longer be downloadable."
        confirmLabel="Delete Snapshot"
        tone="danger"
        isPending={mutations.deleteSnapshot.isPending}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => void remove()}
      />
    </div>
  );
}

function FilterSelect({
  label,
  onChange,
  options,
  value,
}: {
  label: string;
  value: string;
  options: readonly (readonly [string, string])[];
  onChange: (value: string) => void;
}) {
  return (
    <Phase8FilterField label={label}>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
      >
        {options.map(([optionValue, optionLabel]) => (
          <option key={optionValue || 'all'} value={optionValue}>
            {optionLabel}
          </option>
        ))}
      </select>
    </Phase8FilterField>
  );
}

function Cell({
  children,
  strong = false,
}: {
  children: React.ReactNode;
  strong?: boolean;
}) {
  return (
    <td
      className={`px-4 py-3 text-xs ${
        strong ? 'font-semibold text-slate-900' : 'text-slate-600'
      }`}
    >
      {children}
    </td>
  );
}

function Action({
  icon: Icon,
  label,
  onClick,
}: {
  icon: typeof Download;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-2.5 text-xs font-semibold text-indigo-700 hover:bg-indigo-50"
    >
      <Icon className="size-3.5" aria-hidden="true" />
      {label}
    </button>
  );
}

const formatFileSize = (value: number | null): string => {
  if (value === null) {
    return '—';
  }
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
};

const formatUser = (value: ReportSnapshot['generatedBy']): string => {
  if (typeof value === 'string') {
    return value;
  }
  return value?.name ?? 'Unknown user';
};
