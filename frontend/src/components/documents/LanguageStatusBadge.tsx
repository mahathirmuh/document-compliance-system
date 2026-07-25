import { getLanguageStatusClass, languageStatusLabels } from './languageDisplay';
import type {
  LanguageDetectionJobStatus,
  LanguageDetectionRunStatus,
} from '../../types/languageDetection';

export function LanguageStatusBadge({
  status,
}: {
  status: LanguageDetectionJobStatus | LanguageDetectionRunStatus;
}) {
  const label =
    status in languageStatusLabels
      ? languageStatusLabels[status as LanguageDetectionJobStatus]
      : status;
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-[10px] font-semibold ring-1 ring-inset ${getLanguageStatusClass(
        status as LanguageDetectionJobStatus,
      )}`}
    >
      {label}
    </span>
  );
}
