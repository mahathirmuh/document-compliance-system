import { ChevronRight, Folder, FolderPlus, Home, LoaderCircle } from 'lucide-react';
import { useMemo, useState } from 'react';

import { getApiErrorMessage } from '../../api/errors';
import {
  useSharePointFolders,
  useSharePointMappingMutations,
} from '../../hooks/useSharePointMappings';
import type { SharePointFolderItem } from '../../types/sharepoint';
import { Phase10Action, Phase10Empty, phase10InputClass } from '../phase10/Phase10Ui';

interface BrowserLocation {
  id: string | null;
  name: string;
  path: string;
}

export interface SharePointBrowserFolder extends SharePointFolderItem {
  path: string;
}

export function SharePointFolderBrowser({
  canCreateFolder,
  connectionId,
  initialPath = '',
  onSelect,
}: {
  connectionId: string;
  initialPath?: string;
  canCreateFolder: boolean;
  onSelect: (folder: SharePointBrowserFolder) => void;
}) {
  const [trail, setTrail] = useState<BrowserLocation[]>([
    { id: null, name: 'Root', path: initialPath },
  ]);
  const [newFolderName, setNewFolderName] = useState('');
  const current = trail[trail.length - 1]!;
  const queryParams = useMemo(
    () => ({
      connectionId,
      ...(current.id
        ? { parentItemId: current.id }
        : current.path
          ? { folderPath: current.path }
          : {}),
    }),
    [connectionId, current.id, current.path],
  );
  const query = useSharePointFolders(queryParams);
  const mutations = useSharePointMappingMutations();

  const openFolder = (folder: SharePointFolderItem): void => {
    const path = `${current.path.replace(/\/+$/, '')}/${folder.name}`.replace(
      /^\/+/,
      '',
    );
    setTrail((items) => [...items, { id: folder.id, name: folder.name, path }]);
  };

  const createFolder = async (): Promise<void> => {
    const name = newFolderName.trim();
    if (!name) {
      return;
    }
    const folder = await mutations.createFolder.mutateAsync({
      connectionId,
      parentItemId: current.id,
      name,
    });
    setNewFolderName('');
    await query.refetch();
    openFolder(folder);
  };

  return (
    <div className="space-y-4">
      <nav
        aria-label="SharePoint folder breadcrumb"
        className="flex flex-wrap items-center gap-1 rounded-xl bg-slate-50 p-3 text-xs"
      >
        {trail.map((location, index) => (
          <div
            key={`${location.id ?? 'root'}-${index}`}
            className="flex items-center gap-1"
          >
            {index > 0 && (
              <ChevronRight className="size-3 text-slate-400" aria-hidden="true" />
            )}
            <button
              type="button"
              onClick={() => {
                setTrail((items) => items.slice(0, index + 1));
              }}
              className="inline-flex items-center gap-1 rounded-lg px-2 py-1 font-semibold text-blue-700 hover:bg-blue-50"
            >
              {index === 0 && <Home className="size-3" aria-hidden="true" />}
              {location.name}
            </button>
          </div>
        ))}
      </nav>

      {canCreateFolder && (
        <form
          className="flex gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            void createFolder();
          }}
        >
          <input
            aria-label="New folder name"
            value={newFolderName}
            onChange={(event) => setNewFolderName(event.target.value)}
            placeholder="New folder name"
            className={phase10InputClass}
          />
          <button
            type="submit"
            disabled={!newFolderName.trim() || mutations.createFolder.isPending}
            className="inline-flex min-h-10 shrink-0 items-center gap-2 rounded-xl bg-blue-700 px-4 text-xs font-semibold text-white disabled:opacity-50"
          >
            <FolderPlus className="size-4" aria-hidden="true" />
            Create
          </button>
        </form>
      )}

      {query.isLoading && (
        <div
          aria-label="Loading SharePoint folders"
          className="grid h-48 place-items-center rounded-2xl bg-slate-50"
        >
          <LoaderCircle
            className="size-6 animate-spin text-blue-600"
            aria-hidden="true"
          />
        </div>
      )}
      {query.error && (
        <div role="alert" className="rounded-xl bg-rose-50 p-4 text-sm text-rose-700">
          {getApiErrorMessage(query.error, 'SharePoint folders could not be loaded.')}
        </div>
      )}
      {query.data && query.data.length === 0 && (
        <Phase10Empty>This folder has no child folders.</Phase10Empty>
      )}
      {query.data && query.data.length > 0 && (
        <ul className="divide-y divide-slate-100 overflow-hidden rounded-2xl border border-slate-200">
          {query.data.map((folder) => {
            const path = `${current.path.replace(/\/+$/, '')}/${folder.name}`.replace(
              /^\/+/,
              '',
            );
            return (
              <li
                key={folder.id}
                className="flex items-center justify-between gap-3 bg-white p-3"
              >
                <button
                  type="button"
                  onClick={() => openFolder(folder)}
                  className="flex min-w-0 flex-1 items-center gap-3 text-left"
                >
                  <Folder
                    className="size-5 shrink-0 text-amber-500"
                    aria-hidden="true"
                  />
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-semibold text-slate-900">
                      {folder.name}
                    </span>
                    <span className="block truncate text-[11px] text-slate-500">
                      {path}
                    </span>
                  </span>
                </button>
                <Phase10Action
                  label={`Select ${folder.name}`}
                  onClick={() => onSelect({ ...folder, path })}
                  tone="primary"
                />
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
