import { zodResolver } from '@hookform/resolvers/zod';
import { AlertTriangle, Save } from 'lucide-react';
import { useEffect, useMemo, useRef } from 'react';
import { useForm } from 'react-hook-form';

import { DocumentCodeParser } from '../DocumentCodeParser';
import { GeneratedCodePreview } from '../GeneratedCodePreview';
import { getApiErrorMessage } from '../../../api/errors';
import { appConfig } from '../../../config/app';
import { useDocumentFormOptions } from '../../../hooks/useDocumentFormOptions';
import { useAuthStore } from '../../../store/authStore';
import type {
  DocumentCreate,
  DocumentDetail,
  DocumentParseResponse,
  DocumentUpdate,
} from '../../../types/document';
import type {
  DocumentFormBaseOption,
  DocumentFormSectionOption,
  DocumentFormTypeOption,
} from '../../../types/documentFormOptions';
import {
  generateDocumentCodePreview,
  generateFullDocumentCodePreview,
} from '../../../utils/documentCodes';
import {
  cancelButtonClassName,
  errorClassName,
  inputClassName,
  labelClassName,
  submitButtonClassName,
} from '../../master-data/forms/formStyles';
import { DocumentIdentityFields } from './DocumentIdentityFields';
import { DocumentInformationFields } from './DocumentInformationFields';
import {
  buildDocumentCreatePayload,
  buildDocumentUpdatePayload,
} from './documentFormPayload';
import { documentFormSchema, type DocumentFormValues } from './documentFormSchema';
import { InitialRevisionFields } from './InitialRevisionFields';

interface DocumentFormProps {
  mode: 'create' | 'edit';
  document?: DocumentDetail | null;
  isPending: boolean;
  onCancel: () => void;
  onSubmit: (payload: DocumentCreate | DocumentUpdate) => Promise<void>;
}

const toOption = (
  reference:
    | DocumentDetail['department']
    | DocumentDetail['section']
    | DocumentDetail['ownerDepartment'],
): DocumentFormBaseOption | null =>
  reference
    ? {
        id: reference.id,
        code: reference.code,
        name: reference.name,
      }
    : null;

const getDefaults = (
  document: DocumentDetail | null | undefined,
  defaultCompanyCode: string,
  departmentId: string | null,
): DocumentFormValues => ({
  companyCode: document?.companyCode ?? defaultCompanyCode,
  departmentId: document?.departmentId ?? departmentId ?? '',
  sectionId: document?.sectionId ?? '',
  documentTypeId: document?.documentTypeId ?? '',
  documentTypeRequiresSection: false,
  documentNumber: document?.documentNumber ?? '',
  title: document?.title ?? '',
  description: document?.description ?? '',
  ownerDepartmentId: document?.ownerDepartmentId ?? '',
  documentOwnerName: document?.documentOwnerName ?? '',
  createInitialRevision: document === null || document === undefined,
  revisionCode: 'Rev.000',
  documentStatusId: '',
  validationRuleId: '',
  issueDate: '',
  effectiveDate: '',
  reviewDate: '',
  expiryDate: '',
  sharepointUrl: '',
  externalReference: '',
  remarks: '',
  codeChanged: false,
  changeReason: '',
});

export function DocumentForm({
  document,
  isPending,
  mode,
  onCancel,
  onSubmit,
}: DocumentFormProps) {
  const user = useAuthStore((state) => state.user);
  const formOptionsQuery = useDocumentFormOptions();
  const defaultCompanyCode =
    formOptionsQuery.data?.defaultCompanyCode.trim().toUpperCase() ||
    appConfig.defaultCompanyCode;
  const departmentLocked = user?.role === 'DEPARTMENT_USER';
  const readOnly = Boolean(document?.isArchived);
  const {
    formState: { errors },
    handleSubmit,
    register,
    reset,
    setValue,
    watch,
  } = useForm<DocumentFormValues>({
    resolver: zodResolver(documentFormSchema),
    defaultValues: getDefaults(
      document,
      defaultCompanyCode,
      user?.departmentId ?? null,
    ),
  });

  const departmentId = watch('departmentId');
  const documentTypeId = watch('documentTypeId');
  const sectionId = watch('sectionId');
  const createInitialRevision = watch('createInitialRevision');
  const companyCode = watch('companyCode');
  const documentNumber = watch('documentNumber');
  const revisionCode = watch('revisionCode');
  const defaultedValidationRuleTypeId = useRef<string | null>(null);

  useEffect(() => {
    reset(getDefaults(document, defaultCompanyCode, user?.departmentId ?? null));
  }, [defaultCompanyCode, document, reset, user?.departmentId]);

  const currentDepartment = useMemo(
    () => toOption(document?.department ?? null),
    [document],
  );
  const currentSection = useMemo<DocumentFormSectionOption | null>(
    () =>
      document?.section
        ? {
            id: document.section.id,
            code: document.section.code,
            name: document.section.name,
            departmentId: document.departmentId,
          }
        : null,
    [document],
  );
  const currentOwnerDepartment = useMemo(
    () => toOption(document?.ownerDepartment ?? null),
    [document],
  );
  const departments = useMemo(() => {
    const options = [...(formOptionsQuery.data?.departments ?? [])];
    [currentDepartment, currentOwnerDepartment].forEach((current) => {
      if (current && !options.some((option) => option.id === current.id)) {
        options.push(current);
      }
    });
    return options;
  }, [currentDepartment, currentOwnerDepartment, formOptionsQuery.data?.departments]);
  const sections = useMemo(() => {
    const options = (formOptionsQuery.data?.sections ?? []).filter(
      (section) => section.departmentId === departmentId,
    );
    if (
      currentSection?.departmentId === departmentId &&
      !options.some((option) => option.id === currentSection.id)
    ) {
      options.push(currentSection);
    }
    return options;
  }, [currentSection, departmentId, formOptionsQuery.data?.sections]);
  const configuredCurrentDocumentType = formOptionsQuery.data?.documentTypes.find(
    (documentType) => documentType.id === document?.documentTypeId,
  );
  const currentDocumentType = useMemo<DocumentFormTypeOption | null>(
    () =>
      document?.documentType
        ? (configuredCurrentDocumentType ?? {
            id: document.documentType.id,
            code: document.documentType.code,
            name: document.documentType.name,
            requiresSection: document.sectionId !== null,
            defaultValidationRuleId: null,
          })
        : null,
    [configuredCurrentDocumentType, document],
  );
  const documentTypes = useMemo(() => {
    const options = [...(formOptionsQuery.data?.documentTypes ?? [])];
    if (
      currentDocumentType &&
      !options.some((option) => option.id === currentDocumentType.id)
    ) {
      options.push(currentDocumentType);
    }
    return options;
  }, [currentDocumentType, formOptionsQuery.data?.documentTypes]);
  const selectedDocumentType =
    documentTypes.find((type) => type.id === documentTypeId) ?? null;
  const requiresSection = selectedDocumentType?.requiresSection ?? false;

  useEffect(() => {
    setValue('documentTypeRequiresSection', requiresSection, {
      shouldValidate: true,
    });
    if (selectedDocumentType && !requiresSection) {
      setValue('sectionId', '', { shouldValidate: true });
    }
  }, [requiresSection, selectedDocumentType, setValue]);

  useEffect(() => {
    if (!createInitialRevision || mode !== 'create') {
      return;
    }
    const currentStatusId = watch('documentStatusId');
    if (!currentStatusId) {
      const initialStatus = formOptionsQuery.data?.documentStatuses.find(
        (status) => status.isInitial,
      );
      if (initialStatus) {
        setValue('documentStatusId', initialStatus.id, { shouldValidate: true });
      }
    }
  }, [
    createInitialRevision,
    formOptionsQuery.data?.documentStatuses,
    mode,
    setValue,
    watch,
  ]);

  useEffect(() => {
    if (!createInitialRevision || mode !== 'create') {
      return;
    }
    if (!selectedDocumentType) {
      defaultedValidationRuleTypeId.current = null;
      return;
    }
    if (defaultedValidationRuleTypeId.current === selectedDocumentType.id) {
      return;
    }
    const rules = formOptionsQuery.data?.validationRules ?? [];
    const defaultRule =
      rules.find((rule) => rule.id === selectedDocumentType.defaultValidationRuleId) ??
      rules.find(
        (rule) => rule.isDefault && rule.documentTypeId === selectedDocumentType.id,
      ) ??
      rules.find((rule) => rule.isDefault && rule.documentTypeId === null);
    setValue('validationRuleId', defaultRule?.id ?? '');
    defaultedValidationRuleTypeId.current = selectedDocumentType.id;
  }, [
    createInitialRevision,
    formOptionsQuery.data?.validationRules,
    mode,
    selectedDocumentType,
    setValue,
  ]);

  const availableValidationRules = useMemo(
    () =>
      (formOptionsQuery.data?.validationRules ?? []).filter(
        (rule) =>
          rule.documentTypeId === null || rule.documentTypeId === documentTypeId,
      ),
    [documentTypeId, formOptionsQuery.data?.validationRules],
  );

  const departmentCode =
    departments.find((department) => department.id === departmentId)?.code ?? '';
  const sectionCode = sections.find((section) => section.id === sectionId)?.code ?? '';
  const baseDocumentCode = generateDocumentCodePreview({
    companyCode,
    departmentCode,
    sectionCode: requiresSection ? sectionCode : null,
    documentTypeCode: selectedDocumentType?.code ?? '',
    documentNumber,
  });
  const fullDocumentCode =
    createInitialRevision && baseDocumentCode
      ? generateFullDocumentCodePreview(baseDocumentCode, revisionCode)
      : '';
  const codeChanged =
    mode === 'edit' &&
    Boolean(baseDocumentCode) &&
    baseDocumentCode !== document?.baseDocumentCode;

  useEffect(() => {
    setValue('codeChanged', codeChanged, { shouldValidate: true });
  }, [codeChanged, setValue]);

  const applyParsedCode = (parsed: DocumentParseResponse): void => {
    const parsedDepartmentAllowed =
      !departmentLocked || parsed.department.id === user?.departmentId;
    setValue('companyCode', parsed.companyCode, { shouldValidate: true });
    if (parsedDepartmentAllowed) {
      setValue('departmentId', parsed.department.id, { shouldValidate: true });
      setValue('sectionId', parsed.section?.id ?? '', { shouldValidate: true });
    }
    setValue('documentTypeId', parsed.documentType.id, { shouldValidate: true });
    setValue('documentNumber', parsed.documentNumber, { shouldValidate: true });
    if (parsed.revisionCode) {
      setValue('createInitialRevision', true);
      setValue('revisionCode', parsed.revisionCode, { shouldValidate: true });
    }
  };

  const submit = handleSubmit(async (values) => {
    if (readOnly) {
      return;
    }
    await onSubmit(
      mode === 'create'
        ? buildDocumentCreatePayload(values)
        : buildDocumentUpdatePayload(values),
    );
  });

  return (
    <form onSubmit={(event) => void submit(event)} className="space-y-5" noValidate>
      {mode === 'create' && <DocumentCodeParser onParsed={applyParsedCode} />}
      {document?.isArchived && (
        <div
          role="status"
          className="flex gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900"
        >
          <AlertTriangle className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
          This document is archived. Its metadata is read-only until it is restored.
        </div>
      )}
      {departmentLocked && !user?.departmentId && (
        <div
          role="alert"
          className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"
        >
          Your account has no assigned department. Contact an administrator before
          creating or editing documents.
        </div>
      )}
      {formOptionsQuery.error && (
        <div
          role="alert"
          className="flex flex-col gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800 sm:flex-row sm:items-center sm:justify-between"
        >
          <span>
            {getApiErrorMessage(
              formOptionsQuery.error,
              'Document form options could not be loaded.',
            )}
          </span>
          <button
            type="button"
            onClick={() => void formOptionsQuery.refetch()}
            className="min-h-9 rounded-xl border border-rose-300 px-3 text-xs font-semibold hover:bg-rose-100"
          >
            Retry
          </button>
        </div>
      )}
      <DocumentIdentityFields
        register={register}
        errors={errors}
        departments={departments}
        sections={sections}
        documentTypes={documentTypes}
        currentDepartment={currentDepartment}
        currentSection={
          currentSection?.departmentId === departmentId ? currentSection : null
        }
        currentDocumentType={currentDocumentType}
        isLoading={formOptionsQuery.isLoading}
        isLoadingSections={formOptionsQuery.isLoading}
        departmentLocked={departmentLocked}
        selectedDepartmentId={departmentId}
        onDepartmentChange={() =>
          setValue('sectionId', '', {
            shouldDirty: true,
            shouldValidate: true,
          })
        }
        readOnly={readOnly}
      />
      <GeneratedCodePreview
        baseDocumentCode={baseDocumentCode}
        {...(fullDocumentCode ? { fullDocumentCode } : {})}
      />
      {codeChanged && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
          <div className="flex gap-3 text-sm text-amber-900">
            <AlertTriangle className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
            <div>
              <p className="font-semibold">Document code will change</p>
              <p className="mt-1 text-xs leading-5 text-amber-800">
                Existing revision codes will be regenerated transactionally. Final or
                effective documents may require Document Controller authority.
              </p>
            </div>
          </div>
          <label className={`${labelClassName} mt-4`}>
            Change Reason
            <textarea
              {...register('changeReason')}
              className={`${inputClassName} min-h-24 py-3`}
              placeholder="Explain the controlled code change"
              maxLength={1_000}
            />
            {errors.changeReason && (
              <p className={errorClassName}>{errors.changeReason.message}</p>
            )}
          </label>
        </div>
      )}
      <DocumentInformationFields
        register={register}
        errors={errors}
        departments={departments}
        readOnly={readOnly}
      />
      {mode === 'create' && (
        <InitialRevisionFields
          register={register}
          errors={errors}
          statuses={formOptionsQuery.data?.documentStatuses ?? []}
          validationRules={availableValidationRules}
          enabled={createInitialRevision}
          readOnly={readOnly}
        />
      )}
      {!readOnly && (
        <div className="flex flex-col-reverse gap-3 border-t border-slate-200 pt-5 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onCancel}
            disabled={isPending}
            className={cancelButtonClassName}
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={
              isPending ||
              formOptionsQuery.isLoading ||
              formOptionsQuery.isError ||
              (departmentLocked && !user?.departmentId)
            }
            className={`${submitButtonClassName} inline-flex items-center justify-center gap-2`}
          >
            <Save className="size-4" aria-hidden="true" />
            {isPending
              ? 'Saving...'
              : mode === 'create'
                ? 'Create Document'
                : 'Save Changes'}
          </button>
        </div>
      )}
    </form>
  );
}
