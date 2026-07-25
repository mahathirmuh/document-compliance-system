import { apiClient } from './client';
import type { ApiResponse } from '../types/auth';
import type { MasterDataOption } from '../types/masterData';
import type {
  ValidationRule,
  ValidationRuleCreate,
  ValidationRuleList,
  ValidationRuleListParams,
  ValidationRuleUpdate,
} from '../types/validationRule';

const resourcePath = '/master-data/validation-rules';

export const validationRuleApi = {
  async list(params: ValidationRuleListParams): Promise<ValidationRuleList> {
    const { data: response } = await apiClient.get<ApiResponse<ValidationRuleList>>(
      resourcePath,
      { params },
    );
    return response.data;
  },

  async getById(id: string): Promise<ValidationRule> {
    const { data: response } = await apiClient.get<ApiResponse<ValidationRule>>(
      `${resourcePath}/${id}`,
    );
    return response.data;
  },

  async create(payload: ValidationRuleCreate): Promise<ValidationRule> {
    const { data: response } = await apiClient.post<ApiResponse<ValidationRule>>(
      resourcePath,
      payload,
    );
    return response.data;
  },

  async update(id: string, payload: ValidationRuleUpdate): Promise<ValidationRule> {
    const { data: response } = await apiClient.put<ApiResponse<ValidationRule>>(
      `${resourcePath}/${id}`,
      payload,
    );
    return response.data;
  },

  async activate(id: string): Promise<ValidationRule> {
    const { data: response } = await apiClient.patch<ApiResponse<ValidationRule>>(
      `${resourcePath}/${id}/activate`,
    );
    return response.data;
  },

  async deactivate(id: string): Promise<ValidationRule> {
    const { data: response } = await apiClient.patch<ApiResponse<ValidationRule>>(
      `${resourcePath}/${id}/deactivate`,
    );
    return response.data;
  },

  async setDefault(id: string): Promise<ValidationRule> {
    const { data: response } = await apiClient.patch<ApiResponse<ValidationRule>>(
      `${resourcePath}/${id}/set-default`,
    );
    return response.data;
  },

  async getOptions(): Promise<MasterDataOption[]> {
    const { data: response } = await apiClient.get<ApiResponse<MasterDataOption[]>>(
      `${resourcePath}/options`,
      { params: { activeOnly: true } },
    );
    return response.data;
  },
};
