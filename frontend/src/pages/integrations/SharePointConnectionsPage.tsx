import {
  CheckCircle2,
  Edit3,
  Eye,
  FolderOpen,
  Link2,
  Plus,
  Power,
  Star,
} from 'lucide-react';
import { useState } from 'react';

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
  Phase10StatusBadge,
  phase10InputClass,
  phase10TextareaClass,
} from '../../components/phase10/Phase10Ui';
import { SharePointFolderBrowser } from '../../components/sharepoint/SharePointFolderBrowser';
import {
  useSharePointConnectionMutations,
  useSharePointConnections,
} from '../../hooks/useSharePointConnections';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type {
  SharePointConnection,
  SharePointConnectionCreate,
} from '../../types/sharepoint';
import { formatDateTime } from '../../utils/formatters';

type DialogTarget =
  | { mode: 'create'; connection: null }
  | { mode: 'edit' | 'view' | 'browse'; connection: SharePointConnection };

export function SharePointConnectionsPage() {
  const [page, setPage] = useState(1);
  const [target, setTarget] = useState<DialogTarget | null>(null);
  const query = useSharePointConnections({ page, pageSize: 20 });
  const mutations = useSharePointConnectionMutations();
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canConfigure = hasPermission('sharepoint:configure');
  const canTest = hasPermission('sharepoint:test_connection');
  const { showToast } = useToast();

  const save = async (payload: SharePointConnectionCreate): Promise<void> => {
    try {
      if (target?.mode === 'edit' && target.connection) {
        await mutations.update.mutateAsync({
          connectionId: target.connection.id,
          payload,
        });
      } else {
        await mutations.create.mutateAsync(payload);
      }
      setTarget(null);
      showToast({ tone: 'success', title: 'SharePoint connection saved' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Connection could not be saved',
        message: getApiErrorMessage(error, 'Review the connection configuration.'),
      });
    }
  };

  const testConnection = async (connection: SharePointConnection): Promise<void> => {
    try {
      const result = await mutations.test.mutateAsync(connection.id);
      showToast({
        tone: result.status === 'CONNECTED' ? 'success' : 'info',
        title: `Connection ${result.status.replaceAll('_', ' ').toLowerCase()}`,
        message: result.message,
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Connection test failed',
        message: getApiErrorMessage(error, 'Microsoft Graph could not be reached.'),
      });
    }
  };

  const disable = async (connection: SharePointConnection): Promise<void> => {
    try {
      await mutations.disable.mutateAsync(connection.id);
      showToast({ tone: 'success', title: 'Connection disabled' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Connection could not be disabled',
        message: getApiErrorMessage(error, 'Try again.'),
      });
    }
  };

  const setDefault = async (connection: SharePointConnection): Promise<void> => {
    try {
      await mutations.setDefault.mutateAsync(connection.id);
      showToast({ tone: 'success', title: 'Default connection updated' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Default connection could not be changed',
        message: getApiErrorMessage(error, 'Try again.'),
      });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <MasterDataPageHeader
          eyebrow="Integrations"
          title="SharePoint Connections"
          description="Configure scoped SharePoint Online document libraries. Credentials remain in backend secret management and are never returned here."
        />
        {canConfigure && (
          <button
            type="button"
            onClick={() => setTarget({ mode: 'create', connection: null })}
            className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-blue-700 px-4 text-xs font-semibold text-white"
          >
            <Plus className="size-4" aria-hidden="true" />
            Add Connection
          </button>
        )}
      </div>

      <div className="rounded-2xl border border-blue-200 bg-blue-50 p-4 text-xs leading-5 text-blue-800">
        Frontend requests are sent only to the authenticated application API. No
        Microsoft Graph access token, webhook client state, or delta link is exposed.
      </div>

      {query.isLoading && <Phase8Loading label="Loading SharePoint connections" />}
      {query.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            query.error,
            'SharePoint connections could not be loaded.',
          )}
          onRetry={() => void query.refetch()}
        />
      )}
      {query.data && query.data.items.length === 0 && (
        <Phase10Empty>No SharePoint connections are configured.</Phase10Empty>
      )}
      {query.data && query.data.items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
            <table className="min-w-[88rem] divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  {[
                    'Name',
                    'Site',
                    'Library',
                    'Root Folder',
                    'Authentication Mode',
                    'Status',
                    'Last Tested',
                    'Default',
                    'Active',
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
                {query.data.items.map((connection) => (
                  <tr key={connection.id}>
                    <Phase10Cell strong>{connection.name}</Phase10Cell>
                    <Phase10Cell>
                      {connection.siteHostname}
                      <span className="block text-[10px] text-slate-400">
                        {connection.sitePath}
                      </span>
                    </Phase10Cell>
                    <Phase10Cell>{connection.libraryName}</Phase10Cell>
                    <Phase10Cell>{connection.rootFolderPath}</Phase10Cell>
                    <Phase10Cell>
                      {connection.authMode.replaceAll('_', ' ')}
                    </Phase10Cell>
                    <Phase10Cell>
                      <Phase10StatusBadge status={connection.status} />
                    </Phase10Cell>
                    <Phase10Cell>
                      {connection.lastTestedAt
                        ? formatDateTime(connection.lastTestedAt)
                        : 'Never'}
                    </Phase10Cell>
                    <Phase10Cell>{connection.isDefault ? 'Yes' : 'No'}</Phase10Cell>
                    <Phase10Cell>{connection.isActive ? 'Yes' : 'No'}</Phase10Cell>
                    <td className="px-4 py-3">
                      <div className="flex min-w-max flex-wrap gap-1.5">
                        <Phase10Action
                          label="View"
                          icon={Eye}
                          onClick={() => setTarget({ mode: 'view', connection })}
                        />
                        {canConfigure && (
                          <Phase10Action
                            label="Edit"
                            icon={Edit3}
                            onClick={() => setTarget({ mode: 'edit', connection })}
                          />
                        )}
                        {canTest && (
                          <Phase10Action
                            label="Test Connection"
                            icon={CheckCircle2}
                            disabled={mutations.test.isPending}
                            onClick={() => void testConnection(connection)}
                          />
                        )}
                        <Phase10Action
                          label="Browse"
                          icon={FolderOpen}
                          disabled={!connection.driveId || !connection.isActive}
                          onClick={() => setTarget({ mode: 'browse', connection })}
                        />
                        {canConfigure && !connection.isDefault && (
                          <Phase10Action
                            label="Set Default"
                            icon={Star}
                            onClick={() => void setDefault(connection)}
                          />
                        )}
                        {canConfigure && connection.isActive && (
                          <Phase10Action
                            label="Disable"
                            icon={Power}
                            tone="danger"
                            onClick={() => void disable(connection)}
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
            label="connections"
            onPageChange={setPage}
          />
        </>
      )}

      {target?.mode === 'browse' && (
        <Phase10Dialog
          open
          label={`Browse ${target.connection.name}`}
          title={`Browse ${target.connection.name}`}
          description="Browsing is restricted to this connection and configured library."
          onClose={() => setTarget(null)}
        >
          <SharePointFolderBrowser
            connectionId={target.connection.id}
            initialPath={target.connection.rootFolderPath}
            canCreateFolder={canConfigure}
            onSelect={(folder) =>
              showToast({
                tone: 'success',
                title: 'Folder selected',
                message: folder.path,
              })
            }
          />
        </Phase10Dialog>
      )}
      {target && target.mode !== 'browse' && (
        <ConnectionDialog
          key={`${target.mode}-${target.connection?.id ?? 'new'}`}
          mode={target.mode}
          connection={target.connection}
          pending={mutations.create.isPending || mutations.update.isPending}
          onClose={() => setTarget(null)}
          onSave={save}
        />
      )}
    </div>
  );
}

function ConnectionDialog({
  connection,
  mode,
  onClose,
  onSave,
  pending,
}: {
  mode: 'create' | 'edit' | 'view';
  connection: SharePointConnection | null;
  pending: boolean;
  onClose: () => void;
  onSave: (payload: SharePointConnectionCreate) => Promise<void>;
}) {
  const [name, setName] = useState(connection?.name ?? '');
  const [description, setDescription] = useState(connection?.description ?? '');
  const [tenantReference, setTenantReference] = useState(
    connection?.tenantIdReference ?? '',
  );
  const [hostname, setHostname] = useState(connection?.siteHostname ?? '');
  const [sitePath, setSitePath] = useState(connection?.sitePath ?? '');
  const [siteId, setSiteId] = useState(connection?.siteId ?? '');
  const [driveId, setDriveId] = useState(connection?.driveId ?? '');
  const [libraryName, setLibraryName] = useState(connection?.libraryName ?? '');
  const [rootPath, setRootPath] = useState(
    connection?.rootFolderPath ?? 'DocumentCompliance',
  );
  const [authMode, setAuthMode] = useState<'CLIENT_SECRET' | 'CERTIFICATE'>(
    connection?.authMode ?? 'CLIENT_SECRET',
  );
  const [isDefault, setIsDefault] = useState(connection?.isDefault ?? false);
  const readOnly = mode === 'view';
  const valid =
    name.trim() &&
    tenantReference.trim() &&
    hostname.trim() &&
    sitePath.trim() &&
    libraryName.trim() &&
    rootPath.trim();

  return (
    <Phase10Dialog
      open
      label={`${mode} SharePoint connection`}
      title={
        mode === 'create'
          ? 'Add SharePoint Connection'
          : mode === 'edit'
            ? 'Edit SharePoint Connection'
            : 'SharePoint Connection Details'
      }
      description="Existing credentials are intentionally never loaded into this form."
      onClose={onClose}
    >
      <form
        className="grid gap-4 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (!valid || readOnly) {
            return;
          }
          void onSave({
            name: name.trim(),
            description: description.trim() || null,
            tenantIdReference: tenantReference.trim(),
            siteHostname: hostname.trim(),
            sitePath: sitePath.trim(),
            siteId: siteId.trim() || null,
            driveId: driveId.trim() || null,
            libraryName: libraryName.trim(),
            rootFolderPath: rootPath.trim(),
            authMode,
            isDefault,
          });
        }}
      >
        <Field label="Name">
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            disabled={readOnly}
            className={phase10InputClass}
          />
        </Field>
        <Field label="Tenant reference">
          <input
            value={tenantReference}
            onChange={(event) => setTenantReference(event.target.value)}
            disabled={readOnly}
            className={phase10InputClass}
          />
        </Field>
        <Field label="Site hostname">
          <input
            value={hostname}
            onChange={(event) => setHostname(event.target.value)}
            disabled={readOnly}
            placeholder="contoso.sharepoint.com"
            className={phase10InputClass}
          />
        </Field>
        <Field label="Site path">
          <input
            value={sitePath}
            onChange={(event) => setSitePath(event.target.value)}
            disabled={readOnly}
            placeholder="/sites/Documents"
            className={phase10InputClass}
          />
        </Field>
        <Field label="Site ID">
          <input
            value={siteId}
            onChange={(event) => setSiteId(event.target.value)}
            disabled={readOnly}
            className={phase10InputClass}
          />
        </Field>
        <Field label="Drive ID">
          <input
            value={driveId}
            onChange={(event) => setDriveId(event.target.value)}
            disabled={readOnly}
            className={phase10InputClass}
          />
        </Field>
        <Field label="Library name">
          <input
            value={libraryName}
            onChange={(event) => setLibraryName(event.target.value)}
            disabled={readOnly}
            className={phase10InputClass}
          />
        </Field>
        <Field label="Root folder">
          <input
            value={rootPath}
            onChange={(event) => setRootPath(event.target.value)}
            disabled={readOnly}
            className={phase10InputClass}
          />
        </Field>
        <Field label="Authentication mode">
          <select
            value={authMode}
            onChange={(event) =>
              setAuthMode(event.target.value as 'CLIENT_SECRET' | 'CERTIFICATE')
            }
            disabled={readOnly}
            className={phase10InputClass}
          >
            <option value="CLIENT_SECRET">Client Secret</option>
            <option value="CERTIFICATE">Certificate</option>
          </select>
        </Field>
        <label className="flex items-center gap-2 self-end pb-2 text-xs font-semibold text-slate-700">
          <input
            type="checkbox"
            checked={isDefault}
            onChange={(event) => setIsDefault(event.target.checked)}
            disabled={readOnly}
          />
          Default connection
        </label>
        {!readOnly && (
          <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-xs leading-5 text-blue-800 sm:col-span-2">
            Microsoft application credentials are managed by the production secret
            provider and are never loaded into or submitted by this form. Rotate the
            client secret or certificate externally, restart the API if required, then
            use <strong>Test Connection</strong>.
          </div>
        )}
        <div className="sm:col-span-2">
          <Field label="Description">
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              disabled={readOnly}
              rows={3}
              className={phase10TextareaClass}
            />
          </Field>
        </div>
        {connection?.lastTestMessage && (
          <div className="sm:col-span-2 rounded-xl bg-slate-50 p-4 text-xs text-slate-600">
            <p className="font-semibold text-slate-800">Last connection test</p>
            <p className="mt-1">{connection.lastTestMessage}</p>
          </div>
        )}
        <div className="flex justify-end gap-2 sm:col-span-2">
          <button
            type="button"
            onClick={onClose}
            className="min-h-10 rounded-xl border border-slate-300 px-4 text-xs font-semibold"
          >
            {readOnly ? 'Close' : 'Cancel'}
          </button>
          {!readOnly && (
            <button
              type="submit"
              disabled={!valid || pending}
              className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-blue-700 px-4 text-xs font-semibold text-white disabled:opacity-50"
            >
              <Link2 className="size-4" aria-hidden="true" />
              {pending ? 'Saving…' : 'Save Connection'}
            </button>
          )}
        </div>
      </form>
    </Phase10Dialog>
  );
}

function Field({ children, label }: { children: React.ReactNode; label: string }) {
  return (
    <label className="text-xs font-semibold text-slate-700">
      {label}
      <span className="mt-1.5 block">{children}</span>
    </label>
  );
}
