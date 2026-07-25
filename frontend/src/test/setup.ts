import '@testing-library/jest-dom/vitest';

import { cleanup } from '@testing-library/react';
import { afterEach, beforeEach } from 'vitest';

import { resetAuthStore } from '../store/authStore';
import { useUiStore } from '../store/uiStore';

const resetClientState = (): void => {
  resetAuthStore();
  useUiStore.setState({
    isSidebarCollapsed: false,
    isMobileSidebarOpen: false,
  });
  window.localStorage.clear();
};

beforeEach(() => {
  resetClientState();
});

afterEach(() => {
  cleanup();
  resetClientState();
});
