import { FilePlus2, Upload } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import { ArchiveDocumentDialog } from '../../components/documents/ArchiveDocumentDialog';
import { BulkDocumentActionBar } from '../../components/documents/BulkDocumentActionBar';
import { BulkUpdateStatusDialog } from '../../components/documents/BulkUpdateStatusDialog';
import { DocumentExportButton } from '../../components/documents/DocumentExportButton';
import {
  DocumentFilters,
  type DocumentFilterValues,
} from '../../components/documents/DocumentFilters';
import { DocumentImportDialog } from '../../components/documents/DocumentImportDialog';
import { DocumentTable } from '../../components/documents/DocumentTable';
import { ConfirmationDialog } from '../../components/master-data/ConfirmationDialog';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { useDocumentFormOptions } from '../../hooks/useDocumentFormOptions';
import { useDocumentListControls } from '../../hooks/useDocumentListControls';
import { useDocumentMutations } from '../../hooks/useDocumentMutations';
import { useDocuments } from '../../hooks/useDocuments';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type { DocumentListItem } from '../../types/document';
import type { DocumentFormStatusOption } from '../../types/documentFormOptions';

interface DocumentRegisterViewProps {
  archived: boolean;
}

export function DocumentRegisterView({ archived }: DocumentRegisterViewProps) {
  const controls = useDocumentListControls(archived);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [archiveTarget, setArchiveTarget] = useState<DocumentListItem | null>(null);
  const [restoreTarget, setRestoreTarget] = useState<DocumentListItem | null>(null);
  const [bulkArchiveOpen, setBulkArchiveOpen] = useState(false);
  const [bulkRestoreOpen, setBulkRestoreOpen] = useState(false);
  const [bulkStatus, setBulkStatus] = useState<DocumentFormStatusOption | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canCreate = hasPermission('documents:create');
  const canUpdate = hasPermission('documents:update');
  const canArchive = hasPermission('documents:archive');
  const canRestore = hasPermission('documents:restore');
  const canExport = hasPermission('documents:export');
  const canImport = hasPermission('documents:import');
  const canManageRevisions = hasPermission('documents:manage_revisions');
  const query = useDocuments(controls.params);
  const mutations = useDocumentMutations();
  const formOptions = useDocumentFormOptions();
  const departments = formOptions.data?.departments ?? [];
  const sections = (formOptions.data?.sections ?? []).filter(
    (section) => section.departmentId === controls.filters.departmentId,
  );
  const documentTypes = formOptions.data?.documentTypes ?? [];
  const documentStatuses = formOptions.data?.documentStatuses ?? [];
  const { showToast } = useToast();
  const { page: _page, pageSize: _pageSize, ...exportParams } = controls.params;
  void _page;
  void _pageSize;
  const selectionContextKey = useMemo(
    () => JSON.stringify(controls.params),
    [controls.params],
  );
  const clearSelection = useCallback((): void => {
    setSelectedIds((current) => (current.size === 0 ? current : new Set()));
  }, []);

  useEffect(() => {
    clearSelection();
  }, [clearSelection, selectionContextKey]);

  const changeFilters = (updates: Partial<DocumentFilterValues>): void => {
    clearSelection();
    controls.setFilters(updates);
  };

  const resetFilters = (): void => {
    clearSelection();
    controls.resetFilters();
  };

  const changeSort = (key: string): void => {
    clearSelection();
    controls.setSort(key);
  };

  const setSelection = (next: Set<string>): void => {
    if (next.size > 100) {
      showToast({
        tone: 'error',
        title: 'Bulk selection is limited to 100 documents',
      });
      return;
    }
    setSelectedIds(next);
  };

  const archiveOne = async (reason: string): Promise<void> => {
    if (!archiveTarget) {
      return;
    }
    try {
      await mutations.archive.mutateAsync({
        documentId: archiveTarget.id,
        payload: { reason },
      });
      showToast({ tone: 'success', title: 'Document archived' });
      setArchiveTarget(null);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Document could not be archived',
        message: getApiErrorMessage(error, 'Review its status and try again.'),
      });
    }
  };

  const restoreOne = async (): Promise<void> => {
    if (!restoreTarget) {
      return;
    }
    try {
      await mutations.restore.mutateAsync(restoreTarget.id);
      showToast({ tone: 'success', title: 'Document restored' });
      setRestoreTarget(null);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Document could not be restored',
        message: getApiErrorMessage(error, 'Check for a conflicting document code.'),
      });
    }
  };

  const bulkArchive = async (reason: string): Promise<void> => {
    try {
      const result = await mutations.bulkArchive.mutateAsync({
        documentIds: [...selectedIds],
        reason,
      });
      showToast({
        tone: result.failed > 0 ? 'info' : 'success',
        title: 'Bulk archive completed',
        message: `${result.succeeded} succeeded and ${result.failed} failed.`,
      });
      setSelectedIds(new Set());
      setBulkArchiveOpen(false);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Bulk archive failed',
        message: getApiErrorMessage(error, 'No unconfirmed changes were retained.'),
      });
    }
  };

  const bulkRestore = async (): Promise<void> => {
    try {
      const result = await mutations.bulkRestore.mutateAsync({
        documentIds: [...selectedIds],
      });
      showToast({
        tone: result.failed > 0 ? 'info' : 'success',
        title: 'Bulk restore completed',
        message: `${result.succeeded} succeeded and ${result.failed} failed.`,
      });
      setSelectedIds(new Set());
      setBulkRestoreOpen(false);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Bulk restore failed',
        message: getApiErrorMessage(error, 'Check for conflicting document codes.'),
      });
    }
  };

  const bulkUpdateStatus = async (reason: string): Promise<void> => {
    if (!bulkStatus) {
      return;
    }
    try {
      const result = await mutations.bulkUpdateStatus.mutateAsync({
        documentIds: [...selectedIds],
        documentStatusId: bulkStatus.id,
        reason,
      });
      showToast({
        tone: result.failed > 0 ? 'info' : 'success',
        title: 'Bulk status update completed',
        message: `${result.succeeded} succeeded and ${result.failed} failed.`,
      });
      setSelectedIds(new Set());
      setBulkStatus(null);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Bulk status update failed',
        message: getApiErrorMessage(error, 'Review current revisions and try again.'),
      });
    }
  };

  const isBulkPending =
    mutations.bulkArchive.isPending ||
    mutations.bulkRestore.isPending ||
    mutations.bulkUpdateStatus.isPending;

  return (
    <div className="space-y-5">
      <MasterDataPageHeader
        eyebrow="Documents"
        title={archived ? 'Archived Documents' : 'Document Register'}
        description={
          archived
            ? 'Open retained document metadata and restore controlled records when appropriate.'
            : 'Search and maintain controlled document identities, current revisions, and SharePoint metadata.'
        }
        actions={
          <>
            {canExport && <DocumentExportButton params={exportParams} />}
            {!archived && canImport && (
              <button
                type="button"
                onClick={() => setImportOpen(true)}
                className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-3.5 text-sm font-semibold text-blue-700 hover:bg-blue-100"
              >
                <Upload className="size-4" aria-hidden="true" />
                Import XLSX
              </button>
            )}
            {!archived && canCreate && (
              <Link
                to="/documents/new"
                className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white hover:bg-blue-800"
              >
                <FilePlus2 className="size-4" aria-hidden="true" />
                Add Document
              </Link>
            )}
          </>
        }
      />
      <DocumentFilters
        values={controls.filters}
        departments={departments}
        sections={sections}
        documentTypes={documentTypes}
        documentStatuses={documentStatuses}
        isLoadingSections={formOptions.isLoading}
        onChange={changeFilters}
        onReset={resetFilters}
      />
      {formOptions.error && (
        <div
          role="alert"
          className="flex flex-col gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 sm:flex-row sm:items-center sm:justify-between"
        >
          <span>
            {getApiErrorMessage(
              formOptions.error,
              'Document filter options could not be loaded.',
            )}
          </span>
          <button
            type="button"
            onClick={() => void formOptions.refetch()}
            className="min-h-9 rounded-xl border border-amber-300 px-3 text-xs font-semibold hover:bg-amber-100"
          >
            Retry options
          </button>
        </div>
      )}
      <BulkDocumentActionBar
        selectedCount={selectedIds.size}
        isArchivedView={archived}
        statuses={documentStatuses}
        canArchive={canArchive}
        canRestore={canRestore}
        canUpdateStatus={canManageRevisions}
        isPending={isBulkPending}
        onClear={() => setSelectedIds(new Set())}
        onArchive={() => setBulkArchiveOpen(true)}
        onRestore={() => setBulkRestoreOpen(true)}
        onUpdateStatus={(statusId) =>
          setBulkStatus(
            documentStatuses.find((status) => status.id === statusId) ?? null,
          )
        }
      />
      <DocumentTable
        items={query.data?.items ?? []}
        isLoading={query.isLoading}
        errorMessage={
          query.error
            ? getApiErrorMessage(query.error, 'Documents could not be loaded.')
            : null
        }
        page={query.data?.page ?? controls.page}
        pageSize={query.data?.pageSize ?? controls.pageSize}
        totalItems={query.data?.totalItems ?? 0}
        totalPages={query.data?.totalPages ?? 0}
        sortBy={controls.sortBy}
        sortOrder={controls.sortOrder}
        selectedIds={selectedIds}
        canUpdate={canUpdate}
        canArchive={canArchive}
        canRestore={canRestore}
        canManageRevisions={canManageRevisions}
        canSelect={archived ? canRestore : canArchive || canManageRevisions}
        onSelectionChange={setSelection}
        onSort={changeSort}
        onPageChange={(page) => {
          setSelectedIds(new Set());
          controls.setPage(page);
        }}
        onPageSizeChange={(pageSize) => {
          setSelectedIds(new Set());
          controls.setPageSize(pageSize);
        }}
        onArchive={setArchiveTarget}
        onRestore={setRestoreTarget}
        onRetry={() => void query.refetch()}
      />

      <ArchiveDocumentDialog
        isOpen={archiveTarget !== null}
        isPending={mutations.archive.isPending}
        onClose={() => setArchiveTarget(null)}
        onConfirm={archiveOne}
      />
      <ArchiveDocumentDialog
        isOpen={bulkArchiveOpen}
        documentCount={selectedIds.size}
        isPending={mutations.bulkArchive.isPending}
        onClose={() => setBulkArchiveOpen(false)}
        onConfirm={bulkArchive}
      />
      <ConfirmationDialog
        isOpen={restoreTarget !== null}
        title="Restore document?"
        message={`Restore ${restoreTarget?.baseDocumentCode ?? 'this document'} to the active register. The backend will recheck code uniqueness.`}
        confirmLabel="Restore"
        tone="primary"
        isPending={mutations.restore.isPending}
        onCancel={() => setRestoreTarget(null)}
        onConfirm={() => void restoreOne()}
      />
      <ConfirmationDialog
        isOpen={bulkRestoreOpen}
        title={`Restore ${selectedIds.size} documents?`}
        message="Each document code is rechecked. Conflicts are returned as per-item failures."
        confirmLabel="Restore documents"
        tone="primary"
        isPending={mutations.bulkRestore.isPending}
        onCancel={() => setBulkRestoreOpen(false)}
        onConfirm={() => void bulkRestore()}
      />
      <BulkUpdateStatusDialog
        status={bulkStatus}
        documentCount={selectedIds.size}
        isPending={mutations.bulkUpdateStatus.isPending}
        onClose={() => setBulkStatus(null)}
        onConfirm={bulkUpdateStatus}
      />
      <DocumentImportDialog isOpen={importOpen} onClose={() => setImportOpen(false)} />
    </div>
  );
}
