import { FileText, Sheet } from 'lucide-react';

import type { ExtractedContainer } from '../../types/extractedContent';

const getContainerLabel = (container: ExtractedContainer): string => {
  if (container.containerType === 'PDF_PAGE') {
    return container.title || `Page ${container.containerIndex}`;
  }
  if (container.containerType === 'XLSX_WORKSHEET') {
    return container.name || `Worksheet ${container.containerIndex}`;
  }
  if (container.containerType === 'DOCX_BODY') {
    return container.title || 'Document body';
  }
  const part = container.containerType === 'DOCX_HEADER' ? 'Header' : 'Footer';
  return container.name || `${part} ${container.containerIndex}`;
};

export function ContainerNavigator({
  containers,
  onSelect,
  selectedId,
}: {
  containers: readonly ExtractedContainer[];
  selectedId: string | null;
  onSelect: (container: ExtractedContainer) => void;
}) {
  if (containers.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-slate-300 p-5 text-center text-xs text-slate-500">
        No extracted containers are available.
      </p>
    );
  }
  return (
    <nav aria-label="Extracted content containers">
      <ul className="space-y-1.5">
        {containers.map((container) => {
          const Icon = container.containerType === 'XLSX_WORKSHEET' ? Sheet : FileText;
          const selected = container.id === selectedId;
          return (
            <li key={container.id}>
              <button
                type="button"
                onClick={() => onSelect(container)}
                aria-current={selected ? 'page' : undefined}
                className={`flex min-h-10 w-full items-center gap-2 rounded-xl px-3 text-left text-xs font-semibold transition ${
                  selected
                    ? 'bg-blue-700 text-white'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-950'
                }`}
              >
                <Icon className="size-3.5 shrink-0" aria-hidden="true" />
                <span className="truncate">{getContainerLabel(container)}</span>
                <span
                  className={`ml-auto text-[10px] ${
                    selected ? 'text-blue-100' : 'text-slate-400'
                  }`}
                >
                  {container.wordCount.toLocaleString()}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
