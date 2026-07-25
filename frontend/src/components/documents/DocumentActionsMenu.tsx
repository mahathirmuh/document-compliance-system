import {
  Archive,
  Copy,
  ExternalLink,
  Eye,
  GitBranch,
  Pencil,
  RotateCcw,
} from 'lucide-react';
import { Link } from 'react-router';

import { useToast } from '../../providers/useToast';
import type { DocumentListItem } from '../../types/document';

interface DocumentActionsMenuProps {
  document: DocumentListItem;
  canUpdate: boolean;
  canArchive: boolean;
  canRestore: boolean;
  canManageRevisions: boolean;
  onArchive: (document: DocumentListItem) => void;
  onRestore: (document: DocumentListItem) => void;
}

const actionClassName =
  'inline-flex min-h-8 items-center gap-1.5 rounded-lg px-2 text-[11px] font-semibold text-slate-600 transition hover:bg-slate-100 hover:text-slate-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600';

export function DocumentActionsMenu({
  canArchive,
  canManageRevisions,
  canRestore,
  canUpdate,
  document,
  onArchive,
  onRestore,
}: DocumentActionsMenuProps) {
  const { showToast } = useToast();
  const copyCode = async (): Promise<void> => {
    try {
      await navigator.clipboard.writeText(document.baseDocumentCode);
      showToast({ tone: 'success', title: 'Document code copied' });
    } catch {
      showToast({ tone: 'error', title: 'Document code could not be copied' });
    }
  };

  return (
    <div className="flex min-w-max flex-wrap items-center gap-0.5">
      <Link
        to={`/documents/${document.id}`}
        className={actionClassName}
        aria-label={`View ${document.baseDocumentCode}`}
      >
        <Eye className="size-3.5" aria-hidden="true" />
        View
      </Link>
      {canUpdate && !document.isArchived && (
        <Link
          to={`/documents/${document.id}/edit`}
          className={actionClassName}
          aria-label={`Edit ${document.baseDocumentCode}`}
        >
          <Pencil className="size-3.5" aria-hidden="true" />
          Edit
        </Link>
      )}
      {canManageRevisions && !document.isArchived && (
        <Link
          to={`/documents/${document.id}/revisions`}
          className={actionClassName}
          aria-label={`Manage revisions for ${document.baseDocumentCode}`}
        >
          <GitBranch className="size-3.5" aria-hidden="true" />
          Revisions
        </Link>
      )}
      <button type="button" onClick={() => void copyCode()} className={actionClassName}>
        <Copy className="size-3.5" aria-hidden="true" />
        Copy
      </button>
      {document.currentRevision?.sharepointUrl && (
        <a
          href={document.currentRevision.sharepointUrl}
          target="_blank"
          rel="noopener noreferrer"
          className={actionClassName}
        >
          <ExternalLink className="size-3.5" aria-hidden="true" />
          SharePoint
        </a>
      )}
      {!document.isArchived && canArchive && (
        <button
          type="button"
          onClick={() => onArchive(document)}
          className={`${actionClassName} text-amber-700 hover:bg-amber-50 hover:text-amber-900`}
        >
          <Archive className="size-3.5" aria-hidden="true" />
          Archive
        </button>
      )}
      {document.isArchived && canRestore && (
        <button
          type="button"
          onClick={() => onRestore(document)}
          className={`${actionClassName} text-emerald-700 hover:bg-emerald-50 hover:text-emerald-900`}
        >
          <RotateCcw className="size-3.5" aria-hidden="true" />
          Restore
        </button>
      )}
    </div>
  );
}
