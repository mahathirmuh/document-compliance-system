import { Clock3, Download, FileBarChart } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import { Phase8ErrorAlert } from '../../components/compliance/Phase8TableUtilities';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { AdvancedReportBuilder } from '../../components/reports/AdvancedReportBuilder';
import {
  useAdvancedReportMutations,
  useReportJob,
  useReportJobs,
  useReportSnapshots,
} from '../../hooks/useAdvancedReports';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type {
  AdvancedReportType,
  ReportGenerateRequest,
  ReportScheduleCreate,
} from '../../types/advancedReporting';
import { downloadFile } from '../../utils/downloadFile';
import { formatDateTime } from '../../utils/formatters';

const analyticsSections = [
  'Executive Overview',
  'Compliance Trends',
  'Translation Quality',
  'Glossary Quality',
  'Finding Trends',
  'Department Comparison',
  'Document Type Comparison',
  'Processing Performance',
  'Revision Improvement',
] as const;

export function AdvancedAnalyticsPage({
  initialReportType = 'COMPLIANCE_OVERVIEW',
}: {
  initialReportType?: AdvancedReportType;
}) {
  const [jobId, setJobId] = useState<string | null>(null);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canExport = hasPermission('advanced_reports:export');
  const canConfigure = hasPermission('advanced_reports:configure');
  const jobQuery = useReportJob(jobId);
  const jobsQuery = useReportJobs({ page: 1, pageSize: 10 });
  const snapshotsQuery = useReportSnapshots({ page: 1, pageSize: 20 });
  const mutations = useAdvancedReportMutations();
  const { showToast } = useToast();

  const generate = async (payload: ReportGenerateRequest): Promise<void> => {
    try {
      const job = await mutations.generate.mutateAsync(payload);
      setJobId(job.id);
      showToast({
        tone: 'success',
        title: 'Advanced report queued',
        message: 'Dataset generation is running in the reporting worker.',
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Report could not be generated',
        message: getApiErrorMessage(error, 'Review the filters and row limits.'),
      });
    }
  };

  const saveSchedule = async (payload: ReportScheduleCreate): Promise<void> => {
    try {
      await mutations.createSchedule.mutateAsync(payload);
      showToast({
        tone: 'success',
        title: 'Report schedule saved',
        message: 'Phase 9 schedules support manual execution; no email is sent.',
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Schedule could not be saved',
        message: getApiErrorMessage(error, 'Review timezone and cron expression.'),
      });
    }
  };

  const latestAvailable = snapshotsQuery.data?.items.find(
    (snapshot) => snapshot.status === 'AVAILABLE',
  );
  const summaryEntries = latestAvailable?.metadata?.summary
    ? Object.entries(latestAvailable.metadata.summary)
    : [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <MasterDataPageHeader
          eyebrow="Reports"
          title="Advanced Analytics"
          description="Generate compliance, translation quality, glossary, revision, and processing analytics from authorized operational data."
        />
        <div className="flex gap-2">
          <Link
            to="/reports/snapshots"
            className="inline-flex min-h-10 items-center rounded-xl border border-slate-300 px-4 text-xs font-semibold text-slate-700"
          >
            Report Snapshots
          </Link>
          <Link
            to="/reports/schedules"
            className="inline-flex min-h-10 items-center rounded-xl border border-slate-300 px-4 text-xs font-semibold text-slate-700"
          >
            Report Schedules
          </Link>
        </div>
      </div>

      {canExport || canConfigure ? (
        <AdvancedReportBuilder
          canGenerate={canExport}
          canSaveSchedule={canConfigure}
          initialReportType={initialReportType}
          isGenerating={mutations.generate.isPending}
          isSavingSchedule={mutations.createSchedule.isPending}
          onGenerate={generate}
          onSaveSchedule={saveSchedule}
        />
      ) : (
        <p className="rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-600">
          You can view authorized analytics. Report generation and schedule
          configuration require additional permission.
        </p>
      )}

      {jobId && jobQuery.data && (
        <section className="rounded-2xl border border-indigo-200 bg-indigo-50 p-5">
          <div className="flex items-center justify-between text-xs font-semibold text-indigo-900">
            <span>{jobQuery.data.currentStage?.replaceAll('_', ' ') ?? 'Queued'}</span>
            <span>{jobQuery.data.progress}%</span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-indigo-100">
            <span
              className="block h-full bg-indigo-700"
              style={{
                width: `${Math.max(0, Math.min(100, jobQuery.data.progress))}%`,
              }}
            />
          </div>
          <p className="mt-2 text-xs text-indigo-800">
            {jobQuery.data.status.replaceAll('_', ' ')} · polling stops at terminal
            status
          </p>
          {jobQuery.data.errorMessage && (
            <p role="alert" className="mt-2 text-xs text-rose-800">
              {jobQuery.data.errorMessage}
            </p>
          )}
        </section>
      )}

      {(jobsQuery.error ?? snapshotsQuery.error) && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            jobsQuery.error ?? snapshotsQuery.error,
            'Analytics data could not be loaded.',
          )}
        />
      )}

      <section>
        <div className="flex items-end justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-950">Executive Overview</h2>
            <p className="mt-1 text-xs text-slate-500">
              {latestAvailable
                ? `Latest authorized snapshot: ${latestAvailable.reportName}`
                : 'Generate a report to populate real metrics.'}
            </p>
          </div>
          {latestAvailable?.generatedAt && (
            <span className="text-xs text-slate-500">
              {formatDateTime(latestAvailable.generatedAt)}
            </span>
          )}
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {summaryEntries.length > 0 ? (
            summaryEntries.slice(0, 8).map(([label, value]) => (
              <div
                key={label}
                className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
              >
                <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                  {label.replaceAll('_', ' ')}
                </p>
                <p className="mt-2 text-xl font-semibold text-slate-950">
                  {value === null ? '—' : String(value)}
                </p>
              </div>
            ))
          ) : (
            <div className="col-span-full rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
              No generated metric snapshot is available. This page does not use mock
              analytics.
            </div>
          )}
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {analyticsSections.slice(1).map((section) => (
          <article
            key={section}
            className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
          >
            <FileBarChart className="size-5 text-indigo-700" aria-hidden="true" />
            <h2 className="mt-3 text-sm font-semibold text-slate-950">{section}</h2>
            <p className="mt-2 text-xs leading-5 text-slate-600">
              Available through the corresponding report type and current authorized
              filter snapshot.
            </p>
          </article>
        ))}
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-950">Recent Report Jobs</h2>
          <Clock3 className="size-4 text-slate-400" aria-hidden="true" />
        </div>
        <div className="mt-3 divide-y divide-slate-100">
          {(jobsQuery.data?.items ?? []).map((job) => (
            <div
              key={job.id}
              className="flex flex-wrap items-center justify-between gap-3 py-3 text-xs"
            >
              <span className="font-semibold text-slate-900">{job.reportName}</span>
              <span>{job.reportType.replaceAll('_', ' ')}</span>
              <span>{job.progress}%</span>
              <span className="text-slate-500">{job.status.replaceAll('_', ' ')}</span>
            </div>
          ))}
          {(jobsQuery.data?.items.length ?? 0) === 0 && (
            <p className="py-7 text-center text-sm text-slate-500">
              No report jobs have been created.
            </p>
          )}
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-950">Latest Snapshots</h2>
        <div className="mt-3 divide-y divide-slate-100">
          {(snapshotsQuery.data?.items ?? []).slice(0, 5).map((snapshot) => (
            <div
              key={snapshot.id}
              className="flex flex-wrap items-center justify-between gap-3 py-3 text-xs"
            >
              <span className="font-semibold text-slate-900">
                {snapshot.reportName}
              </span>
              <span className="uppercase">{snapshot.fileFormat}</span>
              <span>{snapshot.status}</span>
              {snapshot.status === 'AVAILABLE' && canExport && (
                <button
                  type="button"
                  disabled={mutations.download.isPending}
                  onClick={async () => {
                    const result = await mutations.download.mutateAsync(snapshot.id);
                    downloadFile(
                      result,
                      `${snapshot.reportName}.${snapshot.fileFormat}`,
                    );
                  }}
                  className="inline-flex items-center gap-1 font-semibold text-indigo-700"
                >
                  <Download className="size-3.5" aria-hidden="true" />
                  Download
                </button>
              )}
            </div>
          ))}
        </div>
      </section>

      <p className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-900">
        Reports exclude full document text by default, use bounded snippets, and are
        downloaded only through authenticated endpoints. Scheduled email delivery is not
        available in Phase 9.
      </p>
    </div>
  );
}
