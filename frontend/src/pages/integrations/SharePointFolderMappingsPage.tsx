import { Edit3, FolderTree, Plus } from 'lucide-react';
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
import { SharePointFolderBrowser } from '../../components/sharepoint/SharePointFolderBrowser';
import { useDepartmentOptions } from '../../hooks/useDepartments';
import { useDocumentTypeOptions } from '../../hooks/useDocumentTypes';
import { useSharePointConnections } from '../../hooks/useSharePointConnections';
import {
  useSharePointFolderMappings,
  useSharePointMappingMutations,
} from '../../hooks/useSharePointMappings';
import { useSectionOptions } from '../../hooks/useSections';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type {
  FolderMappingScope,
  SharePointFolderMapping,
  SharePointFolderMappingWrite,
} from '../../types/sharepoint';

export function SharePointFolderMappingsPage() {
  const [page, setPage] = useState(1);
  const [target, setTarget] = useState<SharePointFolderMapping | 'create' | null>(null);
  const query = useSharePointFolderMappings({ page, pageSize: 20 });
  const connections = useSharePointConnections({ page: 1, pageSize: 100 });
  const departments = useDepartmentOptions();
  const sections = useSectionOptions();
  const documentTypes = useDocumentTypeOptions();
  const mutations = useSharePointMappingMutations();
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canConfigure = hasPermission('sharepoint:configure');
  const { showToast } = useToast();

  const save = async (payload: SharePointFolderMappingWrite): Promise<void> => {
    try {
      if (target && target !== 'create') {
        await mutations.updateFolderMapping.mutateAsync({
          mappingId: target.id,
          payload,
        });
      } else {
        await mutations.createFolderMapping.mutateAsync(payload);
      }
      setTarget(null);
      showToast({ tone: 'success', title: 'Folder mapping saved' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Folder mapping could not be saved',
        message: getApiErrorMessage(error, 'Review scope and folder path.'),
      });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <MasterDataPageHeader
          eyebrow="Integrations"
          title="SharePoint Folder Mappings"
          description="Resolve each document scope to one deterministic, connection-scoped remote folder."
        />
        {canConfigure && (
          <button
            type="button"
            onClick={() => setTarget('create')}
            className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-blue-700 px-4 text-xs font-semibold text-white"
          >
            <Plus className="size-4" aria-hidden="true" />
            Add Mapping
          </button>
        )}
      </div>
      {query.isLoading && <Phase8Loading label="Loading folder mappings" />}
      {query.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            query.error,
            'Folder mappings could not be loaded.',
          )}
          onRetry={() => void query.refetch()}
        />
      )}
      {query.data && query.data.items.length === 0 && (
        <Phase10Empty>No folder mappings configured.</Phase10Empty>
      )}
      {query.data && query.data.items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
            <table className="min-w-[76rem] divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  {[
                    'Connection',
                    'Scope',
                    'Department',
                    'Section',
                    'Document Type',
                    'Remote Folder',
                    'Filename Pattern',
                    'Create Missing',
                    'Priority',
                    'Status',
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
                {query.data.items.map((mapping) => (
                  <tr key={mapping.id}>
                    <Phase10Cell strong>
                      {connections.data?.items.find(
                        (item) => item.id === mapping.sharepointConnectionId,
                      )?.name ?? mapping.sharepointConnectionId}
                    </Phase10Cell>
                    <Phase10Cell>
                      {mapping.mappingScope.replaceAll('_', ' ')}
                    </Phase10Cell>
                    <Phase10Cell>
                      {departments.data?.find(
                        (item) => item.id === mapping.departmentId,
                      )?.name ?? '—'}
                    </Phase10Cell>
                    <Phase10Cell>
                      {sections.data?.find((item) => item.id === mapping.sectionId)
                        ?.name ?? '—'}
                    </Phase10Cell>
                    <Phase10Cell>
                      {documentTypes.data?.find(
                        (item) => item.id === mapping.documentTypeId,
                      )?.name ?? '—'}
                    </Phase10Cell>
                    <Phase10Cell>{mapping.remoteFolderPath}</Phase10Cell>
                    <Phase10Cell>{mapping.filenamePattern ?? 'Default'}</Phase10Cell>
                    <Phase10Cell>
                      {mapping.createFolderIfMissing ? 'Yes' : 'No'}
                    </Phase10Cell>
                    <Phase10Cell>{mapping.priority}</Phase10Cell>
                    <Phase10Cell>
                      {mapping.isActive ? 'Active' : 'Disabled'}
                    </Phase10Cell>
                    <td className="px-4 py-3">
                      {canConfigure && (
                        <Phase10Action
                          label="Edit"
                          icon={Edit3}
                          onClick={() => setTarget(mapping)}
                        />
                      )}
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
            label="folder mappings"
            onPageChange={setPage}
          />
        </>
      )}
      {target && (
        <FolderMappingDialog
          key={target === 'create' ? 'new' : target.id}
          mapping={target === 'create' ? null : target}
          pending={
            mutations.createFolderMapping.isPending ||
            mutations.updateFolderMapping.isPending
          }
          onClose={() => setTarget(null)}
          onSave={save}
        />
      )}
    </div>
  );
}

function FolderMappingDialog({
  mapping,
  onClose,
  onSave,
  pending,
}: {
  mapping: SharePointFolderMapping | null;
  pending: boolean;
  onClose: () => void;
  onSave: (payload: SharePointFolderMappingWrite) => Promise<void>;
}) {
  const connections = useSharePointConnections({ page: 1, pageSize: 100 });
  const departments = useDepartmentOptions();
  const sections = useSectionOptions();
  const documentTypes = useDocumentTypeOptions();
  const [connectionId, setConnectionId] = useState(
    mapping?.sharepointConnectionId ?? '',
  );
  const [scope, setScope] = useState<FolderMappingScope>(
    mapping?.mappingScope ?? 'GLOBAL',
  );
  const [departmentId, setDepartmentId] = useState(mapping?.departmentId ?? '');
  const [sectionId, setSectionId] = useState(mapping?.sectionId ?? '');
  const [documentTypeId, setDocumentTypeId] = useState(mapping?.documentTypeId ?? '');
  const [remotePath, setRemotePath] = useState(mapping?.remoteFolderPath ?? '');
  const [remoteFolderId, setRemoteFolderId] = useState(mapping?.remoteFolderId ?? '');
  const [filenamePattern, setFilenamePattern] = useState(
    mapping?.filenamePattern ?? '',
  );
  const [createMissing, setCreateMissing] = useState(
    mapping?.createFolderIfMissing ?? true,
  );
  const [priority, setPriority] = useState(mapping?.priority ?? 100);
  const [active, setActive] = useState(mapping?.isActive ?? true);
  const [browse, setBrowse] = useState(false);
  const requiresDepartment = scope.includes('DEPARTMENT');
  const requiresSection = scope.includes('SECTION');
  const requiresDocumentType = scope.includes('DOCUMENT_TYPE');
  const valid =
    connectionId &&
    remotePath.trim() &&
    priority >= 0 &&
    (!requiresDepartment || departmentId) &&
    (!requiresSection || sectionId) &&
    (!requiresDocumentType || documentTypeId);

  return (
    <Phase10Dialog
      open
      label={mapping ? 'Edit folder mapping' : 'Create folder mapping'}
      title={mapping ? 'Edit Folder Mapping' : 'Create Folder Mapping'}
      description="Higher-priority matching is resolved deterministically by the backend."
      onClose={onClose}
    >
      <form
        className="grid gap-4 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (!valid) {
            return;
          }
          void onSave({
            sharepointConnectionId: connectionId,
            mappingScope: scope,
            departmentId: requiresDepartment ? departmentId : null,
            sectionId: requiresSection ? sectionId : null,
            documentTypeId: requiresDocumentType ? documentTypeId : null,
            remoteFolderPath: remotePath.trim(),
            remoteFolderId: remoteFolderId || null,
            filenamePattern: filenamePattern.trim() || null,
            createFolderIfMissing: createMissing,
            isActive: active,
            priority,
          });
        }}
      >
        <Field label="Connection">
          <select
            value={connectionId}
            onChange={(event) => {
              setConnectionId(event.target.value);
              setRemotePath('');
              setRemoteFolderId('');
            }}
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
        <Field label="Mapping scope">
          <select
            value={scope}
            onChange={(event) => setScope(event.target.value as FolderMappingScope)}
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
        <Field label="Remote folder path">
          <div className="flex gap-2">
            <input
              value={remotePath}
              onChange={(event) => setRemotePath(event.target.value)}
              className={phase10InputClass}
              placeholder="/DocumentCompliance/HRM"
            />
            <button
              type="button"
              disabled={!connectionId}
              onClick={() => setBrowse((open) => !open)}
              className="grid size-10 shrink-0 place-items-center rounded-xl border border-slate-300 text-blue-700 disabled:opacity-50"
              aria-label="Browse remote folders"
            >
              <FolderTree className="size-4" aria-hidden="true" />
            </button>
          </div>
        </Field>
        <Field label="Filename pattern">
          <input
            value={filenamePattern}
            onChange={(event) => setFilenamePattern(event.target.value)}
            placeholder="{documentCode}_{revision}"
            className={phase10InputClass}
          />
        </Field>
        <Field label="Priority">
          <input
            type="number"
            min={0}
            value={priority}
            onChange={(event) => setPriority(Number(event.target.value))}
            className={phase10InputClass}
          />
        </Field>
        <div className="flex flex-wrap items-end gap-4 pb-2 text-xs font-semibold text-slate-700">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={createMissing}
              onChange={(event) => setCreateMissing(event.target.checked)}
            />
            Create folder if missing
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={active}
              onChange={(event) => setActive(event.target.checked)}
            />
            Active
          </label>
        </div>
        {browse && connectionId && (
          <div className="sm:col-span-2 rounded-2xl border border-slate-200 p-4">
            <SharePointFolderBrowser
              connectionId={connectionId}
              canCreateFolder
              onSelect={(folder) => {
                setRemotePath(folder.path);
                setRemoteFolderId(folder.id);
                setBrowse(false);
              }}
            />
          </div>
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
            {pending ? 'Saving…' : 'Save Mapping'}
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
