import { describe, expect, it } from 'vitest';

import {
  generateDocumentCodePreview,
  generateFullDocumentCodePreview,
  normalizeRevisionCode,
} from './documentCodes';

describe('document code previews', () => {
  it('generates base codes with and without a section', () => {
    expect(
      generateDocumentCodePreview({
        companyCode: 'mti',
        departmentCode: 'hrm',
        sectionCode: 'ier',
        documentTypeCode: 'sop',
        documentNumber: '001',
      }),
    ).toBe('MTI-HRM-IER-SOP-001');
    expect(
      generateDocumentCodePreview({
        companyCode: 'mti',
        departmentCode: 'hrm',
        documentTypeCode: 'pol',
        documentNumber: '001',
      }),
    ).toBe('MTI-HRM-POL-001');
  });

  it('uses backend-specific validation for each base-code component', () => {
    expect(
      generateDocumentCodePreview({
        companyCode: 'MT-I',
        departmentCode: 'HRM',
        documentTypeCode: 'POL',
        documentNumber: '001',
      }),
    ).toBe('');
    expect(
      generateDocumentCodePreview({
        companyCode: 'MTI',
        departmentCode: 'H-R',
        documentTypeCode: 'POL',
        documentNumber: '001',
      }),
    ).toBe('');
    expect(
      generateDocumentCodePreview({
        companyCode: 'MTI',
        departmentCode: 'HRM',
        sectionCode: 'I.ER',
        documentTypeCode: 'S-OP',
        documentNumber: '2026.001-A',
      }),
    ).toBe('');
    expect(
      generateDocumentCodePreview({
        companyCode: 'MTI_01',
        departmentCode: 'HRM',
        sectionCode: 'IER',
        documentTypeCode: 'S-OP',
        documentNumber: '2026.001-A',
      }),
    ).toBe('MTI_01-HRM-IER-S-OP-2026.001-A');
  });

  it.each([
    ['0', 'Rev.000'],
    ['Rev000', 'Rev.000'],
    ['rev.12', 'Rev.012'],
    ['A', 'Rev.A'],
    ['rev.b-2', 'Rev.B-2'],
    ['Rev.A.2', 'Rev.A.2'],
  ])('normalizes %s as %s', (value, expected) => {
    expect(normalizeRevisionCode(value)).toBe(expected);
  });

  it.each(['1A', 'Rev.1A', 'Rev.A_B', 'Rev./A', '9'.repeat(27)])(
    'does not preview invalid backend revision value %s',
    (value) => {
      expect(generateFullDocumentCodePreview('MTI-HRM-POL-001', value)).toBe('');
    },
  );

  it('generates a full revision code', () => {
    expect(generateFullDocumentCodePreview('MTI-HRM-POL-001', '1')).toBe(
      'MTI-HRM-POL-001_Rev.001',
    );
  });
});
