import { describe, expect, it } from 'vitest';

import { documentKeys } from './documentQueryKeys';

describe('document query keys', () => {
  it('isolates list and revision caches by user and session generation', () => {
    const params = {
      page: 1,
      pageSize: 20,
      isArchived: false,
    } as const;
    expect(documentKeys.list(['user-a', 1], params)).not.toEqual(
      documentKeys.list(['user-a', 2], params),
    );
    expect(documentKeys.revisions.list(['user-a', 1], 'document-1')).not.toEqual(
      documentKeys.revisions.list(['user-b', 1], 'document-1'),
    );
    expect(documentKeys.formOptions(['user-a', 1])).not.toEqual(
      documentKeys.formOptions(['user-a', 2]),
    );
  });
});
