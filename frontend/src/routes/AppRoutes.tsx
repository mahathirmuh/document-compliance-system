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
