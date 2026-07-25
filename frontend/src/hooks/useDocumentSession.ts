import { useAuthStore } from '../store/authStore';
import type { DocumentSessionScope } from './documentQueryKeys';

export const useDocumentSession = (): DocumentSessionScope => {
  const userId = useAuthStore((state) => state.user?.id ?? 'anonymous');
  const generation = useAuthStore((state) => state.sessionGeneration);
  return [userId, generation] as const;
};
