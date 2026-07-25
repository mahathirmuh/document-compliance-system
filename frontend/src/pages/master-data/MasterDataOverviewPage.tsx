import {
  Building2,
  FileType2,
  Layers3,
  Plus,
  ShieldCheck,
  Upload,
  Workflow,
  type LucideIcon,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router';

import { MasterDataImportDialog } from '../../components/master-data/MasterDataImportDialog';
import { MasterDataPageHeader } from '../../components/master-data/MasterDataPageHeader';
import { getApiErrorMessage } from '../../api/errors';
import { useMasterDataOverview } from '../../hooks/useMasterDataOverview';
import { useAuthStore } from '../../store/authStore';
import type { MasterDataOverview, OverviewCount } from '../../types/masterData';

interface OverviewCardDefinition {
  key: keyof MasterDataOverview;
  label: string;
  path: string;
  icon: LucideIcon;
}

const cards: readonly OverviewCardDefinition[] = [
  {
    key: 'departments',
    label: 'Departments',
    path: '/master-data/departments',
    icon: Building2,
  },
  {
    key: 'sections',
    label: 'Sections',
    path: '/master-data/sections',
    icon: Layers3,
  },
  {
    key: 'documentTypes',
    label: 'Document Types',
    path: '/master-data/document-types',
    icon: FileType2,
  },
  {
    key: 'documentStatuses',
    label: 'Document Statuses',
    path: '/master-data/document-statuses',
    icon: Workflow,
  },
  {
    key: 'validationRules',
    label: 'Validation Rules',
    path: '/master-data/validation-rules',
    icon: ShieldCheck,
  },
];

export function MasterDataOverviewPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [isImportOpen, setImportOpen] = useState(false);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canCreate = hasPermission('master_data:create');
  const overview = useMasterDataOverview();

  useEffect(() => {
    if (searchParams.get('action') !== 'import' || !canCreate) {
      return;
    }
    setImportOpen(true);
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current);
        next.delete('action');
        return next;
      },
      { replace: true },
    );
  }, [canCreate, searchParams, setSearchParams]);

  return (
    <div className="space-y-6">
      <MasterDataPageHeader
        title="Master Data Overview"
        description="Maintain the controlled reference data used throughout document compliance workflows."
        actions={
          canCreate ? (
            <button
              type="button"
              onClick={() => setImportOpen(true)}
              className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white transition hover:bg-blue-800"
            >
              <Upload className="size-4" aria-hidden="true" />
              Import Master Data
            </button>
          ) : undefined
        }
      />

      {overview.isError && (
        <div
          role="alert"
          className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"
        >
          {getApiErrorMessage(
            overview.error,
            'Master data overview could not be loaded.',
          )}
          <button
            type="button"
            onClick={() => void overview.refetch()}
            className="ml-3 font-semibold underline"
          >
            Try again
          </button>
        </div>
      )}

      <section
        className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5"
        aria-label="Master data totals"
      >
        {cards.map((card) => (
          <OverviewCard
            key={card.key}
            definition={card}
            counts={overview.data?.[card.key]}
            isLoading={overview.isLoading}
          />
        ))}
      </section>

      {canCreate && (
        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <h2 className="text-lg font-semibold text-slate-950">Quick actions</h2>
          <p className="mt-1 text-sm text-slate-500">
            Add common reference data or start a validated spreadsheet import.
          </p>
          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {[
              {
                label: 'Add Department',
                path: '/master-data/departments?action=create',
              },
              { label: 'Add Section', path: '/master-data/sections?action=create' },
              {
                label: 'Add Document Type',
                path: '/master-data/document-types?action=create',
              },
            ].map(({ label, path }) => (
              <Link
                key={label}
                to={path}
                className="flex min-h-12 items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 text-sm font-semibold text-slate-700 transition hover:border-blue-300 hover:bg-blue-50 hover:text-blue-800"
              >
                <Plus className="size-4 text-blue-700" aria-hidden="true" />
                {label}
              </Link>
            ))}
            <button
              type="button"
              onClick={() => setImportOpen(true)}
              className="flex min-h-12 items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 text-left text-sm font-semibold text-slate-700 transition hover:border-blue-300 hover:bg-blue-50 hover:text-blue-800"
            >
              <Upload className="size-4 text-blue-700" aria-hidden="true" />
              Import Master Data
            </button>
          </div>
        </section>
      )}

      <MasterDataImportDialog
        isOpen={isImportOpen}
        onClose={() => setImportOpen(false)}
      />
    </div>
  );
}

function OverviewCard({
  counts,
  definition: { icon: Icon, label, path },
  isLoading,
}: {
  definition: OverviewCardDefinition;
  counts: OverviewCount | undefined;
  isLoading: boolean;
}) {
  return (
    <Link
      to={path}
      className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-blue-300 hover:shadow-md"
    >
      <div className="grid size-10 place-items-center rounded-xl bg-blue-50 text-blue-700">
        <Icon className="size-4.5" aria-hidden="true" />
      </div>
      <h2 className="mt-4 text-sm font-semibold text-slate-950 group-hover:text-blue-800">
        {label}
      </h2>
      {isLoading ? (
        <div className="mt-4 h-8 w-16 animate-pulse rounded bg-slate-100" />
      ) : (
        <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
          {counts?.total ?? 0}
        </p>
      )}
      <div className="mt-3 flex gap-3 text-[11px] text-slate-500">
        <span>
          <strong className="text-emerald-700">{counts?.active ?? 0}</strong> active
        </span>
        <span>
          <strong className="text-slate-700">{counts?.inactive ?? 0}</strong> inactive
        </span>
      </div>
    </Link>
  );
}
