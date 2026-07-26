import {
  ArrowLeft,
  ExternalLink,
  RefreshCw,
  ShieldCheck,
  UserRoundCheck,
} from 'lucide-react';
import { useState } from 'react';
import { Link, useParams } from 'react-router';

import { getApiErrorMessage } from '../../api/errors';
import { AcceptRiskDialog } from '../../components/compliance/AcceptRiskDialog';
import { AssignFindingDialog } from '../../components/compliance/AssignFindingDialog';
import { FalsePositiveDialog } from '../../components/compliance/FalsePositiveDialog';
import {
  FindingSeverityBadge,
  FindingStatusBadge,
} from '../../components/compliance/FindingBadges';
import {
  Phase8ErrorAlert,
  Phase8Loading,
} from '../../components/compliance/Phase8TableUtilities';
import { ReopenFindingDialog } from '../../components/compliance/ReopenFindingDialog';
import { ResolveFindingDialog } from '../../components/compliance/ResolveFindingDialog';
import { ReturnToOpenFindingDialog } from '../../components/compliance/ReturnToOpenFindingDialog';
import { ReviewFindingDialog } from '../../components/compliance/ReviewFindingDialog';
import { useComplianceRun } from '../../hooks/useCompliance';
import { useFindingActions } from '../../hooks/useFindingActions';
import { useFinding } from '../../hooks/useFindings';
import { useToast } from '../../providers/useToast';
import { useAuthStore } from '../../store/authStore';
import {
  findingActionTransitions,
  type FindingAcceptRiskRequest,
  type FindingAssignRequest,
  type FindingFalsePositiveRequest,
  type FindingReopenRequest,
  type FindingResolveRequest,
  type FindingReturnToOpenRequest,
  type FindingReviewRequest,
} from '../../types/finding';
import { formatDate, formatDateTime } from '../../utils/formatters';

type FindingAction =
  | 'review'
  | 'return-to-open'
  | 'resolve'
  | 'false-positive'
  | 'accept-risk'
  | 'reopen'
  | 'assign'
  | null;

export function FindingDetailPage() {
  const { findingId = '' } = useParams();
  const query = useFinding(findingId || null);
  const sourceRunQuery = useComplianceRun(query.data?.complianceRunId ?? null);
  const actions = useFindingActions();
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const [activeAction, setActiveAction] = useState<FindingAction>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const { showToast } = useToast();

  const runAction = async (
    label: string,
    operation: () => Promise<unknown>,
  ): Promise<void> => {
    setActionError(null);
    try {
      await operation();
      setActiveAction(null);
      showToast({ tone: 'success', title: label });
    } catch (error: unknown) {
      setActionError(
        getApiErrorMessage(error, 'The finding action could not be completed.'),
      );
    }
  };

  if (query.isLoading) {
    return <Phase8Loading label="Loading finding detail" />;
  }
  if (query.error || !query.data) {
    return (
      <Phase8ErrorAlert
        message={getApiErrorMessage(
          query.error,
          'The finding was not found or is outside your scope.',
        )}
        onRetry={() => void query.refetch()}
      />
    );
  }

  const finding = query.data;
  const availableActions = findingActionTransitions[finding.status];
  const canReview =
    availableActions.includes('review') && hasPermission('findings:review');
  const canReturnToOpen =
    availableActions.includes('return-to-open') && hasPermission('findings:review');
  const canResolve =
    availableActions.includes('resolve') && hasPermission('findings:resolve');
  const canFalsePositive =
    availableActions.includes('false-positive') &&
    hasPermission('findings:false_positive');
  const canAcceptRisk =
    availableActions.includes('accept-risk') && hasPermission('findings:resolve');
  const canReopen =
    availableActions.includes('reopen') && hasPermission('findings:reopen');
  const canAssign =
    availableActions.includes('assign') && hasPermission('findings:update');
  const sourceRunId = finding.complianceRunId
    ? (sourceRunQuery.data?.extractionRunId ?? null)
    : null;
  const sourcePath =
    finding.complianceRunId && !sourceRunId
      ? null
      : `/documents/${finding.documentId}/revisions/${finding.documentRevisionId}/extracted-content?${new URLSearchParams(
          {
            ...(sourceRunId ? { runId: sourceRunId } : {}),
            ...(finding.containerId ? { containerId: finding.containerId } : {}),
            ...(finding.extractedBlockId ? { blockId: finding.extractedBlockId } : {}),
            ...(finding.ocrBlockId ? { ocrBlockId: finding.ocrBlockId } : {}),
            ...(finding.pageNumber ? { page: String(finding.pageNumber) } : {}),
            ...(finding.worksheetName ? { worksheet: finding.worksheetName } : {}),
            ...(finding.cellCoordinate ? { cell: finding.cellCoordinate } : {}),
            ...(finding.sourceReference
              ? { sourceReference: finding.sourceReference }
              : {}),
          },
        ).toString()}`;

  return (
    <div className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
        <Link
          to="/compliance/findings"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-blue-700"
        >
          <ArrowLeft className="size-3.5" aria-hidden="true" />
          Findings
        </Link>
        <div className="mt-5 flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <div className="flex flex-wrap gap-2">
              <FindingSeverityBadge severity={finding.severity} />
              <FindingStatusBadge status={finding.status} />
              {!finding.isSystemGenerated && (
                <span className="rounded-full bg-violet-50 px-2.5 py-1 text-[10px] font-semibold text-violet-700">
                  Manual Finding
                </span>
              )}
              {finding.isRepeat && (
                <span className="rounded-full bg-amber-50 px-2.5 py-1 text-[10px] font-semibold text-amber-700">
                  Repeated Finding
                </span>
              )}
            </div>
            <p className="mt-4 font-mono text-xs font-semibold text-slate-500">
              {finding.findingCode}
            </p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
              {finding.title}
            </h1>
            <p className="mt-2 text-sm text-slate-500">
              {finding.document?.baseDocumentCode ?? finding.documentId}
              {finding.revision ? ` · ${finding.revision.revisionCode}` : ''}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {canReview && (
              <ActionButton
                label="Start Review"
                onClick={() => setActiveAction('review')}
              />
            )}
            {canResolve && (
              <ActionButton
                label="Resolve"
                onClick={() => setActiveAction('resolve')}
              />
            )}
            {canReturnToOpen && (
              <ActionButton
                label="Return to Open"
                onClick={() => setActiveAction('return-to-open')}
              />
            )}
            {canFalsePositive && (
              <ActionButton
                label="Mark False Positive"
                onClick={() => setActiveAction('false-positive')}
              />
            )}
            {canAcceptRisk && (
              <ActionButton
                label="Accept Risk"
                onClick={() => setActiveAction('accept-risk')}
              />
            )}
            {canReopen && (
              <ActionButton
                label="Reopen"
                icon={<RefreshCw className="size-3.5" />}
                onClick={() => setActiveAction('reopen')}
              />
            )}
            {canAssign && (
              <ActionButton
                label="Assign"
                icon={<UserRoundCheck className="size-3.5" />}
                onClick={() => setActiveAction('assign')}
              />
            )}
            {sourcePath ? (
              <Link
                to={sourcePath}
                className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-blue-700 px-3.5 text-sm font-semibold text-white"
              >
                <ExternalLink className="size-4" aria-hidden="true" />
                Open Source
              </Link>
            ) : (
              <span className="inline-flex min-h-10 items-center rounded-xl bg-slate-200 px-3.5 text-sm font-semibold text-slate-500">
                {sourceRunQuery.error ? 'Source unavailable' : 'Loading source…'}
              </span>
            )}
          </div>
        </div>
      </section>

      {sourceRunQuery.error && (
        <Phase8ErrorAlert
          message={getApiErrorMessage(
            sourceRunQuery.error,
            'The immutable extraction source for this compliance run could not be loaded.',
          )}
          onRetry={() => void sourceRunQuery.refetch()}
        />
      )}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(20rem,0.42fr)]">
        <div className="space-y-5">
          <DetailSection title="Finding">
            <DefinitionList
              items={[
                ['Description', finding.description],
                ['Recommendation', finding.recommendation ?? '—'],
                ['Expected', formatJsonValue(finding.expectedValue)],
                ['Actual', formatJsonValue(finding.actualValue)],
              ]}
            />
          </DetailSection>
          <DetailSection title="Source and provenance">
            <DefinitionList
              items={[
                ['Validation Run', finding.complianceRunId ?? 'Manual finding'],
                ['Validation Rule', finding.validationRule?.name ?? '—'],
                ['Language', finding.languageCode?.toUpperCase() ?? '—'],
                ['Section', finding.sectionCode ?? '—'],
                ['Source Reference', finding.sourceReference ?? '—'],
                ['Page', finding.pageNumber?.toString() ?? '—'],
                ['Worksheet', finding.worksheetName ?? '—'],
                ['Cell', finding.cellCoordinate ?? '—'],
                ['Container', finding.containerId ?? '—'],
                ['Extracted Block', finding.extractedBlockId ?? '—'],
                ['OCR Block', finding.ocrBlockId ?? '—'],
              ]}
            />
          </DetailSection>
          <DetailSection title="Finding history">
            <ol className="space-y-4">
              {finding.history.map((entry) => (
                <li key={entry.id} className="flex gap-4">
                  <span className="mt-1.5 size-2 shrink-0 rounded-full bg-blue-600" />
                  <div>
                    <p className="text-sm font-semibold text-slate-900">
                      {entry.action.replaceAll('_', ' ')}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      {entry.actor?.name ?? 'System'} ·{' '}
                      {formatDateTime(entry.createdAt)}
                    </p>
                    {(entry.comment || entry.reason) && (
                      <p className="mt-2 whitespace-pre-wrap text-xs leading-5 text-slate-700">
                        {entry.comment ?? entry.reason}
                      </p>
                    )}
                  </div>
                </li>
              ))}
              {finding.history.length === 0 && (
                <li className="text-sm text-slate-500">
                  No status changes have been recorded.
                </li>
              )}
            </ol>
          </DetailSection>
        </div>
        <aside className="space-y-5">
          <DetailSection title="Workflow">
            <DefinitionList
              items={[
                ['Assigned To', finding.assignedTo?.name ?? 'Unassigned'],
                [
                  'Reviewed',
                  finding.reviewedAt
                    ? `${finding.reviewedBy?.name ?? 'Unknown'} · ${formatDateTime(finding.reviewedAt)}`
                    : '—',
                ],
                ['Review Comment', finding.reviewComment ?? '—'],
                [
                  'Resolved',
                  finding.resolvedAt
                    ? `${finding.resolvedBy?.name ?? 'Unknown'} · ${formatDateTime(finding.resolvedAt)}`
                    : '—',
                ],
                ['Resolution', finding.resolutionComment ?? '—'],
                ['False-positive Reason', finding.falsePositiveReason ?? '—'],
                ['Reopen Reason', finding.reopenReason ?? '—'],
              ]}
            />
          </DetailSection>
          {finding.acceptedRiskReason && (
            <DetailSection title="Accepted risk">
              <DefinitionList
                items={[
                  ['Reason', finding.acceptedRiskReason],
                  ['Expiry', formatDate(finding.acceptedRiskExpiryDate)],
                  [
                    'Accepted At',
                    finding.acceptedRiskAt
                      ? formatDateTime(finding.acceptedRiskAt)
                      : '—',
                  ],
                ]}
              />
            </DetailSection>
          )}
          {finding.previousFindingId && (
            <Link
              to={`/compliance/findings/${finding.previousFindingId}`}
              className="flex items-center gap-2 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-xs font-semibold text-amber-800"
            >
              <ShieldCheck className="size-4" aria-hidden="true" />
              Open previous repeated finding
            </Link>
          )}
          {!canReview &&
            !canReturnToOpen &&
            !canResolve &&
            !canFalsePositive &&
            !canAcceptRisk &&
            !canReopen && (
              <p className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-xs leading-5 text-slate-600">
                No status transition is available for your permissions and this
                finding’s current status.
              </p>
            )}
        </aside>
      </div>

      <ReviewFindingDialog
        isOpen={activeAction === 'review'}
        isPending={actions.review.isPending}
        errorMessage={actionError}
        onClose={() => setActiveAction(null)}
        onSubmit={(payload: FindingReviewRequest) =>
          void runAction('Finding moved to review', () =>
            actions.review.mutateAsync({ findingId: finding.id, payload }),
          )
        }
      />
      <ResolveFindingDialog
        isOpen={activeAction === 'resolve'}
        isPending={actions.resolve.isPending}
        errorMessage={actionError}
        onClose={() => setActiveAction(null)}
        onSubmit={(payload: FindingResolveRequest) =>
          void runAction('Finding resolved', () =>
            actions.resolve.mutateAsync({ findingId: finding.id, payload }),
          )
        }
      />
      <ReturnToOpenFindingDialog
        isOpen={activeAction === 'return-to-open'}
        isPending={actions.returnToOpen.isPending}
        errorMessage={actionError}
        onClose={() => setActiveAction(null)}
        onSubmit={(payload: FindingReturnToOpenRequest) =>
          void runAction('Finding returned to open', () =>
            actions.returnToOpen.mutateAsync({ findingId: finding.id, payload }),
          )
        }
      />
      <FalsePositiveDialog
        isOpen={activeAction === 'false-positive'}
        isPending={actions.falsePositive.isPending}
        errorMessage={actionError}
        onClose={() => setActiveAction(null)}
        onSubmit={(payload: FindingFalsePositiveRequest) =>
          void runAction('Finding marked as false positive', () =>
            actions.falsePositive.mutateAsync({ findingId: finding.id, payload }),
          )
        }
      />
      <AcceptRiskDialog
        isOpen={activeAction === 'accept-risk'}
        isPending={actions.acceptRisk.isPending}
        errorMessage={actionError}
        onClose={() => setActiveAction(null)}
        onSubmit={(payload: FindingAcceptRiskRequest) =>
          void runAction('Finding risk accepted', () =>
            actions.acceptRisk.mutateAsync({ findingId: finding.id, payload }),
          )
        }
      />
      <ReopenFindingDialog
        isOpen={activeAction === 'reopen'}
        isPending={actions.reopen.isPending}
        errorMessage={actionError}
        onClose={() => setActiveAction(null)}
        onSubmit={(payload: FindingReopenRequest) =>
          void runAction('Finding reopened', () =>
            actions.reopen.mutateAsync({ findingId: finding.id, payload }),
          )
        }
      />
      <AssignFindingDialog
        isOpen={activeAction === 'assign'}
        isPending={actions.assign.isPending}
        errorMessage={actionError}
        onClose={() => setActiveAction(null)}
        onSubmit={(payload: FindingAssignRequest) =>
          void runAction('Finding assigned', () =>
            actions.assign.mutateAsync({ findingId: finding.id, payload }),
          )
        }
      />
    </div>
  );
}

function ActionButton({
  icon,
  label,
  onClick,
}: {
  label: string;
  icon?: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 px-3.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
    >
      {icon}
      {label}
    </button>
  );
}

function DetailSection({
  children,
  title,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-950">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function DefinitionList({ items }: { items: readonly (readonly [string, string])[] }) {
  return (
    <dl className="grid gap-4 sm:grid-cols-2">
      {items.map(([label, value]) => (
        <div key={label}>
          <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
            {label}
          </dt>
          <dd className="mt-1 whitespace-pre-wrap break-words text-sm leading-6 text-slate-700">
            {value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

const formatJsonValue = (value: unknown): string => {
  if (value === null || value === undefined) {
    return '—';
  }
  if (typeof value === 'string') {
    return value;
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return 'Unavailable';
  }
};
