import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  compareComplianceRuns,
  exportCompliance,
  exportComplianceReport,
  getComplianceOverview,
  getComplianceReport,
  getComplianceRun,
  getComplianceSummary,
  getDocumentCompliance,
  getScoreBreakdown,
  listDetectedSections,
  listTranslationGroups,
  revalidateCompliance,
  startComplianceValidation,
} from '../api/complianceApi';
import type {
  ComplianceExportFormat,
  ComplianceOverviewParams,
  ComplianceReportParams,
  ComplianceResultListParams,
  ComplianceRevalidateRequest,
  ComplianceStartRequest,
  TranslationGroupListParams,
} from '../types/compliance';
import { documentFileKeys } from './documentFileQueryKeys';
import { documentKeys } from './documentQueryKeys';
import { complianceKeys } from './complianceQueryKeys';
import { findingKeys } from './findingQueryKeys';
import { useDocumentSession } from './useDocumentSession';

export const useComplianceRun = (runId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: complianceKeys.run(scope, runId ?? 'none'),
    queryFn: ({ signal }) => getComplianceRun(runId ?? '', signal),
    enabled: runId !== null,
  });
};

export const useComplianceSummary = (runId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: complianceKeys.summary(scope, runId ?? 'none'),
    queryFn: ({ signal }) => getComplianceSummary(runId ?? '', signal),
    enabled: runId !== null,
  });
};

export const useComplianceScoreBreakdown = (runId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: complianceKeys.score(scope, runId ?? 'none'),
    queryFn: ({ signal }) => getScoreBreakdown(runId ?? '', signal),
    enabled: runId !== null,
  });
};

export const useDetectedSections = (
  runId: string | null,
  params: ComplianceResultListParams,
  options: { enabled?: boolean } = {},
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: complianceKeys.sections(scope, runId ?? 'none', params),
    queryFn: ({ signal }) => listDetectedSections(runId ?? '', params, signal),
    placeholderData: (previous) => previous,
    enabled: runId !== null && (options.enabled ?? true),
  });
};

export const useTranslationGroups = (
  runId: string | null,
  params: TranslationGroupListParams,
  options: { enabled?: boolean } = {},
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: complianceKeys.groups(scope, runId ?? 'none', params),
    queryFn: ({ signal }) => listTranslationGroups(runId ?? '', params, signal),
    placeholderData: (previous) => previous,
    enabled: runId !== null && (options.enabled ?? true),
  });
};

export const useLatestCompliance = (fileId: string | null, enabled = true) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: complianceKeys.latest(scope, fileId ?? 'none'),
    queryFn: ({ signal }) => getDocumentCompliance(fileId ?? '', signal),
    enabled: enabled && fileId !== null,
  });
};

export const useComplianceComparison = (
  runId: string | null,
  otherRunId: string | null,
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: complianceKeys.comparison(scope, runId ?? 'none', otherRunId ?? 'none'),
    queryFn: ({ signal }) =>
      compareComplianceRuns(runId ?? '', otherRunId ?? '', signal),
    enabled: runId !== null && otherRunId !== null,
  });
};

export const useComplianceOverview = (params: ComplianceOverviewParams) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: complianceKeys.overview(scope, params),
    queryFn: ({ signal }) => getComplianceOverview(params, signal),
    placeholderData: (previous) => previous,
  });
};

export const useComplianceReport = (params: ComplianceReportParams) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: complianceKeys.report(scope, params),
    queryFn: ({ signal }) => getComplianceReport(params, signal),
    placeholderData: (previous) => previous,
  });
};

export const useComplianceMutations = () => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();
  const invalidate = async (): Promise<void> => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: complianceKeys.all(scope) }),
      queryClient.invalidateQueries({ queryKey: findingKeys.all(scope) }),
      queryClient.invalidateQueries({ queryKey: documentFileKeys.all(scope) }),
      queryClient.invalidateQueries({ queryKey: documentKeys.all(scope) }),
    ]);
  };

  return {
    start: useMutation({
      mutationFn: (payload: ComplianceStartRequest) =>
        startComplianceValidation(payload),
      onSuccess: invalidate,
    }),
    revalidate: useMutation({
      mutationFn: ({
        payload,
        runId,
      }: {
        runId: string;
        payload: ComplianceRevalidateRequest;
      }) => revalidateCompliance(runId, payload),
      onSuccess: invalidate,
    }),
    export: useMutation({
      mutationFn: ({
        format,
        runId,
      }: {
        runId: string;
        format: ComplianceExportFormat;
      }) => exportCompliance(runId, format),
    }),
    exportReport: useMutation({
      mutationFn: ({
        format,
        params,
      }: {
        format: ComplianceExportFormat;
        params: Omit<ComplianceReportParams, 'page' | 'pageSize'>;
      }) => exportComplianceReport(format, params),
    }),
  } as const;
};
