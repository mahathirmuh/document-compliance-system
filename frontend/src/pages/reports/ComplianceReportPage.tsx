import { Download, Eye, Search } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import { ComplianceStatusBadge } from '../../components/compliance/ComplianceStatusBadge';
import {
  Phase8ErrorAlert,
  Phase8FilterField,
  Phase8Loading,
  Phase8Pagination,
} from '../../components/compliance/Phase8TableUtilities';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { useComplianceMutations, useComplianceReport } from '../../hooks/useCompliance';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { useDocumentFormOptions } from '../../hooks/useDocumentFormOptions';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type {
  ComplianceReportParams,
  ComplianceStatus,
  LanguagePresenceStatus,
} from '../../types/compliance';
import { downloadFile } from '../../utils/downloadFile';
import { formatDateTime } from '../../utils/formatters';

export function ComplianceReportPage() {
  const user = useAuthStore((state) => state.user);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const departmentLocked = !hasPermission('compliance:view_all_departments');
  const [searchInput, setSearchInput] = useState('');
  const search = useDebouncedValue(searchInput.trim(), 350);
  const [departmentId, setDepartmentId] = useState(
    departmentLocked ? (user?.departmentId ?? '') : '',
  );
  const [sectionId, setSectionId] = useState('');
  const [documentTypeId, setDocumentTypeId] = useState('');
  const [validationRuleId, setValidationRuleId] = useState('');
  const [complianceStatus, setComplianceStatus] = useState<ComplianceStatus | ''>('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [page, setPage] = useState(1);
  const optionsQuery = useDocumentFormOptions();
  const params: ComplianceReportParams = {
    page,
    pageSize: 20,
    sortBy: 'lastValidated',
    sortOrder: 'desc',
    ...(search ? { search } : {}),
    ...(departmentId ? { departmentId } : {}),
    ...(sectionId ? { sectionId } : {}),
    ...(documentTypeId ? { documentTypeId } : {}),
    ...(validationRuleId ? { validationRuleId } : {}),
    ...(complianceStatus ? { complianceStatus } : {}),
    ...(dateFrom ? { dateFrom } : {}),
    ...(dateTo ? { dateTo } : {}),
  };
  const query = useComplianceReport(params);
  const mutations = useComplianceMutations();
  const { showToast } = useToast();

  const exportReport = async (format: 'xlsx' | 'json'): Promise<void> => {
    const filters = {
      ...(search ? { search } : {}),
      ...(departmentId ? { departmentId } : {}),
      ...(sectionId ? { sectionId } : {}),
      ...(documentTypeId ? { documentTypeId } : {}),
      ...(validationRuleId ? { validationRuleId } : {}),
      ...(complianceStatus ? { complianceStatus } : {}),
      ...(dateFrom ? { dateFrom } : {}),
      ...(dateTo ? { dateTo } : {}),
      sortBy: 'lastValidated',
      sortOrder: 'desc' as const,
    };
    try {
      const result = await mutations.exportReport.mutateAsync({
        format,
        params: filters,
      });
      downloadFile(result, `compliance-report.${format}`);
      showToast({
        tone: 'success',
        title: `Compliance report ${format.toUpperCase()} downloaded`,
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Compliance report export failed',
        message: getApiErrorMessage(error, 'The report could not be downloaded.'),
      });
    }
  };

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Reports"
        title="Compliance Report"
        description="Exportable document-level compliance results using the same permission and department filters as the API."
        actions={
          hasPermission('compliance:export') ? (
            <>
              {(['xlsx', 'json'] as const).map((format) => (
                <button
                  key={format}
                  type="button"
                  disabled={mutations.exportReport.isPending}
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
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
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
                placeholder="Document code or title"
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
          <Phase8FilterField label="Section">
            <select
              value={sectionId}
              onChange={(event) => {
                setSectionId(event.target.value);
                setPage(1);
              }}
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
              onChange={(event) => {
                setDocumentTypeId(event.target.value);
                setPage(1);
              }}
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
              onChange={(event) => {
                setValidationRuleId(event.target.value);
                setPage(1);
              }}
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
              onChange={(event) => {
                setComplianceStatus(event.target.value as ComplianceStatus | '');
                setPage(1);
              }}
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
              ).map((candidate) => (
                <option key={candidate} value={candidate}>
                  {candidate.replaceAll('_', ' ')}
                </option>
              ))}
            </select>
          </Phase8FilterField>
          <Phase8FilterField label="Validated From">
            <input
              type="date"
              value={dateFrom}
              onChange={(event) => {
                setDateFrom(event.target.value);
                setPage(1);
              }}
              className="min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
            />
          </Phase8FilterField>
          <Phase8FilterField label="Validated To">
            <input
              type="date"
              min={dateFrom || undefined}
              value={dateTo}
              onChange={(event) => {
                setDateTo(event.target.value);
                setPage(1);
              }}
              className="min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
            />
          </Phase8FilterField>
        </div>
      </section>

      {query.isLoading && <Phase8Loading label="Loading compliance report" />}
      {query.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            query.error,
            'The compliance report could not be loaded.',
          )}
          onRetry={() => void query.refetch()}
        />
      )}
      {query.data && (
        <>
          <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
            <div className="overflow-x-auto">
              <table className="min-w-[110rem] divide-y divide-slate-200">
                <thead className="bg-slate-50">
                  <tr>
                    {[
                      'Document Code',
                      'Title',
                      'Department',
                      'Section',
                      'Document Type',
                      'Revision',
                      'Validation Rule',
                      'Indonesia',
                      'English',
                      'Chinese',
                      'Section Completeness',
                      'Language Order',
                      'Score',
                      'Compliance Status',
                      'Critical',
                      'Major',
                      'Last Validated',
                      'Action',
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
                  {query.data.items.map((item) => (
                    <tr key={item.runId}>
                      <td className="px-4 py-3 text-xs font-semibold text-blue-700">
                        {item.documentCode}
                      </td>
                      <td className="max-w-xs px-4 py-3 text-xs text-slate-700">
                        {item.title}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-600">
                        {item.department}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-600">
                        {item.section ?? '—'}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-600">
                        {item.documentType}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-600">
                        {item.revision}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-600">
                        {item.validationRule}
                      </td>
                      {(['id', 'en', 'zh'] as const).map((code) => (
                        <td key={code} className="px-4 py-3">
                          <PresenceBadge value={item.languagePresence[code]} />
                        </td>
                      ))}
                      <td className="px-4 py-3 text-xs text-slate-600">
                        {item.sectionCompleteness.toFixed(1)}%
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-600">
                        {item.languageOrderValid === null
                          ? 'Not evaluated'
                          : item.languageOrderValid
                            ? 'Valid'
                            : 'Invalid'}
                      </td>
                      <td className="px-4 py-3 text-sm font-semibold text-slate-900">
                        {item.score?.toFixed(1) ?? '—'}
                      </td>
                      <td className="px-4 py-3">
                        <ComplianceStatusBadge status={item.complianceStatus} />
                      </td>
                      <td className="px-4 py-3 text-xs text-rose-700">
                        {item.criticalFindings}
                      </td>
                      <td className="px-4 py-3 text-xs text-orange-700">
                        {item.majorFindings}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">
                        {formatDateTime(item.lastValidated)}
                      </td>
                      <td className="px-4 py-3">
                        <Link
                          to={`/documents/${item.documentId}/compliance?fileId=${item.documentFileId}&runId=${item.runId}`}
                          className="inline-flex items-center gap-1.5 text-xs font-semibold text-blue-700"
                        >
                          <Eye className="size-3.5" aria-hidden="true" />
                          View
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {query.data.items.length === 0 && (
              <p className="px-6 py-12 text-center text-sm text-slate-500">
                No compliance report rows match these filters.
              </p>
            )}
          </div>
          <Phase8Pagination
            page={page}
            totalItems={query.data.totalItems}
            totalPages={query.data.totalPages}
            label="documents"
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
}

function PresenceBadge({ value }: { value: LanguagePresenceStatus }) {
  const label =
    value === 'PRESENT'
      ? 'Detected'
      : value === 'NOT_PRESENT'
        ? 'Missing'
        : value === 'MIXED_ONLY'
          ? 'Mixed Only'
          : 'Insufficient';
  return (
    <span
      className={`rounded-full px-2 py-1 text-[10px] font-semibold ${
        value === 'PRESENT'
          ? 'bg-emerald-50 text-emerald-700'
          : value === 'NOT_PRESENT'
            ? 'bg-rose-50 text-rose-700'
            : 'bg-amber-50 text-amber-700'
      }`}
    >
      {label}
    </span>
  );
}
