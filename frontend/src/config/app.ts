import packageMetadata from '../../package.json';

export const appConfig = {
  name: 'Document Compliance & Multilingual Validation System',
  shortName: 'Document Compliance',
  version: import.meta.env.VITE_APP_VERSION || packageMetadata.version,
  defaultCompanyCode:
    import.meta.env.VITE_DEFAULT_COMPANY_CODE?.trim().toUpperCase() || 'MTI',
  healthRefreshIntervalMs: 30_000,
} as const;
