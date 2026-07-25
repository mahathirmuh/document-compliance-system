import type {
  LanguageCode,
  LanguageDetectionJobStatus,
  LanguagePresenceStatus,
} from '../../types/languageDetection';
import { languageLabels } from '../../types/languageDetection';

export const languageStatusLabels: Record<LanguageDetectionJobStatus, string> = {
  QUEUED: 'Queued',
  LOADING_CONTENT: 'Loading Content',
  DETECTING: 'Detecting',
  AGGREGATING: 'Aggregating',
  PERSISTING: 'Persisting',
  COMPLETED: 'Completed',
  PARTIALLY_COMPLETED: 'Partially Completed',
  FAILED: 'Failed',
  CANCEL_REQUESTED: 'Cancel Requested',
  CANCELLED: 'Cancelled',
};

export const getLanguageStatusClass = (status: LanguageDetectionJobStatus): string => {
  if (status === 'COMPLETED') {
    return 'bg-emerald-50 text-emerald-800 ring-emerald-200';
  }
  if (status === 'PARTIALLY_COMPLETED') {
    return 'bg-amber-50 text-amber-800 ring-amber-200';
  }
  if (status === 'FAILED') {
    return 'bg-rose-50 text-rose-800 ring-rose-200';
  }
  if (status === 'CANCELLED') {
    return 'bg-slate-100 text-slate-700 ring-slate-200';
  }
  if (status === 'CANCEL_REQUESTED') {
    return 'bg-orange-50 text-orange-800 ring-orange-200';
  }
  return 'bg-blue-50 text-blue-800 ring-blue-200';
};

export const languageClasses: Record<LanguageCode, string> = {
  id: 'bg-blue-50 text-blue-800 ring-blue-200',
  en: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  zh: 'bg-rose-50 text-rose-800 ring-rose-200',
  mixed: 'bg-violet-50 text-violet-800 ring-violet-200',
  unknown: 'bg-slate-100 text-slate-700 ring-slate-200',
  other: 'bg-amber-50 text-amber-800 ring-amber-200',
};

export const languageShortLabels: Record<LanguageCode, string> = {
  id: 'ID · Bahasa Indonesia',
  en: 'EN · English',
  zh: 'ZH · 中文 / Mandarin',
  mixed: 'Mixed',
  unknown: 'Unknown',
  other: 'Other',
};

export const presenceLabels: Record<LanguagePresenceStatus, string> = {
  PRESENT: 'Present',
  NOT_PRESENT: 'Not Present',
  INSUFFICIENT_EVIDENCE: 'Insufficient Evidence',
};

export const getPresenceClass = (status: LanguagePresenceStatus): string => {
  if (status === 'PRESENT') {
    return 'text-emerald-800 bg-emerald-50';
  }
  if (status === 'NOT_PRESENT') {
    return 'text-slate-700 bg-slate-100';
  }
  return 'text-amber-800 bg-amber-50';
};

export const formatLanguageCode = (code: LanguageCode): string => languageLabels[code];
