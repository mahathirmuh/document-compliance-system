import { Download, Plus, Search, UserRoundCheck } from 'lucide-react';
import { useState } from 'react';
import { useSearchParams } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import { AssignFindingDialog } from '../../components/compliance/AssignFindingDialog';
import { CreateManualFindingDialog } from '../../components/compliance/CreateManualFindingDialog';
import { FindingsTable } from '../../components/compliance/FindingsTable';
import {
  Phase8ErrorAlert,
  Phase8FilterField,
  Phase8Loading,
  Phase8Pagination,
} from '../../components/compliance/Phase8TableUtilities';
import { ReviewFindingDialog } from '../../components/compliance/ReviewFindingDialog';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { useDocumentFormOptions } from '../../hooks/useDocumentFormOptions';
import { useFindingActions } from '../../hooks/useFindingActions';
import { useFindings, useFindingsExport } from '../../hooks/useFindings';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type { RequiredLanguageCode } from '../../types/compliance';
import {
  findingSeverities,
  findingStatuses,
  findingTypes,
  type FindingAssignRequest,
  type FindingListParams,
  type FindingReviewRequest,
  type FindingSeverity,
  type FindingStatus,
  type FindingType,
  type ManualFindingRequest,
} from '../../types/finding';
import { downloadFile } from '../../utils/downloadFile';

export function FindingsPage({ reviewMode = false }: { reviewMode?: boolean }) {
  const [routeSearchParams] = useSearchParams();
  const complianceRunId = routeSearchParams.get('runId')?.trim() ?? '';
  const user = useAuthStore((state) => state.user);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const departmentLocked = !hasPermission('compliance:view_all_departments');
  const [searchInput, setSearchInput] = useState('');
  const search = useDebouncedValue(searchInput.trim(), 350);
  const [departmentId, setDepartmentId] = useState(
    departmentLocked ? (user?.departmentId ?? '') : '',
  );
  const [documentId, setDocumentId] = useState('');
  const [severity, setSeverity] = useState<FindingSeverity | ''>('');
  const [status, setStatus] = useState<FindingStatus | ''>(
    reviewMode ? 'IN_REVIEW' : '',
  );
  const [findingType, setFindingType] = useState<FindingType | ''>('');
  const [languageCode, setLanguageCode] = useState<RequiredLanguageCode | ''>('');
  const [section, setSection] = useState('');
  const [assignedTo, setAssignedTo] = useState('');
  const [createdFrom, setCreatedFrom] = useState('');
  const [createdTo, setCreatedTo] = useState('');
  const [page, setPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [manualOpen, setManualOpen] = useState(false);
  const [bulkAssignOpen, setBulkAssignOpen] = useState(false);
  const [bulkReviewOpen, setBulkReviewOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const optionsQuery = useDocumentFormOptions();
  const params: FindingListParams = {
    page,
    pageSize: 20,
    sortBy: 'severity',
    sortOrder: 'desc',
    ...(search ? { search } : {}),
    ...(departmentId ? { departmentId } : {}),
    ...(documentId.trim() ? { documentId: documentId.trim() } : {}),
    ...(severity ? { severity } : {}),
    ...(status ? { status } : {}),
    ...(findingType ? { findingType } : {}),
    ...(languageCode ? { languageCode } : {}),
    ...(section.trim() ? { section: section.trim() } : {}),
    ...(assignedTo.trim() ? { assignedTo: assignedTo.trim() } : {}),
    ...(createdFrom ? { createdFrom } : {}),
    ...(createdTo ? { createdTo } : {}),
    ...(complianceRunId ? { complianceRunId } : {}),
  };
  const query = useFindings(params);
  const actions = useFindingActions();
  const exportMutation = useFindingsExport();
  const { showToast } = useToast();

  const createManual = async (payload: ManualFindingRequest): Promise<void> => {
    setActionError(null);
    try {
      await actions.createManual.mutateAsync(payload);
      setManualOpen(false);
      showToast({ tone: 'success', title: 'Manual finding created' });
    } catch (error: unknown) {
      setActionError(getApiErrorMessage(error, 'The finding could not be created.'));
    }
  };

  const bulkAssign = async (payload: FindingAssignRequest): Promise<void> => {
    setActionError(null);
    try {
      const result = await actions.bulkAction.mutateAsync({
        action: 'ASSIGN',
        findingIds: selectedIds,
        assignedTo: payload.assignedTo,
      });
      setSelectedIds([]);
      setBulkAssignOpen(false);
      showToast({
        tone: 'success',
        title: `${result.processedCount} findings assigned`,
      });
    } catch (error: unknown) {
      setActionError(getApiErrorMessage(error, 'Assignment could not be completed.'));
    }
  };

  const bulkReview = async (payload: FindingReviewRequest): Promise<void> => {
    setActionError(null);
    try {
      const result = await actions.bulkAction.mutateAsync({
        action: 'REVIEW',
        findingIds: selectedIds,
        comment: payload.comment,
      });
      setSelectedIds([]);
      setBulkReviewOpen(false);
      showToast({
        tone: 'success',
        title: `${result.processedCount} findings moved to review`,
      });
    } catch (error: unknown) {
      setActionError(getApiErrorMessage(error, 'Review could not be started.'));
    }
  };

  const exportCurrent = async (format: 'json' | 'xlsx'): Promise<void> => {
    const filters = {
      sortBy: 'severity',
      sortOrder: 'desc' as const,
      ...(search ? { search } : {}),
      ...(departmentId ? { departmentId } : {}),
      ...(documentId.trim() ? { documentId: documentId.trim() } : {}),
      ...(severity ? { severity } : {}),
      ...(status ? { status } : {}),
      ...(findingType ? { findingType } : {}),
      ...(languageCode ? { languageCode } : {}),
      ...(section.trim() ? { section: section.trim() } : {}),
      ...(assignedTo.trim() ? { assignedTo: assignedTo.trim() } : {}),
      ...(createdFrom ? { createdFrom } : {}),
      ...(createdTo ? { createdTo } : {}),
      ...(complianceRunId ? { complianceRunId } : {}),
    };
    try {
      const result = await exportMutation.mutateAsync({ format, params: filters });
      downloadFile(result, `findings.${format}`);
      showToast({
        tone: 'success',
        title: `Findings ${format.toUpperCase()} downloaded`,
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Findings export failed',
        message: getApiErrorMessage(error, 'The export could not be downloaded.'),
      });
    }
  };

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        eyebrow="Compliance"
        title={reviewMode ? 'Review Findings' : 'Findings'}
        description="Filter and review auditable compliance findings. Status changes require finding-specific comments or reasons."
        actions={
          <>
            {hasPermission('findings:export') &&
              (['xlsx', 'json'] as const).map((format) => (
                <button
                  key={format}
                  type="button"
                  disabled={exportMutation.isPending}
                  onClick={() => void exportCurrent(format)}
                  className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 px-3 text-xs font-semibold uppercase text-slate-700 disabled:opacity-50"
                >
                  <Download className="size-4" aria-hidden="true" />
                  {format}
                </button>
              ))}
            {hasPermission('findings:create_manual') && (
              <button
                type="button"
                onClick={() => {
                  setActionError(null);
                  setManualOpen(true);
                }}
                className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white"
              >
                <Plus className="size-4" aria-hidden="true" />
                Manual Finding
              </button>
            )}
          </>
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
          <Phase8FilterField label="Document">
            <input
              value={documentId}
              onChange={(event) => {
                setDocumentId(event.target.value);
                setPage(1);
              }}
              placeholder="Document ID"
              className="min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
            />
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
          <Phase8FilterField label="Finding Type">
            <select
              value={findingType}
              onChange={(event) => {
                setFindingType(event.target.value as FindingType | '');
                setPage(1);
              }}
              className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
            >
              <option value="">All types</option>
              {findingTypes.map((candidate) => (
                <option key={candidate} value={candidate}>
                  {candidate.replaceAll('_', ' ')}
                </option>
              ))}
            </select>
          </Phase8FilterField>
          <Phase8FilterField label="Language">
            <select
              value={languageCode}
              onChange={(event) => {
                setLanguageCode(event.target.value as RequiredLanguageCode | '');
                setPage(1);
              }}
              className="min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
            >
              <option value="">All languages</option>
              <option value="id">Bahasa Indonesia</option>
              <option value="en">English</option>
              <option value="zh">中文 / Mandarin</option>
            </select>
          </Phase8FilterField>
          <Phase8FilterField label="Section">
            <input
              value={section}
              onChange={(event) => {
                setSection(event.target.value);
                setPage(1);
              }}
              placeholder="Canonical code"
              className="min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
            />
          </Phase8FilterField>
          <Phase8FilterField label="Assigned To">
            <input
              value={assignedTo}
              onChange={(event) => {
                setAssignedTo(event.target.value);
                setPage(1);
              }}
              placeholder="User ID"
              className="min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm"
            />
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
        {departmentLocked && (
          <p className="mt-3 text-xs text-slate-500">
            Findings outside your assigned department are not shown.
          </p>
        )}
      </section>

      {selectedIds.length > 0 && (
        <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-blue-200 bg-blue-50 p-3 text-xs text-blue-800">
          <span className="font-semibold">{selectedIds.length} selected</span>
          {hasPermission('findings:update') && (
            <button
              type="button"
              onClick={() => setBulkAssignOpen(true)}
              className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-white px-3 font-semibold"
            >
              <UserRoundCheck className="size-3.5" aria-hidden="true" />
              Assign
            </button>
          )}
          {hasPermission('findings:review') && (
            <button
              type="button"
              onClick={() => setBulkReviewOpen(true)}
              className="min-h-9 rounded-lg bg-white px-3 font-semibold"
            >
              Move to In Review
            </button>
          )}
          <span className="text-blue-700">
            Resolve and false-positive actions remain finding-specific.
          </span>
        </div>
      )}

      {query.isLoading && <Phase8Loading label="Loading findings" />}
      {query.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(query.error, 'Findings could not be loaded.')}
          onRetry={() => void query.refetch()}
        />
      )}
      {query.data && (
        <>
          <FindingsTable
            findings={query.data.items}
            showSelection={
              hasPermission('findings:update') || hasPermission('findings:review')
            }
            selectedIds={selectedIds}
            onSelectionChange={setSelectedIds}
          />
          <Phase8Pagination
            page={page}
            totalItems={query.data.totalItems}
            totalPages={query.data.totalPages}
            label="findings"
            onPageChange={(nextPage) => {
              setSelectedIds([]);
              setPage(nextPage);
            }}
          />
        </>
      )}

      <CreateManualFindingDialog
        isOpen={manualOpen}
        isPending={actions.createManual.isPending}
        errorMessage={actionError}
        onClose={() => setManualOpen(false)}
        onSubmit={(payload) => void createManual(payload)}
      />
      <AssignFindingDialog
        isOpen={bulkAssignOpen}
        isPending={actions.bulkAction.isPending}
        errorMessage={actionError}
        onClose={() => setBulkAssignOpen(false)}
        onSubmit={(payload) => void bulkAssign(payload)}
      />
      <ReviewFindingDialog
        isOpen={bulkReviewOpen}
        isPending={actions.bulkAction.isPending}
        errorMessage={actionError}
        onClose={() => setBulkReviewOpen(false)}
        onSubmit={(payload) => void bulkReview(payload)}
      />
    </div>
  );
}

export function ReviewFindingsPage() {
  return <FindingsPage reviewMode />;
}
