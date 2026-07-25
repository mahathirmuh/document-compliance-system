import { useQuery } from '@tanstack/react-query';

import { masterDataApi } from '../api/masterDataApi';
import { masterDataKeys } from './masterDataQueryKeys';
import { useMasterDataSession } from './useMasterDataSession';

export const useMasterDataOverview = () => {
  const scope = useMasterDataSession();

  return useQuery({
    queryKey: masterDataKeys.overview(scope),
    queryFn: masterDataApi.getOverview,
    staleTime: 30_000,
  });
};
