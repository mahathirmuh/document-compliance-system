import { Edit3, Pause, Plus, Power } from 'lucide-react';
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
import {
  useNotificationMutations,
  useNotificationRules,
  useNotificationTemplates,
} from '../../hooks/useNotifications';
import { useDepartmentOptions } from '../../hooks/useDepartments';
import { useDocumentTypeOptions } from '../../hooks/useDocumentTypes';
import { useToast } from '../../providers/useToast';
import {
  notificationChannels,
  notificationEventTypes,
  type NotificationRecipientType,
  type NotificationRule,
  type NotificationRuleCreate,
  type NotificationRuleUpdate,
  type NotificationScopeType,
  type NotificationSeverity,
} from '../../types/notification';

const recipientValueKey: Partial<Record<NotificationRecipientType, string>> = {
  SPECIFIC_USERS: 'userIds',
  SPECIFIC_EMAILS: 'emails',
  TEAMS_CHANNEL: 'channelIds',
  TELEGRAM_CHAT: 'chatIds',
};

const configuredRecipientValues = (rule: NotificationRule | null): string => {
  if (!rule) return '';
  const key = recipientValueKey[rule.recipientType];
  if (!key) return '';
  const values = rule.recipientValueJson[key];
  return Array.isArray(values) ? values.map(String).join(', ') : '';
};

export function NotificationRulesPage() {
  const [page, setPage] = useState(1);
  const [target, setTarget] = useState<NotificationRule | 'create' | null>(null);
  const query = useNotificationRules({ page, pageSize: 20 });
  const mutations = useNotificationMutations();
  const { showToast } = useToast();

  const save = async (payload: NotificationRuleCreate): Promise<void> => {
    try {
      if (target && target !== 'create') {
        const update: NotificationRuleUpdate = {
          name: payload.name,
          severityFilterJson: payload.severityFilterJson,
          recipientType: payload.recipientType,
          recipientValueJson: payload.recipientValueJson,
          templateId: payload.templateId,
          sendImmediately: payload.sendImmediately,
          digestEnabled: payload.digestEnabled,
          digestSchedule: payload.digestSchedule,
          isMandatory: payload.isMandatory,
          isActive: payload.isActive,
        };
        await mutations.updateRule.mutateAsync({
          ruleId: target.id,
          payload: update,
        });
      } else {
        await mutations.createRule.mutateAsync(payload);
      }
      setTarget(null);
      showToast({ tone: 'success', title: 'Notification rule saved' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Rule could not be saved',
        message: getApiErrorMessage(error, 'Review recipient and template scope.'),
      });
    }
  };

  const toggle = async (rule: NotificationRule): Promise<void> => {
    try {
      await mutations.setRuleActive.mutateAsync({
        ruleId: rule.id,
        active: !rule.isActive,
      });
      showToast({
        tone: 'success',
        title: rule.isActive ? 'Rule deactivated' : 'Rule activated',
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Rule status could not be changed',
        message: getApiErrorMessage(error, 'Try again.'),
      });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <MasterDataPageHeader
          eyebrow="Administration"
          title="Notification Rules"
          description="Resolve trusted event recipients and templates without accepting arbitrary recipients from event payloads."
        />
        <button
          type="button"
          onClick={() => setTarget('create')}
          className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-blue-700 px-4 text-xs font-semibold text-white"
        >
          <Plus className="size-4" aria-hidden="true" /> Add Rule
        </button>
      </div>
      {query.isLoading && <Phase8Loading label="Loading notification rules" />}
      {query.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            query.error,
            'Notification rules could not be loaded.',
          )}
          onRetry={() => void query.refetch()}
        />
      )}
      {query.data && query.data.items.length === 0 && (
        <Phase10Empty>No notification rules configured.</Phase10Empty>
      )}
      {query.data && query.data.items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
            <table className="min-w-[80rem] divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  {[
                    'Name',
                    'Event',
                    'Channel',
                    'Scope',
                    'Severity',
                    'Recipient',
                    'Template',
                    'Delivery',
                    'Digest',
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
                {query.data.items.map((rule) => (
                  <tr key={rule.id}>
                    <Phase10Cell strong>{rule.name}</Phase10Cell>
                    <Phase10Cell>{rule.eventType.replaceAll('_', ' ')}</Phase10Cell>
                    <Phase10Cell>{rule.channel.replaceAll('_', ' ')}</Phase10Cell>
                    <Phase10Cell>{rule.scopeType}</Phase10Cell>
                    <Phase10Cell>
                      {rule.severityFilterJson.join(', ') || 'All'}
                    </Phase10Cell>
                    <Phase10Cell>{rule.recipientType.replaceAll('_', ' ')}</Phase10Cell>
                    <Phase10Cell>{rule.templateId}</Phase10Cell>
                    <Phase10Cell>
                      {rule.sendImmediately ? 'Immediate' : 'Scheduled'}
                    </Phase10Cell>
                    <Phase10Cell>
                      {rule.digestEnabled
                        ? (rule.digestSchedule ?? 'Enabled')
                        : 'Disabled'}
                    </Phase10Cell>
                    <Phase10Cell>{rule.isActive ? 'Yes' : 'No'}</Phase10Cell>
                    <td className="px-4 py-3">
                      <div className="flex min-w-max gap-1.5">
                        <Phase10Action
                          label="Edit"
                          icon={Edit3}
                          onClick={() => setTarget(rule)}
                        />
                        <Phase10Action
                          label={rule.isActive ? 'Deactivate' : 'Activate'}
                          icon={rule.isActive ? Pause : Power}
                          onClick={() => void toggle(rule)}
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
            label="rules"
            onPageChange={setPage}
          />
        </>
      )}
      {target && (
        <RuleDialog
          key={target === 'create' ? 'new' : target.id}
          rule={target === 'create' ? null : target}
          pending={mutations.createRule.isPending || mutations.updateRule.isPending}
          onClose={() => setTarget(null)}
          onSave={save}
        />
      )}
    </div>
  );
}

function RuleDialog({
  rule,
  pending,
  onClose,
  onSave,
}: {
  rule: NotificationRule | null;
  pending: boolean;
  onClose: () => void;
  onSave: (payload: NotificationRuleCreate) => Promise<void>;
}) {
  const departments = useDepartmentOptions();
  const documentTypes = useDocumentTypeOptions();
  const templates = useNotificationTemplates({
    page: 1,
    pageSize: 100,
    includeInactive: false,
  });
  const [name, setName] = useState(rule?.name ?? '');
  const [eventType, setEventType] = useState(
    rule?.eventType ?? notificationEventTypes[0],
  );
  const [channel, setChannel] = useState(rule?.channel ?? 'IN_APP');
  const [scopeType, setScopeType] = useState<NotificationScopeType>(
    rule?.scopeType ?? 'GLOBAL',
  );
  const [departmentId, setDepartmentId] = useState(rule?.departmentId ?? '');
  const [documentTypeId, setDocumentTypeId] = useState(
    rule?.documentTypeId ?? '',
  );
  const [severity, setSeverity] = useState<NotificationSeverity[]>(
    rule ? [...rule.severityFilterJson] : [],
  );
  const [recipientType, setRecipientType] = useState<NotificationRecipientType>(
    rule?.recipientType ?? 'DOCUMENT_CONTROLLER',
  );
  const [recipientValue, setRecipientValue] = useState(
    configuredRecipientValues(rule),
  );
  const [templateId, setTemplateId] = useState(rule?.templateId ?? '');
  const [immediate, setImmediate] = useState(rule?.sendImmediately ?? true);
  const [digestEnabled, setDigestEnabled] = useState(rule?.digestEnabled ?? false);
  const [digestSchedule, setDigestSchedule] = useState(rule?.digestSchedule ?? '');
  const [mandatory, setMandatory] = useState(rule?.isMandatory ?? false);
  const [active, setActive] = useState(rule?.isActive ?? true);
  const requiresValue = [
    'SPECIFIC_USERS',
    'SPECIFIC_EMAILS',
    'TEAMS_CHANNEL',
    'TELEGRAM_CHAT',
  ].includes(recipientType);
  const valid =
    name.trim() &&
    templateId &&
    (!scopeType.includes('DEPARTMENT') || departmentId) &&
    (!scopeType.includes('DOCUMENT_TYPE') || documentTypeId) &&
    (!requiresValue || recipientValue.trim()) &&
    (!digestEnabled || digestSchedule.trim());
  return (
    <Phase10Dialog
      open
      label={rule ? 'Edit notification rule' : 'Create notification rule'}
      title={rule ? 'Edit Notification Rule' : 'Create Notification Rule'}
      onClose={onClose}
    >
      <form
        className="grid gap-4 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (!valid) return;
          const valueKey = recipientValueKey[recipientType];
          const values = recipientValue
            .split(',')
            .map((value) => value.trim())
            .filter(Boolean);
          void onSave({
            name: name.trim(),
            eventType,
            channel,
            scopeType,
            departmentId: scopeType.includes('DEPARTMENT')
              ? departmentId
              : null,
            documentTypeId: scopeType.includes('DOCUMENT_TYPE')
              ? documentTypeId
              : null,
            severityFilterJson: severity,
            recipientType,
            recipientValueJson: valueKey ? { [valueKey]: values } : {},
            templateId,
            sendImmediately: immediate,
            digestEnabled,
            digestSchedule: digestEnabled ? digestSchedule.trim() : null,
            isMandatory: mandatory,
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
        <Field label="Event type">
          <select
            value={eventType}
            disabled={rule !== null}
            onChange={(event) => setEventType(event.target.value as typeof eventType)}
            className={phase10InputClass}
          >
            {notificationEventTypes.map((value) => (
              <option key={value} value={value}>
                {value.replaceAll('_', ' ')}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Channel">
          <select
            value={channel}
            disabled={rule !== null}
            onChange={(event) => {
              setChannel(event.target.value as typeof channel);
              setTemplateId('');
            }}
            className={phase10InputClass}
          >
            {notificationChannels.map((value) => (
              <option key={value} value={value}>
                {value.replaceAll('_', ' ')}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Scope">
          <select
            value={scopeType}
            disabled={rule !== null}
            onChange={(event) =>
              setScopeType(event.target.value as NotificationScopeType)
            }
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
        {scopeType.includes('DEPARTMENT') && (
          <Field label="Department">
            <select
              value={departmentId}
              disabled={rule !== null}
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
        {scopeType.includes('DOCUMENT_TYPE') && (
          <Field label="Document type">
            <select
              value={documentTypeId}
              disabled={rule !== null}
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
        <Field label="Recipient type">
          <select
            value={recipientType}
            onChange={(event) =>
              setRecipientType(event.target.value as NotificationRecipientType)
            }
            className={phase10InputClass}
          >
            {[
              'EVENT_ACTOR',
              'DOCUMENT_OWNER',
              'DOCUMENT_CONTROLLER',
              'DEPARTMENT_USERS',
              'ROLE',
              'SPECIFIC_USERS',
              'SPECIFIC_EMAILS',
              'TEAMS_CHANNEL',
              'TELEGRAM_CHAT',
            ].map((value) => (
              <option key={value} value={value}>
                {value.replaceAll('_', ' ')}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Recipient values">
          <input
            value={recipientValue}
            onChange={(event) => setRecipientValue(event.target.value)}
            disabled={!requiresValue}
            placeholder="Comma-separated trusted references"
            className={phase10InputClass}
          />
        </Field>
        <Field label="Template">
          <select
            value={templateId}
            onChange={(event) => setTemplateId(event.target.value)}
            className={phase10InputClass}
          >
            <option value="">Select template</option>
            {templates.data?.items
              .filter(
                (template) =>
                  template.channel === channel &&
                  template.eventType === eventType &&
                  template.isActive,
              )
              .map((template) => (
                <option key={template.id} value={template.id}>
                  {template.name}
                </option>
              ))}
          </select>
        </Field>
        <Field label="Digest schedule">
          <input
            value={digestSchedule}
            onChange={(event) => setDigestSchedule(event.target.value)}
            disabled={!digestEnabled}
            placeholder="0 8 * * 1"
            className={phase10InputClass}
          />
        </Field>
        <div className="flex flex-wrap gap-3 text-xs font-semibold text-slate-700 sm:col-span-2">
          {(['INFORMATION', 'WARNING', 'ERROR', 'CRITICAL'] as const).map(
            (value) => (
              <label key={value} className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={severity.includes(value)}
                  onChange={(event) =>
                    setSeverity((current) =>
                      event.target.checked
                        ? [...current, value]
                        : current.filter((item) => item !== value),
                    )
                  }
                />{' '}
                {value}
              </label>
            ),
          )}
        </div>
        <div className="flex flex-wrap gap-4 text-xs font-semibold text-slate-700 sm:col-span-2">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={immediate}
              onChange={(event) => setImmediate(event.target.checked)}
            />{' '}
            Send immediately
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={digestEnabled}
              onChange={(event) => setDigestEnabled(event.target.checked)}
            />{' '}
            Digest enabled
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={active}
              onChange={(event) => setActive(event.target.checked)}
            />{' '}
            Active
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={mandatory}
              onChange={(event) => setMandatory(event.target.checked)}
            />{' '}
            Mandatory
          </label>
        </div>
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
            {pending ? 'Saving…' : 'Save Rule'}
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
