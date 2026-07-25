import { useAuthStore } from '../store/authStore';
import type { SessionQueryScope } from './masterDataQueryKeys';

export const useMasterDataSession = (): SessionQueryScope => {
  const userId = useAuthStore((state) => state.user?.id ?? 'anonymous');
  const generation = useAuthStore((state) => state.sessionGeneration);
  return [userId, generation] as const;
};
