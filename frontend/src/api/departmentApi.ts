import { apiClient } from './client';
import type { ApiResponse } from '../types/auth';
import type {
  Department,
  DepartmentCreate,
  DepartmentList,
  DepartmentListParams,
  DepartmentUpdate,
} from '../types/department';
import type { MasterDataOption } from '../types/masterData';

const resourcePath = '/master-data/departments';

export const departmentApi = {
  async list(params: DepartmentListParams): Promise<DepartmentList> {
    const { data: response } = await apiClient.get<ApiResponse<DepartmentList>>(
      resourcePath,
      { params },
    );
    return response.data;
  },

  async getById(id: string): Promise<Department> {
    const { data: response } = await apiClient.get<ApiResponse<Department>>(
      `${resourcePath}/${id}`,
    );
    return response.data;
  },

  async create(payload: DepartmentCreate): Promise<Department> {
    const { data: response } = await apiClient.post<ApiResponse<Department>>(
      resourcePath,
      payload,
    );
    return response.data;
  },

  async update(id: string, payload: DepartmentUpdate): Promise<Department> {
    const { data: response } = await apiClient.put<ApiResponse<Department>>(
      `${resourcePath}/${id}`,
      payload,
    );
    return response.data;
  },

  async activate(id: string): Promise<Department> {
    const { data: response } = await apiClient.patch<ApiResponse<Department>>(
      `${resourcePath}/${id}/activate`,
    );
    return response.data;
  },

  async deactivate(id: string): Promise<Department> {
    const { data: response } = await apiClient.patch<ApiResponse<Department>>(
      `${resourcePath}/${id}/deactivate`,
    );
    return response.data;
  },

  async getOptions(activeOnly = true): Promise<MasterDataOption[]> {
    const { data: response } = await apiClient.get<ApiResponse<MasterDataOption[]>>(
      `${resourcePath}/options`,
      { params: { activeOnly } },
    );
    return response.data;
  },
};
