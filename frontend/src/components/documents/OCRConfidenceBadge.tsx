import { formatConfidence } from './ocrDisplay';
import { getOCRConfidenceCategory } from '../../types/ocr';

export function OCRConfidenceBadge({
  confidence,
  lowConfidenceThreshold,
  label = true,
  reviewConfidenceThreshold,
}: {
  confidence: number | null;
  lowConfidenceThreshold: number;
  label?: boolean;
  reviewConfidenceThreshold: number;
}) {
  if (confidence === null) {
    return (
      <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-semibold text-slate-600">
        Confidence unavailable
      </span>
    );
  }

  const category = getOCRConfidenceCategory(
    confidence,
    lowConfidenceThreshold,
    reviewConfidenceThreshold,
  );
  const details = {
    HIGH: {
      label: 'High Confidence',
      className: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
    },
    REVIEW: {
      label: 'Needs Review',
      className: 'bg-amber-50 text-amber-800 ring-amber-200',
    },
    LOW: {
      label: 'Low Confidence',
      className: 'bg-rose-50 text-rose-800 ring-rose-200',
    },
  }[category];

  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-[10px] font-semibold ring-1 ring-inset ${details.className}`}
    >
      {label ? `${details.label} · ` : ''}
      {formatConfidence(confidence)}
    </span>
  );
}
