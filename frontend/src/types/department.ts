import type {
  MasterDataAuditFields,
  MasterDataListParams,
  PaginatedData,
} from './masterData';

export interface Department extends MasterDataAuditFields {
  id: string;
  code: string;
  name: string;
  description: string | null;
  isActive: boolean;
}

export interface DepartmentCreate {
  code: string;
  name: string;
  description: string | null;
  isActive: boolean;
}

export type DepartmentUpdate = DepartmentCreate;
export type DepartmentListParams = MasterDataListParams;
export type DepartmentList = PaginatedData<Department>;
