import { useQuery } from '@tanstack/react-query';

import { fetchHealth } from '../api/health';
import { appConfig } from '../config/app';

export const healthQueryKey = ['service-health'] as const;

export const useHealthCheck = () =>
  useQuery({
    queryKey: healthQueryKey,
    queryFn: fetchHealth,
    retry: import.meta.env.MODE === 'test' ? false : 1,
    retryDelay: 1_000,
    refetchInterval: appConfig.healthRefreshIntervalMs,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    staleTime: 10_000,
  });
