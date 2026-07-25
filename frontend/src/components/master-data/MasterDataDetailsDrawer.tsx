import type { ReactNode } from 'react';

import { MasterDataFormDrawer } from './MasterDataFormDrawer';

export interface DetailField {
  label: string;
  value: ReactNode;
  fullWidth?: boolean;
}

interface MasterDataDetailsDrawerProps {
  isOpen: boolean;
  title: string;
  subtitle?: string | undefined;
  fields: readonly DetailField[];
  onClose: () => void;
}

export function MasterDataDetailsDrawer({
  fields,
  isOpen,
  onClose,
  subtitle,
  title,
}: MasterDataDetailsDrawerProps) {
  return (
    <MasterDataFormDrawer
      isOpen={isOpen}
      onClose={onClose}
      title={title}
      {...(subtitle ? { description: subtitle } : {})}
    >
      <dl className="grid gap-4 sm:grid-cols-2">
        {fields.map((field) => (
          <div
            key={field.label}
            className={`rounded-xl border border-slate-200 bg-slate-50 p-3 ${
              field.fullWidth ? 'sm:col-span-2' : ''
            }`}
          >
            <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              {field.label}
            </dt>
            <dd className="mt-1 break-words text-sm font-medium text-slate-800">
              {field.value}
            </dd>
          </div>
        ))}
      </dl>
    </MasterDataFormDrawer>
  );
}
