import {
  Edit3,
  Pause,
  Play,
  Plus,
  Power,
  RotateCcw,
  TriangleAlert,
} from 'lucide-react';
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
  ReasonDialog,
  phase10InputClass,
  phase10TextareaClass,
} from '../../components/phase10/Phase10Ui';
import { useDepartmentOptions } from '../../hooks/useDepartments';
import { useDocumentTypeOptions } from '../../hooks/useDocumentTypes';
import { useSharePointConnections } from '../../hooks/useSharePointConnections';
import { useSharePointFolderMappings } from '../../hooks/useSharePointMappings';
import {
  useSharePointSyncMutations,
  useSharePointSyncProfiles,
} from '../../hooks/useSharePointSync';
import { useSectionOptions } from '../../hooks/useSections';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import {
  syncDirections,
  type SharePointSyncProfile,
  type SharePointSyncProfileWrite,
  type SyncConflictPolicy,
  type SyncDeletePolicy,
  type SyncDirection,
  type SyncScopeType,
} from '../../types/synchronisation';
import { formatDateTime } from '../../utils/formatters';

export function SharePointSyncProfilesPage() {
  const [page, setPage] = useState(1);
  const [target, setTarget] = useState<SharePointSyncProfile | 'create' | null>(null);
  const [resetTarget, setResetTarget] = useState<SharePointSyncProfile | null>(null);
  const query = useSharePointSyncProfiles({ page, pageSize: 20 });
  const connections = useSharePointConnections({ page: 1, pageSize: 100 });
  const mutations = useSharePointSyncMutations();
  const canConfigure = useAuthStore((state) =>
    state.hasPermission('sharepoint:configure'),
  );
  const canSync = useAuthStore((state) => state.hasPermission('sharepoint:sync'));
  const { showToast } = useToast();

  const save = async (payload: SharePointSyncProfileWrite): Promise<void> => {
    try {
      if (target && target !== 'create') {
        await mutations.updateProfile.mutateAsync({
          profileId: target.id,
          payload,
        });
      } else {
        await mutations.createProfile.mutateAsync(payload);
      }
      setTarget(null);
      showToast({ tone: 'success', title: 'Sync profile saved' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Sync profile could not be saved',
        message: getApiErrorMessage(error, 'Review conflict and delete policies.'),
      });
    }
  };

  const run = async (profile: SharePointSyncProfile): Promise<void> => {
    try {
      await mutations.runProfile.mutateAsync({
        profileId: profile.id,
        jobType: profile.deltaSyncEnabled ? 'MANUAL_INCREMENTAL' : 'MANUAL_FULL',
      });
      showToast({ tone: 'success', title: 'SharePoint sync queued' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Sync could not be queued',
        message: getApiErrorMessage(error, 'Check whether another job is active.'),
      });
    }
  };

  const toggle = async (profile: SharePointSyncProfile): Promise<void> => {
    try {
      await mutations.setProfileActive.mutateAsync({
        profileId: profile.id,
        active: !profile.isActive,
      });
      showToast({
        tone: 'success',
        title: profile.isActive ? 'Sync profile deactivated' : 'Sync profile activated',
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Profile status could not be changed',
        message: getApiErrorMessage(error, 'Try again.'),
      });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <MasterDataPageHeader
          eyebrow="Integrations"
          title="SharePoint Sync Profiles"
          description="Control direction, scope, delta processing, webhook triggers, conflicts, and remote-delete handling."
        />
        {canConfigure && (
          <button
            type="button"
            onClick={() => setTarget('create')}
            className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-blue-700 px-4 text-xs font-semibold text-white"
          >
            <Plus className="size-4" aria-hidden="true" />
            Add Profile
          </button>
        )}
      </div>
      {query.isLoading && <Phase8Loading label="Loading sync profiles" />}
      {query.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            query.error,
            'Sync profiles could not be loaded.',
          )}
          onRetry={() => void query.refetch()}
        />
      )}
      {query.data && query.data.items.length === 0 && (
        <Phase10Empty>No SharePoint sync profiles configured.</Phase10Empty>
      )}
      {query.data && query.data.items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
            <table className="min-w-[88rem] divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  {[
                    'Name',
                    'Connection',
                    'Direction',
                    'Scope',
                    'Folder Mapping',
                    'Metadata Mapping',
                    'Conflict Policy',
                    'Delete Policy',
                    'Delta Sync',
                    'Webhook',
                    'Schedule',
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
                {query.data.items.map((profile) => (
                  <tr key={profile.id}>
                    <Phase10Cell strong>{profile.name}</Phase10Cell>
                    <Phase10Cell>
                      {connections.data?.items.find(
                        (item) => item.id === profile.sharepointConnectionId,
                      )?.name ?? profile.sharepointConnectionId}
                    </Phase10Cell>
                    <Phase10Cell>{profile.direction}</Phase10Cell>
                    <Phase10Cell>{profile.scopeType}</Phase10Cell>
                    <Phase10Cell>
                      {profile.folderMappingId ? 'Configured' : '—'}
                    </Phase10Cell>
                    <Phase10Cell>
                      {Object.keys(profile.metadataMappingProfile).length
                        ? 'Configured'
                        : 'Default'}
                    </Phase10Cell>
                    <Phase10Cell>
                      {profile.conflictPolicy.replaceAll('_', ' ')}
                    </Phase10Cell>
                    <Phase10Cell>
                      {profile.deletePolicy.replaceAll('_', ' ')}
                    </Phase10Cell>
                    <Phase10Cell>
                      {profile.deltaSyncEnabled ? 'Enabled' : 'Disabled'}
                    </Phase10Cell>
                    <Phase10Cell>
                      {profile.webhookEnabled ? 'Enabled' : 'Disabled'}
                    </Phase10Cell>
                    <Phase10Cell>{profile.syncSchedule ?? 'Manual'}</Phase10Cell>
                    <Phase10Cell>{profile.isActive ? 'Yes' : 'No'}</Phase10Cell>
                    <Phase10Cell>{formatDateTime(profile.updatedAt)}</Phase10Cell>
                    <td className="px-4 py-3">
                      <div className="flex min-w-max gap-1.5">
                        {canConfigure && (
                          <>
                            <Phase10Action
                              label="Edit"
                              icon={Edit3}
                              onClick={() => setTarget(profile)}
                            />
                            <Phase10Action
                              label={profile.isActive ? 'Deactivate' : 'Activate'}
                              icon={profile.isActive ? Pause : Power}
                              onClick={() => void toggle(profile)}
                            />
                            <Phase10Action
                              label="Reset Delta"
                              icon={RotateCcw}
                              tone="danger"
                              disabled={!profile.deltaSyncEnabled}
                              onClick={() => setResetTarget(profile)}
                            />
                          </>
                        )}
                        {canSync && (
                          <Phase10Action
                            label="Run"
                            icon={Play}
                            tone="primary"
                            disabled={
                              !profile.isActive || mutations.runProfile.isPending
                            }
                            onClick={() => void run(profile)}
                          />
                        )}
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
            label="sync profiles"
            onPageChange={setPage}
          />
        </>
      )}
      {target && (
        <SyncProfileDialog
          key={target === 'create' ? 'new' : target.id}
          profile={target === 'create' ? null : target}
          pending={
            mutations.createProfile.isPending || mutations.updateProfile.isPending
          }
          onClose={() => setTarget(null)}
          onSave={save}
        />
      )}
      <ReasonDialog
        open={resetTarget !== null}
        title="Reset delta state?"
        description="The next run may require a controlled full reconciliation. Existing delta links are never exposed."
        confirmLabel="Reset Delta"
        isPending={mutations.resetDelta.isPending}
        onClose={() => setResetTarget(null)}
        onConfirm={async (reason) => {
          if (!resetTarget) return;
          try {
            await mutations.resetDelta.mutateAsync({
              profileId: resetTarget.id,
              reason,
            });
            setResetTarget(null);
            showToast({ tone: 'success', title: 'Delta state reset' });
          } catch (error: unknown) {
            showToast({
              tone: 'error',
              title: 'Delta state could not be reset',
              message: getApiErrorMessage(error, 'Try again.'),
            });
          }
        }}
      />
    </div>
  );
}

function SyncProfileDialog({
  onClose,
  onSave,
  pending,
  profile,
}: {
  profile: SharePointSyncProfile | null;
  pending: boolean;
  onClose: () => void;
  onSave: (payload: SharePointSyncProfileWrite) => Promise<void>;
}) {
  const connections = useSharePointConnections({ page: 1, pageSize: 100 });
  const mappings = useSharePointFolderMappings({ page: 1, pageSize: 100 });
  const departments = useDepartmentOptions();
  const sections = useSectionOptions();
  const documentTypes = useDocumentTypeOptions();
  const [name, setName] = useState(profile?.name ?? '');
  const [description, setDescription] = useState(profile?.description ?? '');
  const [connectionId, setConnectionId] = useState(
    profile?.sharepointConnectionId ?? '',
  );
  const [direction, setDirection] = useState<SyncDirection>(
    profile?.direction ?? 'OUTBOUND',
  );
  const [scope, setScope] = useState<SyncScopeType>(profile?.scopeType ?? 'GLOBAL');
  const [departmentId, setDepartmentId] = useState(profile?.departmentId ?? '');
  const [sectionId, setSectionId] = useState(profile?.sectionId ?? '');
  const [documentTypeId, setDocumentTypeId] = useState(profile?.documentTypeId ?? '');
  const [folderMappingId, setFolderMappingId] = useState(
    profile?.folderMappingId ?? '',
  );
  const [metadataMappingProfile, setMetadataMappingProfile] = useState(
    JSON.stringify(profile?.metadataMappingProfile ?? {}, null, 2),
  );
  const [conflictPolicy, setConflictPolicy] = useState<SyncConflictPolicy>(
    profile?.conflictPolicy ?? 'MANUAL',
  );
  const [deletePolicy, setDeletePolicy] = useState<SyncDeletePolicy>(
    profile?.deletePolicy ?? 'IGNORE_REMOTE_DELETE',
  );
  const [schedule, setSchedule] = useState(profile?.syncSchedule ?? '');
  const [deltaEnabled, setDeltaEnabled] = useState(profile?.deltaSyncEnabled ?? true);
  const [webhookEnabled, setWebhookEnabled] = useState(
    profile?.webhookEnabled ?? false,
  );
  const [active, setActive] = useState(profile?.isActive ?? true);
  const requiresDepartment = scope.includes('DEPARTMENT');
  const requiresSection = scope.includes('SECTION');
  const requiresDocumentType = scope.includes('DOCUMENT_TYPE');
  let parsedMetadataProfile: Record<string, unknown> | null = null;
  try {
    const parsed: unknown = JSON.parse(metadataMappingProfile);
    if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
      parsedMetadataProfile = parsed as Record<string, unknown>;
    }
  } catch {
    parsedMetadataProfile = null;
  }
  const risky =
    direction === 'BIDIRECTIONAL' ||
    conflictPolicy === 'APPLICATION_WINS' ||
    conflictPolicy === 'SHAREPOINT_WINS' ||
    deletePolicy !== 'IGNORE_REMOTE_DELETE';
  const valid =
    name.trim() &&
    connectionId &&
    folderMappingId &&
    (!requiresDepartment || departmentId) &&
    (!requiresSection || sectionId) &&
    (!requiresDocumentType || documentTypeId) &&
    parsedMetadataProfile !== null &&
    (direction !== 'BIDIRECTIONAL' || Boolean(conflictPolicy));

  return (
    <Phase10Dialog
      open
      label={profile ? 'Edit sync profile' : 'Create sync profile'}
      title={profile ? 'Edit Sync Profile' : 'Create Sync Profile'}
      description="Bidirectional sync requires an explicit conflict policy. The default remains manual resolution."
      onClose={onClose}
      width="max-w-4xl"
    >
      <form
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
        onSubmit={(event) => {
          event.preventDefault();
          if (!valid) return;
          void onSave({
            name: name.trim(),
            description: description.trim() || null,
            sharepointConnectionId: connectionId,
            direction,
            scopeType: scope,
            departmentId: requiresDepartment ? departmentId : null,
            sectionId: requiresSection ? sectionId : null,
            documentTypeId: requiresDocumentType ? documentTypeId : null,
            folderMappingId,
            metadataMappingProfile: parsedMetadataProfile ?? {},
            conflictPolicy,
            deletePolicy,
            syncSchedule: schedule.trim() || null,
            deltaSyncEnabled: deltaEnabled,
            webhookEnabled,
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
        <Field label="Connection">
          <select
            value={connectionId}
            onChange={(event) => setConnectionId(event.target.value)}
            className={phase10InputClass}
          >
            <option value="">Select connection</option>
            {connections.data?.items
              .filter((item) => item.isActive)
              .map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
          </select>
        </Field>
        <Field label="Direction">
          <select
            value={direction}
            onChange={(event) => setDirection(event.target.value as SyncDirection)}
            className={phase10InputClass}
          >
            {syncDirections.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Scope">
          <select
            value={scope}
            onChange={(event) => setScope(event.target.value as SyncScopeType)}
            className={phase10InputClass}
          >
            {[
              'GLOBAL',
              'DEPARTMENT',
              'SECTION',
              'DOCUMENT_TYPE',
              'DEPARTMENT_DOCUMENT_TYPE',
              'SECTION_DOCUMENT_TYPE',
            ].map((value) => (
              <option key={value} value={value}>
                {value.replaceAll('_', ' ')}
              </option>
            ))}
          </select>
        </Field>
        {requiresDepartment && (
          <Field label="Department">
            <select
              value={departmentId}
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
        {requiresSection && (
          <Field label="Section">
            <select
              value={sectionId}
              onChange={(event) => setSectionId(event.target.value)}
              className={phase10InputClass}
            >
              <option value="">Select section</option>
              {sections.data?.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.code} · {option.name}
                </option>
              ))}
            </select>
          </Field>
        )}
        {requiresDocumentType && (
          <Field label="Document type">
            <select
              value={documentTypeId}
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
        <Field label="Folder mapping">
          <select
            value={folderMappingId}
            onChange={(event) => setFolderMappingId(event.target.value)}
            className={phase10InputClass}
          >
            <option value="">Select folder mapping</option>
            {mappings.data?.items
              .filter(
                (item) =>
                  item.isActive &&
                  (!connectionId || item.sharepointConnectionId === connectionId),
              )
              .map((item) => (
                <option key={item.id} value={item.id}>
                  {item.mappingScope} · {item.remoteFolderPath}
                </option>
              ))}
          </select>
        </Field>
        <Field label="Metadata mapping profile (JSON)">
          <textarea
            value={metadataMappingProfile}
            onChange={(event) => setMetadataMappingProfile(event.target.value)}
            rows={3}
            className={phase10TextareaClass}
          />
        </Field>
        {parsedMetadataProfile === null && (
          <p role="alert" className="self-end text-xs text-rose-700">
            Metadata mapping profile must be a JSON object.
          </p>
        )}
        <Field label="Conflict policy">
          <select
            value={conflictPolicy}
            onChange={(event) =>
              setConflictPolicy(event.target.value as SyncConflictPolicy)
            }
            className={phase10InputClass}
          >
            {[
              'MANUAL',
              'APPLICATION_WINS',
              'SHAREPOINT_WINS',
              'LATEST_MODIFIED_WINS',
              'CREATE_COPY',
            ].map((value) => (
              <option key={value} value={value}>
                {value.replaceAll('_', ' ')}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Delete policy">
          <select
            value={deletePolicy}
            onChange={(event) =>
              setDeletePolicy(event.target.value as SyncDeletePolicy)
            }
            className={phase10InputClass}
          >
            {[
              'IGNORE_REMOTE_DELETE',
              'ARCHIVE_LOCAL',
              'MARK_MISSING',
              'DELETE_LOCAL_SOFT',
            ].map((value) => (
              <option key={value} value={value}>
                {value.replaceAll('_', ' ')}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Schedule">
          <input
            value={schedule}
            onChange={(event) => setSchedule(event.target.value)}
            placeholder="Manual or cron expression"
            className={phase10InputClass}
          />
        </Field>
        <div className="flex flex-wrap items-end gap-4 pb-2 text-xs font-semibold text-slate-700 lg:col-span-2">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={deltaEnabled}
              onChange={(event) => setDeltaEnabled(event.target.checked)}
            />{' '}
            Delta sync
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={webhookEnabled}
              onChange={(event) => setWebhookEnabled(event.target.checked)}
            />{' '}
            Webhook
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
        <div className="lg:col-span-3">
          <Field label="Description">
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={3}
              className={phase10TextareaClass}
            />
          </Field>
        </div>
        {risky && (
          <div
            role="alert"
            className="flex gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-800 lg:col-span-3"
          >
            <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            This profile can overwrite, duplicate, archive, or soft-delete data
            depending on detected changes. Review policies before activation; manual
            conflicts are never overwritten automatically.
          </div>
        )}
        <div className="flex justify-end gap-2 lg:col-span-3">
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
            {pending ? 'Saving…' : 'Save Profile'}
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
