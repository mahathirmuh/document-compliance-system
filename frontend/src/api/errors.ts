import axios from 'axios';

import type { ApiResponse } from '../types/auth';

export const getApiErrorMessage = (error: unknown, fallbackMessage: string): string => {
  if (axios.isAxiosError<ApiResponse<null>>(error)) {
    const response = error.response?.data;
    return response?.errors?.[0]?.message || response?.message || fallbackMessage;
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return fallbackMessage;
};
