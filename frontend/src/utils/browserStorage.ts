import type { StateStorage } from 'zustand/middleware';

const fallbackStorage = new Map<string, string>();

const memoryStorage: StateStorage = {
  getItem: (name) => fallbackStorage.get(name) ?? null,
  setItem: (name, value) => {
    fallbackStorage.set(name, value);
  },
  removeItem: (name) => {
    fallbackStorage.delete(name);
  },
};

export const getPreferenceStorage = (): StateStorage => {
  if (typeof window === 'undefined') {
    return memoryStorage;
  }

  return window.localStorage;
};
