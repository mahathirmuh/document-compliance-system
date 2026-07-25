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
import { DepartmentForm } from '../../components/master-data/forms/DepartmentForm';
import { useDepartments, useDepartmentMutations } from '../../hooks/useDepartments';
import { useMasterDataListControls } from '../../hooks/useMasterDataListControls';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type {
  Department,
  DepartmentCreate,
  DepartmentUpdate,
} from '../../types/department';
import { formatDateTime, toExportParams } from '../../utils/formatters';

type DrawerMode = 'create' | 'edit' | null;

export function DepartmentsPage() {
  const controls = useMasterDataListControls();
  const [searchParams, setSearchParams] = useSearchParams();
  const [drawerMode, setDrawerMode] = useState<DrawerMode>(null);
  const [selected, setSelected] = useState<Department | null>(null);
  const [viewing, setViewing] = useState<Department | null>(null);
  const [statusTarget, setStatusTarget] = useState<Department | null>(null);
  const [isImportOpen, setImportOpen] = useState(false);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canCreate = hasPermission('master_data:create');
  const canUpdate = hasPermission('master_data:update');
  const canDelete = hasPermission('master_data:delete');
  const query = useDepartments(controls.params);
  const mutations = useDepartmentMutations();
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

  const isSaving = mutations.create.isPending || mutations.update.isPending;

  const saveDepartment = async (
    payload: DepartmentCreate | DepartmentUpdate,
  ): Promise<void> => {
    try {
      if (drawerMode === 'edit' && selected) {
        await mutations.update.mutateAsync({ id: selected.id, payload });
      } else {
        await mutations.create.mutateAsync(payload);
      }
      showToast({
        tone: 'success',
        title: drawerMode === 'edit' ? 'Department updated' : 'Department created',
      });
      setDrawerMode(null);
      setSelected(null);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Department could not be saved',
        message: getApiErrorMessage(error, 'Check the form and try again.'),
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
        title: `Department ${statusTarget.isActive ? 'deactivated' : 'activated'}`,
      });
      setStatusTarget(null);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Status could not be changed',
        message: getApiErrorMessage(error, 'Try again or review dependent sections.'),
      });
    }
  };

  const columns: readonly DataTableColumn<Department>[] = [
    {
      key: 'code',
      header: 'Code',
      sortable: true,
      render: (department) => (
        <span className="font-mono text-xs font-semibold text-slate-900">
          {department.code}
        </span>
      ),
    },
    {
      key: 'name',
      header: 'Name',
      sortable: true,
      render: (department) => (
        <span className="font-medium text-slate-900">{department.name}</span>
      ),
    },
    {
      key: 'description',
      header: 'Description',
      render: (department) => (
        <span className="block max-w-xs truncate">{department.description || '—'}</span>
      ),
    },
    {
      key: 'isActive',
      header: 'Status',
      sortable: true,
      render: (department) => <ActiveStatusBadge isActive={department.isActive} />,
    },
    {
      key: 'createdAt',
      header: 'Created At',
      sortable: true,
      render: (department) => formatDateTime(department.createdAt),
    },
    {
      key: 'updatedAt',
      header: 'Updated At',
      sortable: true,
      render: (department) => formatDateTime(department.updatedAt),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (department) => (
        <div className="flex min-w-max items-center gap-1">
          <RowActionButton
            icon={Eye}
            label="View"
            onClick={() => setViewing(department)}
          />
          {canUpdate && (
            <RowActionButton
              icon={Pencil}
              label="Edit"
              onClick={() => {
                setSelected(department);
                setDrawerMode('edit');
              }}
            />
          )}
          {((department.isActive && canDelete) ||
            (!department.isActive && canUpdate)) && (
            <EntityStatusToggle
              isActive={department.isActive}
              onClick={() => setStatusTarget(department)}
            />
          )}
        </div>
      ),
    },
  ];

  const listError = query.error
    ? getApiErrorMessage(query.error, 'Departments could not be loaded.')
    : null;

  return (
    <div className="space-y-5">
      <MasterDataPageHeader
        title="Departments"
        description="Manage organizational departments and their availability for dependent sections."
        actions={
          <>
            <MasterDataExportButton
              entityType="departments"
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
                  Add Department
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
        getRowKey={(department) => department.id}
        isLoading={query.isLoading}
        errorMessage={listError}
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
        emptyTitle="No departments found"
      />

      <MasterDataFormDrawer
        isOpen={drawerMode !== null}
        onClose={() => setDrawerMode(null)}
        title={drawerMode === 'edit' ? 'Edit Department' : 'Add Department'}
        description="Codes are normalized to uppercase and must be unique."
      >
        <DepartmentForm
          department={drawerMode === 'edit' ? selected : null}
          isPending={isSaving}
          onCancel={() => setDrawerMode(null)}
          onSubmit={saveDepartment}
        />
      </MasterDataFormDrawer>

      <MasterDataDetailsDrawer
        isOpen={viewing !== null}
        onClose={() => setViewing(null)}
        title={viewing?.name ?? 'Department details'}
        subtitle={viewing?.code}
        fields={
          viewing
            ? [
                { label: 'Code', value: viewing.code },
                {
                  label: 'Status',
                  value: <ActiveStatusBadge isActive={viewing.isActive} />,
                },
                {
                  label: 'Description',
                  value: viewing.description || '—',
                  fullWidth: true,
                },
                { label: 'Created At', value: formatDateTime(viewing.createdAt) },
                { label: 'Updated At', value: formatDateTime(viewing.updatedAt) },
              ]
            : []
        }
      />

      <ConfirmationDialog
        isOpen={statusTarget !== null}
        title={`${statusTarget?.isActive ? 'Deactivate' : 'Activate'} department?`}
        message={
          statusTarget?.isActive
            ? 'The department will no longer appear in active dropdowns. Existing sections remain intact and may trigger a backend warning.'
            : 'The department will become available for new section assignments.'
        }
        confirmLabel={statusTarget?.isActive ? 'Deactivate' : 'Activate'}
        tone={statusTarget?.isActive ? 'danger' : 'primary'}
        isPending={mutations.activate.isPending || mutations.deactivate.isPending}
        onCancel={() => setStatusTarget(null)}
        onConfirm={() => void changeStatus()}
      />

      <MasterDataImportDialog
        isOpen={isImportOpen}
        initialEntityType="departments"
        onClose={() => setImportOpen(false)}
      />
    </div>
  );
}
