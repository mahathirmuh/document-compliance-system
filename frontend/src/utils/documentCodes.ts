const documentComponentPattern = /^[A-Z0-9_]+$/;
const documentTypeComponentPattern = /^[A-Z0-9_-]+$/;
const documentNumberPattern = /^[A-Z0-9._-]+$/;
const revisionInputPattern = /^(?:REV\.?)?(.+)$/i;
const revisionValuePattern = /^(?:\d+|[A-Z][A-Z0-9.-]*)$/;
const maximumRevisionValueLength = 26;

export interface DocumentCodeParts {
  companyCode: string;
  departmentCode: string;
  sectionCode?: string | null;
  documentTypeCode: string;
  documentNumber: string;
}

const normalizeCodePart = (value: string): string => value.trim().toUpperCase();

const getRevisionValue = (value: string): string | null => {
  const match = revisionInputPattern.exec(value.trim().toUpperCase());
  const revisionValue = match?.[1]?.trim() ?? '';
  return revisionValue.length > 0 &&
    revisionValue.length <= maximumRevisionValueLength &&
    revisionValuePattern.test(revisionValue)
    ? revisionValue
    : null;
};

export const isValidRevisionCode = (value: string): boolean =>
  getRevisionValue(value) !== null;

export const generateDocumentCodePreview = ({
  companyCode,
  departmentCode,
  documentNumber,
  documentTypeCode,
  sectionCode,
}: DocumentCodeParts): string => {
  const company = normalizeCodePart(companyCode);
  const department = normalizeCodePart(departmentCode);
  const section = sectionCode ? normalizeCodePart(sectionCode) : '';
  const documentType = normalizeCodePart(documentTypeCode);
  const number = normalizeCodePart(documentNumber);

  if (
    !documentComponentPattern.test(company) ||
    !documentComponentPattern.test(department) ||
    (section !== '' && !documentComponentPattern.test(section)) ||
    !documentTypeComponentPattern.test(documentType) ||
    !documentNumberPattern.test(number)
  ) {
    return '';
  }
  return [company, department, section, documentType, number].filter(Boolean).join('-');
};

export const normalizeRevisionCode = (value: string): string => {
  const normalizedInput = value.trim();
  const revisionValue = getRevisionValue(normalizedInput);
  if (!revisionValue) {
    return normalizedInput;
  }

  if (/^\d+$/.test(revisionValue)) {
    return `Rev.${revisionValue.padStart(3, '0')}`;
  }
  return `Rev.${revisionValue}`;
};

export const generateFullDocumentCodePreview = (
  baseDocumentCode: string,
  revisionCode: string,
): string => {
  const baseCode = baseDocumentCode.trim().toUpperCase();
  if (!isValidRevisionCode(revisionCode)) {
    return '';
  }
  const revision = normalizeRevisionCode(revisionCode);
  return baseCode && revision ? `${baseCode}_${revision}` : '';
};
