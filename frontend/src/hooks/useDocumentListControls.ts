import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router';

import type { DocumentFilterValues } from '../components/documents/DocumentFilters';
import {
  documentSortFields,
  type DocumentListParams,
  type DocumentSortField,
} from '../types/document';
import { masterDataPageSizes, type SortOrder } from '../types/masterData';

const filterKeys = [
  'search',
  'departmentId',
  'sectionId',
  'documentTypeId',
  'documentStatusId',
  'revisionCode',
  'hasSharePointUrl',
  'createdFrom',
  'createdTo',
  'effectiveFrom',
  'effectiveTo',
] as const;

const parsePositiveInteger = (value: string | null, fallback: number): number => {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
};

const parsePageSize = (value: string | null): number => {
  const parsed = parsePositiveInteger(value, 20);
  return masterDataPageSizes.some((size) => size === parsed) ? parsed : 20;
};

const parseOptionalBoolean = (value: string | null): boolean | undefined => {
  if (value === 'true') {
    return true;
  }
  if (value === 'false') {
    return false;
  }
  return undefined;
};

export const useDocumentListControls = (isArchived: boolean) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const page = parsePositiveInteger(searchParams.get('page'), 1);
  const pageSize = parsePageSize(searchParams.get('pageSize'));
  const requestedSortBy = searchParams.get('sortBy');
  const sortBy: DocumentSortField =
    requestedSortBy && documentSortFields.some((field) => field === requestedSortBy)
      ? (requestedSortBy as DocumentSortField)
      : 'updatedAt';
  const sortOrder: SortOrder = searchParams.get('sortOrder') === 'asc' ? 'asc' : 'desc';

  const filters = useMemo<DocumentFilterValues>(
    () => ({
      search: searchParams.get('search')?.trim() ?? '',
      departmentId: searchParams.get('departmentId') ?? '',
      sectionId: searchParams.get('sectionId') ?? '',
      documentTypeId: searchParams.get('documentTypeId') ?? '',
      documentStatusId: searchParams.get('documentStatusId') ?? '',
      revisionCode: searchParams.get('revisionCode') ?? '',
      hasSharePointUrl: parseOptionalBoolean(searchParams.get('hasSharePointUrl')),
      createdFrom: searchParams.get('createdFrom') ?? '',
      createdTo: searchParams.get('createdTo') ?? '',
      effectiveFrom: searchParams.get('effectiveFrom') ?? '',
      effectiveTo: searchParams.get('effectiveTo') ?? '',
    }),
    [searchParams],
  );

  const updateSearchParams = useCallback(
    (updates: Record<string, string | null>): void => {
      setSearchParams(
        (current) => {
          const next = new URLSearchParams(current);
          Object.entries(updates).forEach(([key, value]) => {
            if (value === null || value === '') {
              next.delete(key);
            } else {
              next.set(key, value);
            }
          });
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  const setFilters = useCallback(
    (updates: Partial<DocumentFilterValues>): void => {
      const serialized = Object.fromEntries(
        Object.entries(updates).map(([key, value]) => [
          key,
          value === undefined || value === '' ? null : String(value),
        ]),
      );
      updateSearchParams({ ...serialized, page: null });
    },
    [updateSearchParams],
  );

  const resetFilters = useCallback((): void => {
    const reset = Object.fromEntries(filterKeys.map((key) => [key, null])) as Record<
      string,
      null
    >;
    updateSearchParams({ ...reset, page: null });
  }, [updateSearchParams]);

  const params = useMemo<DocumentListParams>(
    () => ({
      page,
      pageSize,
      sortBy,
      sortOrder,
      isArchived,
      ...(filters.search ? { search: filters.search } : {}),
      ...(filters.departmentId ? { departmentId: filters.departmentId } : {}),
      ...(filters.sectionId ? { sectionId: filters.sectionId } : {}),
      ...(filters.documentTypeId ? { documentTypeId: filters.documentTypeId } : {}),
      ...(filters.documentStatusId
        ? { documentStatusId: filters.documentStatusId }
        : {}),
      ...(filters.revisionCode ? { revisionCode: filters.revisionCode } : {}),
      ...(filters.hasSharePointUrl === undefined
        ? {}
        : { hasSharePointUrl: filters.hasSharePointUrl }),
      ...(filters.createdFrom ? { createdFrom: filters.createdFrom } : {}),
      ...(filters.createdTo ? { createdTo: filters.createdTo } : {}),
      ...(filters.effectiveFrom ? { effectiveFrom: filters.effectiveFrom } : {}),
      ...(filters.effectiveTo ? { effectiveTo: filters.effectiveTo } : {}),
    }),
    [filters, isArchived, page, pageSize, sortBy, sortOrder],
  );

  return {
    params,
    filters,
    page,
    pageSize,
    sortBy,
    sortOrder,
    setFilters,
    resetFilters,
    setPage: (nextPage: number) =>
      updateSearchParams({ page: nextPage <= 1 ? null : String(nextPage) }),
    setPageSize: (nextPageSize: number) =>
      updateSearchParams({
        pageSize: nextPageSize === 20 ? null : String(nextPageSize),
        page: null,
      }),
    setSort: (key: string) => {
      if (!documentSortFields.some((field) => field === key)) {
        return;
      }
      const nextOrder: SortOrder =
        sortBy === key && sortOrder === 'asc' ? 'desc' : 'asc';
      updateSearchParams({
        sortBy: key === 'updatedAt' ? null : key,
        sortOrder: nextOrder === 'desc' ? null : nextOrder,
        page: null,
      });
    },
  };
};
