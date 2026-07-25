import { useContext } from 'react';

import { ToastContext, type ToastContextValue } from './toastContext';

export const useToast = (): ToastContextValue => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within ToastProvider.');
  }
  return context;
};
