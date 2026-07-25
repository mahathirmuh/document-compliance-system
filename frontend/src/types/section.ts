import type {
  MasterDataAuditFields,
  MasterDataListParams,
  PaginatedData,
} from './masterData';

export interface SectionDepartment {
  id: string;
  code: string;
  name: string;
  isActive: boolean;
}

export interface Section extends MasterDataAuditFields {
  id: string;
  departmentId: string;
  department?: SectionDepartment;
  departmentCode?: string;
  departmentName?: string;
  code: string;
  name: string;
  description: string | null;
  isActive: boolean;
}

export interface SectionCreate {
  departmentId: string;
  code: string;
  name: string;
  description: string | null;
  isActive: boolean;
}

export type SectionUpdate = SectionCreate;

export interface SectionListParams extends MasterDataListParams {
  departmentId?: string;
}

export interface SectionOptionsParams {
  departmentId?: string;
  activeOnly?: boolean;
}

export type SectionList = PaginatedData<Section>;
