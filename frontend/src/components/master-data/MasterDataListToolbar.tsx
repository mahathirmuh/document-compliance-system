import { Search, X } from 'lucide-react';
import { useEffect, useState, type FormEvent, type ReactNode } from 'react';

interface MasterDataListToolbarProps {
  search: string;
  onSearchChange: (search: string) => void;
  isActive: boolean | undefined;
  onIsActiveChange: (isActive: boolean | undefined) => void;
  children?: ReactNode;
}

export function MasterDataListToolbar({
  children,
  isActive,
  onIsActiveChange,
  onSearchChange,
  search,
}: MasterDataListToolbarProps) {
  const [draft, setDraft] = useState(search);

  useEffect(() => setDraft(search), [search]);

  const submitSearch = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    onSearchChange(draft.trim());
  };

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm lg:flex-row lg:items-center">
      <form onSubmit={submitSearch} role="search" className="relative min-w-0 flex-1">
        <Search
          className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400"
          aria-hidden="true"
        />
        <input
          type="search"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Search code, name, or description"
          aria-label="Search master data"
          className="min-h-11 w-full rounded-xl border border-slate-300 bg-white pl-10 pr-10 text-sm text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
        />
        {draft && (
          <button
            type="button"
            onClick={() => {
              setDraft('');
              onSearchChange('');
            }}
            aria-label="Clear search"
            className="absolute right-2.5 top-1/2 grid size-7 -translate-y-1/2 place-items-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            <X className="size-3.5" aria-hidden="true" />
          </button>
        )}
      </form>
      <select
        value={isActive === undefined ? 'all' : isActive ? 'active' : 'inactive'}
        onChange={(event) => {
          const value = event.target.value;
          onIsActiveChange(value === 'all' ? undefined : value === 'active');
        }}
        aria-label="Filter by status"
        className="min-h-11 rounded-xl border border-slate-300 bg-white px-3.5 text-sm font-medium text-slate-700 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
      >
        <option value="all">All statuses</option>
        <option value="active">Active</option>
        <option value="inactive">Inactive</option>
      </select>
      {children}
    </div>
  );
}
