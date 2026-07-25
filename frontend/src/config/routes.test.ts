import { describe, expect, it } from 'vitest';

import { getRouteBreadcrumbs, getRouteTitle } from './routes';

describe('document route metadata', () => {
  it.each([
    ['/documents/abc', 'Document Details'],
    ['/documents/abc/edit', 'Edit Document'],
    ['/documents/abc/revisions', 'Revision Management'],
  ])('resolves %s to %s', (path, title) => {
    expect(getRouteTitle(path)).toBe(title);
  });

  it('links a nested revision breadcrumb through document details', () => {
    expect(getRouteBreadcrumbs('/documents/abc/revisions')).toEqual([
      { label: 'Documents', path: '/documents' },
      { label: 'Document Details', path: '/documents/abc' },
      { label: 'Revision Management' },
    ]);
  });
});
