import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

import { getPreferenceStorage } from '../utils/browserStorage';

interface UiState {
  isSidebarCollapsed: boolean;
  isMobileSidebarOpen: boolean;
  toggleSidebar: () => void;
  toggleMobileSidebar: () => void;
  closeMobileSidebar: () => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      isSidebarCollapsed: false,
      isMobileSidebarOpen: false,
      toggleSidebar: () => {
        set((state) => ({ isSidebarCollapsed: !state.isSidebarCollapsed }));
      },
      toggleMobileSidebar: () => {
        set((state) => ({
          isMobileSidebarOpen: !state.isMobileSidebarOpen,
        }));
      },
      closeMobileSidebar: () => {
        set({ isMobileSidebarOpen: false });
      },
    }),
    {
      name: 'document-compliance-ui',
      storage: createJSONStorage(getPreferenceStorage),
      partialize: (state) => ({
        isSidebarCollapsed: state.isSidebarCollapsed,
      }),
    },
  ),
);
