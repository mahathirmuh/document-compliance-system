import {
  Archive,
  ArrowLeft,
  Building2,
  CalendarDays,
  FilePenLine,
  FileType2,
  GitBranch,
  Pencil,
  RotateCcw,
  ShieldCheck,
  Tag,
} from 'lucide-react';
import { Link, useParams, useSearchParams } from 'react-router';
import { useState } from 'react';

import { getApiErrorMessage } from '../../api/errors';
import { ArchiveDocumentDialog } from '../../components/documents/ArchiveDocumentDialog';
import { ArchivedBadge } from '../../components/documents/ArchivedBadge';
import { DocumentCodeField } from '../../components/documents/DocumentCodeField';
import { DocumentExportButton } from '../../components/documents/DocumentExportButton';
import { DocumentFilesSection } from '../../components/documents/DocumentFilesSection';
import { DocumentIntelligenceSection } from '../../components/documents/DocumentIntelligenceSection';
import { DocumentRevisionManager } from '../../components/documents/DocumentRevisionManager';
import { DocumentStatusBadge } from '../../components/documents/DocumentStatusBadge';
import { DocumentSummaryCard } from '../../components/documents/DocumentSummaryCard';
import { RevisionBadge } from '../../components/documents/RevisionBadge';
import { SharePointLink } from '../../components/documents/SharePointLink';
import { ConfirmationDialog } from '../../components/master-data/ConfirmationDialog';
import { useDocument } from '../../hooks/useDocument';
import { useRevisionFiles } from '../../hooks/useDocumentFiles';
import { useDocumentMutations } from '../../hooks/useDocumentMutations';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import type { DocumentDetail } from '../../types/document';
import { formatDate, formatDateTime } from '../../utils/formatters';

type DetailTab = 'overview' | 'revisions' | 'files' | 'intelligence' | 'history';

export function DocumentDetailPage() {
  const { documentId = '' } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [restoreOpen, setRestoreOpen] = useState(false);
  const query = useDocument(documentId || null);
  const mutations = useDocumentMutations();
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canUpdate = hasPermission('documents:update');
  const canArchive = hasPermission('documents:archive');
  const canRestore = hasPermission('documents:restore');
  const canExport = hasPermission('documents:export');
  const canManageRevisions = hasPermission('documents:manage_revisions');
  const canUseIntelligence =
    hasPermission('documents:ocr') ||
    hasPermission('documents:view_ocr_results') ||
    hasPermission('documents:view_ocr_history') ||
    hasPermission('documents:detect_language') ||
    hasPermission('documents:view_language_results');
  const { showToast } = useToast();
  const requestedTab = searchParams.get('tab');
  const tab: DetailTab =
    requestedTab === 'revisions' ||
    requestedTab === 'files' ||
    (requestedTab === 'intelligence' && canUseIntelligence) ||
    requestedTab === 'history'
      ? requestedTab
      : 'overview';

  const archive = async (reason: string): Promise<void> => {
    try {
      await mutations.archive.mutateAsync({
        documentId,
        payload: { reason },
      });
      showToast({ tone: 'success', title: 'Document archived' });
      setArchiveOpen(false);
      await query.refetch();
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Document could not be archived',
        message: getApiErrorMessage(error, 'Review its current state and try again.'),
      });
    }
  };

  const restore = async (): Promise<void> => {
    try {
      await mutations.restore.mutateAsync(documentId);
      showToast({ tone: 'success', title: 'Document restored' });
      setRestoreOpen(false);
      await query.refetch();
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Document could not be restored',
        message: getApiErrorMessage(error, 'Check for a conflicting document code.'),
      });
    }
  };

  if (query.isLoading) {
    return (
      <div className="space-y-5" aria-label="Loading document details">
        <div className="h-44 animate-pulse rounded-3xl bg-slate-100" />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }, (_, index) => (
            <div key={index} className="h-24 animate-pulse rounded-2xl bg-slate-100" />
          ))}
        </div>
        <div className="h-80 animate-pulse rounded-3xl bg-slate-100" />
      </div>
    );
  }
  if (query.error || !query.data) {
    return (
      <div className="rounded-3xl border border-rose-200 bg-white p-8 text-center shadow-sm">
        <h1 className="text-lg font-semibold text-slate-950">
          Document could not be opened
        </h1>
        <p className="mt-2 text-sm text-rose-700">
          {getApiErrorMessage(
            query.error,
            'It was not found or is outside your scope.',
          )}
        </p>
        <Link
          to="/documents"
          className="mt-5 inline-flex min-h-10 items-center gap-2 rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white"
        >
          <ArrowLeft className="size-4" aria-hidden="true" />
          Document Register
        </Link>
      </div>
    );
  }

  const document = query.data;
  const current = document.currentRevision;

  return (
    <div className="space-y-5">
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0">
            <Link
              to={document.isArchived ? '/documents/archived' : '/documents'}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-blue-700 hover:text-blue-900"
            >
              <ArrowLeft className="size-3.5" aria-hidden="true" />
              {document.isArchived ? 'Archived Documents' : 'Document Register'}
            </Link>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <DocumentCodeField
                code={document.baseDocumentCode}
                className="max-w-full text-base"
              />
              <RevisionBadge
                revisionCode={current?.revisionCode ?? null}
                isCurrent={Boolean(current)}
              />
              <DocumentStatusBadge
                code={current?.status.code ?? null}
                name={current?.status.name ?? null}
              />
              {document.isArchived && <ArchivedBadge />}
            </div>
            <h1 className="mt-3 text-2xl font-semibold tracking-tight text-slate-950 sm:text-3xl">
              {document.title}
            </h1>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            {canExport && (
              <DocumentExportButton
                params={{ baseDocumentCode: document.baseDocumentCode }}
                label="Export Record"
              />
            )}
            {current?.sharepointUrl && (
              <a
                href={current.sharepointUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex min-h-10 items-center rounded-xl border border-blue-200 bg-blue-50 px-3.5 text-sm font-semibold text-blue-700 hover:bg-blue-100"
              >
                Open SharePoint
              </a>
            )}
            {!document.isArchived && canUpdate && (
              <Link
                to={`/documents/${document.id}/edit`}
                className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 px-3.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                <Pencil className="size-4" aria-hidden="true" />
                Edit
              </Link>
            )}
            {!document.isArchived && canManageRevisions && (
              <Link
                to={`/documents/${document.id}/revisions`}
                className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-blue-700 px-3.5 text-sm font-semibold text-white hover:bg-blue-800"
              >
                <GitBranch className="size-4" aria-hidden="true" />
                Manage Revisions
              </Link>
            )}
            {!document.isArchived && canArchive && (
              <button
                type="button"
                onClick={() => setArchiveOpen(true)}
                className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-amber-600 px-3.5 text-sm font-semibold text-white hover:bg-amber-700"
              >
                <Archive className="size-4" aria-hidden="true" />
                Archive
              </button>
            )}
            {document.isArchived && canRestore && (
              <button
                type="button"
                onClick={() => setRestoreOpen(true)}
                className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-emerald-600 px-3.5 text-sm font-semibold text-white hover:bg-emerald-700"
              >
                <RotateCcw className="size-4" aria-hidden="true" />
                Restore
              </button>
            )}
          </div>
        </div>
      </section>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <DocumentSummaryCard
          icon={Building2}
          label="Department"
          value={`${document.department.code} — ${document.department.name}`}
        />
        <DocumentSummaryCard
          icon={Tag}
          label="Section"
          value={document.section?.name ?? 'Not required'}
        />
        <DocumentSummaryCard
          icon={FileType2}
          label="Document Type"
          value={`${document.documentType.code} — ${document.documentType.name}`}
        />
        <DocumentSummaryCard
          icon={GitBranch}
          label="Current Revision"
          value={current?.revisionCode ?? 'No Revision'}
        />
        <DocumentSummaryCard
          icon={ShieldCheck}
          label="Status"
          value={current?.status.name ?? 'No status'}
        />
        <DocumentSummaryCard
          icon={CalendarDays}
          label="Effective Date"
          value={formatDate(current?.effectiveDate)}
        />
        <DocumentSummaryCard
          icon={ShieldCheck}
          label="Validation Rule"
          value={current?.validationRule?.name ?? 'Not assigned'}
        />
      </div>

      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div className="flex overflow-x-auto border-b border-slate-200 px-4 sm:px-6">
          {(
            [
              'overview',
              'revisions',
              'files',
              ...(canUseIntelligence ? (['intelligence'] as const) : []),
              'history',
            ] as const
          ).map((candidate) => (
            <button
              key={candidate}
              type="button"
              onClick={() =>
                setSearchParams(candidate === 'overview' ? {} : { tab: candidate }, {
                  replace: true,
                })
              }
              className={`min-h-13 whitespace-nowrap border-b-2 px-4 text-sm font-semibold capitalize ${
                tab === candidate
                  ? 'border-blue-700 text-blue-700'
                  : 'border-transparent text-slate-500 hover:text-slate-900'
              }`}
            >
              {candidate}
            </button>
          ))}
        </div>
        <div className="p-5 sm:p-7">
          {tab === 'overview' && <DocumentOverview document={document} />}
          {tab === 'revisions' && (
            <DocumentRevisionManager document={document} compact />
          )}
          {tab === 'files' && <DocumentFilesSection document={document} />}
          {tab === 'intelligence' && (
            <CurrentDocumentIntelligence document={document} />
          )}
          {tab === 'history' && <DocumentActivitySummary document={document} />}
        </div>
      </section>

      <ArchiveDocumentDialog
        isOpen={archiveOpen}
        isPending={mutations.archive.isPending}
        onClose={() => setArchiveOpen(false)}
        onConfirm={archive}
      />
      <ConfirmationDialog
        isOpen={restoreOpen}
        title="Restore document?"
        message="The backend will recheck code uniqueness before making this record active."
        confirmLabel="Restore"
        tone="primary"
        isPending={mutations.restore.isPending}
        onCancel={() => setRestoreOpen(false)}
        onConfirm={() => void restore()}
      />
    </div>
  );
}

function CurrentDocumentIntelligence({ document }: { document: DocumentDetail }) {
  const revisionId = document.currentRevision?.id ?? null;
  const filesQuery = useRevisionFiles(document.id, revisionId);
  const files = (filesQuery.data ?? []).filter(
    (file) => file.isCurrent && file.fileStatus === 'AVAILABLE',
  );

  if (!revisionId) {
    return (
      <p className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-600">
        Create a revision and upload its physical file before running content
        intelligence.
      </p>
    );
  }
  if (filesQuery.isLoading) {
    return (
      <div
        aria-label="Loading content intelligence"
        className="h-56 animate-pulse rounded-2xl bg-slate-100"
      />
    );
  }
  if (filesQuery.error) {
    return (
      <p role="alert" className="text-sm text-rose-700">
        {getApiErrorMessage(
          filesQuery.error,
          'The current physical file could not be loaded.',
        )}
      </p>
    );
  }
  if (files.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-600">
        Upload a current physical file before running OCR or language detection.
      </p>
    );
  }
  return (
    <DocumentIntelligenceSection files={files} documentArchived={document.isArchived} />
  );
}

function DocumentOverview({ document }: { document: DocumentDetail }) {
  const current = document.currentRevision;
  const fields = [
    ['Company Code', document.companyCode],
    ['Document Number', document.documentNumber],
    ['Owner Department', document.ownerDepartment?.name ?? document.department.name],
    ['Document Owner', document.documentOwnerName ?? '—'],
    ['Issue Date', formatDate(current?.issueDate)],
    ['Effective Date', formatDate(current?.effectiveDate)],
    ['Review Date', formatDate(current?.reviewDate)],
    ['Expiry Date', formatDate(current?.expiryDate)],
    ['External Reference', current?.externalReference ?? '—'],
  ] as const;

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(18rem,0.55fr)]">
      <div>
        <h2 className="text-sm font-semibold text-slate-950">Document Metadata</h2>
        <dl className="mt-4 grid gap-4 sm:grid-cols-2">
          {fields.map(([label, value]) => (
            <div key={label}>
              <dt className="text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-500">
                {label}
              </dt>
              <dd className="mt-1 text-sm text-slate-800">{value}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-6 border-t border-slate-200 pt-5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-500">
            Description
          </p>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">
            {document.description ?? 'No description provided.'}
          </p>
        </div>
      </div>
      <div className="space-y-5 rounded-2xl bg-slate-50 p-5">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-500">
            SharePoint
          </p>
          <div className="mt-2">
            <SharePointLink url={current?.sharepointUrl ?? null} />
          </div>
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-500">
            Current Revision Remarks
          </p>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">
            {current?.remarks ?? 'No remarks.'}
          </p>
        </div>
        {document.isArchived && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-3">
            <p className="text-xs font-semibold text-amber-900">Archive information</p>
            <p className="mt-1 text-xs leading-5 text-amber-800">
              {document.archiveReason ?? 'No reason provided.'}
            </p>
            <p className="mt-2 text-[10px] text-amber-700">
              {document.archivedAt ? formatDateTime(document.archivedAt) : '—'} ·{' '}
              {document.archivedBy?.name ?? 'Unknown user'}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function DocumentActivitySummary({ document }: { document: DocumentDetail }) {
  const events = [
    {
      label: 'Document created',
      detail: document.createdBy?.name ?? 'Unknown user',
      timestamp: document.createdAt,
    },
    {
      label: 'Metadata last updated',
      detail: document.updatedBy?.name ?? 'Unknown user',
      timestamp: document.updatedAt,
    },
    ...(document.archivedAt
      ? [
          {
            label: 'Document archived',
            detail: document.archivedBy?.name ?? 'Unknown user',
            timestamp: document.archivedAt,
          },
        ]
      : []),
  ];

  return (
    <div>
      <div className="flex items-start gap-3 rounded-xl border border-blue-200 bg-blue-50 p-4 text-xs leading-5 text-blue-800">
        <FilePenLine className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        This summary uses document audit fields returned by the backend. Full audit-log
        access remains permission-controlled.
      </div>
      <ol className="mt-5 space-y-4">
        {events.map((event) => (
          <li key={`${event.label}-${event.timestamp}`} className="flex gap-4">
            <span className="mt-1.5 size-2 shrink-0 rounded-full bg-blue-600" />
            <div>
              <p className="text-sm font-semibold text-slate-900">{event.label}</p>
              <p className="mt-1 text-xs text-slate-500">
                {event.detail} · {formatDateTime(event.timestamp)}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
