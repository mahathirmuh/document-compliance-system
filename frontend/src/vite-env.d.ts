/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_APP_VERSION?: string;
  readonly VITE_DEFAULT_COMPANY_CODE?: string;
  readonly VITE_DOCUMENT_MAX_FILE_SIZE_MB?: string;
  readonly VITE_DOCUMENT_BATCH_MAX_FILES?: string;
  readonly VITE_DOCUMENT_BATCH_MAX_TOTAL_SIZE_MB?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
