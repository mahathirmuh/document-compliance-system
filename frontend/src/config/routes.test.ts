import { describe, expect, it } from 'vitest';

import { getRouteBreadcrumbs, getRouteTitle } from './routes';

describe('document route metadata', () => {
  it.each([
    ['/documents/abc', 'Document Details'],
    ['/documents/abc/edit', 'Edit Document'],
    ['/documents/abc/revisions', 'Revision Management'],
    ['/documents/abc/extracted-content', 'Extracted Content'],
    ['/documents/abc/revisions/rev/extracted-content', 'Extracted Content'],
    ['/documents/abc/revisions/rev/extraction-history', 'Revision Extraction History'],
    ['/documents/abc/ocr-results', 'OCR Results'],
    ['/documents/abc/revisions/rev/ocr-results', 'OCR Results'],
    ['/documents/abc/language-results', 'Language Results'],
    ['/documents/abc/revisions/rev/language-results', 'Language Results'],
    ['/documents/abc/compliance', 'Document Compliance'],
    ['/documents/abc/revisions/rev/compliance', 'Document Compliance'],
    ['/compliance/findings/finding-id', 'Finding Details'],
  ])('resolves %s to %s', (path, title) => {
    expect(getRouteTitle(path)).toBe(title);
  });

  it('resolves every Phase 8 navigation route', () => {
    expect(getRouteTitle('/documents/validation-queue')).toBe('Validation Queue');
    expect(getRouteTitle('/documents/validation-history')).toBe('Validation History');
    expect(getRouteTitle('/compliance')).toBe('Compliance Overview');
    expect(getRouteTitle('/compliance/languages')).toBe('Language Compliance');
    expect(getRouteTitle('/compliance/sections')).toBe('Section Compliance');
    expect(getRouteTitle('/compliance/language-order')).toBe('Language Order');
    expect(getRouteTitle('/reports/compliance')).toBe('Compliance Report');
    expect(getRouteTitle('/reports/findings')).toBe('Findings Report');
  });

  it('links a nested revision breadcrumb through document details', () => {
    expect(getRouteBreadcrumbs('/documents/abc/revisions')).toEqual([
      { label: 'Documents', path: '/documents' },
      { label: 'Document Details', path: '/documents/abc' },
      { label: 'Revision Management' },
    ]);
  });
});
