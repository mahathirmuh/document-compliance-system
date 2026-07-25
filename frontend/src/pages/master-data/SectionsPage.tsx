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
import { SectionForm } from '../../components/master-data/forms/SectionForm';
import { useDepartmentOptions } from '../../hooks/useDepartments';
import { useMasterDataListControls } from '../../hooks/useMasterDataListControls';
import { useSections, useSectionMutations } from '../../hooks/useSections';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type { Section, SectionCreate, SectionUpdate } from '../../types/section';
import { formatDateTime, toExportParams } from '../../utils/formatters';

type DrawerMode = 'create' | 'edit' | null;

export function SectionsPage() {
  const controls = useMasterDataListControls();
  const [searchParams, setSearchParams] = useSearchParams();
  const departmentId = searchParams.get('departmentId') ?? '';
  const [drawerMode, setDrawerMode] = useState<DrawerMode>(null);
  const [selected, setSelected] = useState<Section | null>(null);
  const [viewing, setViewing] = useState<Section | null>(null);
  const [statusTarget, setStatusTarget] = useState<Section | null>(null);
  const [isImportOpen, setImportOpen] = useState(false);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canCreate = hasPermission('master_data:create');
  const canUpdate = hasPermission('master_data:update');
  const canDelete = hasPermission('master_data:delete');
  const listParams = {
    ...controls.params,
    ...(departmentId ? { departmentId } : {}),
  };
  const query = useSections(listParams);
  const filterDepartments = useDepartmentOptions(false);
  const activeDepartments = useDepartmentOptions(true);
  const mutations = useSectionMutations();
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

  const saveSection = async (payload: SectionCreate | SectionUpdate): Promise<void> => {
    try {
      if (drawerMode === 'edit' && selected) {
        await mutations.update.mutateAsync({ id: selected.id, payload });
      } else {
        await mutations.create.mutateAsync(payload);
      }
      showToast({
        tone: 'success',
        title: drawerMode === 'edit' ? 'Section updated' : 'Section created',
      });
      setDrawerMode(null);
      setSelected(null);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Section could not be saved',
        message: getApiErrorMessage(error, 'Check the department and duplicate code.'),
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
        title: `Section ${statusTarget.isActive ? 'deactivated' : 'activated'}`,
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

  const columns: readonly DataTableColumn<Section>[] = [
    {
      key: 'department',
      header: 'Department',
      render: (section) => (
        <span className="font-medium text-slate-800">
          {section.department?.code ?? section.departmentCode ?? section.departmentId}
        </span>
      ),
    },
    {
      key: 'code',
      header: 'Code',
      sortable: true,
      render: (section) => (
        <span className="font-mono text-xs font-semibold text-slate-900">
          {section.code}
        </span>
      ),
    },
    {
      key: 'name',
      header: 'Name',
      sortable: true,
      render: (section) => (
        <span className="font-medium text-slate-900">{section.name}</span>
      ),
    },
    {
      key: 'description',
      header: 'Description',
      render: (section) => (
        <span className="block max-w-xs truncate">{section.description || '—'}</span>
      ),
    },
    {
      key: 'isActive',
      header: 'Status',
      sortable: true,
      render: (section) => <ActiveStatusBadge isActive={section.isActive} />,
    },
    {
      key: 'updatedAt',
      header: 'Updated At',
      sortable: true,
      render: (section) => formatDateTime(section.updatedAt),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (section) => (
        <div className="flex min-w-max items-center gap-1">
          <RowActionButton
            icon={Eye}
            label="View"
            onClick={() => setViewing(section)}
          />
          {canUpdate && (
            <RowActionButton
              icon={Pencil}
              label="Edit"
              onClick={() => {
                setSelected(section);
                setDrawerMode('edit');
              }}
            />
          )}
          {((section.isActive && canDelete) || (!section.isActive && canUpdate)) && (
            <EntityStatusToggle
              isActive={section.isActive}
              onClick={() => setStatusTarget(section)}
            />
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-5">
      <MasterDataPageHeader
        title="Sections"
        description="Maintain department-owned sections. New sections can only use active departments."
        actions={
          <>
            <MasterDataExportButton
              entityType="sections"
              params={toExportParams(listParams)}
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
                  Add Section
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
      >
        <select
          value={departmentId}
          onChange={(event) =>
            controls.updateParams({
              departmentId: event.target.value || null,
              page: null,
            })
          }
          aria-label="Filter by department"
          className="min-h-11 min-w-48 rounded-xl border border-slate-300 bg-white px-3.5 text-sm font-medium text-slate-700 outline-none focus:border-blue-600"
        >
          <option value="">All departments</option>
          {filterDepartments.data?.map((department) => (
            <option key={department.id} value={department.id}>
              {department.code} — {department.name}
              {!department.isActive ? ' (inactive)' : ''}
            </option>
          ))}
        </select>
      </MasterDataListToolbar>
      <DataTable
        columns={columns}
        items={query.data?.items ?? []}
        getRowKey={(section) => section.id}
        isLoading={query.isLoading}
        errorMessage={
          query.error
            ? getApiErrorMessage(query.error, 'Sections could not be loaded.')
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
        emptyTitle="No sections found"
      />

      <MasterDataFormDrawer
        isOpen={drawerMode !== null}
        onClose={() => setDrawerMode(null)}
        title={drawerMode === 'edit' ? 'Edit Section' : 'Add Section'}
        description="A section code is unique within its department."
      >
        <SectionForm
          section={drawerMode === 'edit' ? selected : null}
          departments={activeDepartments.data ?? []}
          isLoadingDepartments={activeDepartments.isLoading}
          isPending={mutations.create.isPending || mutations.update.isPending}
          onCancel={() => setDrawerMode(null)}
          onSubmit={saveSection}
        />
      </MasterDataFormDrawer>

      <MasterDataDetailsDrawer
        isOpen={viewing !== null}
        onClose={() => setViewing(null)}
        title={viewing?.name ?? 'Section details'}
        subtitle={viewing?.code}
        fields={
          viewing
            ? [
                {
                  label: 'Department',
                  value:
                    viewing.department?.name ??
                    viewing.departmentName ??
                    viewing.departmentId,
                },
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
        title={`${statusTarget?.isActive ? 'Deactivate' : 'Activate'} section?`}
        message={
          statusTarget?.isActive
            ? 'The section will no longer be available for new records.'
            : 'The section becomes available only when its department is also active.'
        }
        confirmLabel={statusTarget?.isActive ? 'Deactivate' : 'Activate'}
        tone={statusTarget?.isActive ? 'danger' : 'primary'}
        isPending={mutations.activate.isPending || mutations.deactivate.isPending}
        onCancel={() => setStatusTarget(null)}
        onConfirm={() => void changeStatus()}
      />

      <MasterDataImportDialog
        isOpen={isImportOpen}
        initialEntityType="sections"
        onClose={() => setImportOpen(false)}
      />
    </div>
  );
}
