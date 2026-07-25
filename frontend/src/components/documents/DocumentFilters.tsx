import { RotateCcw, Search, SlidersHorizontal, X } from 'lucide-react';
import { useEffect, useState } from 'react';

import type { DocumentFormBaseOption } from '../../types/documentFormOptions';

export interface DocumentFilterValues {
  search: string;
  departmentId: string;
  sectionId: string;
  documentTypeId: string;
  documentStatusId: string;
  revisionCode: string;
  hasSharePointUrl: boolean | undefined;
  createdFrom: string;
  createdTo: string;
  effectiveFrom: string;
  effectiveTo: string;
}

interface DocumentFiltersProps {
  values: DocumentFilterValues;
  departments: readonly DocumentFormBaseOption[];
  sections: readonly DocumentFormBaseOption[];
  documentTypes: readonly DocumentFormBaseOption[];
  documentStatuses: readonly DocumentFormBaseOption[];
  isLoadingSections?: boolean;
  onChange: (updates: Partial<DocumentFilterValues>) => void;
  onReset: () => void;
}

const selectClassName =
  'min-h-10 w-full rounded-xl border border-slate-300 bg-white px-3 text-xs font-medium text-slate-700 outline-none transition focus:border-blue-600 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-100';

export function DocumentFilters({
  departments,
  documentStatuses,
  documentTypes,
  isLoadingSections = false,
  onChange,
  onReset,
  sections,
  values,
}: DocumentFiltersProps) {
  const [searchDraft, setSearchDraft] = useState(values.search);
  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => setSearchDraft(values.search), [values.search]);

  useEffect(() => {
    if (searchDraft.trim() === values.search) {
      return;
    }
    const timeout = window.setTimeout(
      () => onChange({ search: searchDraft.trim() }),
      400,
    );
    return () => window.clearTimeout(timeout);
  }, [onChange, searchDraft, values.search]);

  return (
    <section
      className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
      aria-label="Document filters"
    >
      <div className="grid gap-3 lg:grid-cols-[minmax(16rem,1fr)_repeat(3,minmax(10rem,0.42fr))_auto]">
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400"
            aria-hidden="true"
          />
          <input
            type="search"
            value={searchDraft}
            onChange={(event) => setSearchDraft(event.target.value)}
            placeholder="Search code, title, owner, or reference"
            aria-label="Search documents"
            className="min-h-10 w-full rounded-xl border border-slate-300 pl-10 pr-9 text-sm outline-none transition focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
          />
          {searchDraft && (
            <button
              type="button"
              onClick={() => {
                setSearchDraft('');
                onChange({ search: '' });
              }}
              aria-label="Clear document search"
              className="absolute right-2 top-1/2 grid size-7 -translate-y-1/2 place-items-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            >
              <X className="size-3.5" aria-hidden="true" />
            </button>
          )}
        </div>
        <select
          value={values.departmentId}
          onChange={(event) =>
            onChange({ departmentId: event.target.value, sectionId: '' })
          }
          aria-label="Filter by department"
          className={selectClassName}
        >
          <option value="">All departments</option>
          {departments.map((department) => (
            <option key={department.id} value={department.id}>
              {department.code} — {department.name}
            </option>
          ))}
        </select>
        <select
          value={values.sectionId}
          onChange={(event) => onChange({ sectionId: event.target.value })}
          aria-label="Filter by section"
          className={selectClassName}
          disabled={!values.departmentId || isLoadingSections}
        >
          <option value="">
            {!values.departmentId
              ? 'Choose department first'
              : isLoadingSections
                ? 'Loading sections...'
                : 'All sections'}
          </option>
          {sections.map((section) => (
            <option key={section.id} value={section.id}>
              {section.code} — {section.name}
            </option>
          ))}
        </select>
        <select
          value={values.documentTypeId}
          onChange={(event) => onChange({ documentTypeId: event.target.value })}
          aria-label="Filter by document type"
          className={selectClassName}
        >
          <option value="">All document types</option>
          {documentTypes.map((documentType) => (
            <option key={documentType.id} value={documentType.id}>
              {documentType.code} — {documentType.name}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => setShowAdvanced((current) => !current)}
          aria-expanded={showAdvanced}
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-slate-300 px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50"
        >
          <SlidersHorizontal className="size-3.5" aria-hidden="true" />
          More
        </button>
      </div>

      {showAdvanced && (
        <div className="mt-4 grid gap-3 border-t border-slate-200 pt-4 sm:grid-cols-2 lg:grid-cols-4">
          <select
            value={values.documentStatusId}
            onChange={(event) => onChange({ documentStatusId: event.target.value })}
            aria-label="Filter by document status"
            className={selectClassName}
          >
            <option value="">All document statuses</option>
            {documentStatuses.map((status) => (
              <option key={status.id} value={status.id}>
                {status.code} — {status.name}
              </option>
            ))}
          </select>
          <input
            value={values.revisionCode}
            onChange={(event) => onChange({ revisionCode: event.target.value })}
            aria-label="Filter by revision"
            placeholder="Revision, e.g. Rev.001"
            className={selectClassName}
          />
          <select
            value={
              values.hasSharePointUrl === undefined
                ? 'all'
                : values.hasSharePointUrl
                  ? 'linked'
                  : 'unlinked'
            }
            onChange={(event) =>
              onChange({
                hasSharePointUrl:
                  event.target.value === 'all'
                    ? undefined
                    : event.target.value === 'linked',
              })
            }
            aria-label="Filter by SharePoint link"
            className={selectClassName}
          >
            <option value="all">Any SharePoint status</option>
            <option value="linked">Has SharePoint link</option>
            <option value="unlinked">No SharePoint link</option>
          </select>
          <button
            type="button"
            onClick={onReset}
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-slate-300 px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            <RotateCcw className="size-3.5" aria-hidden="true" />
            Reset filters
          </button>
          <DateFilter
            label="Created from"
            value={values.createdFrom}
            onChange={(createdFrom) => onChange({ createdFrom })}
          />
          <DateFilter
            label="Created to"
            value={values.createdTo}
            onChange={(createdTo) => onChange({ createdTo })}
          />
          <DateFilter
            label="Effective from"
            value={values.effectiveFrom}
            onChange={(effectiveFrom) => onChange({ effectiveFrom })}
          />
          <DateFilter
            label="Effective to"
            value={values.effectiveTo}
            onChange={(effectiveTo) => onChange({ effectiveTo })}
          />
        </div>
      )}
    </section>
  );
}

function DateFilter({
  label,
  onChange,
  value,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-500">
      {label}
      <input
        type="date"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={`${selectClassName} mt-1.5 normal-case`}
      />
    </label>
  );
}
