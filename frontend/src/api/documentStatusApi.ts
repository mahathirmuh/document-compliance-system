import { apiClient } from './client';
import type { ApiResponse } from '../types/auth';
import type {
  DocumentStatus,
  DocumentStatusCreate,
  DocumentStatusList,
  DocumentStatusListParams,
  DocumentStatusUpdate,
} from '../types/documentStatus';
import type { MasterDataOption } from '../types/masterData';

const resourcePath = '/master-data/document-statuses';

export const documentStatusApi = {
  async list(params: DocumentStatusListParams): Promise<DocumentStatusList> {
    const { data: response } = await apiClient.get<ApiResponse<DocumentStatusList>>(
      resourcePath,
      { params },
    );
    return response.data;
  },

  async getById(id: string): Promise<DocumentStatus> {
    const { data: response } = await apiClient.get<ApiResponse<DocumentStatus>>(
      `${resourcePath}/${id}`,
    );
    return response.data;
  },

  async create(payload: DocumentStatusCreate): Promise<DocumentStatus> {
    const { data: response } = await apiClient.post<ApiResponse<DocumentStatus>>(
      resourcePath,
      payload,
    );
    return response.data;
  },

  async update(id: string, payload: DocumentStatusUpdate): Promise<DocumentStatus> {
    const { data: response } = await apiClient.put<ApiResponse<DocumentStatus>>(
      `${resourcePath}/${id}`,
      payload,
    );
    return response.data;
  },

  async activate(id: string): Promise<DocumentStatus> {
    const { data: response } = await apiClient.patch<ApiResponse<DocumentStatus>>(
      `${resourcePath}/${id}/activate`,
    );
    return response.data;
  },

  async deactivate(id: string): Promise<DocumentStatus> {
    const { data: response } = await apiClient.patch<ApiResponse<DocumentStatus>>(
      `${resourcePath}/${id}/deactivate`,
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
