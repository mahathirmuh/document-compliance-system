import { Edit3, Play, Plus, ShieldAlert } from 'lucide-react';
import { useState, type ReactNode } from 'react';

import { getApiErrorMessage } from '../../api/errors';
import {
  Phase8ErrorAlert,
  Phase8Loading,
  Phase8Pagination,
} from '../../components/compliance/Phase8TableUtilities';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import {
  Phase10Action,
  Phase10Cell,
  Phase10Dialog,
  Phase10Empty,
  phase10InputClass,
} from '../../components/phase10/Phase10Ui';
import { useDepartmentOptions } from '../../hooks/useDepartments';
import { useDocumentTypeOptions } from '../../hooks/useDocumentTypes';
import {
  useRetentionPolicies,
  useRetentionPolicyMutations,
} from '../../hooks/useRetentionPolicies';
import { useToast } from '../../providers/useToast';
import {
  retentionEntityTypes,
  type RetentionPolicy,
  type RetentionPolicyCreate,
  type RetentionPolicyUpdate,
  type RetentionScopeType,
} from '../../types/retention';
import { formatDateTime } from '../../utils/formatters';

export function RetentionPoliciesPage() {
  const [page, setPage] = useState(1);
  const [target, setTarget] = useState<RetentionPolicy | 'create' | null>(null);
  const [cleanupTarget, setCleanupTarget] = useState<RetentionPolicy | null>(null);
  const query = useRetentionPolicies({ page, pageSize: 20 });
  const mutations = useRetentionPolicyMutations();
  const { showToast } = useToast();

  const save = async (payload: RetentionPolicyCreate): Promise<void> => {
    try {
      if (target && target !== 'create') {
        const update: RetentionPolicyUpdate = {
          name: payload.name,
          retentionDays: payload.retentionDays,
          archiveAfterDays: payload.archiveAfterDays,
          deleteAfterDays: payload.deleteAfterDays,
          legalHoldEnabled: payload.legalHoldEnabled,
          isActive: payload.isActive,
        };
        await mutations.update.mutateAsync({
          policyId: target.id,
          payload: update,
        });
      } else {
        await mutations.create.mutateAsync(payload);
      }
      setTarget(null);
      showToast({ tone: 'success', title: 'Retention policy saved' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Retention policy could not be saved',
        message: getApiErrorMessage(error, 'Review the lifecycle boundaries.'),
      });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <MasterDataPageHeader
          eyebrow="Administration"
          title="Retention Policies"
          description="Configure scoped lifecycle policy and run safe dry-run previews before maintenance workers remove eligible data."
        />
        <button
          type="button"
          onClick={() => setTarget('create')}
          className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-blue-700 px-4 text-xs font-semibold text-white"
        >
          <Plus className="size-4" aria-hidden="true" />
          Add Policy
        </button>
      </div>
      <div className="flex gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-800">
        <ShieldAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        Audit logs and document revisions require explicit approved policy. Legal hold
        always prevents cleanup. The UI starts every execution in dry-run mode.
      </div>
      {query.isLoading && <Phase8Loading label="Loading retention policies" />}
      {query.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            query.error,
            'Retention policies could not be loaded.',
          )}
          onRetry={() => void query.refetch()}
        />
      )}
      {query.data && query.data.items.length === 0 && (
        <Phase10Empty>No retention policies configured.</Phase10Empty>
      )}
      {query.data && query.data.items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
            <table className="min-w-[76rem] divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  {[
                    'Name',
                    'Entity',
                    'Scope',
                    'Retention',
                    'Archive After',
                    'Delete After',
                    'Legal Hold',
                    'Active',
                    'Updated',
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
                {query.data.items.map((policy) => (
                  <tr key={policy.id}>
                    <Phase10Cell strong>{policy.name}</Phase10Cell>
                    <Phase10Cell>{policy.entityType.replaceAll('_', ' ')}</Phase10Cell>
                    <Phase10Cell>
                      {policy.scopeType}
                      {policy.departmentId ? ` · ${policy.departmentId}` : ''}
                      {policy.documentTypeId ? ` · ${policy.documentTypeId}` : ''}
                    </Phase10Cell>
                    <Phase10Cell>{policy.retentionDays} days</Phase10Cell>
                    <Phase10Cell>
                      {policy.archiveAfterDays === null
                        ? '—'
                        : `${policy.archiveAfterDays} days`}
                    </Phase10Cell>
                    <Phase10Cell>
                      {policy.deleteAfterDays === null
                        ? '—'
                        : `${policy.deleteAfterDays} days`}
                    </Phase10Cell>
                    <Phase10Cell>
                      {policy.legalHoldEnabled ? 'Enabled' : 'No'}
                    </Phase10Cell>
                    <Phase10Cell>{policy.isActive ? 'Yes' : 'No'}</Phase10Cell>
                    <Phase10Cell>
                      {formatDateTime(policy.updatedAt)}
                    </Phase10Cell>
                    <td className="px-4 py-3">
                      <div className="flex min-w-max gap-1.5">
                        <Phase10Action
                          label="Edit"
                          icon={Edit3}
                          onClick={() => setTarget(policy)}
                        />
                        <Phase10Action
                          label="Dry Run"
                          icon={Play}
                          disabled={!policy.isActive}
                          onClick={() => setCleanupTarget(policy)}
                        />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Phase8Pagination
            page={page}
            totalItems={query.data.totalItems}
            totalPages={query.data.totalPages}
            label="retention policies"
            onPageChange={setPage}
          />
        </>
      )}
      {target && (
        <RetentionDialog
          key={target === 'create' ? 'new' : target.id}
          policy={target === 'create' ? null : target}
          pending={mutations.create.isPending || mutations.update.isPending}
          onClose={() => setTarget(null)}
          onSave={save}
        />
      )}
      {cleanupTarget && (
        <RetentionRunDialog
          policy={cleanupTarget}
          pending={mutations.run.isPending}
          onClose={() => setCleanupTarget(null)}
          onRun={async (batchSize) => {
            try {
              const result = await mutations.run.mutateAsync({
                entityType: cleanupTarget.entityType,
                dryRun: true,
                batchSize,
              });
              setCleanupTarget(null);
              showToast({
                tone: 'success',
                title: 'Retention dry-run completed',
                message: `${result.eligibleCount} of ${result.scannedCount} scanned records are eligible.`,
              });
            } catch (error: unknown) {
              showToast({
                tone: 'error',
                title: 'Retention dry-run failed',
                message: getApiErrorMessage(error, 'Try again.'),
              });
            }
          }}
        />
      )}
    </div>
  );
}

function RetentionRunDialog({
  onClose,
  onRun,
  pending,
  policy,
}: {
  policy: RetentionPolicy;
  pending: boolean;
  onClose: () => void;
  onRun: (batchSize: number) => Promise<void>;
}) {
  const [batchSize, setBatchSize] = useState(500);
  return (
    <Phase10Dialog
      open
      label="Run retention dry-run"
      title="Run Retention Dry-Run?"
      description={`Preview ${policy.entityType.replaceAll('_', ' ')} eligibility without archiving or deleting data.`}
      onClose={onClose}
      width="max-w-lg"
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (batchSize < 1 || batchSize > 5000) return;
          void onRun(batchSize);
        }}
      >
        <Field label="Maximum batch size">
          <input
            type="number"
            min={1}
            max={5000}
            value={batchSize}
            onChange={(event) => setBatchSize(Number(event.target.value))}
            className={phase10InputClass}
          />
        </Field>
        <p className="mt-3 rounded-xl bg-amber-50 p-3 text-xs leading-5 text-amber-800">
          Dry-run is enforced for this action. Legal-hold records are counted as
          skipped and remain unchanged.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="min-h-10 rounded-xl border border-slate-300 px-4 text-xs font-semibold"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={pending || batchSize < 1 || batchSize > 5000}
            className="min-h-10 rounded-xl bg-blue-700 px-4 text-xs font-semibold text-white disabled:opacity-50"
          >
            {pending ? 'Running…' : 'Run Dry-Run'}
          </button>
        </div>
      </form>
    </Phase10Dialog>
  );
}

function RetentionDialog({
  onClose,
  onSave,
  pending,
  policy,
}: {
  policy: RetentionPolicy | null;
  pending: boolean;
  onClose: () => void;
  onSave: (payload: RetentionPolicyCreate) => Promise<void>;
}) {
  const departments = useDepartmentOptions();
  const documentTypes = useDocumentTypeOptions();
  const [name, setName] = useState(policy?.name ?? '');
  const [entityType, setEntityType] = useState(policy?.entityType ?? 'TEMP_UPLOAD');
  const [scope, setScope] = useState<RetentionScopeType>(policy?.scopeType ?? 'GLOBAL');
  const [departmentId, setDepartmentId] = useState(policy?.departmentId ?? '');
  const [documentTypeId, setDocumentTypeId] = useState(policy?.documentTypeId ?? '');
  const [retentionDays, setRetentionDays] = useState(policy?.retentionDays ?? 365);
  const [archiveDays, setArchiveDays] = useState<number | ''>(
    policy?.archiveAfterDays ?? '',
  );
  const [deleteDays, setDeleteDays] = useState<number | ''>(
    policy?.deleteAfterDays ?? '',
  );
  const [legalHold, setLegalHold] = useState(policy?.legalHoldEnabled ?? false);
  const [active, setActive] = useState(policy?.isActive ?? true);
  const valid =
    name.trim() &&
    retentionDays > 0 &&
    (!scope.includes('DEPARTMENT') || departmentId) &&
    (!scope.includes('DOCUMENT_TYPE') || documentTypeId) &&
    (archiveDays === '' || archiveDays >= retentionDays) &&
    (deleteDays === '' ||
      deleteDays >= (archiveDays === '' ? retentionDays : archiveDays));

  return (
    <Phase10Dialog
      open
      label={policy ? 'Edit retention policy' : 'Create retention policy'}
      title={policy ? 'Edit Retention Policy' : 'Create Retention Policy'}
      onClose={onClose}
    >
      <form
        className="grid gap-4 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (!valid) return;
          void onSave({
            name: name.trim(),
            entityType,
            scopeType: scope,
            departmentId: scope.includes('DEPARTMENT') ? departmentId : null,
            documentTypeId: scope.includes('DOCUMENT_TYPE')
              ? documentTypeId
              : null,
            retentionDays,
            archiveAfterDays: archiveDays === '' ? null : archiveDays,
            deleteAfterDays: deleteDays === '' ? null : deleteDays,
            legalHoldEnabled: legalHold,
            isActive: active,
          });
        }}
      >
        <Field label="Name">
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            className={phase10InputClass}
          />
        </Field>
        <Field label="Entity type">
          <select
            value={entityType}
            disabled={policy !== null}
            onChange={(event) => setEntityType(event.target.value as typeof entityType)}
            className={phase10InputClass}
          >
            {retentionEntityTypes.map((value) => (
              <option key={value} value={value}>
                {value.replaceAll('_', ' ')}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Scope">
          <select
            value={scope}
            disabled={policy !== null}
            onChange={(event) => setScope(event.target.value as RetentionScopeType)}
            className={phase10InputClass}
          >
            <option value="GLOBAL">Global</option>
            <option value="DEPARTMENT">Department</option>
            <option value="DOCUMENT_TYPE">Document Type</option>
            <option value="DEPARTMENT_DOCUMENT_TYPE">
              Department and Document Type
            </option>
          </select>
        </Field>
        {scope.includes('DEPARTMENT') && (
          <Field label="Department">
            <select
              value={departmentId}
              disabled={policy !== null}
              onChange={(event) => setDepartmentId(event.target.value)}
              className={phase10InputClass}
            >
              <option value="">Select department</option>
              {departments.data?.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.code} · {option.name}
                </option>
              ))}
            </select>
          </Field>
        )}
        {scope.includes('DOCUMENT_TYPE') && (
          <Field label="Document type">
            <select
              value={documentTypeId}
              disabled={policy !== null}
              onChange={(event) => setDocumentTypeId(event.target.value)}
              className={phase10InputClass}
            >
              <option value="">Select document type</option>
              {documentTypes.data?.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.code} · {option.name}
                </option>
              ))}
            </select>
          </Field>
        )}
        <Field label="Retention days">
          <input
            type="number"
            min={1}
            value={retentionDays}
            onChange={(event) => setRetentionDays(Number(event.target.value))}
            className={phase10InputClass}
          />
        </Field>
        <Field label="Archive after days">
          <input
            type="number"
            min={retentionDays}
            value={archiveDays}
            onChange={(event) =>
              setArchiveDays(event.target.value ? Number(event.target.value) : '')
            }
            className={phase10InputClass}
          />
        </Field>
        <Field label="Delete after days">
          <input
            type="number"
            min={archiveDays === '' ? retentionDays : archiveDays}
            value={deleteDays}
            onChange={(event) =>
              setDeleteDays(event.target.value ? Number(event.target.value) : '')
            }
            className={phase10InputClass}
          />
        </Field>
        <div className="flex items-end gap-4 pb-2 text-xs font-semibold text-slate-700">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={legalHold}
              onChange={(event) => setLegalHold(event.target.checked)}
            />{' '}
            Legal hold
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={active}
              onChange={(event) => setActive(event.target.checked)}
            />{' '}
            Active
          </label>
        </div>
        {!valid && (
          <p role="alert" className="text-xs text-rose-700 sm:col-span-2">
            Lifecycle days must be ordered: retention ≤ archive ≤ delete.
          </p>
        )}
        <div className="flex justify-end gap-2 sm:col-span-2">
          <button
            type="button"
            onClick={onClose}
            className="min-h-10 rounded-xl border border-slate-300 px-4 text-xs font-semibold"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!valid || pending}
            className="min-h-10 rounded-xl bg-blue-700 px-4 text-xs font-semibold text-white disabled:opacity-50"
          >
            {pending ? 'Saving…' : 'Save Policy'}
          </button>
        </div>
      </form>
    </Phase10Dialog>
  );
}

function Field({ children, label }: { children: ReactNode; label: string }) {
  return (
    <label className="text-xs font-semibold text-slate-700">
      {label}
      <span className="mt-1.5 block">{children}</span>
    </label>
  );
}
