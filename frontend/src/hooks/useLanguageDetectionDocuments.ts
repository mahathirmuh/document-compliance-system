import { useQuery } from '@tanstack/react-query';

import { listLanguageDetectionDocuments } from '../api/languageDetectionApi';
import {
  isActiveLanguageDetectionStatus,
  type LanguageDetectionDocumentListParams,
} from '../types/languageDetection';
import { languageDetectionKeys } from './languageDetectionQueryKeys';
import { useDocumentSession } from './useDocumentSession';

const pollIntervalMs = 3_000;

export const useLanguageDetectionDocuments = (
  params: LanguageDetectionDocumentListParams,
  options: { enabled?: boolean; pollActive?: boolean } = {},
) => {
  const scope = useDocumentSession();
  return useQuery({
    queryKey: languageDetectionKeys.documentList(scope, params),
    queryFn: ({ signal }) => listLanguageDetectionDocuments(params, signal),
    enabled: options.enabled ?? true,
    placeholderData: (previous) => previous,
    refetchInterval: (state) =>
      options.pollActive &&
      state.state.data?.items.some(
        (item) =>
          item.languageDetectionStatus !== null &&
          isActiveLanguageDetectionStatus(item.languageDetectionStatus),
      )
        ? pollIntervalMs
        : false,
  });
};
