import { apiClient } from './client';
import type { ApiResponse } from '../types/auth';
import type {
  DocumentType,
  DocumentTypeCreate,
  DocumentTypeList,
  DocumentTypeListParams,
  DocumentTypeUpdate,
} from '../types/documentType';
import type { MasterDataOption } from '../types/masterData';

const resourcePath = '/master-data/document-types';

export const documentTypeApi = {
  async list(params: DocumentTypeListParams): Promise<DocumentTypeList> {
    const { data: response } = await apiClient.get<ApiResponse<DocumentTypeList>>(
      resourcePath,
      { params },
    );
    return response.data;
  },

  async getById(id: string): Promise<DocumentType> {
    const { data: response } = await apiClient.get<ApiResponse<DocumentType>>(
      `${resourcePath}/${id}`,
    );
    return response.data;
  },

  async create(payload: DocumentTypeCreate): Promise<DocumentType> {
    const { data: response } = await apiClient.post<ApiResponse<DocumentType>>(
      resourcePath,
      payload,
    );
    return response.data;
  },

  async update(id: string, payload: DocumentTypeUpdate): Promise<DocumentType> {
    const { data: response } = await apiClient.put<ApiResponse<DocumentType>>(
      `${resourcePath}/${id}`,
      payload,
    );
    return response.data;
  },

  async activate(id: string): Promise<DocumentType> {
    const { data: response } = await apiClient.patch<ApiResponse<DocumentType>>(
      `${resourcePath}/${id}/activate`,
    );
    return response.data;
  },

  async deactivate(id: string): Promise<DocumentType> {
    const { data: response } = await apiClient.patch<ApiResponse<DocumentType>>(
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
