import { apiClient } from './client';
import type { ApiResponse } from '../types/auth';
import type { MasterDataOption } from '../types/masterData';
import type {
  Section,
  SectionCreate,
  SectionList,
  SectionListParams,
  SectionOptionsParams,
  SectionUpdate,
} from '../types/section';

const resourcePath = '/master-data/sections';

export const sectionApi = {
  async list(params: SectionListParams): Promise<SectionList> {
    const { data: response } = await apiClient.get<ApiResponse<SectionList>>(
      resourcePath,
      { params },
    );
    return response.data;
  },

  async getById(id: string): Promise<Section> {
    const { data: response } = await apiClient.get<ApiResponse<Section>>(
      `${resourcePath}/${id}`,
    );
    return response.data;
  },

  async create(payload: SectionCreate): Promise<Section> {
    const { data: response } = await apiClient.post<ApiResponse<Section>>(
      resourcePath,
      payload,
    );
    return response.data;
  },

  async update(id: string, payload: SectionUpdate): Promise<Section> {
    const { data: response } = await apiClient.put<ApiResponse<Section>>(
      `${resourcePath}/${id}`,
      payload,
    );
    return response.data;
  },

  async activate(id: string): Promise<Section> {
    const { data: response } = await apiClient.patch<ApiResponse<Section>>(
      `${resourcePath}/${id}/activate`,
    );
    return response.data;
  },

  async deactivate(id: string): Promise<Section> {
    const { data: response } = await apiClient.patch<ApiResponse<Section>>(
      `${resourcePath}/${id}/deactivate`,
    );
    return response.data;
  },

  async getOptions(params: SectionOptionsParams = {}): Promise<MasterDataOption[]> {
    const { data: response } = await apiClient.get<ApiResponse<MasterDataOption[]>>(
      `${resourcePath}/options`,
      { params },
    );
    return response.data;
  },
};
