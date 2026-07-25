import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import {
  cancelUploadSession,
  confirmSingleUpload,
  uploadSingleFile,
} from '../api/documentUploadApi';
import type { UploadConfirmationRequest } from '../types/documentUpload';
import { documentFileKeys } from './documentFileQueryKeys';
import { documentKeys } from './documentQueryKeys';
import { useDocumentSession } from './useDocumentSession';

interface UploadSingleVariables {
  file: File;
  documentId?: string;
  revisionId?: string;
}

interface ConfirmSingleVariables {
  sessionId: string;
  payload: UploadConfirmationRequest;
}

export const useDocumentUpload = () => {
  const [progress, setProgress] = useState(0);
  const scope = useDocumentSession();
  const queryClient = useQueryClient();

  const invalidateFileState = async (): Promise<void> => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: documentFileKeys.all(scope) }),
      queryClient.invalidateQueries({ queryKey: documentKeys.all(scope) }),
    ]);
  };

  const upload = useMutation({
    mutationFn: ({ documentId, file, revisionId }: UploadSingleVariables) => {
      setProgress(0);
      return uploadSingleFile(file, {
        ...(documentId ? { documentId } : {}),
        ...(revisionId ? { revisionId } : {}),
        onProgress: setProgress,
      });
    },
    onSuccess: () => setProgress(100),
  });

  const confirm = useMutation({
    mutationFn: ({ payload, sessionId }: ConfirmSingleVariables) =>
      confirmSingleUpload(sessionId, payload),
    onSuccess: invalidateFileState,
  });

  const cancel = useMutation({
    mutationFn: cancelUploadSession,
    onSuccess: invalidateFileState,
  });

  const reset = (): void => {
    setProgress(0);
    upload.reset();
    confirm.reset();
    cancel.reset();
  };

  return {
    progress,
    upload,
    confirm,
    cancel,
    reset,
  } as const;
};
