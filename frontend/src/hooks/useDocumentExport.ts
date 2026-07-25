import { useMutation } from '@tanstack/react-query';

import { exportDocumentRegister } from '../api/documentExportApi';
import type { DocumentExportParams } from '../types/document';

export const useDocumentExport = () =>
  useMutation({
    mutationFn: (params: DocumentExportParams) => exportDocumentRegister(params),
  });
