import { Eye, Pencil, Plus, Upload } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import { ActiveStatusBadge } from '../../components/master-data/ActiveStatusBadge';
import { ConfirmationDialog } from '../../components/master-data/ConfirmationDialog';
import {
  DataTable,
  type DataTableColumn,
} from '../../components/master-data/DataTable';
import { EntityStatusToggle } from '../../components/master-data/EntityStatusToggle';
import { MasterDataDetailsDrawer } from '../../components/master-data/MasterDataDetailsDrawer';
import { MasterDataExportButton } from '../../components/master-data/MasterDataExportButton';
import { MasterDataFormDrawer } from '../../components/master-data/MasterDataFormDrawer';
import { MasterDataImportDialog } from '../../components/master-data/MasterDataImportDialog';
import { MasterDataListToolbar } from '../../components/master-data/MasterDataListToolbar';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { RowActionButton } from '../../components/master-data/RowActionButton';
import { DocumentStatusForm } from '../../components/master-data/forms/DocumentStatusForm';
import {
  useDocumentStatusMutations,
  useDocumentStatuses,
} from '../../hooks/useDocumentStatuses';
import { useMasterDataListControls } from '../../hooks/useMasterDataListControls';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type {
  DocumentStatus,
  DocumentStatusCreate,
  DocumentStatusUpdate,
} from '../../types/documentStatus';
import { formatBoolean, formatDateTime, toExportParams } from '../../utils/formatters';

type DrawerMode = 'create' | 'edit' | null;

const Flag = ({ value }: { value: boolean }) => (
  <span
    className={`inline-flex rounded-full px-2 py-1 text-[10px] font-semibold ${
      value ? 'bg-blue-50 text-blue-700' : 'bg-slate-100 text-slate-500'
    }`}
  >
    {value ? 'Yes' : 'No'}
  </span>
);

export function DocumentStatusesPage() {
  const controls = useMasterDataListControls('displayOrder');
  const [searchParams, setSearchParams] = useSearchParams();
  const [drawerMode, setDrawerMode] = useState<DrawerMode>(null);
  const [selected, setSelected] = useState<DocumentStatus | null>(null);
  const [viewing, setViewing] = useState<DocumentStatus | null>(null);
  const [statusTarget, setStatusTarget] = useState<DocumentStatus | null>(null);
  const [isImportOpen, setImportOpen] = useState(false);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canCreate = hasPermission('master_data:create');
  const canUpdate = hasPermission('master_data:update');
  const canDelete = hasPermission('master_data:delete');
  const query = useDocumentStatuses(controls.params);
  const mutations = useDocumentStatusMutations();
  const { showToast } = useToast();

  useEffect(() => {
    if (searchParams.get('action') !== 'create' || !canCreate) {
      return;
    }
    setSelected(null);
    setDrawerMode('create');
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current);
        next.delete('action');
        return next;
      },
      { replace: true },
    );
  }, [canCreate, searchParams, setSearchParams]);

  const saveDocumentStatus = async (
    payload: DocumentStatusCreate | DocumentStatusUpdate,
  ): Promise<void> => {
    try {
      if (drawerMode === 'edit' && selected) {
        await mutations.update.mutateAsync({ id: selected.id, payload });
      } else {
        await mutations.create.mutateAsync(payload);
      }
      showToast({
        tone: 'success',
        title:
          drawerMode === 'edit' ? 'Document status updated' : 'Document status created',
      });
      setDrawerMode(null);
      setSelected(null);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Document status could not be saved',
        message: getApiErrorMessage(
          error,
          'Check the display order and initial-status rule.',
        ),
      });
    }
  };

  const changeStatus = async (): Promise<void> => {
    if (!statusTarget) {
      return;
    }
    try {
      if (statusTarget.isActive) {
        await mutations.deactivate.mutateAsync(statusTarget.id);
      } else {
        await mutations.activate.mutateAsync(statusTarget.id);
      }
      showToast({
        tone: 'success',
        title: `Document status ${statusTarget.isActive ? 'deactivated' : 'activated'}`,
      });
      setStatusTarget(null);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Status could not be changed',
        message: getApiErrorMessage(error, 'Try again.'),
      });
    }
  };

  const columns: readonly DataTableColumn<DocumentStatus>[] = [
    {
      key: 'displayOrder',
      header: 'Order',
      sortable: true,
      render: (status) => (
        <span className="font-semibold text-slate-800">{status.displayOrder}</span>
      ),
    },
    {
      key: 'code',
      header: 'Code',
      sortable: true,
      render: (status) => (
        <span className="font-mono text-xs font-semibold text-slate-900">
          {status.code}
        </span>
      ),
    },
    {
      key: 'name',
      header: 'Name',
      sortable: true,
      render: (status) => (
        <span className="font-medium text-slate-900">{status.name}</span>
      ),
    },
    {
      key: 'isInitial',
      header: 'Initial',
      render: (status) => <Flag value={status.isInitial} />,
    },
    {
      key: 'isFinal',
      header: 'Final',
      render: (status) => <Flag value={status.isFinal} />,
    },
    {
      key: 'isObsolete',
      header: 'Obsolete',
      render: (status) => <Flag value={status.isObsolete} />,
    },
    {
      key: 'isActive',
      header: 'Status',
      sortable: true,
      render: (status) => <ActiveStatusBadge isActive={status.isActive} />,
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (status) => (
        <div className="flex min-w-max items-center gap-1">
          <RowActionButton icon={Eye} label="View" onClick={() => setViewing(status)} />
          {canUpdate && (
            <RowActionButton
              icon={Pencil}
              label="Edit"
              onClick={() => {
                setSelected(status);
                setDrawerMode('edit');
              }}
            />
          )}
          {((status.isActive && canDelete) || (!status.isActive && canUpdate)) && (
            <EntityStatusToggle
              isActive={status.isActive}
              onClick={() => setStatusTarget(status)}
            />
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-5">
      <MasterDataPageHeader
        title="Document Statuses"
        description="Maintain ordered lifecycle statuses and enforce one initial status across the workflow."
        actions={
          <>
            <MasterDataExportButton
              entityType="document-statuses"
              params={toExportParams(controls.params)}
            />
            {canCreate && (
              <>
                <button
                  type="button"
                  onClick={() => setImportOpen(true)}
                  className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-3.5 text-sm font-semibold text-blue-700 hover:bg-blue-100"
                >
                  <Upload className="size-4" aria-hidden="true" />
                  Import
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setSelected(null);
                    setDrawerMode('create');
                  }}
                  className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white hover:bg-blue-800"
                >
                  <Plus className="size-4" aria-hidden="true" />
                  Add Document Status
                </button>
              </>
            )}
          </>
        }
      />
      <MasterDataListToolbar
        search={controls.search}
        onSearchChange={controls.setSearch}
        isActive={controls.isActive}
        onIsActiveChange={controls.setIsActive}
      />
      <DataTable
        columns={columns}
        items={query.data?.items ?? []}
        getRowKey={(status) => status.id}
        isLoading={query.isLoading}
        errorMessage={
          query.error
            ? getApiErrorMessage(query.error, 'Document statuses could not be loaded.')
            : null
        }
        onRetry={() => void query.refetch()}
        page={query.data?.page ?? controls.page}
        pageSize={query.data?.pageSize ?? controls.pageSize}
        totalItems={query.data?.totalItems ?? 0}
        totalPages={query.data?.totalPages ?? 0}
        sortBy={controls.sortBy}
        sortOrder={controls.sortOrder}
        onSort={controls.setSort}
        onPageChange={controls.setPage}
        onPageSizeChange={controls.setPageSize}
        emptyTitle="No document statuses found"
      />

      <MasterDataFormDrawer
        isOpen={drawerMode !== null}
        onClose={() => setDrawerMode(null)}
        title={drawerMode === 'edit' ? 'Edit Document Status' : 'Add Document Status'}
        description="Backend validation guarantees only one initial status."
      >
        <DocumentStatusForm
          documentStatus={drawerMode === 'edit' ? selected : null}
          isPending={mutations.create.isPending || mutations.update.isPending}
          onCancel={() => setDrawerMode(null)}
          onSubmit={saveDocumentStatus}
        />
      </MasterDataFormDrawer>

      <MasterDataDetailsDrawer
        isOpen={viewing !== null}
        onClose={() => setViewing(null)}
        title={viewing?.name ?? 'Document status details'}
        subtitle={viewing?.code}
        fields={
          viewing
            ? [
                { label: 'Display Order', value: viewing.displayOrder },
                {
                  label: 'Status',
                  value: <ActiveStatusBadge isActive={viewing.isActive} />,
                },
                { label: 'Initial', value: formatBoolean(viewing.isInitial) },
                { label: 'Final', value: formatBoolean(viewing.isFinal) },
                { label: 'Obsolete', value: formatBoolean(viewing.isObsolete) },
                {
                  label: 'Description',
                  value: viewing.description || '—',
                  fullWidth: true,
                },
                { label: 'Updated At', value: formatDateTime(viewing.updatedAt) },
              ]
            : []
        }
      />

      <ConfirmationDialog
        isOpen={statusTarget !== null}
        title={`${statusTarget?.isActive ? 'Deactivate' : 'Activate'} document status?`}
        message={
          statusTarget?.isActive
            ? 'The lifecycle status will no longer be available for new transitions.'
            : 'The lifecycle status will become available again.'
        }
        confirmLabel={statusTarget?.isActive ? 'Deactivate' : 'Activate'}
        tone={statusTarget?.isActive ? 'danger' : 'primary'}
        isPending={mutations.activate.isPending || mutations.deactivate.isPending}
        onCancel={() => setStatusTarget(null)}
        onConfirm={() => void changeStatus()}
      />

      <MasterDataImportDialog
        isOpen={isImportOpen}
        initialEntityType="document-statuses"
        onClose={() => setImportOpen(false)}
      />
    </div>
  );
}
