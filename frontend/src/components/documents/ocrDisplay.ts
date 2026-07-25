import type {
  OCRJobStatus,
  OCRLanguageProfile,
  OCRPageStatus,
  OCRPreprocessingProfile,
} from '../../types/ocr';

export const ocrStatusLabels: Record<OCRJobStatus, string> = {
  QUEUED: 'Queued',
  INSPECTING: 'Inspecting',
  RENDERING: 'Rendering',
  PREPROCESSING: 'Preprocessing',
  RECOGNISING: 'Recognising',
  MERGING: 'Merging',
  PERSISTING: 'Persisting',
  COMPLETED: 'Completed',
  PARTIALLY_COMPLETED: 'Partially Completed',
  FAILED: 'Failed',
  CANCEL_REQUESTED: 'Cancel Requested',
  CANCELLED: 'Cancelled',
};

export const ocrPageStatusLabels: Record<OCRPageStatus, string> = {
  COMPLETED: 'Completed',
  LOW_CONFIDENCE: 'Low Confidence',
  NO_TEXT_FOUND: 'No Text Found',
  FAILED: 'Failed',
  SKIPPED: 'Skipped',
};

export const ocrProfileLabels: Record<OCRLanguageProfile, string> = {
  LATIN: 'Latin (Indonesian / English)',
  CHINESE_SIMPLIFIED: 'Chinese Simplified',
  AUTO_MULTILINGUAL: 'Automatic Multilingual',
};

export const ocrPreprocessingLabels: Record<OCRPreprocessingProfile, string> = {
  NONE: 'None',
  STANDARD: 'Standard',
  AGGRESSIVE: 'Aggressive',
};

export const getOCRStatusClass = (status: OCRJobStatus | OCRPageStatus): string => {
  if (status === 'COMPLETED') {
    return 'bg-emerald-50 text-emerald-800 ring-emerald-200';
  }
  if (status === 'PARTIALLY_COMPLETED' || status === 'LOW_CONFIDENCE') {
    return 'bg-amber-50 text-amber-800 ring-amber-200';
  }
  if (status === 'FAILED') {
    return 'bg-rose-50 text-rose-800 ring-rose-200';
  }
  if (status === 'CANCELLED' || status === 'SKIPPED') {
    return 'bg-slate-100 text-slate-700 ring-slate-200';
  }
  if (status === 'CANCEL_REQUESTED' || status === 'NO_TEXT_FOUND') {
    return 'bg-orange-50 text-orange-800 ring-orange-200';
  }
  return 'bg-blue-50 text-blue-800 ring-blue-200';
};

export const formatConfidence = (value: number | null): string =>
  value === null ? '—' : `${Math.round(value * 100)}%`;
