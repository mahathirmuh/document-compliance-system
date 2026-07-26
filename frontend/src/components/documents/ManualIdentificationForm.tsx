import { zodResolver } from '@hookform/resolvers/zod';
import { AlertTriangle, ArrowLeft, CheckCircle2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import {
  errorClassName,
  inputClassName,
  labelClassName,
  textareaClassName,
} from '../master-data/forms/formStyles';
import { useDocumentFormOptions } from '../../hooks/useDocumentFormOptions';
import { useDocumentRevisions } from '../../hooks/useDocumentRevisions';
import { useDocuments } from '../../hooks/useDocuments';
import { useAuthStore } from '../../store/authStore';
import type {
  UploadConfirmationItem,
  UploadProposedAction,
  UploadSessionItem,
} from '../../types/documentUpload';
import {
  generateDocumentCodePreview,
  generateFullDocumentCodePreview,
  isValidRevisionCode,
  normalizeRevisionCode,
} from '../../utils/documentCodes';
import { isUploadActionAllowed, uploadActionLabels } from '../../utils/uploadActions';
import { isHttpUrl } from '../../utils/urls';

const confirmableActions = [
  'ATTACH_TO_EXISTING_REVISION',
  'CREATE_DOCUMENT_AND_REVISION',
  'ADD_NEW_REVISION',
  'REPLACE_CURRENT_FILE',
  'SKIP',
] as const satisfies readonly UploadProposedAction[];

const actionSchema = z
  .object({
    action: z.enum([
      '',
      'ATTACH_TO_EXISTING_REVISION',
      'CREATE_DOCUMENT_AND_REVISION',
      'ADD_NEW_REVISION',
      'REPLACE_CURRENT_FILE',
      'SKIP',
    ]),
    documentId: z.string(),
    revisionId: z.string(),
    companyCode: z.string().trim().max(20),
    departmentId: z.string(),
    sectionId: z.string(),
    documentTypeId: z.string(),
    documentTypeRequiresSection: z.boolean(),
    documentNumber: z.string().trim().max(50),
    title: z.string().trim().max(500),
    description: z.string().trim().max(10_000),
    revisionCode: z.string().trim().max(30),
    documentStatusId: z.string(),
    validationRuleId: z.string(),
    issueDate: z.string(),
    effectiveDate: z.string(),
    sharepointUrl: z
      .string()
      .trim()
      .max(2_000)
      .refine((value) => !value || isHttpUrl(value), {
        message: 'Enter a valid HTTP or HTTPS URL.',
      }),
    setAsCurrentRevision: z.boolean(),
    reason: z.string().trim().max(1_000),
    allowDuplicate: z.boolean(),
  })
  .superRefine((values, context) => {
    if (!values.action) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['action'],
        message: 'Select an action for this file.',
      });
      return;
    }
    if (values.action === 'SKIP') {
      return;
    }

    const requiresExistingDocument =
      values.action === 'ATTACH_TO_EXISTING_REVISION' ||
      values.action === 'ADD_NEW_REVISION' ||
      values.action === 'REPLACE_CURRENT_FILE';
    if (
      requiresExistingDocument &&
      !z.string().uuid().safeParse(values.documentId).success
    ) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['documentId'],
        message: 'Select a document within your accessible department scope.',
      });
    }
    if (
      (values.action === 'ATTACH_TO_EXISTING_REVISION' ||
        values.action === 'REPLACE_CURRENT_FILE') &&
      !z.string().uuid().safeParse(values.revisionId).success
    ) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['revisionId'],
        message: 'Select a target revision.',
      });
    }

    if (values.action === 'CREATE_DOCUMENT_AND_REVISION') {
      const requiredFields = [
        ['departmentId', values.departmentId, 'Department is required.'],
        ['documentTypeId', values.documentTypeId, 'Document type is required.'],
        ['documentNumber', values.documentNumber, 'Document number is required.'],
        ['title', values.title, 'Document title is required.'],
      ] as const;
      requiredFields.forEach(([path, value, message]) => {
        if (!value) {
          context.addIssue({
            code: z.ZodIssueCode.custom,
            path: [path],
            message,
          });
        }
      });
      if (!values.companyCode || !/^[A-Za-z0-9_]+$/.test(values.companyCode)) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['companyCode'],
          message:
            'Company code is required and may use letters, numbers, or underscores.',
        });
      }
      if (!values.documentNumber || !/^[A-Za-z0-9._-]+$/.test(values.documentNumber)) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['documentNumber'],
          message: 'Use letters, numbers, dots, dashes, or underscores.',
        });
      }
      if (values.documentTypeRequiresSection && !values.sectionId) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['sectionId'],
          message: 'Section is required for this document type.',
        });
      }
    }

    if (
      values.action === 'CREATE_DOCUMENT_AND_REVISION' ||
      values.action === 'ADD_NEW_REVISION'
    ) {
      if (!values.revisionCode || !isValidRevisionCode(values.revisionCode)) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['revisionCode'],
          message: 'Enter a valid revision code.',
        });
      }
      if (!values.documentStatusId) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['documentStatusId'],
          message: 'Document status is required.',
        });
      }
    }
    if (values.action === 'REPLACE_CURRENT_FILE' && !values.reason) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['reason'],
        message: 'Replacement reason is required.',
      });
    }
  });

type ActionFormValues = z.infer<typeof actionSchema>;

interface ManualIdentificationFormProps {
  item: UploadSessionItem;
  initialAction?: UploadProposedAction | null;
  isSubmitting: boolean;
  onBack: () => void;
  onSubmit: (item: UploadConfirmationItem) => Promise<void>;
  submitLabel?: string;
}

const emptyDefaults = {
  action: '',
  documentId: '',
  revisionId: '',
  companyCode: '',
  departmentId: '',
  sectionId: '',
  documentTypeId: '',
  documentTypeRequiresSection: false,
  documentNumber: '',
  title: '',
  description: '',
  revisionCode: '',
  documentStatusId: '',
  validationRuleId: '',
  issueDate: '',
  effectiveDate: '',
  sharepointUrl: '',
  setAsCurrentRevision: true,
  reason: '',
  allowDuplicate: false,
} satisfies ActionFormValues;

export function ManualIdentificationForm({
  initialAction,
  isSubmitting,
  item,
  onBack,
  onSubmit,
  submitLabel,
}: ManualIdentificationFormProps) {
  const permissions = useAuthStore((state) => state.permissions);
  const availableActions = useMemo(
    () =>
      confirmableActions.filter((action) => isUploadActionAllowed(action, permissions)),
    [permissions],
  );
  const requestedAction = initialAction ?? item.proposedAction;
  const proposedAction = availableActions.includes(
    requestedAction as (typeof confirmableActions)[number],
  )
    ? (requestedAction as (typeof confirmableActions)[number])
    : '';
  const optionsQuery = useDocumentFormOptions();
  const [documentSearch, setDocumentSearch] = useState(
    item.matchedDocument?.baseDocumentCode ?? '',
  );
  const documentsQuery = useDocuments({
    page: 1,
    pageSize: 100,
    isArchived: false,
    ...(documentSearch.trim() ? { search: documentSearch.trim() } : {}),
    sortBy: 'baseDocumentCode',
    sortOrder: 'asc',
  });

  const {
    formState: { errors },
    getValues,
    handleSubmit,
    register,
    reset,
    setError,
    setValue,
    watch,
  } = useForm<ActionFormValues>({
    resolver: zodResolver(actionSchema),
    defaultValues: emptyDefaults,
  });

  useEffect(() => {
    reset({
      ...emptyDefaults,
      action: proposedAction,
      documentId: item.matchedDocument?.id ?? '',
      revisionId: item.matchedRevision?.id ?? '',
      companyCode: item.parsedMetadata?.companyCode ?? '',
      documentNumber: item.parsedMetadata?.documentNumber ?? '',
      title: item.parsedMetadata?.title ?? '',
      revisionCode: item.parsedMetadata?.revisionCode ?? '',
    });
    setDocumentSearch(item.matchedDocument?.baseDocumentCode ?? '');
  }, [item, proposedAction, reset]);

  const options = optionsQuery.data;
  useEffect(() => {
    if (!options) {
      return;
    }
    const parsed = item.parsedMetadata;
    const department = options.departments.find(
      (candidate) => candidate.code === parsed?.departmentCode,
    );
    const section = options.sections.find(
      (candidate) =>
        candidate.code === parsed?.sectionCode &&
        (!department || candidate.departmentId === department.id),
    );
    const documentType = options.documentTypes.find(
      (candidate) => candidate.code === parsed?.documentTypeCode,
    );
    const initialStatus = options.documentStatuses.find(
      (candidate) => candidate.isInitial,
    );

    if (!getValues('departmentId') && department) {
      setValue('departmentId', department.id);
    }
    if (!getValues('sectionId') && section) {
      setValue('sectionId', section.id);
    }
    if (!getValues('documentTypeId') && documentType) {
      setValue('documentTypeId', documentType.id);
      setValue('documentTypeRequiresSection', documentType.requiresSection);
      if (documentType.defaultValidationRuleId) {
        setValue('validationRuleId', documentType.defaultValidationRuleId);
      }
    }
    if (!getValues('documentStatusId') && initialStatus) {
      setValue('documentStatusId', initialStatus.id);
    }
    if (!getValues('companyCode') && options.defaultCompanyCode) {
      setValue('companyCode', options.defaultCompanyCode);
    }
  }, [getValues, item.parsedMetadata, options, setValue]);

  const action = watch('action');
  const selectedDocumentId = watch('documentId');
  const selectedDepartmentId = watch('departmentId');
  const selectedTypeId = watch('documentTypeId');
  const companyCode = watch('companyCode');
  const documentNumber = watch('documentNumber');
  const sectionId = watch('sectionId');
  const revisionCode = watch('revisionCode');
  const revisionsQuery = useDocumentRevisions(selectedDocumentId || null);

  const selectedDepartment = options?.departments.find(
    (candidate) => candidate.id === selectedDepartmentId,
  );
  const selectedSection = options?.sections.find(
    (candidate) => candidate.id === sectionId,
  );
  const selectedType = options?.documentTypes.find(
    (candidate) => candidate.id === selectedTypeId,
  );
  const availableSections = useMemo(
    () =>
      (options?.sections ?? []).filter(
        (candidate) => candidate.departmentId === selectedDepartmentId,
      ),
    [options?.sections, selectedDepartmentId],
  );

  const generatedBaseCode = generateDocumentCodePreview({
    companyCode,
    departmentCode: selectedDepartment?.code ?? '',
    sectionCode: selectedSection?.code ?? null,
    documentTypeCode: selectedType?.code ?? '',
    documentNumber,
  });
  const generatedFullCode = generateFullDocumentCodePreview(
    generatedBaseCode,
    revisionCode,
  );

  const submit = handleSubmit(async (values) => {
    if (!values.action) {
      return;
    }
    if (
      item.identificationStatus === 'DUPLICATE_FILE' &&
      values.action !== 'SKIP' &&
      !values.allowDuplicate
    ) {
      setError('allowDuplicate', {
        type: 'manual',
        message: 'Acknowledge the duplicate warning before continuing.',
      });
      return;
    }
    const metadata = {
      companyCode: values.companyCode || null,
      departmentId: values.departmentId || null,
      sectionId: values.sectionId || null,
      documentTypeId: values.documentTypeId || null,
      documentNumber: values.documentNumber || null,
      title: values.title || null,
      description: values.description || null,
      revisionCode: values.revisionCode
        ? normalizeRevisionCode(values.revisionCode)
        : null,
      documentStatusId: values.documentStatusId || null,
      validationRuleId: values.validationRuleId || null,
      issueDate: values.issueDate || null,
      effectiveDate: values.effectiveDate || null,
      sharepointUrl: values.sharepointUrl || null,
      setAsCurrentRevision: values.setAsCurrentRevision,
      reason: values.reason || null,
      allowDuplicate: values.allowDuplicate,
    };
    await onSubmit({
      uploadItemId: item.uploadItemId,
      action: values.action,
      documentId: values.documentId || null,
      revisionId: values.revisionId || null,
      metadata,
    });
  });

  const existingAction =
    action === 'ATTACH_TO_EXISTING_REVISION' ||
    action === 'ADD_NEW_REVISION' ||
    action === 'REPLACE_CURRENT_FILE';
  const revisionTargetAction =
    action === 'ATTACH_TO_EXISTING_REVISION' || action === 'REPLACE_CURRENT_FILE';
  const revisionMetadataAction =
    action === 'CREATE_DOCUMENT_AND_REVISION' || action === 'ADD_NEW_REVISION';

  return (
    <form onSubmit={(event) => void submit(event)} className="space-y-5" noValidate>
      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <label className={labelClassName}>
          Confirm action
          <select {...register('action')} className={inputClassName}>
            <option value="">Select an action</option>
            {availableActions.map((candidate) => (
              <option key={candidate} value={candidate}>
                {uploadActionLabels[candidate]}
              </option>
            ))}
          </select>
          {errors.action && <p className={errorClassName}>{errors.action.message}</p>}
        </label>
      </section>

      {existingAction && (
        <section className="rounded-2xl border border-slate-200 bg-white p-5">
          <h3 className="text-sm font-semibold text-slate-950">Register target</h3>
          <label className={`${labelClassName} mt-4`}>
            Search Documents
            <input
              value={documentSearch}
              onChange={(event) => setDocumentSearch(event.target.value)}
              className={inputClassName}
              placeholder="Document code or title"
            />
            <span className="text-[11px] font-normal leading-5 text-slate-500">
              Search runs against the server. Refine the code or title to find documents
              beyond the initial results.
            </span>
          </label>
          <div className="mt-4 grid gap-5 md:grid-cols-2">
            <Field label="Document" error={errors.documentId?.message}>
              <select
                {...register('documentId')}
                className={inputClassName}
                disabled={documentsQuery.isLoading}
                onChange={(event) => {
                  setValue('documentId', event.target.value, {
                    shouldDirty: true,
                    shouldValidate: true,
                  });
                  setValue('revisionId', '', { shouldDirty: true });
                }}
              >
                <option value="">Select document</option>
                {(documentsQuery.data?.items ?? []).map((document) => (
                  <option key={document.id} value={document.id}>
                    {document.baseDocumentCode} — {document.title}
                  </option>
                ))}
              </select>
            </Field>
            {revisionTargetAction && (
              <Field label="Revision" error={errors.revisionId?.message}>
                <select
                  {...register('revisionId')}
                  className={inputClassName}
                  disabled={!selectedDocumentId || revisionsQuery.isLoading}
                >
                  <option value="">Select revision</option>
                  {(revisionsQuery.data ?? []).map((revision) => (
                    <option key={revision.id} value={revision.id}>
                      {revision.revisionCode} — {revision.fullDocumentCode}
                    </option>
                  ))}
                </select>
              </Field>
            )}
          </div>
          {documentsQuery.error && (
            <p role="alert" className="mt-3 text-xs text-rose-700">
              Documents could not be loaded. Your department scope is enforced by the
              server.
            </p>
          )}
        </section>
      )}

      {action === 'CREATE_DOCUMENT_AND_REVISION' && (
        <section className="rounded-2xl border border-slate-200 bg-white p-5">
          <h3 className="text-sm font-semibold text-slate-950">
            Manual document identification
          </h3>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            Active master data and your department scope are loaded from the server.
          </p>
          <div className="mt-5 grid gap-5 md:grid-cols-2">
            <Field label="Company Code" error={errors.companyCode?.message}>
              <input
                {...register('companyCode')}
                className={inputClassName}
                maxLength={20}
              />
            </Field>
            <Field label="Department" error={errors.departmentId?.message}>
              <select
                {...register('departmentId')}
                className={inputClassName}
                onChange={(event) => {
                  setValue('departmentId', event.target.value, {
                    shouldDirty: true,
                    shouldValidate: true,
                  });
                  setValue('sectionId', '', { shouldDirty: true });
                }}
              >
                <option value="">Select department</option>
                {(options?.departments ?? []).map((department) => (
                  <option key={department.id} value={department.id}>
                    {department.code} — {department.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Section" error={errors.sectionId?.message}>
              <select {...register('sectionId')} className={inputClassName}>
                <option value="">No section</option>
                {availableSections.map((section) => (
                  <option key={section.id} value={section.id}>
                    {section.code} — {section.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Document Type" error={errors.documentTypeId?.message}>
              <select
                {...register('documentTypeId')}
                className={inputClassName}
                onChange={(event) => {
                  const nextType = options?.documentTypes.find(
                    (candidate) => candidate.id === event.target.value,
                  );
                  setValue('documentTypeId', event.target.value, {
                    shouldDirty: true,
                    shouldValidate: true,
                  });
                  setValue(
                    'documentTypeRequiresSection',
                    nextType?.requiresSection ?? false,
                  );
                  setValue('validationRuleId', nextType?.defaultValidationRuleId ?? '');
                }}
              >
                <option value="">Select document type</option>
                {(options?.documentTypes ?? []).map((documentType) => (
                  <option key={documentType.id} value={documentType.id}>
                    {documentType.code} — {documentType.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Document Number" error={errors.documentNumber?.message}>
              <input
                {...register('documentNumber')}
                className={inputClassName}
                maxLength={50}
                placeholder="001"
              />
            </Field>
            <Field label="Document Title" error={errors.title?.message}>
              <input
                {...register('title')}
                className={inputClassName}
                maxLength={500}
              />
            </Field>
          </div>
          <label className={`${labelClassName} mt-5`}>
            Description
            <textarea {...register('description')} className={textareaClassName} />
          </label>
          <div className="mt-5 grid gap-3 rounded-2xl bg-slate-50 p-4 sm:grid-cols-2">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                Generated Base Document Code
              </p>
              <p className="mt-1 break-all text-sm font-semibold text-slate-900">
                {generatedBaseCode || 'Complete the identity fields'}
              </p>
            </div>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                Generated Full Document Code
              </p>
              <p className="mt-1 break-all text-sm font-semibold text-slate-900">
                {generatedFullCode || 'Complete the revision fields'}
              </p>
            </div>
          </div>
        </section>
      )}

      {revisionMetadataAction && (
        <section className="rounded-2xl border border-slate-200 bg-white p-5">
          <h3 className="text-sm font-semibold text-slate-950">Revision metadata</h3>
          <div className="mt-4 grid gap-5 md:grid-cols-2">
            <Field label="Revision Code" error={errors.revisionCode?.message}>
              <input
                {...register('revisionCode')}
                className={inputClassName}
                placeholder="Rev.000"
              />
            </Field>
            <Field label="Document Status" error={errors.documentStatusId?.message}>
              <select {...register('documentStatusId')} className={inputClassName}>
                <option value="">Select status</option>
                {(options?.documentStatuses ?? []).map((status) => (
                  <option key={status.id} value={status.id}>
                    {status.code} — {status.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Validation Rule" error={errors.validationRuleId?.message}>
              <select {...register('validationRuleId')} className={inputClassName}>
                <option value="">No validation rule</option>
                {(options?.validationRules ?? [])
                  .filter(
                    (rule) =>
                      rule.documentTypeId === null ||
                      !selectedTypeId ||
                      rule.documentTypeId === selectedTypeId,
                  )
                  .map((rule) => (
                    <option key={rule.id} value={rule.id}>
                      {rule.code} — {rule.name}
                    </option>
                  ))}
              </select>
            </Field>
            <Field label="Issue Date">
              <input
                {...register('issueDate')}
                type="date"
                className={inputClassName}
              />
            </Field>
            <Field label="Effective Date">
              <input
                {...register('effectiveDate')}
                type="date"
                className={inputClassName}
              />
            </Field>
            <Field label="SharePoint URL" error={errors.sharepointUrl?.message}>
              <input
                {...register('sharepointUrl')}
                type="url"
                className={inputClassName}
                placeholder="https://..."
              />
            </Field>
          </div>
          {action === 'ADD_NEW_REVISION' && (
            <label className="mt-5 flex items-center gap-3 text-sm text-slate-700">
              <input
                {...register('setAsCurrentRevision')}
                type="checkbox"
                className="size-4 rounded border-slate-300"
              />
              Set this as the current revision
            </label>
          )}
        </section>
      )}

      {action === 'REPLACE_CURRENT_FILE' && (
        <section className="rounded-2xl border border-amber-200 bg-amber-50 p-5">
          <div className="flex gap-3">
            <AlertTriangle
              className="mt-0.5 size-5 shrink-0 text-amber-700"
              aria-hidden="true"
            />
            <div className="flex-1">
              <h3 className="text-sm font-semibold text-amber-950">
                Sensitive replacement
              </h3>
              <p className="mt-1 text-xs leading-5 text-amber-800">
                The current file will remain in history. Final or effective revisions
                may only be replaced by an authorized controller.
              </p>
              <label className={`${labelClassName} mt-4`}>
                Replacement Reason
                <textarea {...register('reason')} className={textareaClassName} />
                {errors.reason && (
                  <p className={errorClassName}>{errors.reason.message}</p>
                )}
              </label>
            </div>
          </div>
        </section>
      )}

      {item.identificationStatus === 'DUPLICATE_FILE' && action !== 'SKIP' && (
        <div>
          <label className="flex items-start gap-3 rounded-2xl border border-orange-200 bg-orange-50 p-4 text-sm text-orange-950">
            <input
              {...register('allowDuplicate')}
              type="checkbox"
              className="mt-0.5 size-4 rounded border-orange-300"
            />
            <span>
              <strong className="block">
                Continue after reviewing duplicate warning
              </strong>
              <span className="mt-1 block text-xs leading-5 text-orange-800">
                The backend will still reject an exact duplicate on the same revision
                and will recheck your permission and department scope.
              </span>
            </span>
          </label>
          {errors.allowDuplicate && (
            <p className={errorClassName}>{errors.allowDuplicate.message}</p>
          )}
        </div>
      )}

      <div className="flex flex-col-reverse gap-3 border-t border-slate-200 pt-5 sm:flex-row sm:justify-between">
        <button
          type="button"
          onClick={onBack}
          disabled={isSubmitting}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
        >
          <ArrowLeft className="size-4" aria-hidden="true" />
          Back
        </button>
        <button
          type="submit"
          disabled={isSubmitting || item.identificationStatus === 'INVALID'}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-blue-700 px-5 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <CheckCircle2 className="size-4" aria-hidden="true" />
          {isSubmitting
            ? 'Saving...'
            : (submitLabel ?? (action === 'SKIP' ? 'Skip File' : 'Confirm Upload'))}
        </button>
      </div>
    </form>
  );
}

function Field({
  children,
  error,
  label,
}: {
  label: string;
  error?: string | undefined;
  children: React.ReactNode;
}) {
  return (
    <label className={labelClassName}>
      {label}
      {children}
      {error && <p className={errorClassName}>{error}</p>}
    </label>
  );
}
