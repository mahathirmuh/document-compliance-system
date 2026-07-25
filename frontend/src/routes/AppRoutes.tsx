import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router';

import { PermissionGuard } from '../components/auth/PermissionGuard';
import { ProtectedRoute } from '../components/auth/ProtectedRoute';
import { FullScreenLoader } from '../components/common/FullScreenLoader';
import { AppLayout } from '../components/layout/AppLayout';
import { useAuthStore } from '../store/authStore';

const LoginPage = lazy(() =>
  import('../pages/auth/LoginPage').then((module) => ({
    default: module.LoginPage,
  })),
);
const DashboardPage = lazy(() =>
  import('../pages/dashboard/DashboardPage').then((module) => ({
    default: module.DashboardPage,
  })),
);
const UnauthorizedPage = lazy(() =>
  import('../pages/UnauthorizedPage').then((module) => ({
    default: module.UnauthorizedPage,
  })),
);
const NotFoundPage = lazy(() =>
  import('../pages/NotFoundPage').then((module) => ({
    default: module.NotFoundPage,
  })),
);
const SystemStatusPage = lazy(() =>
  import('../pages/SystemStatusPage').then((module) => ({
    default: module.SystemStatusPage,
  })),
);
const MasterDataOverviewPage = lazy(() =>
  import('../pages/master-data/MasterDataOverviewPage').then((module) => ({
    default: module.MasterDataOverviewPage,
  })),
);
const DepartmentsPage = lazy(() =>
  import('../pages/master-data/DepartmentsPage').then((module) => ({
    default: module.DepartmentsPage,
  })),
);
const SectionsPage = lazy(() =>
  import('../pages/master-data/SectionsPage').then((module) => ({
    default: module.SectionsPage,
  })),
);
const DocumentTypesPage = lazy(() =>
  import('../pages/master-data/DocumentTypesPage').then((module) => ({
    default: module.DocumentTypesPage,
  })),
);
const DocumentStatusesPage = lazy(() =>
  import('../pages/master-data/DocumentStatusesPage').then((module) => ({
    default: module.DocumentStatusesPage,
  })),
);
const ValidationRulesPage = lazy(() =>
  import('../pages/master-data/ValidationRulesPage').then((module) => ({
    default: module.ValidationRulesPage,
  })),
);
const DocumentsPage = lazy(() =>
  import('../pages/documents/DocumentsPage').then((module) => ({
    default: module.DocumentsPage,
  })),
);
const CreateDocumentPage = lazy(() =>
  import('../pages/documents/CreateDocumentPage').then((module) => ({
    default: module.CreateDocumentPage,
  })),
);
const ArchivedDocumentsPage = lazy(() =>
  import('../pages/documents/ArchivedDocumentsPage').then((module) => ({
    default: module.ArchivedDocumentsPage,
  })),
);
const UploadDocumentPage = lazy(() =>
  import('../pages/documents/UploadDocumentPage').then((module) => ({
    default: module.UploadDocumentPage,
  })),
);
const BatchUploadPage = lazy(() =>
  import('../pages/documents/BatchUploadPage').then((module) => ({
    default: module.BatchUploadPage,
  })),
);
const UploadHistoryPage = lazy(() =>
  import('../pages/documents/UploadHistoryPage').then((module) => ({
    default: module.UploadHistoryPage,
  })),
);
const ExtractionQueuePage = lazy(() =>
  import('../pages/documents/ExtractionQueuePage').then((module) => ({
    default: module.ExtractionQueuePage,
  })),
);
const ExtractionHistoryPage = lazy(() =>
  import('../pages/documents/ExtractionHistoryPage').then((module) => ({
    default: module.ExtractionHistoryPage,
  })),
);
const OCRQueuePage = lazy(() =>
  import('../pages/documents/OCRQueuePage').then((module) => ({
    default: module.OCRQueuePage,
  })),
);
const OCRHistoryPage = lazy(() =>
  import('../pages/documents/OCRHistoryPage').then((module) => ({
    default: module.OCRHistoryPage,
  })),
);
const OCRResultPage = lazy(() =>
  import('../pages/documents/OCRResultPage').then((module) => ({
    default: module.OCRResultPage,
  })),
);
const LanguageDetectionPage = lazy(() =>
  import('../pages/documents/LanguageDetectionPage').then((module) => ({
    default: module.LanguageDetectionPage,
  })),
);
const LanguageResultPage = lazy(() =>
  import('../pages/documents/LanguageResultPage').then((module) => ({
    default: module.LanguageResultPage,
  })),
);
const ExtractedContentPage = lazy(() =>
  import('../pages/documents/ExtractedContentPage').then((module) => ({
    default: module.ExtractedContentPage,
  })),
);
const DocumentExtractionHistoryPage = lazy(() =>
  import('../pages/documents/DocumentExtractionHistoryPage').then((module) => ({
    default: module.DocumentExtractionHistoryPage,
  })),
);
const DocumentRevisionFilePage = lazy(() =>
  import('../pages/documents/DocumentRevisionFilePage').then((module) => ({
    default: module.DocumentRevisionFilePage,
  })),
);
const DocumentDetailPage = lazy(() =>
  import('../pages/documents/DocumentDetailPage').then((module) => ({
    default: module.DocumentDetailPage,
  })),
);
const EditDocumentPage = lazy(() =>
  import('../pages/documents/EditDocumentPage').then((module) => ({
    default: module.EditDocumentPage,
  })),
);
const DocumentRevisionsPage = lazy(() =>
  import('../pages/documents/DocumentRevisionsPage').then((module) => ({
    default: module.DocumentRevisionsPage,
  })),
);

function RootRedirect() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  return <Navigate to={isAuthenticated ? '/dashboard' : '/login'} replace />;
}

export function AppRoutes() {
  return (
    <Suspense fallback={<FullScreenLoader message="Loading page..." />}>
      <Routes>
        <Route path="/" element={<RootRedirect />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/unauthorized" element={<UnauthorizedPage />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route
              path="/dashboard"
              element={
                <PermissionGuard permission="dashboard:view">
                  <DashboardPage />
                </PermissionGuard>
              }
            />
            <Route path="/system-status" element={<SystemStatusPage />} />
            <Route
              path="/documents"
              element={
                <PermissionGuard permission="documents:view">
                  <DocumentsPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/new"
              element={
                <PermissionGuard permission="documents:create">
                  <CreateDocumentPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/archived"
              element={
                <PermissionGuard permission="documents:view">
                  <ArchivedDocumentsPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/upload"
              element={
                <PermissionGuard permission="documents:upload">
                  <UploadDocumentPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/batch-upload"
              element={
                <PermissionGuard permission="documents:batch_upload">
                  <BatchUploadPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/upload-history"
              element={
                <PermissionGuard permission="documents:view_file_history">
                  <UploadHistoryPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/extraction-queue"
              element={
                <PermissionGuard permission="documents:extract">
                  <ExtractionQueuePage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/extraction-history"
              element={
                <PermissionGuard permission="documents:view_extraction_history">
                  <ExtractionHistoryPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/ocr-queue"
              element={
                <PermissionGuard permission="documents:ocr">
                  <OCRQueuePage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/ocr-history"
              element={
                <PermissionGuard permission="documents:view_ocr_history">
                  <OCRHistoryPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/language-detection"
              element={
                <PermissionGuard permission="documents:view_language_results">
                  <LanguageDetectionPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/:documentId/ocr-results"
              element={
                <PermissionGuard permission="documents:view_ocr_results">
                  <OCRResultPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/:documentId/revisions/:revisionId/ocr-results"
              element={
                <PermissionGuard permission="documents:view_ocr_results">
                  <OCRResultPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/:documentId/language-results"
              element={
                <PermissionGuard permission="documents:view_language_results">
                  <LanguageResultPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/:documentId/revisions/:revisionId/language-results"
              element={
                <PermissionGuard permission="documents:view_language_results">
                  <LanguageResultPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/:documentId/extracted-content"
              element={
                <PermissionGuard permission="documents:view_extracted_content">
                  <ExtractedContentPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/:documentId/revisions/:revisionId/extracted-content"
              element={
                <PermissionGuard permission="documents:view_extracted_content">
                  <ExtractedContentPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/:documentId/revisions/:revisionId/extraction-history"
              element={
                <PermissionGuard permission="documents:view_extraction_history">
                  <DocumentExtractionHistoryPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/:documentId/revisions/:revisionId/file"
              element={
                <PermissionGuard permission="documents:view">
                  <DocumentRevisionFilePage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/:documentId"
              element={
                <PermissionGuard permission="documents:view">
                  <DocumentDetailPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/:documentId/edit"
              element={
                <PermissionGuard permission="documents:update">
                  <EditDocumentPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/:documentId/revisions"
              element={
                <PermissionGuard permission="documents:view">
                  <DocumentRevisionsPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/master-data"
              element={
                <PermissionGuard permission="master_data:view">
                  <MasterDataOverviewPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/master-data/departments"
              element={
                <PermissionGuard permission="master_data:view">
                  <DepartmentsPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/master-data/sections"
              element={
                <PermissionGuard permission="master_data:view">
                  <SectionsPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/master-data/document-types"
              element={
                <PermissionGuard permission="master_data:view">
                  <DocumentTypesPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/master-data/document-statuses"
              element={
                <PermissionGuard permission="master_data:view">
                  <DocumentStatusesPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/master-data/validation-rules"
              element={
                <PermissionGuard permission="master_data:view">
                  <ValidationRulesPage />
                </PermissionGuard>
              }
            />
          </Route>
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  );
}
