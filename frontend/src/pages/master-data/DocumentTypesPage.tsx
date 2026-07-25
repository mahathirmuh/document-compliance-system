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
import { DocumentTypeForm } from '../../components/master-data/forms/DocumentTypeForm';
import {
  useDocumentTypeMutations,
  useDocumentTypes,
} from '../../hooks/useDocumentTypes';
import { useMasterDataListControls } from '../../hooks/useMasterDataListControls';
import { useValidationRuleOptions } from '../../hooks/useValidationRules';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type {
  DocumentType,
  DocumentTypeCreate,
  DocumentTypeUpdate,
} from '../../types/documentType';
import { formatBoolean, formatDateTime, toExportParams } from '../../utils/formatters';

type DrawerMode = 'create' | 'edit' | null;

export function DocumentTypesPage() {
  const controls = useMasterDataListControls();
  const [searchParams, setSearchParams] = useSearchParams();
  const [drawerMode, setDrawerMode] = useState<DrawerMode>(null);
  const [selected, setSelected] = useState<DocumentType | null>(null);
  const [viewing, setViewing] = useState<DocumentType | null>(null);
  const [statusTarget, setStatusTarget] = useState<DocumentType | null>(null);
  const [isImportOpen, setImportOpen] = useState(false);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canCreate = hasPermission('master_data:create');
  const canUpdate = hasPermission('master_data:update');
  const canDelete = hasPermission('master_data:delete');
  const query = useDocumentTypes(controls.params);
  const validationRules = useValidationRuleOptions();
  const mutations = useDocumentTypeMutations();
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

  const saveDocumentType = async (
    payload: DocumentTypeCreate | DocumentTypeUpdate,
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
          drawerMode === 'edit' ? 'Document type updated' : 'Document type created',
      });
      setDrawerMode(null);
      setSelected(null);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Document type could not be saved',
        message: getApiErrorMessage(error, 'Check duplicate code and references.'),
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
        title: `Document type ${statusTarget.isActive ? 'deactivated' : 'activated'}`,
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

  const columns: readonly DataTableColumn<DocumentType>[] = [
    {
      key: 'code',
      header: 'Code',
      sortable: true,
      render: (type) => (
        <span className="font-mono text-xs font-semibold text-slate-900">
          {type.code}
        </span>
      ),
    },
    {
      key: 'name',
      header: 'Name',
      sortable: true,
      render: (type) => <span className="font-medium text-slate-900">{type.name}</span>,
    },
    {
      key: 'category',
      header: 'Category',
      sortable: true,
      render: (type) => type.category ?? '—',
    },
    {
      key: 'requiresSection',
      header: 'Requires Section',
      render: (type) => formatBoolean(type.requiresSection),
    },
    {
      key: 'defaultValidationRule',
      header: 'Default Rule',
      render: (type) =>
        type.defaultValidationRule?.code ?? type.defaultValidationRuleId ?? '—',
    },
    {
      key: 'isActive',
      header: 'Status',
      sortable: true,
      render: (type) => <ActiveStatusBadge isActive={type.isActive} />,
    },
    {
      key: 'updatedAt',
      header: 'Updated At',
      sortable: true,
      render: (type) => formatDateTime(type.updatedAt),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (type) => (
        <div className="flex min-w-max items-center gap-1">
          <RowActionButton icon={Eye} label="View" onClick={() => setViewing(type)} />
          {canUpdate && (
            <RowActionButton
              icon={Pencil}
              label="Edit"
              onClick={() => {
                setSelected(type);
                setDrawerMode('edit');
              }}
            />
          )}
          {((type.isActive && canDelete) || (!type.isActive && canUpdate)) && (
            <EntityStatusToggle
              isActive={type.isActive}
              onClick={() => setStatusTarget(type)}
            />
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-5">
      <MasterDataPageHeader
        title="Document Types"
        description="Control document classifications, section requirements, and optional default validation rules."
        actions={
          <>
            <MasterDataExportButton
              entityType="document-types"
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
                  Add Document Type
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
        getRowKey={(type) => type.id}
        isLoading={query.isLoading}
        errorMessage={
          query.error
            ? getApiErrorMessage(query.error, 'Document types could not be loaded.')
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
        emptyTitle="No document types found"
      />

      <MasterDataFormDrawer
        isOpen={drawerMode !== null}
        onClose={() => setDrawerMode(null)}
        title={drawerMode === 'edit' ? 'Edit Document Type' : 'Add Document Type'}
        description="Document type codes are globally unique."
      >
        <DocumentTypeForm
          documentType={drawerMode === 'edit' ? selected : null}
          validationRules={validationRules.data ?? []}
          isLoadingRules={validationRules.isLoading}
          isPending={mutations.create.isPending || mutations.update.isPending}
          onCancel={() => setDrawerMode(null)}
          onSubmit={saveDocumentType}
        />
      </MasterDataFormDrawer>

      <MasterDataDetailsDrawer
        isOpen={viewing !== null}
        onClose={() => setViewing(null)}
        title={viewing?.name ?? 'Document type details'}
        subtitle={viewing?.code}
        fields={
          viewing
            ? [
                { label: 'Category', value: viewing.category ?? '—' },
                {
                  label: 'Requires Section',
                  value: formatBoolean(viewing.requiresSection),
                },
                {
                  label: 'Default Rule',
                  value:
                    viewing.defaultValidationRule?.name ??
                    viewing.defaultValidationRuleId ??
                    '—',
                },
                {
                  label: 'Status',
                  value: <ActiveStatusBadge isActive={viewing.isActive} />,
                },
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
        title={`${statusTarget?.isActive ? 'Deactivate' : 'Activate'} document type?`}
        message={
          statusTarget?.isActive
            ? 'The document type will no longer be selectable for new documents.'
            : 'The document type will become available for new documents.'
        }
        confirmLabel={statusTarget?.isActive ? 'Deactivate' : 'Activate'}
        tone={statusTarget?.isActive ? 'danger' : 'primary'}
        isPending={mutations.activate.isPending || mutations.deactivate.isPending}
        onCancel={() => setStatusTarget(null)}
        onConfirm={() => void changeStatus()}
      />

      <MasterDataImportDialog
        isOpen={isImportOpen}
        initialEntityType="document-types"
        onClose={() => setImportOpen(false)}
      />
    </div>
  );
}
