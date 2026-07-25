import { Download } from 'lucide-react';

import { getApiErrorMessage } from '../../api/errors';
import { useMasterDataImport } from '../../hooks/useMasterDataImport';
import { useToast } from '../../providers/useToast';
import type { MasterDataEntityType } from '../../types/masterData';
import { buildExportFileName, downloadFile } from '../../utils/downloadFile';

interface MasterDataExportButtonProps {
  entityType: MasterDataEntityType;
  params?: Record<string, string | number | boolean>;
}

export function MasterDataExportButton({
  entityType,
  params,
}: MasterDataExportButtonProps) {
  const { exportXlsx } = useMasterDataImport();
  const { showToast } = useToast();

  const exportRecords = async (): Promise<void> => {
    try {
      const result = await exportXlsx.mutateAsync({
        entityType,
        ...(params ? { params } : {}),
      });
      downloadFile(result, buildExportFileName(entityType));
      showToast({
        tone: 'success',
        title: 'Export ready',
        message: 'The XLSX download has started.',
      });
    } catch (error: unknown) {
      showToast({
        tone: 'error',
        title: 'Export failed',
        message: getApiErrorMessage(error, 'The XLSX export could not be created.'),
      });
    }
  };

  return (
    <button
      type="button"
      onClick={() => void exportRecords()}
      disabled={exportXlsx.isPending}
      className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-3.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-60"
    >
      <Download className="size-4" aria-hidden="true" />
      {exportXlsx.isPending ? 'Exporting...' : 'Export XLSX'}
    </button>
  );
}
