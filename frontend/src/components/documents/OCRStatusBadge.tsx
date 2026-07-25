import { getOCRStatusClass, ocrPageStatusLabels, ocrStatusLabels } from './ocrDisplay';
import type { OCRJobStatus, OCRPageStatus, OCRRunStatus } from '../../types/ocr';

export function OCRStatusBadge({
  status,
}: {
  status: OCRJobStatus | OCRRunStatus | OCRPageStatus;
}) {
  const label =
    status in ocrStatusLabels
      ? ocrStatusLabels[status as OCRJobStatus]
      : (ocrPageStatusLabels[status as OCRPageStatus] ??
        status
          .toLowerCase()
          .split('_')
          .map((word) => `${word.charAt(0).toUpperCase()}${word.slice(1)}`)
          .join(' '));

  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-[10px] font-semibold ring-1 ring-inset ${getOCRStatusClass(
        status as OCRJobStatus | OCRPageStatus,
      )}`}
    >
      {label}
    </span>
  );
}
