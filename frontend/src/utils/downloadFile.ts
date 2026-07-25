import type { BinaryDownload } from '../types/masterData';

const unsafeFileNameCharacters = /[<>:"/\\|?*]/g;

export const getDownloadFileName = (
  contentDisposition: string | undefined,
): string | null => {
  if (!contentDisposition) {
    return null;
  }

  const encodedMatch = /filename\*=UTF-8''([^;]+)/i.exec(contentDisposition);
  const plainMatch = /filename="?([^";]+)"?/i.exec(contentDisposition);
  const rawFileName = encodedMatch?.[1] ?? plainMatch?.[1];

  if (!rawFileName) {
    return null;
  }

  try {
    return decodeURIComponent(rawFileName).replace(unsafeFileNameCharacters, '_');
  } catch {
    return rawFileName.replace(unsafeFileNameCharacters, '_');
  }
};

export const downloadFile = (
  download: BinaryDownload,
  fallbackFileName: string,
): void => {
  const objectUrl = URL.createObjectURL(download.blob);
  const anchor = document.createElement('a');
  anchor.href = objectUrl;
  anchor.download = download.fileName || fallbackFileName;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
};

export const buildExportFileName = (entityType: string, date = new Date()): string =>
  `${entityType}_${date.toISOString().slice(0, 10)}.xlsx`;
