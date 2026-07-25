import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

import type {
  AuthSession,
  AuthUser,
  Permission,
  RefreshTokenResponse,
  UserRole,
} from '../types/auth';
import { getPreferenceStorage } from '../utils/browserStorage';

interface AuthState {
  user: AuthUser | null;
  permissions: Permission[];
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isInitializing: boolean;
  sessionGeneration: number;
  setAuth: (session: AuthSession) => void;
  updateTokens: (tokens: RefreshTokenResponse) => void;
  updateIdentity: (user: AuthUser, permissions: Permission[]) => void;
  clearAuth: () => void;
  setInitializing: (isInitializing: boolean) => void;
  hasPermission: (permission: Permission) => boolean;
  hasRole: (roles: UserRole | readonly UserRole[]) => boolean;
}

const initialAuthState = {
  user: null,
  permissions: [],
  accessToken: null,
  refreshToken: null,
  isAuthenticated: false,
  isInitializing: true,
  sessionGeneration: 0,
} satisfies Pick<
  AuthState,
  | 'user'
  | 'permissions'
  | 'accessToken'
  | 'refreshToken'
  | 'isAuthenticated'
  | 'isInitializing'
  | 'sessionGeneration'
>;

/**
 * Phase 2 persists only the session identity and tokens through one isolated
 * storage boundary. Passwords are never part of this state. Production should
 * move refresh-token persistence to a Secure, HttpOnly, SameSite cookie.
 */
export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      ...initialAuthState,
      setAuth: (session) => {
        set((state) => ({
          user: session.user,
          permissions: session.permissions,
          accessToken: session.accessToken,
          refreshToken: session.refreshToken,
          isAuthenticated: true,
          isInitializing: false,
          sessionGeneration: state.sessionGeneration + 1,
        }));
      },
      updateTokens: (tokens) => {
        set((state) => ({
          accessToken: tokens.accessToken,
          refreshToken: tokens.refreshToken,
          user: tokens.user ?? state.user,
          permissions: tokens.permissions ?? state.permissions,
          isAuthenticated: true,
        }));
      },
      updateIdentity: (user, grantedPermissions) => {
        set({
          user,
          permissions: grantedPermissions,
          isAuthenticated: true,
        });
      },
      clearAuth: () => {
        set((state) => ({
          ...initialAuthState,
          isInitializing: false,
          sessionGeneration: state.sessionGeneration + 1,
        }));
      },
      setInitializing: (isInitializing) => {
        set({ isInitializing });
      },
      hasPermission: (permission) => get().permissions.includes(permission),
      hasRole: (roles) => {
        const currentRole = get().user?.role;
        const acceptedRoles = Array.isArray(roles) ? roles : [roles];
        return currentRole !== undefined && acceptedRoles.includes(currentRole);
      },
    }),
    {
      name: 'document-compliance-auth',
      storage: createJSONStorage(getPreferenceStorage),
      version: 1,
      partialize: (state) => ({
        user: state.user,
        permissions: state.permissions,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
      }),
    },
  ),
);

export const resetAuthStore = (): void => {
  useAuthStore.setState(initialAuthState);
};
