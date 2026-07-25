import type { ExtractionJobStatus, ExtractionRunStatus } from '../../types/extraction';

type DisplayStatus = ExtractionJobStatus | ExtractionRunStatus;

export const extractionStatusLabel = (status: DisplayStatus): string =>
  status
    .toLowerCase()
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
