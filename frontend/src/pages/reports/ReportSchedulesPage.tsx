import { Edit3, Pause, Play, Plus, Power } from 'lucide-react';
import { useState } from 'react';

import { getApiErrorMessage } from '../../api/errors';
import {
  Phase8ErrorAlert,
  Phase8Loading,
  Phase8Pagination,
} from '../../components/compliance/Phase8TableUtilities';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import {
  useAdvancedReportMutations,
  useReportSchedules,
} from '../../hooks/useAdvancedReports';
import { useToast } from '../../providers/useToast';
import {
  advancedReportTypes,
  type AdvancedReportType,
  type ReportFormat,
  type ReportSchedule,
  type ReportScheduleCreate,
  type ReportScheduleType,
} from '../../types/advancedReporting';
import { formatDateTime } from '../../utils/formatters';

export function ReportSchedulesPage() {
  const [page, setPage] = useState(1);
  const [dialogTarget, setDialogTarget] = useState<ReportSchedule | 'create' | null>(
    null,
  );
  const query = useReportSchedules({ page, pageSize: 20 });
  const mutations = useAdvancedReportMutations();
  const { showToast } = useToast();

  const save = async (payload: ReportScheduleCreate): Promise<void> => {
    try {
      if (dialogTarget && dialogTarget !== 'create') {
        await mutations.updateSchedule.mutateAsync({
          scheduleId: dialogTarget.id,
          payload,
        });
      } else {
        await mutations.createSchedule.mutateAsync(payload);
      }
      setDialogTarget(null);
      showToast({ tone: 'success', title: 'Report schedule saved' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Schedule could not be saved',
        message: getApiErrorMessage(error, 'Review cron and timezone.'),
      });
    }
  };

  const runNow = async (schedule: ReportSchedule): Promise<void> => {
    try {
      await mutations.runSchedule.mutateAsync(schedule.id);
      showToast({
        tone: 'success',
        title: 'Scheduled report queued',
        message: 'Manual execution started. No email will be sent.',
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Schedule could not run',
        message: getApiErrorMessage(error, 'Try again.'),
      });
    }
  };

  const toggle = async (schedule: ReportSchedule): Promise<void> => {
    try {
      if (schedule.isActive) {
        await mutations.disableSchedule.mutateAsync(schedule.id);
      } else {
        await mutations.updateSchedule.mutateAsync({
          scheduleId: schedule.id,
          payload: { isActive: true },
        });
      }
      showToast({
        tone: 'success',
        title: schedule.isActive ? 'Schedule disabled' : 'Schedule enabled',
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Schedule status could not be changed',
        message: getApiErrorMessage(error, 'Refresh and try again.'),
      });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <MasterDataPageHeader
          eyebrow="Reports"
          title="Report Schedules"
          description="Configure report cadence and run schedules manually. Scheduled email delivery is not implemented in Phase 9."
        />
        <button
          type="button"
          onClick={() => setDialogTarget('create')}
          className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-indigo-700 px-4 text-xs font-semibold text-white"
        >
          <Plus className="size-4" aria-hidden="true" />
          Create Schedule
        </button>
      </div>
      {query.isLoading && <Phase8Loading label="Loading report schedules" />}
      {query.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            query.error,
            'Report schedules could not be loaded.',
          )}
          onRetry={() => void query.refetch()}
        />
      )}
      {query.data && (
        <>
          <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
            <table className="min-w-[78rem] divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  {[
                    'Name',
                    'Report Type',
                    'Schedule',
                    'Timezone',
                    'Formats',
                    'Last Run',
                    'Next Run',
                    'Status',
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
                {query.data.items.map((schedule) => (
                  <tr key={schedule.id}>
                    <Cell strong>{schedule.name}</Cell>
                    <Cell>{schedule.reportType.replaceAll('_', ' ')}</Cell>
                    <Cell>
                      {schedule.scheduleType.replaceAll('_', ' ')}
                      {schedule.cronExpression ? ` · ${schedule.cronExpression}` : ''}
                    </Cell>
                    <Cell>{schedule.timezone}</Cell>
                    <Cell>{schedule.formats.join(', ').toUpperCase()}</Cell>
                    <Cell>
                      {schedule.lastRunAt
                        ? formatDateTime(schedule.lastRunAt)
                        : 'Never'}
                    </Cell>
                    <Cell>
                      {schedule.nextRunAt ? formatDateTime(schedule.nextRunAt) : '—'}
                    </Cell>
                    <Cell>{schedule.isActive ? 'Active' : 'Disabled'}</Cell>
                    <td className="px-4 py-3">
                      <div className="flex min-w-max gap-1">
                        <Action
                          label="Edit"
                          icon={Edit3}
                          onClick={() => setDialogTarget(schedule)}
                        />
                        <Action
                          label="Run Now"
                          icon={Play}
                          onClick={() => void runNow(schedule)}
                        />
                        <Action
                          label={schedule.isActive ? 'Disable' : 'Enable'}
                          icon={schedule.isActive ? Pause : Power}
                          onClick={() => void toggle(schedule)}
                        />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {query.data.items.length === 0 && (
              <p className="p-10 text-center text-sm text-slate-500">
                No report schedules configured.
              </p>
            )}
          </div>
          <Phase8Pagination
            page={page}
            totalItems={query.data.totalItems}
            totalPages={query.data.totalPages}
            label="report schedules"
            onPageChange={setPage}
          />
        </>
      )}
      <ScheduleDialog
        open={dialogTarget !== null}
        schedule={dialogTarget === 'create' ? null : dialogTarget}
        pending={
          mutations.createSchedule.isPending || mutations.updateSchedule.isPending
        }
        onClose={() => setDialogTarget(null)}
        onSave={save}
      />
    </div>
  );
}

function ScheduleDialog({
  onClose,
  onSave,
  open,
  pending,
  schedule,
}: {
  open: boolean;
  schedule: ReportSchedule | null;
  pending: boolean;
  onClose: () => void;
  onSave: (payload: ReportScheduleCreate) => Promise<void>;
}) {
  const [name, setName] = useState('');
  const [reportType, setReportType] =
    useState<AdvancedReportType>('COMPLIANCE_OVERVIEW');
  const [scheduleType, setScheduleType] = useState<ReportScheduleType>('MONTHLY');
  const [cronExpression, setCronExpression] = useState('');
  const [timezone, setTimezone] = useState(
    Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
  );
  const [formats, setFormats] = useState<ReportFormat[]>(['xlsx']);
  const initialKey = schedule?.id ?? (open ? 'create' : 'closed');
  const [loadedKey, setLoadedKey] = useState('');
  if (open && loadedKey !== initialKey) {
    setLoadedKey(initialKey);
    setName(schedule?.name ?? '');
    setReportType(schedule?.reportType ?? 'COMPLIANCE_OVERVIEW');
    setScheduleType(schedule?.scheduleType ?? 'MONTHLY');
    setCronExpression(schedule?.cronExpression ?? '');
    setTimezone(
      schedule?.timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone ?? 'UTC',
    );
    setFormats(schedule ? [...schedule.formats] : ['xlsx']);
  }
  if (!open) {
    return null;
  }
  const valid =
    name.trim() &&
    timezone.trim() &&
    formats.length > 0 &&
    (scheduleType !== 'CUSTOM_CRON' || cronExpression.trim());
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={schedule ? 'Edit report schedule' : 'Create report schedule'}
      className="fixed inset-0 z-50 grid place-items-center bg-slate-950/50 p-4"
    >
      <form
        className="w-full max-w-2xl rounded-3xl bg-white p-6 shadow-2xl"
        onSubmit={(event) => {
          event.preventDefault();
          if (valid) {
            void onSave({
              name: name.trim(),
              reportType,
              filters: schedule?.filters ?? {},
              formats,
              scheduleType,
              cronExpression:
                scheduleType === 'CUSTOM_CRON' ? cronExpression.trim() : null,
              timezone: timezone.trim(),
            });
          }
        }}
      >
        <h2 className="text-lg font-semibold text-slate-950">
          {schedule ? 'Edit Report Schedule' : 'Create Report Schedule'}
        </h2>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <Field label="Name">
            <input
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
              className={inputClass}
            />
          </Field>
          <Field label="Report Type">
            <select
              value={reportType}
              onChange={(event) =>
                setReportType(event.target.value as AdvancedReportType)
              }
              className={inputClass}
            >
              {advancedReportTypes.map((type) => (
                <option key={type} value={type}>
                  {type.replaceAll('_', ' ')}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Schedule Type">
            <select
              value={scheduleType}
              onChange={(event) =>
                setScheduleType(event.target.value as ReportScheduleType)
              }
              className={inputClass}
            >
              {(['DAILY', 'WEEKLY', 'MONTHLY', 'CUSTOM_CRON'] as const).map(
                (candidate) => (
                  <option key={candidate} value={candidate}>
                    {candidate.replaceAll('_', ' ')}
                  </option>
                ),
              )}
            </select>
          </Field>
          <Field label="Timezone">
            <input
              required
              value={timezone}
              onChange={(event) => setTimezone(event.target.value)}
              className={inputClass}
            />
          </Field>
          {scheduleType === 'CUSTOM_CRON' && (
            <Field label="Cron Expression">
              <input
                required
                value={cronExpression}
                onChange={(event) => setCronExpression(event.target.value)}
                className={inputClass}
              />
            </Field>
          )}
          <fieldset>
            <legend className="text-xs font-semibold text-slate-700">Formats</legend>
            <div className="mt-3 flex gap-3">
              {(['xlsx', 'json', 'pdf'] as const).map((format) => (
                <label
                  key={format}
                  className="flex items-center gap-1 text-xs font-semibold uppercase"
                >
                  <input
                    type="checkbox"
                    checked={formats.includes(format)}
                    onChange={(event) =>
                      setFormats((current) =>
                        event.target.checked
                          ? [...current, format]
                          : current.filter((candidate) => candidate !== format),
                      )
                    }
                  />
                  {format}
                </label>
              ))}
            </div>
          </fieldset>
        </div>
        <p className="mt-4 rounded-xl bg-amber-50 p-3 text-xs text-amber-800">
          Schedule configuration and manual execution only. No recipient or email
          delivery is configured.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="min-h-10 rounded-xl border border-slate-300 px-4 text-sm font-semibold"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!valid || pending}
            className="min-h-10 rounded-xl bg-indigo-700 px-4 text-sm font-semibold text-white disabled:opacity-50"
          >
            Save Schedule
          </button>
        </div>
      </form>
    </div>
  );
}

const inputClass =
  'mt-1.5 min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm';

function Field({ children, label }: { label: string; children: React.ReactNode }) {
  return (
    <label className="text-xs font-semibold text-slate-700">
      {label}
      {children}
    </label>
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
  icon: typeof Edit3;
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
