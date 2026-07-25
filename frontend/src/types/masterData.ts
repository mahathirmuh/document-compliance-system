export const masterDataEntityTypes = [
  'departments',
  'sections',
  'document-types',
  'document-statuses',
  'validation-rules',
] as const;

export type MasterDataEntityType = (typeof masterDataEntityTypes)[number];

export type SortOrder = 'asc' | 'desc';

export interface MasterDataAuditFields {
  createdAt: string;
  updatedAt: string;
  createdBy: string | null;
  updatedBy: string | null;
}

export interface MasterDataListParams {
  search?: string;
  isActive?: boolean;
  page: number;
  pageSize: number;
  sortBy?: string;
  sortOrder?: SortOrder;
}

export interface PaginatedData<TItem> {
  items: TItem[];
  page: number;
  pageSize: number;
  totalItems: number;
  totalPages: number;
}

export interface MasterDataOption {
  id: string;
  code: string;
  name: string;
  isActive: boolean;
}

export interface OverviewCount {
  total: number;
  active: number;
  inactive: number;
}

export interface MasterDataOverview {
  departments: OverviewCount;
  sections: OverviewCount;
  documentTypes: OverviewCount;
  documentStatuses: OverviewCount;
  validationRules: OverviewCount;
}

export const importModes = ['CREATE_ONLY', 'UPSERT'] as const;
export type ImportMode = (typeof importModes)[number];

export const importRowStatuses = ['VALID', 'INVALID', 'DUPLICATE'] as const;
export type ImportRowStatus = (typeof importRowStatuses)[number];

export interface ImportPreviewRow {
  rowNumber: number;
  status: ImportRowStatus;
  data: Record<string, unknown>;
  errors: string[];
}

export interface ImportPreview {
  entityType: MasterDataEntityType;
  totalRows: number;
  validRows: number;
  invalidRows: number;
  duplicateRows: number;
  rows: ImportPreviewRow[];
  warnings: string[];
}

export interface ImportResult {
  entityType: MasterDataEntityType;
  mode: ImportMode;
  totalRows: number;
  created: number;
  updated: number;
  skipped: number;
  failed: number;
}

export interface BinaryDownload {
  blob: Blob;
  fileName: string | null;
}

export const masterDataPageSizes = [10, 20, 50, 100] as const;
