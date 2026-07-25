import { describe, expect, it } from 'vitest';

import { masterDataKeys } from './masterDataQueryKeys';

const params = {
  page: 1,
  pageSize: 20,
  sortBy: 'code',
  sortOrder: 'asc',
} as const;

describe('master data query cache isolation', () => {
  it('uses user and session generation in every resource key', () => {
    const firstSession = masterDataKeys.departments.list(['user-a', 1], params);
    const secondUser = masterDataKeys.departments.list(['user-b', 1], params);
    const nextSession = masterDataKeys.departments.list(['user-a', 2], params);

    expect(firstSession).not.toEqual(secondUser);
    expect(firstSession).not.toEqual(nextSession);
  });
});
