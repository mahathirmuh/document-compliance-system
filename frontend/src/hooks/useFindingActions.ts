import { useMutation, useQueryClient } from '@tanstack/react-query';

import {
  acceptFindingRisk,
  assignFinding,
  bulkActionFindings,
  createManualFinding,
  markFalsePositive,
  reopenFinding,
  resolveFinding,
  returnFindingToOpen,
  reviewFinding,
  updateFinding,
} from '../api/findingApi';
import type {
  FindingAcceptRiskRequest,
  FindingAssignRequest,
  FindingBulkActionRequest,
  FindingFalsePositiveRequest,
  FindingReopenRequest,
  FindingResolveRequest,
  FindingReturnToOpenRequest,
  FindingReviewRequest,
  FindingUpdateRequest,
  ManualFindingRequest,
} from '../types/finding';
import { complianceKeys } from './complianceQueryKeys';
import { findingKeys } from './findingQueryKeys';
import { useDocumentSession } from './useDocumentSession';

interface FindingActionVariables<TPayload> {
  findingId: string;
  payload: TPayload;
}

export const useFindingActions = () => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();
  const invalidate = async (): Promise<void> => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: findingKeys.all(scope) }),
      queryClient.invalidateQueries({ queryKey: complianceKeys.all(scope) }),
    ]);
  };

  return {
    createManual: useMutation({
      mutationFn: (payload: ManualFindingRequest) => createManualFinding(payload),
      onSuccess: invalidate,
    }),
    update: useMutation({
      mutationFn: ({
        findingId,
        payload,
      }: FindingActionVariables<FindingUpdateRequest>) =>
        updateFinding(findingId, payload),
      onSuccess: invalidate,
    }),
    review: useMutation({
      mutationFn: ({
        findingId,
        payload,
      }: FindingActionVariables<FindingReviewRequest>) =>
        reviewFinding(findingId, payload),
      onSuccess: invalidate,
    }),
    resolve: useMutation({
      mutationFn: ({
        findingId,
        payload,
      }: FindingActionVariables<FindingResolveRequest>) =>
        resolveFinding(findingId, payload),
      onSuccess: invalidate,
    }),
    returnToOpen: useMutation({
      mutationFn: ({
        findingId,
        payload,
      }: FindingActionVariables<FindingReturnToOpenRequest>) =>
        returnFindingToOpen(findingId, payload),
      onSuccess: invalidate,
    }),
    reopen: useMutation({
      mutationFn: ({
        findingId,
        payload,
      }: FindingActionVariables<FindingReopenRequest>) =>
        reopenFinding(findingId, payload),
      onSuccess: invalidate,
    }),
    falsePositive: useMutation({
      mutationFn: ({
        findingId,
        payload,
      }: FindingActionVariables<FindingFalsePositiveRequest>) =>
        markFalsePositive(findingId, payload),
      onSuccess: invalidate,
    }),
    acceptRisk: useMutation({
      mutationFn: ({
        findingId,
        payload,
      }: FindingActionVariables<FindingAcceptRiskRequest>) =>
        acceptFindingRisk(findingId, payload),
      onSuccess: invalidate,
    }),
    assign: useMutation({
      mutationFn: ({
        findingId,
        payload,
      }: FindingActionVariables<FindingAssignRequest>) =>
        assignFinding(findingId, payload),
      onSuccess: invalidate,
    }),
    bulkAction: useMutation({
      mutationFn: (payload: FindingBulkActionRequest) => bulkActionFindings(payload),
      onSuccess: invalidate,
    }),
  } as const;
};
