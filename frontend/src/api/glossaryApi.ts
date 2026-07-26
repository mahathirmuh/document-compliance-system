import axios, { type AxiosRequestConfig } from 'axios';

import { apiClient } from './client';
import type { ApiResponse } from '../types/auth';
import type {
  GlossaryDownload,
  GlossaryException,
  GlossaryExceptionCreate,
  GlossaryExceptionList,
  GlossaryExceptionUpdate,
  GlossaryExportFormat,
  GlossaryExportParams,
  GlossaryImportConfirmRequest,
  GlossaryImportPreview,
  GlossaryImportResult,
  GlossaryListParams,
  GlossaryProfile,
  GlossaryProfileCreate,
  GlossaryProfileList,
  GlossaryProfileUpdate,
  GlossaryTerm,
  GlossaryTermCreate,
  GlossaryTermList,
  GlossaryTermUpdate,
  GlossaryTestMatchRequest,
  GlossaryTestMatchResponse,
  GlossaryTestMatchResult,
  GlossaryTranslation,
  GlossaryTranslationCreate,
  GlossaryTranslationUpdate,
  GlossaryVariant,
  GlossaryVariantCreate,
  GlossaryVariantUpdate,
} from '../types/glossary';
import type {
  GlossaryHistoryParams,
  GlossaryMatchList,
  GlossaryMatchListParams,
  GlossaryValidationFindingList,
  GlossaryValidationHistory,
  GlossaryValidationJob,
  GlossaryValidationJobList,
  GlossaryValidationJobListParams,
  GlossaryValidationRequest,
  GlossaryValidationRun,
  GlossaryValidationQueuedResult,
  GlossaryValidationSummary,
} from '../types/glossaryValidation';
import { getDownloadFileName } from '../utils/downloadFile';

const rootPath = '/glossary';
const validationPath = `${rootPath}/validation`;
const exportTimeout = 10 * 60 * 1_000;
const paramsSerializer = { indexes: null } as const;

const withSignal = (signal?: AbortSignal): AxiosRequestConfig =>
  signal ? { signal } : {};

export const listGlossaryProfiles = async (
  params: GlossaryListParams,
  signal?: AbortSignal,
): Promise<GlossaryProfileList> => {
  const { data: response } = await apiClient.get<ApiResponse<GlossaryProfileList>>(
    `${rootPath}/profiles`,
    { params, ...withSignal(signal) },
  );
  return response.data;
};

export const getGlossaryProfile = async (
  profileId: string,
  signal?: AbortSignal,
): Promise<GlossaryProfile> => {
  const { data: response } = await apiClient.get<ApiResponse<GlossaryProfile>>(
    `${rootPath}/profiles/${profileId}`,
    withSignal(signal),
  );
  return response.data;
};

export const createGlossaryProfile = async (
  payload: GlossaryProfileCreate,
): Promise<GlossaryProfile> => {
  const { data: response } = await apiClient.post<ApiResponse<GlossaryProfile>>(
    `${rootPath}/profiles`,
    payload,
  );
  return response.data;
};

export const updateGlossaryProfile = async (
  profileId: string,
  payload: GlossaryProfileUpdate,
): Promise<GlossaryProfile> => {
  const { data: response } = await apiClient.put<ApiResponse<GlossaryProfile>>(
    `${rootPath}/profiles/${profileId}`,
    payload,
  );
  return response.data;
};

export const archiveGlossaryProfile = async (
  profileId: string,
): Promise<GlossaryProfile> => {
  const { data: response } = await apiClient.post<ApiResponse<GlossaryProfile>>(
    `${rootPath}/profiles/${profileId}/archive`,
  );
  return response.data;
};

export const restoreGlossaryProfile = async (
  profileId: string,
): Promise<GlossaryProfile> => {
  const { data: response } = await apiClient.post<ApiResponse<GlossaryProfile>>(
    `${rootPath}/profiles/${profileId}/restore`,
  );
  return response.data;
};

export const listGlossaryTerms = async (
  params: GlossaryListParams,
  signal?: AbortSignal,
): Promise<GlossaryTermList> => {
  const { data: response } = await apiClient.get<ApiResponse<GlossaryTermList>>(
    `${rootPath}/terms`,
    { params, ...withSignal(signal) },
  );
  return response.data;
};

export const getGlossaryTerm = async (
  termId: string,
  signal?: AbortSignal,
): Promise<GlossaryTerm> => {
  const { data: response } = await apiClient.get<ApiResponse<GlossaryTerm>>(
    `${rootPath}/terms/${termId}`,
    withSignal(signal),
  );
  return response.data;
};

export const createGlossaryTerm = async (
  payload: GlossaryTermCreate,
): Promise<GlossaryTerm> => {
  const { data: response } = await apiClient.post<ApiResponse<GlossaryTerm>>(
    `${rootPath}/terms`,
    payload,
  );
  return response.data;
};

export const updateGlossaryTerm = async (
  termId: string,
  payload: GlossaryTermUpdate,
): Promise<GlossaryTerm> => {
  const { data: response } = await apiClient.put<ApiResponse<GlossaryTerm>>(
    `${rootPath}/terms/${termId}`,
    payload,
  );
  return response.data;
};

export const archiveGlossaryTerm = async (termId: string): Promise<GlossaryTerm> => {
  const { data: response } = await apiClient.post<ApiResponse<GlossaryTerm>>(
    `${rootPath}/terms/${termId}/archive`,
  );
  return response.data;
};

export const restoreGlossaryTerm = async (termId: string): Promise<GlossaryTerm> => {
  const { data: response } = await apiClient.post<ApiResponse<GlossaryTerm>>(
    `${rootPath}/terms/${termId}/restore`,
  );
  return response.data;
};

export const addGlossaryTranslation = async (
  termId: string,
  payload: GlossaryTranslationCreate,
): Promise<GlossaryTranslation> => {
  const { data: response } = await apiClient.post<ApiResponse<GlossaryTranslation>>(
    `${rootPath}/terms/${termId}/translations`,
    payload,
  );
  return response.data;
};

export const updateGlossaryTranslation = async (
  translationId: string,
  payload: GlossaryTranslationUpdate,
): Promise<GlossaryTranslation> => {
  const { data: response } = await apiClient.put<ApiResponse<GlossaryTranslation>>(
    `${rootPath}/translations/${translationId}`,
    payload,
  );
  return response.data;
};

export const addGlossaryVariant = async (
  translationId: string,
  payload: GlossaryVariantCreate,
): Promise<GlossaryVariant> => {
  const { data: response } = await apiClient.post<ApiResponse<GlossaryVariant>>(
    `${rootPath}/translations/${translationId}/variants`,
    payload,
  );
  return response.data;
};

export const updateGlossaryVariant = async (
  variantId: string,
  payload: GlossaryVariantUpdate,
): Promise<GlossaryVariant> => {
  const { data: response } = await apiClient.put<ApiResponse<GlossaryVariant>>(
    `${rootPath}/variants/${variantId}`,
    payload,
  );
  return response.data;
};

export const listGlossaryExceptions = async (
  params: GlossaryListParams,
  signal?: AbortSignal,
): Promise<GlossaryExceptionList> => {
  const { data: response } = await apiClient.get<ApiResponse<GlossaryExceptionList>>(
    `${rootPath}/exceptions`,
    { params, ...withSignal(signal) },
  );
  return response.data;
};

export const createGlossaryException = async (
  payload: GlossaryExceptionCreate,
): Promise<GlossaryException> => {
  const { data: response } = await apiClient.post<ApiResponse<GlossaryException>>(
    `${rootPath}/exceptions`,
    payload,
  );
  return response.data;
};

export const updateGlossaryException = async (
  exceptionId: string,
  payload: GlossaryExceptionUpdate,
): Promise<GlossaryException> => {
  const { data: response } = await apiClient.put<ApiResponse<GlossaryException>>(
    `${rootPath}/exceptions/${exceptionId}`,
    payload,
  );
  return response.data;
};

export const deactivateGlossaryException = async (
  exceptionId: string,
): Promise<GlossaryException> => {
  const { data: response } = await apiClient.post<ApiResponse<GlossaryException>>(
    `${rootPath}/exceptions/${exceptionId}/deactivate`,
  );
  return response.data;
};

export const downloadGlossaryTemplate = async (): Promise<GlossaryDownload> => {
  const response = await apiClient.get<Blob>(`${rootPath}/import/template`, {
    responseType: 'blob',
  });
  return {
    blob: response.data,
    fileName: getDownloadFileName(response.headers['content-disposition']),
  };
};

export const previewGlossaryImport = async (
  file: File,
): Promise<GlossaryImportPreview> => {
  const formData = new FormData();
  formData.append('file', file);
  const { data: response } = await apiClient.post<ApiResponse<GlossaryImportPreview>>(
    `${rootPath}/import/preview`,
    formData,
  );
  return response.data;
};

export const confirmGlossaryImport = async (
  payload: GlossaryImportConfirmRequest,
): Promise<GlossaryImportResult> => {
  const formData = new FormData();
  formData.append('file', payload.file);
  formData.append('mode', payload.mode ?? 'CREATE_ONLY');
  const { data: response } = await apiClient.post<ApiResponse<GlossaryImportResult>>(
    `${rootPath}/import/confirm`,
    formData,
  );
  return response.data;
};

export const exportGlossary = async (
  format: GlossaryExportFormat,
  params: GlossaryExportParams = {},
): Promise<GlossaryDownload> => {
  const response = await apiClient.get<Blob>(`${rootPath}/export`, {
    params: { ...params, format },
    paramsSerializer,
    responseType: 'blob',
    timeout: exportTimeout,
  });
  return {
    blob: response.data,
    fileName: getDownloadFileName(response.headers['content-disposition']),
  };
};

export const testGlossaryMatch = async (
  payload: GlossaryTestMatchRequest,
): Promise<readonly GlossaryTestMatchResult[]> => {
  const { data: response } = await apiClient.post<
    ApiResponse<GlossaryTestMatchResponse>
  >(`${rootPath}/test-match`, payload);
  return response.data.matches;
};

export const startGlossaryValidation = async (
  payload: GlossaryValidationRequest,
): Promise<GlossaryValidationQueuedResult> => {
  const { data: response } = await apiClient.post<
    ApiResponse<GlossaryValidationQueuedResult>
  >(`${validationPath}/jobs`, payload);
  return response.data;
};

export const listGlossaryValidationJobs = async (
  params: GlossaryValidationJobListParams,
  signal?: AbortSignal,
): Promise<GlossaryValidationJobList> => {
  const { data: response } = await apiClient.get<
    ApiResponse<GlossaryValidationJobList>
  >(`${validationPath}/jobs`, {
    params,
    paramsSerializer,
    ...withSignal(signal),
  });
  return response.data;
};

export const getGlossaryValidationJob = async (
  jobId: string,
  signal?: AbortSignal,
): Promise<GlossaryValidationJob> => {
  const { data: response } = await apiClient.get<ApiResponse<GlossaryValidationJob>>(
    `${validationPath}/jobs/${jobId}`,
    withSignal(signal),
  );
  return response.data;
};

export const cancelGlossaryValidation = async (
  jobId: string,
): Promise<GlossaryValidationJob> => {
  const { data: response } = await apiClient.post<ApiResponse<GlossaryValidationJob>>(
    `${validationPath}/jobs/${jobId}/cancel`,
  );
  return response.data;
};

export const getGlossaryValidationRun = async (
  runId: string,
  signal?: AbortSignal,
): Promise<GlossaryValidationRun> => {
  const { data: response } = await apiClient.get<ApiResponse<GlossaryValidationRun>>(
    `${validationPath}/runs/${runId}`,
    withSignal(signal),
  );
  return response.data;
};

export const getGlossaryValidationSummary = async (
  runId: string,
  signal?: AbortSignal,
): Promise<GlossaryValidationSummary> => {
  const { data: response } = await apiClient.get<
    ApiResponse<GlossaryValidationSummary>
  >(`${validationPath}/runs/${runId}/summary`, withSignal(signal));
  return response.data;
};

export const listGlossaryMatches = async (
  runId: string,
  params: GlossaryMatchListParams,
  signal?: AbortSignal,
): Promise<GlossaryMatchList> => {
  const { data: response } = await apiClient.get<ApiResponse<GlossaryMatchList>>(
    `${validationPath}/runs/${runId}/matches`,
    { params, ...withSignal(signal) },
  );
  return response.data;
};

export const listGlossaryValidationFindings = async (
  runId: string,
  params: { page: number; pageSize: number },
  signal?: AbortSignal,
): Promise<GlossaryValidationFindingList> => {
  const { data: response } = await apiClient.get<
    ApiResponse<GlossaryValidationFindingList>
  >(`${validationPath}/runs/${runId}/findings`, {
    params,
    ...withSignal(signal),
  });
  return response.data;
};

export const revalidateGlossary = async (
  runId: string,
  payload: { reason: string },
): Promise<GlossaryValidationQueuedResult> => {
  const { data: response } = await apiClient.post<
    ApiResponse<GlossaryValidationQueuedResult>
  >(`${validationPath}/runs/${runId}/revalidate`, payload);
  return response.data;
};

export const exportGlossaryValidation = async (
  runId: string,
  format: GlossaryExportFormat,
): Promise<GlossaryDownload> => {
  const response = await apiClient.get<Blob>(`${validationPath}/runs/${runId}/export`, {
    params: { format },
    responseType: 'blob',
    timeout: exportTimeout,
  });
  return {
    blob: response.data,
    fileName: getDownloadFileName(response.headers['content-disposition']),
  };
};

export const getFileGlossaryValidation = async (
  fileId: string,
  signal?: AbortSignal,
): Promise<GlossaryValidationRun | null> => {
  try {
    const { data: response } = await apiClient.get<
      ApiResponse<GlossaryValidationRun | null>
    >(`/document-files/${fileId}/glossary-validation`, withSignal(signal));
    return response.data;
  } catch (error: unknown) {
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      return null;
    }
    throw error;
  }
};

export const getGlossaryHistory = async (
  fileId: string,
  params: GlossaryHistoryParams,
  signal?: AbortSignal,
): Promise<GlossaryValidationHistory> => {
  const { data: response } = await apiClient.get<
    ApiResponse<GlossaryValidationHistory>
  >(`/document-files/${fileId}/glossary-history`, {
    params,
    ...withSignal(signal),
  });
  return response.data;
};

export const glossaryApi = {
  listGlossaryProfiles,
  getGlossaryProfile,
  createGlossaryProfile,
  updateGlossaryProfile,
  archiveGlossaryProfile,
  restoreGlossaryProfile,
  listGlossaryTerms,
  getGlossaryTerm,
  createGlossaryTerm,
  updateGlossaryTerm,
  archiveGlossaryTerm,
  restoreGlossaryTerm,
  addGlossaryTranslation,
  updateGlossaryTranslation,
  addGlossaryVariant,
  updateGlossaryVariant,
  listGlossaryExceptions,
  createGlossaryException,
  updateGlossaryException,
  deactivateGlossaryException,
  downloadGlossaryTemplate,
  previewGlossaryImport,
  confirmGlossaryImport,
  exportGlossary,
  testGlossaryMatch,
  startGlossaryValidation,
  listGlossaryValidationJobs,
  getGlossaryValidationJob,
  cancelGlossaryValidation,
  getGlossaryValidationRun,
  getGlossaryValidationSummary,
  listGlossaryMatches,
  listGlossaryValidationFindings,
  revalidateGlossary,
  exportGlossaryValidation,
  getFileGlossaryValidation,
  getGlossaryHistory,
} as const;
