import { Edit3, FlaskConical, Plus } from 'lucide-react';
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
  phase10TextareaClass,
} from '../../components/phase10/Phase10Ui';
import {
  useNotificationMutations,
  useNotificationTemplates,
} from '../../hooks/useNotifications';
import { useToast } from '../../providers/useToast';
import {
  notificationChannels,
  notificationEventTypes,
  type NotificationContentType,
  type NotificationTemplate,
  type NotificationTemplateCreate,
  type NotificationTemplateTestResult,
  type NotificationTemplateUpdate,
} from '../../types/notification';

export function NotificationTemplatesPage() {
  const [page, setPage] = useState(1);
  const [target, setTarget] = useState<NotificationTemplate | 'create' | null>(null);
  const [testTarget, setTestTarget] = useState<NotificationTemplate | null>(null);
  const [testResult, setTestResult] = useState<NotificationTemplateTestResult | null>(
    null,
  );
  const query = useNotificationTemplates({ page, pageSize: 20 });
  const mutations = useNotificationMutations();
  const { showToast } = useToast();

  const save = async (payload: NotificationTemplateCreate): Promise<void> => {
    try {
      if (target && target !== 'create') {
        const update: NotificationTemplateUpdate = {
          name: payload.name,
          subjectTemplate: payload.subjectTemplate ?? null,
          bodyTemplate: payload.bodyTemplate,
          contentType: payload.contentType ?? 'PLAIN_TEXT',
          isDefault: payload.isDefault ?? false,
          isActive: payload.isActive ?? true,
        };
        await mutations.updateTemplate.mutateAsync({
          templateId: target.id,
          payload: update,
        });
      } else {
        await mutations.createTemplate.mutateAsync(payload);
      }
      setTarget(null);
      showToast({ tone: 'success', title: 'Notification template saved' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Template could not be saved',
        message: getApiErrorMessage(error, 'Review template variables and channel.'),
      });
    }
  };

  const renderTest = async (): Promise<void> => {
    if (!testTarget) return;
    try {
      const result = await mutations.testTemplate.mutateAsync({
        templateId: testTarget.id,
        payload: {
          variables: {
            documentCode: 'SAMPLE-DOC-001',
            eventType: testTarget.eventType,
            applicationUrl: '/dashboard',
          },
          send: false,
        },
      });
      setTestResult(result);
      showToast({ tone: 'success', title: 'Template preview rendered' });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Template test failed',
        message: getApiErrorMessage(error, 'Check the channel configuration.'),
      });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <MasterDataPageHeader
          eyebrow="Administration"
          title="Notification Templates"
          description="Manage versioned, channel-specific templates rendered by the backend safe-template engine."
        />
        <button
          type="button"
          onClick={() => setTarget('create')}
          className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-blue-700 px-4 text-xs font-semibold text-white"
        >
          <Plus className="size-4" aria-hidden="true" /> Add Template
        </button>
      </div>
      <p className="rounded-2xl border border-blue-200 bg-blue-50 p-4 text-xs leading-5 text-blue-800">
        Only allow-listed variables are rendered. Templates cannot execute JavaScript,
        Python, or arbitrary expressions.
      </p>
      {query.isLoading && <Phase8Loading label="Loading notification templates" />}
      {query.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            query.error,
            'Notification templates could not be loaded.',
          )}
          onRetry={() => void query.refetch()}
        />
      )}
      {query.data && query.data.items.length === 0 && (
        <Phase10Empty>No notification templates configured.</Phase10Empty>
      )}
      {query.data && query.data.items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
            <table className="min-w-[76rem] divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  {[
                    'Code',
                    'Name',
                    'Event',
                    'Channel',
                    'Content Type',
                    'Language',
                    'Version',
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
                {query.data.items.map((template) => (
                  <tr key={template.id}>
                    <Phase10Cell strong>{template.code}</Phase10Cell>
                    <Phase10Cell>{template.name}</Phase10Cell>
                    <Phase10Cell>{template.eventType.replaceAll('_', ' ')}</Phase10Cell>
                    <Phase10Cell>{template.channel.replaceAll('_', ' ')}</Phase10Cell>
                    <Phase10Cell>
                      {template.contentType.replaceAll('_', ' ')}
                    </Phase10Cell>
                    <Phase10Cell>{template.languageCode.toUpperCase()}</Phase10Cell>
                    <Phase10Cell>{template.version}</Phase10Cell>
                    <Phase10Cell>{template.isDefault ? 'Yes' : 'No'}</Phase10Cell>
                    <Phase10Cell>{template.isActive ? 'Yes' : 'No'}</Phase10Cell>
                    <td className="px-4 py-3">
                      <div className="flex min-w-max gap-1.5">
                        <Phase10Action
                          label="Edit"
                          icon={Edit3}
                          onClick={() => setTarget(template)}
                        />
                        <Phase10Action
                          label="Test"
                          icon={FlaskConical}
                          onClick={() => {
                            setTestResult(null);
                            setTestTarget(template);
                          }}
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
            label="templates"
            onPageChange={setPage}
          />
        </>
      )}
      {target && (
        <TemplateDialog
          key={target === 'create' ? 'new' : target.id}
          template={target === 'create' ? null : target}
          pending={
            mutations.createTemplate.isPending || mutations.updateTemplate.isPending
          }
          onClose={() => setTarget(null)}
          onSave={save}
        />
      )}
      {testTarget && (
        <Phase10Dialog
          open
          label="Test notification template"
          title={`Preview ${testTarget.name}`}
          description="Rendering uses generated sample data and does not send a notification."
          onClose={() => {
            setTestTarget(null);
            setTestResult(null);
          }}
          width="max-w-lg"
        >
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void renderTest();
            }}
          >
            <p className="rounded-xl bg-slate-50 p-3 text-xs text-slate-600">
              Sample document code: <strong>SAMPLE-DOC-001</strong>
            </p>
            {testResult && (
              <section
                aria-label="Rendered template preview"
                className="mt-4 space-y-3 rounded-xl border border-slate-200 p-4"
              >
                <div>
                  <p className="text-[10px] font-semibold uppercase text-slate-400">
                    Subject
                  </p>
                  <p className="mt-1 text-sm text-slate-800">
                    {testResult.subject ?? '—'}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] font-semibold uppercase text-slate-400">
                    Body ({testResult.contentType})
                  </p>
                  <pre className="mt-1 max-h-56 overflow-auto whitespace-pre-wrap text-xs text-slate-700">
                    {testResult.body}
                  </pre>
                </div>
              </section>
            )}
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setTestTarget(null);
                  setTestResult(null);
                }}
                className="min-h-10 rounded-xl border border-slate-300 px-4 text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={mutations.testTemplate.isPending}
                className="min-h-10 rounded-xl bg-blue-700 px-4 text-xs font-semibold text-white disabled:opacity-50"
              >
                {mutations.testTemplate.isPending ? 'Rendering…' : 'Render Preview'}
              </button>
            </div>
          </form>
        </Phase10Dialog>
      )}
    </div>
  );
}

function TemplateDialog({
  onClose,
  onSave,
  pending,
  template,
}: {
  template: NotificationTemplate | null;
  pending: boolean;
  onClose: () => void;
  onSave: (payload: NotificationTemplateCreate) => Promise<void>;
}) {
  const [code, setCode] = useState(template?.code ?? '');
  const [name, setName] = useState(template?.name ?? '');
  const [eventType, setEventType] = useState(
    template?.eventType ?? notificationEventTypes[0],
  );
  const [channel, setChannel] = useState(template?.channel ?? 'IN_APP');
  const [subject, setSubject] = useState(template?.subjectTemplate ?? '');
  const [body, setBody] = useState(template?.bodyTemplate ?? '');
  const [contentType, setContentType] = useState<NotificationContentType>(
    template?.contentType ?? 'PLAIN_TEXT',
  );
  const [language, setLanguage] = useState(template?.languageCode ?? 'en');
  const [isDefault, setIsDefault] = useState(template?.isDefault ?? false);
  const [active, setActive] = useState(template?.isActive ?? true);
  const valid =
    /^[A-Z0-9_]+$/.test(code) &&
    name.trim() &&
    body.trim() &&
    language.trim() &&
    (channel === 'IN_APP' || subject.trim());

  return (
    <Phase10Dialog
      open
      label={template ? 'Edit notification template' : 'Create notification template'}
      title={template ? 'Edit Notification Template' : 'Create Notification Template'}
      onClose={onClose}
    >
      <form
        className="grid gap-4 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (!valid) return;
          void onSave({
            code,
            name: name.trim(),
            eventType,
            channel,
            subjectTemplate: subject.trim() || null,
            bodyTemplate: body,
            contentType,
            languageCode: language.trim().toLowerCase(),
            isDefault,
            isActive: active,
          });
        }}
      >
        <Field label="Code">
          <input
            value={code}
            disabled={template !== null}
            onChange={(event) =>
              setCode(event.target.value.toUpperCase().replaceAll(/[^A-Z0-9_]/g, '_'))
            }
            className={phase10InputClass}
          />
        </Field>
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
            disabled={template !== null}
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
            disabled={template !== null}
            onChange={(event) => setChannel(event.target.value as typeof channel)}
            className={phase10InputClass}
          >
            {notificationChannels.map((value) => (
              <option key={value} value={value}>
                {value.replaceAll('_', ' ')}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Content type">
          <select
            value={contentType}
            onChange={(event) =>
              setContentType(event.target.value as NotificationContentType)
            }
            className={phase10InputClass}
          >
            {['PLAIN_TEXT', 'HTML', 'MARKDOWN', 'JSON_CARD'].map((value) => (
              <option key={value} value={value}>
                {value.replaceAll('_', ' ')}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Language code">
          <input
            value={language}
            disabled={template !== null}
            onChange={(event) => setLanguage(event.target.value)}
            className={phase10InputClass}
          />
        </Field>
        <div className="sm:col-span-2">
          <Field label="Subject template">
            <input
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
              disabled={channel === 'IN_APP'}
              className={phase10InputClass}
            />
          </Field>
        </div>
        <div className="sm:col-span-2">
          <Field label="Body template">
            <textarea
              value={body}
              onChange={(event) => setBody(event.target.value)}
              rows={8}
              className={phase10TextareaClass}
            />
          </Field>
        </div>
        <div className="flex gap-4 text-xs font-semibold text-slate-700 sm:col-span-2">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={isDefault}
              onChange={(event) => setIsDefault(event.target.checked)}
            />{' '}
            Default
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
            {pending ? 'Saving…' : 'Save Template'}
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
