import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router';

import {
  masterDataPageSizes,
  type MasterDataListParams,
  type SortOrder,
} from '../types/masterData';

const parsePositiveInteger = (value: string | null, fallback: number): number => {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
};

const parsePageSize = (value: string | null): number => {
  const parsed = parsePositiveInteger(value, 20);
  return masterDataPageSizes.some((size) => size === parsed) ? parsed : 20;
};

const parseActiveFilter = (value: string | null): boolean | undefined => {
  if (value === 'true') {
    return true;
  }
  if (value === 'false') {
    return false;
  }
  return undefined;
};

export const useMasterDataListControls = (
  defaultSortBy = 'code',
  defaultSortOrder: SortOrder = 'asc',
) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const page = parsePositiveInteger(searchParams.get('page'), 1);
  const pageSize = parsePageSize(searchParams.get('pageSize'));
  const search = searchParams.get('search')?.trim() ?? '';
  const isActive = parseActiveFilter(searchParams.get('isActive'));
  const sortBy = searchParams.get('sortBy') || defaultSortBy;
  const sortOrder =
    searchParams.get('sortOrder') === 'desc' ? 'desc' : defaultSortOrder;

  const updateParams = useCallback(
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

  const params = useMemo<MasterDataListParams>(
    () => ({
      page,
      pageSize,
      sortBy,
      sortOrder,
      ...(search ? { search } : {}),
      ...(isActive === undefined ? {} : { isActive }),
    }),
    [isActive, page, pageSize, search, sortBy, sortOrder],
  );

  return {
    params,
    page,
    pageSize,
    search,
    isActive,
    sortBy,
    sortOrder,
    setSearch: (value: string) => updateParams({ search: value, page: null }),
    setIsActive: (value: boolean | undefined) =>
      updateParams({
        isActive: value === undefined ? null : String(value),
        page: null,
      }),
    setPage: (value: number) =>
      updateParams({ page: value <= 1 ? null : String(value) }),
    setPageSize: (value: number) =>
      updateParams({ pageSize: value === 20 ? null : String(value), page: null }),
    setSort: (key: string) => {
      const nextOrder: SortOrder =
        sortBy === key && sortOrder === 'asc' ? 'desc' : 'asc';
      updateParams({
        sortBy: key === defaultSortBy ? null : key,
        sortOrder: nextOrder === defaultSortOrder ? null : nextOrder,
        page: null,
      });
    },
    updateParams,
  };
};
