import type { AxiosRequestConfig } from 'axios';

import { apiClient } from './client';
import type { ApiResponse } from '../types/auth';
import type {
  SectionAlias,
  SectionAliasCreate,
  SectionAliasList,
  SectionAliasListParams,
  SectionAliasProfile,
  SectionAliasProfileCreate,
  SectionAliasProfileList,
  SectionAliasProfileListParams,
  SectionAliasProfileUpdate,
  SectionAliasUpdate,
  SectionDefinition,
  SectionDefinitionCreate,
  SectionDefinitionDownload,
  SectionDefinitionImportConfirmRequest,
  SectionDefinitionImportPreview,
  SectionDefinitionImportResult,
  SectionDefinitionList,
  SectionDefinitionListParams,
  SectionDefinitionUpdate,
  SectionHeadingMatchRequest,
  SectionHeadingMatchResult,
} from '../types/sectionDefinition';
import { getDownloadFileName } from '../utils/downloadFile';

const profilePath = '/master-data/section-alias-profiles';
const definitionPath = '/master-data/section-definitions';
const aliasPath = '/master-data/section-aliases';
const requestTimeout = 2 * 60 * 1_000;
const withSignal = (signal?: AbortSignal): AxiosRequestConfig =>
  signal ? { signal } : {};

const getDownload = (
  blob: Blob,
  contentDisposition: string | undefined,
): SectionDefinitionDownload => ({
  blob,
  fileName: getDownloadFileName(contentDisposition),
});

export const sectionDefinitionApi = {
  async listProfiles(
    params: SectionAliasProfileListParams,
    signal?: AbortSignal,
  ): Promise<SectionAliasProfileList> {
    const { data: response } = await apiClient.get<
      ApiResponse<SectionAliasProfileList>
    >(profilePath, { params, ...withSignal(signal) });
    return response.data;
  },

  async createProfile(
    payload: SectionAliasProfileCreate,
  ): Promise<SectionAliasProfile> {
    const { data: response } = await apiClient.post<ApiResponse<SectionAliasProfile>>(
      profilePath,
      payload,
    );
    return response.data;
  },

  async updateProfile(
    id: string,
    payload: SectionAliasProfileUpdate,
  ): Promise<SectionAliasProfile> {
    const { data: response } = await apiClient.put<ApiResponse<SectionAliasProfile>>(
      `${profilePath}/${id}`,
      payload,
    );
    return response.data;
  },

  async activateProfile(id: string): Promise<SectionAliasProfile> {
    const { data: response } = await apiClient.patch<ApiResponse<SectionAliasProfile>>(
      `${profilePath}/${id}/activate`,
    );
    return response.data;
  },

  async deactivateProfile(id: string): Promise<SectionAliasProfile> {
    const { data: response } = await apiClient.patch<ApiResponse<SectionAliasProfile>>(
      `${profilePath}/${id}/deactivate`,
    );
    return response.data;
  },

  async listDefinitions(
    params: SectionDefinitionListParams,
    signal?: AbortSignal,
  ): Promise<SectionDefinitionList> {
    const { data: response } = await apiClient.get<ApiResponse<SectionDefinitionList>>(
      definitionPath,
      { params, ...withSignal(signal) },
    );
    return response.data;
  },

  async createDefinition(payload: SectionDefinitionCreate): Promise<SectionDefinition> {
    const { data: response } = await apiClient.post<ApiResponse<SectionDefinition>>(
      definitionPath,
      payload,
    );
    return response.data;
  },

  async updateDefinition(
    id: string,
    payload: SectionDefinitionUpdate,
  ): Promise<SectionDefinition> {
    const { data: response } = await apiClient.put<ApiResponse<SectionDefinition>>(
      `${definitionPath}/${id}`,
      payload,
    );
    return response.data;
  },

  async activateDefinition(id: string): Promise<SectionDefinition> {
    const { data: response } = await apiClient.patch<ApiResponse<SectionDefinition>>(
      `${definitionPath}/${id}/activate`,
    );
    return response.data;
  },

  async deactivateDefinition(id: string): Promise<SectionDefinition> {
    const { data: response } = await apiClient.patch<ApiResponse<SectionDefinition>>(
      `${definitionPath}/${id}/deactivate`,
    );
    return response.data;
  },

  async listAliases(
    params: SectionAliasListParams,
    signal?: AbortSignal,
  ): Promise<SectionAliasList> {
    const { data: response } = await apiClient.get<ApiResponse<SectionAliasList>>(
      aliasPath,
      { params, ...withSignal(signal) },
    );
    return response.data;
  },

  async createAlias(payload: SectionAliasCreate): Promise<SectionAlias> {
    const { data: response } = await apiClient.post<ApiResponse<SectionAlias>>(
      aliasPath,
      payload,
    );
    return response.data;
  },

  async updateAlias(id: string, payload: SectionAliasUpdate): Promise<SectionAlias> {
    const { data: response } = await apiClient.put<ApiResponse<SectionAlias>>(
      `${aliasPath}/${id}`,
      payload,
    );
    return response.data;
  },

  async activateAlias(id: string): Promise<SectionAlias> {
    const { data: response } = await apiClient.patch<ApiResponse<SectionAlias>>(
      `${aliasPath}/${id}/activate`,
    );
    return response.data;
  },

  async deactivateAlias(id: string): Promise<SectionAlias> {
    const { data: response } = await apiClient.patch<ApiResponse<SectionAlias>>(
      `${aliasPath}/${id}/deactivate`,
    );
    return response.data;
  },

  async testMatch(
    payload: SectionHeadingMatchRequest,
  ): Promise<SectionHeadingMatchResult> {
    const { data: response } = await apiClient.post<
      ApiResponse<SectionHeadingMatchResult>
    >(`${definitionPath}/test-match`, payload);
    return response.data;
  },

  async previewImport(
    file: File,
    profileId?: string,
  ): Promise<SectionDefinitionImportPreview> {
    const formData = new FormData();
    formData.append('file', file);
    if (profileId) {
      formData.append('profileId', profileId);
    }
    const { data: response } = await apiClient.post<
      ApiResponse<SectionDefinitionImportPreview>
    >(`${definitionPath}/import/preview`, formData, { timeout: requestTimeout });
    return response.data;
  },

  async confirmImport(
    payload: SectionDefinitionImportConfirmRequest,
  ): Promise<SectionDefinitionImportResult> {
    const { data: response } = await apiClient.post<
      ApiResponse<SectionDefinitionImportResult>
    >(`${definitionPath}/import/confirm`, payload, { timeout: requestTimeout });
    return response.data;
  },

  async exportXlsx(profileId?: string): Promise<SectionDefinitionDownload> {
    const response = await apiClient.get<Blob>(`${definitionPath}/export`, {
      params: profileId ? { profileId } : {},
      responseType: 'blob',
      timeout: requestTimeout,
    });
    return getDownload(response.data, response.headers['content-disposition']);
  },
} as const;
