import { useEffect, useRef, type PropsWithChildren } from 'react';

import { authApi } from '../api/authApi';
import { FullScreenLoader } from '../components/common/FullScreenLoader';
import { useAuthStore } from '../store/authStore';

export function AuthProvider({ children }: PropsWithChildren) {
  const isInitializing = useAuthStore((state) => state.isInitializing);
  const initializationStarted = useRef(false);

  useEffect(() => {
    if (initializationStarted.current) {
      return;
    }
    initializationStarted.current = true;

    const initializeSession = async (): Promise<void> => {
      const { accessToken, refreshToken, clearAuth, setInitializing, updateIdentity } =
        useAuthStore.getState();

      if (!accessToken && !refreshToken) {
        clearAuth();
        return;
      }

      try {
        const currentUser = await authApi.getCurrentUser();
        updateIdentity(currentUser.user, currentUser.permissions);
      } catch {
        clearAuth();
      } finally {
        setInitializing(false);
      }
    };

    void initializeSession();
  }, []);

  if (isInitializing) {
    return <FullScreenLoader message="Restoring your secure session..." />;
  }

  return children;
}
