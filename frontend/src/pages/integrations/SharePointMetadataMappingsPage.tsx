import { Edit3, Plus } from 'lucide-react';
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
import { useSharePointConnections } from '../../hooks/useSharePointConnections';
import {
  useSharePointMappingMutations,
  useSharePointMetadataMappings,
} from '../../hooks/useSharePointMappings';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import {
  metadataMappingDataTypes,
  metadataMappingDirections,
  type SharePointMetadataMapping,
  type SharePointMetadataMappingWrite,
} from '../../types/sharepoint';

export function SharePointMetadataMappingsPage() {
  const [page, setPage] = useState(1);
  const [target, setTarget] = useState<SharePointMetadataMapping | 'create' | null>(
    null,
  );
  const query = useSharePointMetadataMappings({ page, pageSize: 20 });
  const mutations = useSharePointMappingMutations();
  const canConfigure = useAuthStore((state) =>
    state.hasPermission('sharepoint:configure'),
  );
  const { showToast } = useToast();

  const save = async (payload: SharePointMetadataMappingWrite): Promise<void> => {
    try {
      if (target && target !== 'create') {
        await mutations.updateMetadataMapping.mutateAsync({
          mappingId: target.id,
          payload,
        });
      } else {
        await mutations.createMetadataMapping.mutateAsync(payload);
      }
      setTarget(null);
      showToast({ tone: 'success', title: 'Metadata mapping saved' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Metadata mapping could not be saved',
        message: getApiErrorMessage(
          error,
          'Use a valid SharePoint internal field name.',
        ),
      });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <MasterDataPageHeader
          eyebrow="Integrations"
          title="SharePoint Metadata Mappings"
          description="Map application fields to SharePoint list-column internal names using registered data transformers."
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
      <p className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-800">
        Configure SharePoint internal column names, not display names. Transformer
        values are restricted to registered backend implementations; arbitrary code is
        never accepted.
      </p>
      {query.isLoading && <Phase8Loading label="Loading metadata mappings" />}
      {query.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            query.error,
            'Metadata mappings could not be loaded.',
          )}
          onRetry={() => void query.refetch()}
        />
      )}
      {query.data && query.data.items.length === 0 && (
        <Phase10Empty>No metadata mappings configured.</Phase10Empty>
      )}
      {query.data && query.data.items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
            <table className="min-w-[68rem] divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  {[
                    'Connection',
                    'Document Field',
                    'SharePoint Internal Name',
                    'Data Type',
                    'Direction',
                    'Required',
                    'Default',
                    'Transformer',
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
                    <Phase10Cell strong>{mapping.connectionName ?? '—'}</Phase10Cell>
                    <Phase10Cell>{mapping.documentField}</Phase10Cell>
                    <Phase10Cell>{mapping.sharepointFieldInternalName}</Phase10Cell>
                    <Phase10Cell>{mapping.dataType.replaceAll('_', ' ')}</Phase10Cell>
                    <Phase10Cell>{mapping.direction}</Phase10Cell>
                    <Phase10Cell>{mapping.isRequired ? 'Yes' : 'No'}</Phase10Cell>
                    <Phase10Cell>{mapping.defaultValue ?? '—'}</Phase10Cell>
                    <Phase10Cell>{mapping.transformerCode ?? 'Default'}</Phase10Cell>
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
            label="metadata mappings"
            onPageChange={setPage}
          />
        </>
      )}
      {target && (
        <MetadataMappingDialog
          key={target === 'create' ? 'new' : target.id}
          mapping={target === 'create' ? null : target}
          pending={
            mutations.createMetadataMapping.isPending ||
            mutations.updateMetadataMapping.isPending
          }
          onClose={() => setTarget(null)}
          onSave={save}
        />
      )}
    </div>
  );
}

const documentFields = [
  'baseDocumentCode',
  'revisionCode',
  'department.code',
  'documentType.code',
  'document.title',
  'documentStatus.code',
] as const;

function MetadataMappingDialog({
  mapping,
  onClose,
  onSave,
  pending,
}: {
  mapping: SharePointMetadataMapping | null;
  pending: boolean;
  onClose: () => void;
  onSave: (payload: SharePointMetadataMappingWrite) => Promise<void>;
}) {
  const connections = useSharePointConnections({ page: 1, pageSize: 100 });
  const [connectionId, setConnectionId] = useState(
    mapping?.sharepointConnectionId ?? '',
  );
  const [documentField, setDocumentField] = useState(
    mapping?.documentField ?? documentFields[0],
  );
  const [sharePointField, setSharePointField] = useState(
    mapping?.sharepointFieldInternalName ?? '',
  );
  const [dataType, setDataType] = useState(mapping?.dataType ?? 'STRING');
  const [direction, setDirection] = useState(mapping?.direction ?? 'OUTBOUND');
  const [required, setRequired] = useState(mapping?.isRequired ?? false);
  const [defaultValue, setDefaultValue] = useState(mapping?.defaultValue ?? '');
  const [transformer, setTransformer] = useState(mapping?.transformerCode ?? '');
  const [active, setActive] = useState(mapping?.isActive ?? true);
  const valid =
    connectionId &&
    documentField.trim() &&
    /^[A-Za-z_][A-Za-z0-9_]*$/.test(sharePointField.trim()) &&
    (!required || defaultValue.trim() || direction !== 'OUTBOUND');

  return (
    <Phase10Dialog
      open
      label={mapping ? 'Edit metadata mapping' : 'Create metadata mapping'}
      title={mapping ? 'Edit Metadata Mapping' : 'Create Metadata Mapping'}
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
            documentField: documentField.trim(),
            sharepointFieldInternalName: sharePointField.trim(),
            dataType,
            direction,
            isRequired: required,
            defaultValue: defaultValue.trim() || null,
            transformerCode: transformer.trim() || null,
            isActive: active,
          });
        }}
      >
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
        <Field label="Document field">
          <input
            list="document-fields"
            value={documentField}
            onChange={(event) => setDocumentField(event.target.value)}
            className={phase10InputClass}
          />
          <datalist id="document-fields">
            {documentFields.map((field) => (
              <option key={field} value={field} />
            ))}
          </datalist>
        </Field>
        <Field label="SharePoint field internal name">
          <input
            value={sharePointField}
            onChange={(event) => setSharePointField(event.target.value)}
            placeholder="DocumentCode"
            className={phase10InputClass}
          />
        </Field>
        <Field label="Data type">
          <select
            value={dataType}
            onChange={(event) =>
              setDataType(
                event.target.value as SharePointMetadataMappingWrite['dataType'],
              )
            }
            className={phase10InputClass}
          >
            {metadataMappingDataTypes.map((value) => (
              <option key={value} value={value}>
                {value.replaceAll('_', ' ')}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Direction">
          <select
            value={direction}
            onChange={(event) =>
              setDirection(
                event.target.value as SharePointMetadataMappingWrite['direction'],
              )
            }
            className={phase10InputClass}
          >
            {metadataMappingDirections.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Default value">
          <input
            value={defaultValue}
            onChange={(event) => setDefaultValue(event.target.value)}
            className={phase10InputClass}
          />
        </Field>
        <Field label="Registered transformer code">
          <input
            value={transformer}
            onChange={(event) => setTransformer(event.target.value)}
            placeholder="Leave blank for standard transformer"
            className={phase10InputClass}
          />
        </Field>
        <div className="flex items-end gap-4 pb-2 text-xs font-semibold text-slate-700">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={required}
              onChange={(event) => setRequired(event.target.checked)}
            />
            Required
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
        {!valid && sharePointField && (
          <p role="alert" className="sm:col-span-2 text-xs text-rose-700">
            Internal names may contain letters, numbers, and underscores and cannot
            start with a number.
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
