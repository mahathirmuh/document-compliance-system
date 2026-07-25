import { Eye, Pencil, Plus, Star, Upload } from 'lucide-react';
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
import { ValidationRuleForm } from '../../components/master-data/forms/ValidationRuleForm';
import { useDocumentTypeOptions } from '../../hooks/useDocumentTypes';
import { useMasterDataListControls } from '../../hooks/useMasterDataListControls';
import {
  useValidationRuleMutations,
  useValidationRules,
} from '../../hooks/useValidationRules';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type {
  ValidationRule,
  ValidationRuleCreate,
  ValidationRuleUpdate,
} from '../../types/validationRule';
import { formatBoolean, formatDateTime, toExportParams } from '../../utils/formatters';

type DrawerMode = 'create' | 'edit' | null;

const getRequiredLanguages = (rule: ValidationRule): string =>
  [
    rule.requiredIndonesian ? 'ID' : null,
    rule.requiredEnglish ? 'EN' : null,
    rule.requiredChinese ? 'ZH' : null,
  ]
    .filter((language): language is string => language !== null)
    .join(', ');

export function ValidationRulesPage() {
  const controls = useMasterDataListControls();
  const [searchParams, setSearchParams] = useSearchParams();
  const documentTypeId = searchParams.get('documentTypeId') ?? '';
  const [drawerMode, setDrawerMode] = useState<DrawerMode>(null);
  const [selected, setSelected] = useState<ValidationRule | null>(null);
  const [viewing, setViewing] = useState<ValidationRule | null>(null);
  const [statusTarget, setStatusTarget] = useState<ValidationRule | null>(null);
  const [defaultTarget, setDefaultTarget] = useState<ValidationRule | null>(null);
  const [isImportOpen, setImportOpen] = useState(false);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canCreate = hasPermission('master_data:create');
  const canUpdate = hasPermission('master_data:update');
  const canDelete = hasPermission('master_data:delete');
  const listParams = {
    ...controls.params,
    ...(documentTypeId ? { documentTypeId } : {}),
  };
  const query = useValidationRules(listParams);
  const documentTypes = useDocumentTypeOptions();
  const mutations = useValidationRuleMutations();
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

  const saveValidationRule = async (
    payload: ValidationRuleCreate | ValidationRuleUpdate,
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
          drawerMode === 'edit' ? 'Validation rule updated' : 'Validation rule created',
      });
      setDrawerMode(null);
      setSelected(null);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Validation rule could not be saved',
        message: getApiErrorMessage(
          error,
          'Check language, score, default, and document type rules.',
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
        title: `Validation rule ${statusTarget.isActive ? 'deactivated' : 'activated'}`,
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

  const setAsDefault = async (): Promise<void> => {
    if (!defaultTarget) {
      return;
    }
    try {
      await mutations.setDefault.mutateAsync(defaultTarget.id);
      showToast({
        tone: 'success',
        title: 'Default validation rule updated',
      });
      setDefaultTarget(null);
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Default rule could not be changed',
        message: getApiErrorMessage(error, 'Review the active default rule.'),
      });
    }
  };

  const columns: readonly DataTableColumn<ValidationRule>[] = [
    {
      key: 'code',
      header: 'Code',
      sortable: true,
      render: (rule) => (
        <span className="font-mono text-xs font-semibold text-slate-900">
          {rule.code}
        </span>
      ),
    },
    {
      key: 'name',
      header: 'Name',
      sortable: true,
      render: (rule) => <span className="font-medium text-slate-900">{rule.name}</span>,
    },
    {
      key: 'documentType',
      header: 'Document Type',
      render: (rule) => rule.documentType?.code ?? 'Global',
    },
    {
      key: 'languages',
      header: 'Languages Required',
      render: (rule) => getRequiredLanguages(rule),
    },
    {
      key: 'coverage',
      header: 'Coverage',
      render: (rule) =>
        `${rule.minimumIndonesianCoverage}/${rule.minimumEnglishCoverage}/${rule.minimumChineseCoverage}%`,
    },
    {
      key: 'validateLanguageOrder',
      header: 'Validate Order',
      render: (rule) => formatBoolean(rule.validateLanguageOrder),
    },
    {
      key: 'validateSections',
      header: 'Validate Sections',
      render: (rule) => formatBoolean(rule.validateSections),
    },
    {
      key: 'isDefault',
      header: 'Default',
      sortable: true,
      render: (rule) =>
        rule.isDefault ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-1 text-[10px] font-semibold text-amber-700">
            <Star className="size-3 fill-current" aria-hidden="true" />
            Default
          </span>
        ) : (
          '—'
        ),
    },
    {
      key: 'isActive',
      header: 'Status',
      sortable: true,
      render: (rule) => <ActiveStatusBadge isActive={rule.isActive} />,
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (rule) => (
        <div className="flex min-w-max items-center gap-1">
          <RowActionButton icon={Eye} label="View" onClick={() => setViewing(rule)} />
          {canUpdate && (
            <>
              <RowActionButton
                icon={Pencil}
                label="Edit"
                onClick={() => {
                  setSelected(rule);
                  setDrawerMode('edit');
                }}
              />
              {!rule.isDefault && rule.isActive && (
                <RowActionButton
                  icon={Star}
                  label="Set default"
                  onClick={() => setDefaultTarget(rule)}
                />
              )}
            </>
          )}
          {((rule.isActive && canDelete) || (!rule.isActive && canUpdate)) && (
            <EntityStatusToggle
              isActive={rule.isActive}
              onClick={() => setStatusTarget(rule)}
            />
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-5">
      <MasterDataPageHeader
        title="Validation Rules"
        description="Configure trilingual coverage, document structure, and compliance-score thresholds."
        actions={
          <>
            <MasterDataExportButton
              entityType="validation-rules"
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
                  Add Validation Rule
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
          value={documentTypeId}
          onChange={(event) =>
            controls.updateParams({
              documentTypeId: event.target.value || null,
              page: null,
            })
          }
          aria-label="Filter by document type"
          className="min-h-11 min-w-48 rounded-xl border border-slate-300 bg-white px-3.5 text-sm font-medium text-slate-700 outline-none focus:border-blue-600"
        >
          <option value="">All document types</option>
          {documentTypes.data?.map((type) => (
            <option key={type.id} value={type.id}>
              {type.code} — {type.name}
            </option>
          ))}
        </select>
      </MasterDataListToolbar>
      <DataTable
        columns={columns}
        items={query.data?.items ?? []}
        getRowKey={(rule) => rule.id}
        isLoading={query.isLoading}
        errorMessage={
          query.error
            ? getApiErrorMessage(query.error, 'Validation rules could not be loaded.')
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
        emptyTitle="No validation rules found"
      />

      <MasterDataFormDrawer
        isOpen={drawerMode !== null}
        onClose={() => setDrawerMode(null)}
        title={drawerMode === 'edit' ? 'Edit Validation Rule' : 'Add Validation Rule'}
        description="Backend rules remain authoritative for defaults and score thresholds."
        size="wide"
      >
        <ValidationRuleForm
          validationRule={drawerMode === 'edit' ? selected : null}
          documentTypes={documentTypes.data ?? []}
          isLoadingDocumentTypes={documentTypes.isLoading}
          isPending={mutations.create.isPending || mutations.update.isPending}
          onCancel={() => setDrawerMode(null)}
          onSubmit={saveValidationRule}
        />
      </MasterDataFormDrawer>

      <MasterDataDetailsDrawer
        isOpen={viewing !== null}
        onClose={() => setViewing(null)}
        title={viewing?.name ?? 'Validation rule details'}
        subtitle={viewing?.code}
        fields={
          viewing
            ? [
                {
                  label: 'Document Type',
                  value: viewing.documentType?.name ?? 'Global',
                },
                { label: 'Languages', value: getRequiredLanguages(viewing) },
                {
                  label: 'Coverage ID / EN / ZH',
                  value: `${viewing.minimumIndonesianCoverage}% / ${viewing.minimumEnglishCoverage}% / ${viewing.minimumChineseCoverage}%`,
                },
                {
                  label: 'Compliance / Partial',
                  value: `${viewing.minimumComplianceScore}% / ${viewing.partialComplianceScore}%`,
                },
                {
                  label: 'Language Order',
                  value: viewing.languageOrder.join(' → '),
                },
                {
                  label: 'Required Sections',
                  value: viewing.requiredSections.join(', ') || '—',
                  fullWidth: true,
                },
                { label: 'Default', value: formatBoolean(viewing.isDefault) },
                {
                  label: 'Status',
                  value: <ActiveStatusBadge isActive={viewing.isActive} />,
                },
                { label: 'Updated At', value: formatDateTime(viewing.updatedAt) },
              ]
            : []
        }
      />

      <ConfirmationDialog
        isOpen={statusTarget !== null}
        title={`${statusTarget?.isActive ? 'Deactivate' : 'Activate'} validation rule?`}
        message={
          statusTarget?.isActive
            ? 'The rule will no longer be available for new document validation.'
            : 'The rule will become available for validation.'
        }
        confirmLabel={statusTarget?.isActive ? 'Deactivate' : 'Activate'}
        tone={statusTarget?.isActive ? 'danger' : 'primary'}
        isPending={mutations.activate.isPending || mutations.deactivate.isPending}
        onCancel={() => setStatusTarget(null)}
        onConfirm={() => void changeStatus()}
      />
      <ConfirmationDialog
        isOpen={defaultTarget !== null}
        title="Set as default validation rule?"
        message={
          defaultTarget?.documentTypeId
            ? 'This replaces the active default for the selected document type.'
            : 'This replaces the active global default validation rule.'
        }
        confirmLabel="Set default"
        tone="primary"
        isPending={mutations.setDefault.isPending}
        onCancel={() => setDefaultTarget(null)}
        onConfirm={() => void setAsDefault()}
      />

      <MasterDataImportDialog
        isOpen={isImportOpen}
        initialEntityType="validation-rules"
        onClose={() => setImportOpen(false)}
      />
    </div>
  );
}
