import { languageClasses, languageShortLabels } from './languageDisplay';
import type { LanguageCode } from '../../types/languageDetection';

export function LanguageBadge({ code }: { code: LanguageCode }) {
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-[10px] font-semibold ring-1 ring-inset ${languageClasses[code]}`}
    >
      {languageShortLabels[code]}
    </span>
  );
}
