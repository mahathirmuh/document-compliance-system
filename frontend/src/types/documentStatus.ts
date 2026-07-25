import type {
  MasterDataAuditFields,
  MasterDataListParams,
  PaginatedData,
} from './masterData';

export interface DocumentStatus extends MasterDataAuditFields {
  id: string;
  code: string;
  name: string;
  description: string | null;
  displayOrder: number;
  isInitial: boolean;
  isFinal: boolean;
  isObsolete: boolean;
  isActive: boolean;
}

export interface DocumentStatusCreate {
  code: string;
  name: string;
  description: string | null;
  displayOrder: number;
  isInitial: boolean;
  isFinal: boolean;
  isObsolete: boolean;
  isActive: boolean;
}

export type DocumentStatusUpdate = DocumentStatusCreate;
export type DocumentStatusListParams = MasterDataListParams;
export type DocumentStatusList = PaginatedData<DocumentStatus>;
