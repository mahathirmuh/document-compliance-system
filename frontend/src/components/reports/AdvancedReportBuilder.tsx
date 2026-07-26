import { CalendarPlus, FileBarChart, RotateCcw } from 'lucide-react';
import { useEffect, useState } from 'react';

import { useDocumentFormOptions } from '../../hooks/useDocumentFormOptions';
import { useGlossaryProfiles } from '../../hooks/useGlossary';
import { useAuthStore } from '../../store/authStore';
import {
  advancedReportTypes,
  type AdvancedReportType,
  type ReportFormat,
  type ReportGenerateRequest,
  type ReportScheduleCreate,
  type ReportScheduleType,
} from '../../types/advancedReporting';

export function AdvancedReportBuilder({
  canGenerate = true,
  canSaveSchedule = true,
  initialReportType = 'COMPLIANCE_OVERVIEW',
  isGenerating,
  isSavingSchedule,
  onGenerate,
  onSaveSchedule,
}: {
  canGenerate?: boolean;
  canSaveSchedule?: boolean;
  initialReportType?: AdvancedReportType;
  isGenerating: boolean;
  isSavingSchedule: boolean;
  onGenerate: (payload: ReportGenerateRequest) => Promise<void>;
  onSaveSchedule: (payload: ReportScheduleCreate) => Promise<void>;
}) {
  const optionsQuery = useDocumentFormOptions();
  const profilesQuery = useGlossaryProfiles({
    page: 1,
    pageSize: 100,
    isActive: true,
  });
  const user = useAuthStore((state) => state.user);
  const role = user?.role;
  const departmentLocked = role === 'DEPARTMENT_USER';
  const [reportType, setReportType] = useState<AdvancedReportType>(initialReportType);
  const [reportName, setReportName] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [departmentId, setDepartmentId] = useState(
    departmentLocked ? (user?.departmentId ?? '') : '',
  );
  const [documentTypeId, setDocumentTypeId] = useState('');
  const [validationRuleId, setValidationRuleId] = useState('');
  const [complianceStatus, setComplianceStatus] = useState('');
  const [languagePair, setLanguagePair] = useState('');
  const [glossaryProfileId, setGlossaryProfileId] = useState('');
  const [outputFormat, setOutputFormat] = useState<ReportFormat>('xlsx');
  const [includeCharts, setIncludeCharts] = useState(true);
  const [includeDetailedTables, setIncludeDetailedTables] = useState(true);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [scheduleType, setScheduleType] = useState<ReportScheduleType>('MONTHLY');
  const [cronExpression, setCronExpression] = useState('');
  const [timezone, setTimezone] = useState(
    Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
  );

  useEffect(() => {
    setReportType(initialReportType);
  }, [initialReportType]);

  const resolvedName =
    reportName.trim() || reportType.replaceAll('_', ' ').toLowerCase();
  const filters = {
    ...(dateFrom ? { dateFrom } : {}),
    ...(dateTo ? { dateTo } : {}),
    ...(departmentId ? { departmentIds: [departmentId] } : {}),
    ...(documentTypeId ? { documentTypeIds: [documentTypeId] } : {}),
    ...(validationRuleId ? { validationRuleIds: [validationRuleId] } : {}),
    ...(complianceStatus ? { complianceStatuses: [complianceStatus] } : {}),
    ...(languagePair ? { languagePairs: [languagePair] } : {}),
    ...(glossaryProfileId ? { glossaryProfileIds: [glossaryProfileId] } : {}),
  };
  const canSubmit =
    (!dateFrom || !dateTo || dateFrom <= dateTo) &&
    (!departmentLocked || Boolean(departmentId));

  const reset = (): void => {
    setReportType(initialReportType);
    setReportName('');
    setDateFrom('');
    setDateTo('');
    setDepartmentId(departmentLocked ? (user?.departmentId ?? '') : '');
    setDocumentTypeId('');
    setValidationRuleId('');
    setComplianceStatus('');
    setLanguagePair('');
    setGlossaryProfileId('');
    setOutputFormat('xlsx');
    setIncludeCharts(true);
    setIncludeDetailedTables(true);
    setScheduleOpen(false);
    setScheduleType('MONTHLY');
    setCronExpression('');
  };

  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <div className="flex items-start gap-3">
        <div className="grid size-10 place-items-center rounded-xl bg-indigo-50 text-indigo-700">
          <FileBarChart className="size-5" aria-hidden="true" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-slate-950">
            Advanced Report Builder
          </h2>
          <p className="mt-1 text-xs leading-5 text-slate-600">
            Generated datasets use your authorized department scope and are stored as
            authenticated report snapshots.
          </p>
        </div>
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
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
        <Field label="Report Name">
          <input
            value={reportName}
            onChange={(event) => setReportName(event.target.value)}
            placeholder={reportType.replaceAll('_', ' ')}
            className={inputClass}
          />
        </Field>
        <Field label="Date From">
          <input
            type="date"
            value={dateFrom}
            onChange={(event) => setDateFrom(event.target.value)}
            className={inputClass}
          />
        </Field>
        <Field label="Date To">
          <input
            type="date"
            min={dateFrom || undefined}
            value={dateTo}
            onChange={(event) => setDateTo(event.target.value)}
            className={inputClass}
          />
        </Field>
        <Field label="Department">
          <select
            value={departmentId}
            disabled={departmentLocked}
            onChange={(event) => setDepartmentId(event.target.value)}
            className={`${inputClass} disabled:bg-slate-100`}
          >
            <option value="">
              {departmentLocked ? 'Assigned department' : 'All authorized departments'}
            </option>
            {(optionsQuery.data?.departments ?? []).map((department) => (
              <option key={department.id} value={department.id}>
                {department.code} — {department.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Document Type">
          <select
            value={documentTypeId}
            onChange={(event) => setDocumentTypeId(event.target.value)}
            className={inputClass}
          >
            <option value="">All document types</option>
            {(optionsQuery.data?.documentTypes ?? []).map((type) => (
              <option key={type.id} value={type.id}>
                {type.code} — {type.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Validation Rule">
          <select
            value={validationRuleId}
            onChange={(event) => setValidationRuleId(event.target.value)}
            className={inputClass}
          >
            <option value="">All validation rules</option>
            {(optionsQuery.data?.validationRules ?? []).map((rule) => (
              <option key={rule.id} value={rule.id}>
                {rule.code} — {rule.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Compliance Status">
          <select
            value={complianceStatus}
            onChange={(event) => setComplianceStatus(event.target.value)}
            className={inputClass}
          >
            <option value="">All compliance statuses</option>
            {[
              'COMPLIANT',
              'PARTIALLY_COMPLIANT',
              'NON_COMPLIANT',
              'NEEDS_REVIEW',
              'NOT_EVALUATED',
            ].map((status) => (
              <option key={status} value={status}>
                {status.replaceAll('_', ' ')}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Language Pair">
          <select
            value={languagePair}
            onChange={(event) => setLanguagePair(event.target.value)}
            className={inputClass}
          >
            <option value="">All language pairs</option>
            <option value="id-en">Indonesian ↔ English</option>
            <option value="id-zh">Indonesian ↔ Chinese</option>
            <option value="en-zh">English ↔ Chinese</option>
          </select>
        </Field>
        <Field label="Glossary Profile">
          <select
            value={glossaryProfileId}
            onChange={(event) => setGlossaryProfileId(event.target.value)}
            className={inputClass}
          >
            <option value="">All glossary profiles</option>
            {(profilesQuery.data?.items ?? []).map((profile) => (
              <option key={profile.id} value={profile.id}>
                {profile.code} — {profile.name}
              </option>
            ))}
          </select>
        </Field>
        <fieldset>
          <legend className="text-xs font-semibold text-slate-700">
            Output Format
          </legend>
          <select
            aria-label="Output Format"
            value={outputFormat}
            onChange={(event) => setOutputFormat(event.target.value as ReportFormat)}
            className={inputClass}
          >
            {(['xlsx', 'json', 'pdf'] as const).map((format) => (
              <option key={format} value={format}>
                {format.toUpperCase()}
              </option>
            ))}
          </select>
        </fieldset>
      </div>

      <div className="mt-5 flex flex-wrap gap-5 rounded-2xl bg-slate-50 p-4">
        <label className="flex items-center gap-2 text-xs font-semibold text-slate-700">
          <input
            type="checkbox"
            checked={includeCharts}
            onChange={(event) => setIncludeCharts(event.target.checked)}
            className="size-4 rounded border-slate-300"
          />
          Include Charts
        </label>
        <label className="flex items-center gap-2 text-xs font-semibold text-slate-700">
          <input
            type="checkbox"
            checked={includeDetailedTables}
            onChange={(event) => setIncludeDetailedTables(event.target.checked)}
            className="size-4 rounded border-slate-300"
          />
          Include Detailed Tables
        </label>
      </div>
      {departmentLocked && (
        <p className="mt-3 text-xs text-slate-500">
          Department scope is locked to your assigned department.
        </p>
      )}
      {dateFrom && dateTo && dateFrom > dateTo && (
        <p role="alert" className="mt-3 text-xs text-rose-700">
          Date To must be on or after Date From.
        </p>
      )}
      {canSaveSchedule && scheduleOpen && (
        <div className="mt-5 grid gap-4 rounded-2xl border border-indigo-200 bg-indigo-50 p-4 md:grid-cols-3">
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
                placeholder="0 7 * * 1"
                className={inputClass}
              />
            </Field>
          )}
          <div className="md:col-span-3">
            <button
              type="button"
              disabled={
                !canSubmit ||
                !timezone.trim() ||
                (scheduleType === 'CUSTOM_CRON' && !cronExpression.trim()) ||
                isSavingSchedule
              }
              onClick={() =>
                void onSaveSchedule({
                  name: resolvedName,
                  reportType,
                  filters,
                  formats: [outputFormat],
                  scheduleType,
                  cronExpression:
                    scheduleType === 'CUSTOM_CRON' ? cronExpression.trim() : null,
                  timezone: timezone.trim(),
                })
              }
              className="min-h-10 rounded-xl bg-indigo-700 px-4 text-xs font-semibold text-white disabled:opacity-50"
            >
              {isSavingSchedule ? 'Saving…' : 'Confirm Schedule'}
            </button>
          </div>
        </div>
      )}

      <div className="mt-6 flex flex-wrap gap-2 border-t border-slate-200 pt-5">
        {canGenerate && (
          <button
            type="button"
            disabled={!canSubmit || isGenerating}
            onClick={() =>
              void onGenerate({
                reportType,
                reportName: resolvedName,
                filters,
                outputFormat,
                includeCharts,
                includeDetailedTables,
              })
            }
            className="min-h-10 rounded-xl bg-indigo-700 px-5 text-sm font-semibold text-white disabled:opacity-50"
          >
            {isGenerating ? 'Generating…' : 'Generate'}
          </button>
        )}
        {canSaveSchedule && (
          <button
            type="button"
            onClick={() => setScheduleOpen((current) => !current)}
            className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-indigo-200 bg-indigo-50 px-4 text-sm font-semibold text-indigo-700"
          >
            <CalendarPlus className="size-4" aria-hidden="true" />
            Save Schedule
          </button>
        )}
        <button
          type="button"
          onClick={reset}
          className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700"
        >
          <RotateCcw className="size-4" aria-hidden="true" />
          Reset
        </button>
      </div>
    </section>
  );
}

const inputClass =
  'mt-1.5 min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm';

function Field({ children, label }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-xs font-semibold text-slate-700">
      {label}
      {children}
    </label>
  );
}
