export interface BreadcrumbItem {
  label: string;
  path?: string;
}

const routeTitles: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/system-status': 'System status',
  '/master-data': 'Master Data Overview',
  '/master-data/departments': 'Departments',
  '/master-data/sections': 'Sections',
  '/master-data/document-types': 'Document Types',
  '/master-data/document-statuses': 'Document Statuses',
  '/master-data/validation-rules': 'Validation Rules',
  '/documents': 'Document Register',
  '/documents/new': 'Add Document',
  '/documents/upload': 'Upload Document',
  '/documents/batch-upload': 'Batch Upload',
  '/documents/extraction-queue': 'Extraction Queue',
  '/documents/ocr-queue': 'OCR Queue',
  '/documents/ocr-history': 'OCR History',
  '/documents/language-detection': 'Language Detection',
  '/documents/extraction-history': 'Extraction History',
  '/documents/upload-history': 'Upload History',
  '/documents/archived': 'Archived Documents',
};

const getDynamicDocumentRouteTitle = (pathname: string): string | null => {
  if (/^\/documents\/[^/]+\/revisions\/[^/]+\/ocr-results$/.test(pathname)) {
    return 'OCR Results';
  }
  if (/^\/documents\/[^/]+\/revisions\/[^/]+\/language-results$/.test(pathname)) {
    return 'Language Results';
  }
  if (/^\/documents\/[^/]+\/ocr-results$/.test(pathname)) {
    return 'OCR Results';
  }
  if (/^\/documents\/[^/]+\/language-results$/.test(pathname)) {
    return 'Language Results';
  }
  if (/^\/documents\/[^/]+\/revisions\/[^/]+\/extraction-history$/.test(pathname)) {
    return 'Revision Extraction History';
  }
  if (/^\/documents\/[^/]+\/revisions\/[^/]+\/extracted-content$/.test(pathname)) {
    return 'Extracted Content';
  }
  if (/^\/documents\/[^/]+\/extracted-content$/.test(pathname)) {
    return 'Extracted Content';
  }
  if (/^\/documents\/[^/]+\/revisions\/[^/]+\/file$/.test(pathname)) {
    return 'Revision Physical File';
  }
  if (/^\/documents\/[^/]+\/edit$/.test(pathname)) {
    return 'Edit Document';
  }
  if (/^\/documents\/[^/]+\/revisions$/.test(pathname)) {
    return 'Revision Management';
  }
  if (/^\/documents\/[^/]+$/.test(pathname)) {
    return 'Document Details';
  }
  return null;
};

export const getRouteTitle = (pathname: string): string =>
  routeTitles[pathname] ?? getDynamicDocumentRouteTitle(pathname) ?? 'Workspace';

export const getRouteBreadcrumbs = (pathname: string): BreadcrumbItem[] => {
  if (pathname === '/dashboard') {
    return [{ label: 'Dashboard' }];
  }
  if (pathname.startsWith('/master-data')) {
    const currentTitle = getRouteTitle(pathname);
    return pathname === '/master-data'
      ? [{ label: 'Master Data' }]
      : [{ label: 'Master Data', path: '/master-data' }, { label: currentTitle }];
  }
  if (pathname.startsWith('/documents')) {
    const currentTitle = getRouteTitle(pathname);
    if (pathname === '/documents') {
      return [{ label: 'Documents' }];
    }
    const fileMatch = /^\/documents\/([^/]+)\/revisions\/([^/]+)\/file$/.exec(pathname);
    const extractionMatch =
      /^\/documents\/([^/]+)\/revisions\/([^/]+)\/(extracted-content|extraction-history|ocr-results|language-results)$/.exec(
        pathname,
      );
    if (extractionMatch) {
      return [
        { label: 'Documents', path: '/documents' },
        { label: 'Document Details', path: `/documents/${extractionMatch[1]}` },
        {
          label: 'Revision Physical File',
          path: `/documents/${extractionMatch[1]}/revisions/${extractionMatch[2]}/file`,
        },
        { label: currentTitle },
      ];
    }
    if (fileMatch) {
      return [
        { label: 'Documents', path: '/documents' },
        { label: 'Document Details', path: `/documents/${fileMatch[1]}` },
        {
          label: 'Revision Management',
          path: `/documents/${fileMatch[1]}/revisions`,
        },
        { label: currentTitle },
      ];
    }
    const detailMatch = /^\/documents\/([^/]+)(?:\/(edit|revisions))?$/.exec(pathname);
    if (detailMatch && detailMatch[2]) {
      return [
        { label: 'Documents', path: '/documents' },
        { label: 'Document Details', path: `/documents/${detailMatch[1]}` },
        { label: currentTitle },
      ];
    }
    return [{ label: 'Documents', path: '/documents' }, { label: currentTitle }];
  }
  return [{ label: getRouteTitle(pathname) }];
};
