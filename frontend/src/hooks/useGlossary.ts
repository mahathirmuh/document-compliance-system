import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  addGlossaryTranslation,
  addGlossaryVariant,
  archiveGlossaryProfile,
  archiveGlossaryTerm,
  confirmGlossaryImport,
  createGlossaryException,
  createGlossaryProfile,
  createGlossaryTerm,
  deactivateGlossaryException,
  downloadGlossaryTemplate,
  exportGlossary,
  getGlossaryProfile,
  getGlossaryTerm,
  listGlossaryExceptions,
  listGlossaryProfiles,
  listGlossaryTerms,
  previewGlossaryImport,
  restoreGlossaryProfile,
  restoreGlossaryTerm,
  testGlossaryMatch,
  updateGlossaryException,
  updateGlossaryProfile,
  updateGlossaryTerm,
  updateGlossaryTranslation,
  updateGlossaryVariant,
} from '../api/glossaryApi';
import type {
  GlossaryExceptionCreate,
  GlossaryExceptionUpdate,
  GlossaryExportFormat,
  GlossaryExportParams,
  GlossaryImportConfirmRequest,
  GlossaryListParams,
  GlossaryProfileCreate,
  GlossaryProfileUpdate,
  GlossaryTermCreate,
  GlossaryTermUpdate,
  GlossaryTestMatchRequest,
  GlossaryTranslationCreate,
  GlossaryTranslationUpdate,
  GlossaryVariantCreate,
  GlossaryVariantUpdate,
} from '../types/glossary';
import { useDocumentSession } from './useDocumentSession';

export const glossaryKeys = {
  root: (scope: readonly [string, number]) => ['glossary', scope[0], scope[1]] as const,
  profiles: (scope: readonly [string, number], params: GlossaryListParams) =>
    [...glossaryKeys.root(scope), 'profiles', params] as const,
  profile: (scope: readonly [string, number], profileId: string) =>
    [...glossaryKeys.root(scope), 'profiles', profileId] as const,
  terms: (scope: readonly [string, number], params: GlossaryListParams) =>
    [...glossaryKeys.root(scope), 'terms', params] as const,
  term: (scope: readonly [string, number], termId: string) =>
    [...glossaryKeys.root(scope), 'terms', termId] as const,
  exceptions: (scope: readonly [string, number], params: GlossaryListParams) =>
    [...glossaryKeys.root(scope), 'exceptions', params] as const,
  validation: (scope: readonly [string, number]) =>
    [...glossaryKeys.root(scope), 'validation'] as const,
} as const;

export const useGlossaryProfiles = (params: GlossaryListParams) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: glossaryKeys.profiles(scope, params),
    queryFn: ({ signal }) => listGlossaryProfiles(params, signal),
    placeholderData: (previous) => previous,
  });
};

export const useGlossaryProfile = (profileId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: glossaryKeys.profile(scope, profileId ?? 'none'),
    queryFn: ({ signal }) => getGlossaryProfile(profileId ?? '', signal),
    enabled: profileId !== null,
  });
};

export const useGlossaryTerms = (params: GlossaryListParams) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: glossaryKeys.terms(scope, params),
    queryFn: ({ signal }) => listGlossaryTerms(params, signal),
    placeholderData: (previous) => previous,
  });
};

export const useGlossaryTerm = (termId: string | null) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: glossaryKeys.term(scope, termId ?? 'none'),
    queryFn: ({ signal }) => getGlossaryTerm(termId ?? '', signal),
    enabled: termId !== null,
  });
};

export const useGlossaryExceptions = (params: GlossaryListParams) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: glossaryKeys.exceptions(scope, params),
    queryFn: ({ signal }) => listGlossaryExceptions(params, signal),
    placeholderData: (previous) => previous,
  });
};

export const useGlossaryMutations = () => {
  const scope = useDocumentSession();
  const queryClient = useQueryClient();
  const invalidate = async (): Promise<void> => {
    await queryClient.invalidateQueries({ queryKey: glossaryKeys.root(scope) });
  };

  return {
    createProfile: useMutation({
      mutationFn: (payload: GlossaryProfileCreate) => createGlossaryProfile(payload),
      onSuccess: invalidate,
    }),
    updateProfile: useMutation({
      mutationFn: ({
        payload,
        profileId,
      }: {
        profileId: string;
        payload: GlossaryProfileUpdate;
      }) => updateGlossaryProfile(profileId, payload),
      onSuccess: invalidate,
    }),
    archiveProfile: useMutation({
      mutationFn: archiveGlossaryProfile,
      onSuccess: invalidate,
    }),
    restoreProfile: useMutation({
      mutationFn: restoreGlossaryProfile,
      onSuccess: invalidate,
    }),
    createTerm: useMutation({
      mutationFn: (payload: GlossaryTermCreate) => createGlossaryTerm(payload),
      onSuccess: invalidate,
    }),
    updateTerm: useMutation({
      mutationFn: ({
        payload,
        termId,
      }: {
        termId: string;
        payload: GlossaryTermUpdate;
      }) => updateGlossaryTerm(termId, payload),
      onSuccess: invalidate,
    }),
    archiveTerm: useMutation({
      mutationFn: archiveGlossaryTerm,
      onSuccess: invalidate,
    }),
    restoreTerm: useMutation({
      mutationFn: restoreGlossaryTerm,
      onSuccess: invalidate,
    }),
    addTranslation: useMutation({
      mutationFn: ({
        payload,
        termId,
      }: {
        termId: string;
        payload: GlossaryTranslationCreate;
      }) => addGlossaryTranslation(termId, payload),
      onSuccess: invalidate,
    }),
    updateTranslation: useMutation({
      mutationFn: ({
        payload,
        translationId,
      }: {
        translationId: string;
        payload: GlossaryTranslationUpdate;
      }) => updateGlossaryTranslation(translationId, payload),
      onSuccess: invalidate,
    }),
    addVariant: useMutation({
      mutationFn: ({
        payload,
        translationId,
      }: {
        translationId: string;
        payload: GlossaryVariantCreate;
      }) => addGlossaryVariant(translationId, payload),
      onSuccess: invalidate,
    }),
    updateVariant: useMutation({
      mutationFn: ({
        payload,
        variantId,
      }: {
        variantId: string;
        payload: GlossaryVariantUpdate;
      }) => updateGlossaryVariant(variantId, payload),
      onSuccess: invalidate,
    }),
    createException: useMutation({
      mutationFn: (payload: GlossaryExceptionCreate) =>
        createGlossaryException(payload),
      onSuccess: invalidate,
    }),
    updateException: useMutation({
      mutationFn: ({
        exceptionId,
        payload,
      }: {
        exceptionId: string;
        payload: GlossaryExceptionUpdate;
      }) => updateGlossaryException(exceptionId, payload),
      onSuccess: invalidate,
    }),
    deactivateException: useMutation({
      mutationFn: deactivateGlossaryException,
      onSuccess: invalidate,
    }),
    template: useMutation({ mutationFn: downloadGlossaryTemplate }),
    previewImport: useMutation({ mutationFn: previewGlossaryImport }),
    confirmImport: useMutation({
      mutationFn: (payload: GlossaryImportConfirmRequest) =>
        confirmGlossaryImport(payload),
      onSuccess: invalidate,
    }),
    export: useMutation({
      mutationFn: ({
        format,
        params,
      }: {
        format: GlossaryExportFormat;
        params?: GlossaryExportParams;
      }) => exportGlossary(format, params),
    }),
    testMatch: useMutation({
      mutationFn: (payload: GlossaryTestMatchRequest) => testGlossaryMatch(payload),
    }),
  } as const;
};
