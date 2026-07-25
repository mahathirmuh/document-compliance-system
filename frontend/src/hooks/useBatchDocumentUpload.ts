import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import {
  cancelUploadSession,
  confirmBatchUpload,
  uploadBatchFiles,
} from '../api/documentUploadApi';
import type { UploadConfirmationRequest } from '../types/documentUpload';
import { estimateBatchFileProgress } from '../utils/documentFiles';
import { documentFileKeys } from './documentFileQueryKeys';
import { documentKeys } from './documentQueryKeys';
import { useDocumentSession } from './useDocumentSession';

interface ConfirmBatchVariables {
  sessionId: string;
  payload: UploadConfirmationRequest;
}

export const useBatchDocumentUpload = () => {
  const [progress, setProgress] = useState(0);
  const [fileProgress, setFileProgress] = useState<number[]>([]);
  const scope = useDocumentSession();
  const queryClient = useQueryClient();

  const upload = useMutation({
    mutationFn: (files: readonly File[]) => {
      setProgress(0);
      setFileProgress(files.map(() => 0));
      return uploadBatchFiles(files, {
        onProgress: (nextProgress) => {
          setProgress(nextProgress);
          setFileProgress(estimateBatchFileProgress(files, nextProgress));
        },
      });
    },
    onSuccess: (_preview, files) => {
      setProgress(100);
      setFileProgress(files.map(() => 100));
    },
  });

  const confirm = useMutation({
    mutationFn: ({ payload, sessionId }: ConfirmBatchVariables) =>
      confirmBatchUpload(sessionId, payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: documentFileKeys.all(scope) }),
        queryClient.invalidateQueries({ queryKey: documentKeys.all(scope) }),
      ]);
    },
  });

  const cancel = useMutation({
    mutationFn: cancelUploadSession,
  });

  const reset = (): void => {
    setProgress(0);
    setFileProgress([]);
    upload.reset();
    confirm.reset();
    cancel.reset();
  };

  return { progress, fileProgress, upload, confirm, cancel, reset } as const;
};
