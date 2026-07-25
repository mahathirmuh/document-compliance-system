import {
  supportedDocumentExtensions,
  supportedDocumentMimeTypes,
  type SupportedDocumentExtension,
} from '../types/documentFile';

const mebibyte = 1024 * 1024;

const positiveNumberOr = (value: string | undefined, fallback: number): number => {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
};

export const documentMaxFileSizeBytes =
  positiveNumberOr(import.meta.env.VITE_DOCUMENT_MAX_FILE_SIZE_MB, 50) * mebibyte;

export const documentBatchMaxFiles = Math.floor(
  positiveNumberOr(import.meta.env.VITE_DOCUMENT_BATCH_MAX_FILES, 50),
);

export const documentBatchMaxTotalSizeBytes =
  positiveNumberOr(import.meta.env.VITE_DOCUMENT_BATCH_MAX_TOTAL_SIZE_MB, 500) *
  mebibyte;

export const documentFileAccept = [
  ...supportedDocumentExtensions.map((extension) => `.${extension}`),
  ...Object.values(supportedDocumentMimeTypes),
].join(',');

export const getDocumentFileExtension = (
  fileName: string,
): SupportedDocumentExtension | null => {
  const extension = fileName.split('.').pop()?.toLowerCase();
  return (
    supportedDocumentExtensions.find((candidate) => candidate === extension) ?? null
  );
};

export interface FileValidationResult {
  valid: boolean;
  extension: SupportedDocumentExtension | null;
  message: string | null;
}

export const validateDocumentFile = (
  file: File,
  maximumSize = documentMaxFileSizeBytes,
): FileValidationResult => {
  const extension = getDocumentFileExtension(file.name);
  if (!extension) {
    return {
      valid: false,
      extension: null,
      message: 'Only PDF, DOCX, and XLSX files are supported.',
    };
  }
  if (file.size <= 0) {
    return {
      valid: false,
      extension,
      message: 'The selected file is empty.',
    };
  }
  if (file.size > maximumSize) {
    return {
      valid: false,
      extension,
      message: `File exceeds the ${formatFileSize(maximumSize)} limit.`,
    };
  }

  const expectedMime = supportedDocumentMimeTypes[extension];
  if (
    file.type &&
    file.type !== expectedMime &&
    file.type !== 'application/octet-stream'
  ) {
    return {
      valid: false,
      extension,
      message: `The declared file type does not match .${extension}.`,
    };
  }

  return { valid: true, extension, message: null };
};

export const formatFileSize = (bytes: number | null | undefined): string => {
  if (bytes === null || bytes === undefined || !Number.isFinite(bytes) || bytes < 0) {
    return '—';
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < mebibyte) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  if (bytes < 1024 * mebibyte) {
    return `${(bytes / mebibyte).toFixed(1)} MB`;
  }
  return `${(bytes / (1024 * mebibyte)).toFixed(1)} GB`;
};

export const estimateBatchFileProgress = (
  files: readonly File[],
  overallProgress: number,
): number[] => {
  if (files.length === 0) {
    return [];
  }
  const normalizedOverall = Math.min(100, Math.max(0, overallProgress));
  const totalSize = files.reduce((sum, file) => sum + file.size, 0);
  if (totalSize === 0) {
    return files.map(() => normalizedOverall);
  }

  const estimatedLoaded = (totalSize * normalizedOverall) / 100;
  let precedingBytes = 0;
  return files.map((file) => {
    const progress =
      file.size === 0
        ? normalizedOverall
        : ((estimatedLoaded - precedingBytes) * 100) / file.size;
    precedingBytes += file.size;
    return Math.round(Math.min(100, Math.max(0, progress)));
  });
};

export const shortFileHash = (hash: string | null | undefined): string =>
  hash ? `${hash.slice(0, 12)}…${hash.slice(-6)}` : '—';
