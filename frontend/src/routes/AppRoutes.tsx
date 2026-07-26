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
const SectionDefinitionsPage = lazy(() =>
  import('../pages/master-data/SectionDefinitionsPage').then((module) => ({
    default: module.SectionDefinitionsPage,
  })),
);
const GlossaryPage = lazy(() =>
  import('../pages/master-data/GlossaryPage').then((module) => ({
    default: module.GlossaryPage,
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
const ValidationQueuePage = lazy(() =>
  import('../pages/documents/ValidationQueuePage').then((module) => ({
    default: module.ValidationQueuePage,
  })),
);
const ValidationHistoryPage = lazy(() =>
  import('../pages/documents/ValidationHistoryPage').then((module) => ({
    default: module.ValidationHistoryPage,
  })),
);
const SimilarityQueuePage = lazy(() =>
  import('../pages/documents/SimilarityQueuePage').then((module) => ({
    default: module.SimilarityQueuePage,
  })),
);
const SimilarityHistoryPage = lazy(() =>
  import('../pages/documents/SimilarityHistoryPage').then((module) => ({
    default: module.SimilarityHistoryPage,
  })),
);
const RevisionComparisonPage = lazy(() =>
  import('../pages/documents/RevisionComparisonPage').then((module) => ({
    default: module.RevisionComparisonPage,
  })),
);
const ComplianceOverviewPage = lazy(() =>
  import('../pages/compliance/ComplianceOverviewPage').then((module) => ({
    default: module.ComplianceOverviewPage,
  })),
);
const LanguageCompliancePage = lazy(() =>
  import('../pages/compliance/LanguageCompliancePage').then((module) => ({
    default: module.LanguageCompliancePage,
  })),
);
const SectionCompliancePage = lazy(() =>
  import('../pages/compliance/SectionCompliancePage').then((module) => ({
    default: module.SectionCompliancePage,
  })),
);
const LanguageOrderPage = lazy(() =>
  import('../pages/compliance/LanguageOrderPage').then((module) => ({
    default: module.LanguageOrderPage,
  })),
);
const TranslationSimilarityPage = lazy(() =>
  import('../pages/compliance/TranslationSimilarityPage').then((module) => ({
    default: module.TranslationSimilarityPage,
  })),
);
const GlossaryCompliancePage = lazy(() =>
  import('../pages/compliance/GlossaryCompliancePage').then((module) => ({
    default: module.GlossaryCompliancePage,
  })),
);
const FindingsPage = lazy(() =>
  import('../pages/compliance/FindingsPage').then((module) => ({
    default: module.FindingsPage,
  })),
);
const ReviewFindingsPage = lazy(() =>
  import('../pages/compliance/FindingsPage').then((module) => ({
    default: module.ReviewFindingsPage,
  })),
);
const FindingDetailPage = lazy(() =>
  import('../pages/compliance/FindingDetailPage').then((module) => ({
    default: module.FindingDetailPage,
  })),
);
const DocumentCompliancePage = lazy(() =>
  import('../pages/compliance/DocumentCompliancePage').then((module) => ({
    default: module.DocumentCompliancePage,
  })),
);
const ComplianceReportPage = lazy(() =>
  import('../pages/reports/ComplianceReportPage').then((module) => ({
    default: module.ComplianceReportPage,
  })),
);
const FindingsReportPage = lazy(() =>
  import('../pages/reports/FindingsReportPage').then((module) => ({
    default: module.FindingsReportPage,
  })),
);
const AdvancedAnalyticsPage = lazy(() =>
  import('../pages/reports/AdvancedAnalyticsPage').then((module) => ({
    default: module.AdvancedAnalyticsPage,
  })),
);
const ReportSnapshotsPage = lazy(() =>
  import('../pages/reports/ReportSnapshotsPage').then((module) => ({
    default: module.ReportSnapshotsPage,
  })),
);
const ReportSchedulesPage = lazy(() =>
  import('../pages/reports/ReportSchedulesPage').then((module) => ({
    default: module.ReportSchedulesPage,
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
const SharePointConnectionsPage = lazy(() =>
  import('../pages/integrations/SharePointConnectionsPage').then((module) => ({
    default: module.SharePointConnectionsPage,
  })),
);
const SharePointFolderMappingsPage = lazy(() =>
  import('../pages/integrations/SharePointFolderMappingsPage').then((module) => ({
    default: module.SharePointFolderMappingsPage,
  })),
);
const SharePointMetadataMappingsPage = lazy(() =>
  import('../pages/integrations/SharePointMetadataMappingsPage').then((module) => ({
    default: module.SharePointMetadataMappingsPage,
  })),
);
const SharePointSyncProfilesPage = lazy(() =>
  import('../pages/integrations/SharePointSyncProfilesPage').then((module) => ({
    default: module.SharePointSyncProfilesPage,
  })),
);
const GraphSubscriptionsPage = lazy(() =>
  import('../pages/integrations/GraphSubscriptionsPage').then((module) => ({
    default: module.GraphSubscriptionsPage,
  })),
);
const SharePointSyncQueuePage = lazy(() =>
  import('../pages/documents/SharePointSyncQueuePage').then((module) => ({
    default: module.SharePointSyncQueuePage,
  })),
);
const SharePointSyncHistoryPage = lazy(() =>
  import('../pages/documents/SharePointSyncHistoryPage').then((module) => ({
    default: module.SharePointSyncHistoryPage,
  })),
);
const SharePointConflictsPage = lazy(() =>
  import('../pages/documents/SharePointConflictsPage').then((module) => ({
    default: module.SharePointConflictsPage,
  })),
);
const SharePointConflictDetailPage = lazy(() =>
  import('../pages/documents/SharePointConflictDetailPage').then((module) => ({
    default: module.SharePointConflictDetailPage,
  })),
);
const NotificationSettingsPage = lazy(() =>
  import('../pages/settings/NotificationSettingsPage').then((module) => ({
    default: module.NotificationSettingsPage,
  })),
);
const NotificationTemplatesPage = lazy(() =>
  import('../pages/admin/NotificationTemplatesPage').then((module) => ({
    default: module.NotificationTemplatesPage,
  })),
);
const NotificationRulesPage = lazy(() =>
  import('../pages/admin/NotificationRulesPage').then((module) => ({
    default: module.NotificationRulesPage,
  })),
);
const NotificationDeliveriesPage = lazy(() =>
  import('../pages/admin/NotificationDeliveriesPage').then((module) => ({
    default: module.NotificationDeliveriesPage,
  })),
);
const SystemHealthPage = lazy(() =>
  import('../pages/admin/SystemHealthPage').then((module) => ({
    default: module.SystemHealthPage,
  })),
);
const BackgroundJobsPage = lazy(() =>
  import('../pages/admin/BackgroundJobsPage').then((module) => ({
    default: module.BackgroundJobsPage,
  })),
);
const RetentionPoliciesPage = lazy(() =>
  import('../pages/admin/RetentionPoliciesPage').then((module) => ({
    default: module.RetentionPoliciesPage,
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
              path="/documents/sharepoint-sync-queue"
              element={
                <PermissionGuard permission="sharepoint:view">
                  <SharePointSyncQueuePage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/sharepoint-sync-history"
              element={
                <PermissionGuard permission="sharepoint:view_history">
                  <SharePointSyncHistoryPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/sharepoint-conflicts"
              element={
                <PermissionGuard permission="sharepoint:view_conflicts">
                  <SharePointConflictsPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/sharepoint-conflicts/:conflictId"
              element={
                <PermissionGuard permission="sharepoint:view_conflicts">
                  <SharePointConflictDetailPage />
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
              path="/documents/validation-queue"
              element={
                <PermissionGuard permission="compliance:view">
                  <ValidationQueuePage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/validation-history"
              element={
                <PermissionGuard permission="compliance:view">
                  <ValidationHistoryPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/similarity-queue"
              element={
                <PermissionGuard permission="similarity:view">
                  <SimilarityQueuePage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/similarity-history"
              element={
                <PermissionGuard permission="similarity:view">
                  <SimilarityHistoryPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/revision-comparison"
              element={
                <PermissionGuard permission="revision_comparison:view">
                  <RevisionComparisonPage />
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
              path="/documents/:documentId/compliance"
              element={
                <PermissionGuard permission="compliance:view">
                  <DocumentCompliancePage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/:documentId/revisions/:revisionId/compliance"
              element={
                <PermissionGuard permission="compliance:view">
                  <DocumentCompliancePage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/:documentId/similarity"
              element={
                <PermissionGuard permission="similarity:view">
                  <TranslationSimilarityPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/:documentId/revisions/:revisionId/similarity"
              element={
                <PermissionGuard permission="similarity:view">
                  <TranslationSimilarityPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/:documentId/revision-comparison"
              element={
                <PermissionGuard permission="revision_comparison:view">
                  <RevisionComparisonPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/documents/:documentId/revisions/compare"
              element={
                <PermissionGuard permission="revision_comparison:view">
                  <RevisionComparisonPage />
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
            <Route
              path="/master-data/section-definitions"
              element={
                <PermissionGuard permission="master_data:view">
                  <SectionDefinitionsPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/master-data/glossary"
              element={
                <PermissionGuard permission="glossary:view">
                  <GlossaryPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/master-data/glossary/:glossaryId"
              element={
                <PermissionGuard permission="glossary:view">
                  <GlossaryPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/compliance"
              element={
                <PermissionGuard permission="compliance:view">
                  <ComplianceOverviewPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/compliance/languages"
              element={
                <PermissionGuard permission="compliance:view">
                  <LanguageCompliancePage />
                </PermissionGuard>
              }
            />
            <Route
              path="/compliance/sections"
              element={
                <PermissionGuard permission="compliance:view">
                  <SectionCompliancePage />
                </PermissionGuard>
              }
            />
            <Route
              path="/compliance/language-order"
              element={
                <PermissionGuard permission="compliance:view">
                  <LanguageOrderPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/compliance/translation-similarity"
              element={
                <PermissionGuard permission="similarity:view">
                  <TranslationSimilarityPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/compliance/glossary"
              element={
                <PermissionGuard permission="glossary:view">
                  <GlossaryCompliancePage />
                </PermissionGuard>
              }
            />
            <Route
              path="/compliance/findings"
              element={
                <PermissionGuard permission="findings:view">
                  <FindingsPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/compliance/findings/review"
              element={
                <PermissionGuard permission="findings:review">
                  <ReviewFindingsPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/compliance/findings/:findingId"
              element={
                <PermissionGuard permission="findings:view">
                  <FindingDetailPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/reports/compliance"
              element={
                <PermissionGuard permission="reports:view">
                  <PermissionGuard permission="compliance:view">
                    <ComplianceReportPage />
                  </PermissionGuard>
                </PermissionGuard>
              }
            />
            <Route
              path="/reports/findings"
              element={
                <PermissionGuard permission="reports:view">
                  <PermissionGuard permission="findings:view">
                    <FindingsReportPage />
                  </PermissionGuard>
                </PermissionGuard>
              }
            />
            <Route
              path="/reports/translation-similarity"
              element={
                <PermissionGuard permission="advanced_reports:view">
                  <AdvancedAnalyticsPage initialReportType="TRANSLATION_SIMILARITY" />
                </PermissionGuard>
              }
            />
            <Route
              path="/reports/glossary-compliance"
              element={
                <PermissionGuard permission="advanced_reports:view">
                  <AdvancedAnalyticsPage initialReportType="GLOSSARY_COMPLIANCE" />
                </PermissionGuard>
              }
            />
            <Route
              path="/reports/revision-changes"
              element={
                <PermissionGuard permission="advanced_reports:view">
                  <AdvancedAnalyticsPage initialReportType="REVISION_CHANGES" />
                </PermissionGuard>
              }
            />
            <Route
              path="/reports/advanced-analytics"
              element={
                <PermissionGuard permission="advanced_reports:view">
                  <AdvancedAnalyticsPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/reports/snapshots"
              element={
                <PermissionGuard permission="advanced_reports:view">
                  <ReportSnapshotsPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/reports/schedules"
              element={
                <PermissionGuard permission="advanced_reports:configure">
                  <ReportSchedulesPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/integrations/sharepoint"
              element={<Navigate to="/integrations/sharepoint/connections" replace />}
            />
            <Route
              path="/integrations/sharepoint/connections"
              element={
                <PermissionGuard permission="sharepoint:view">
                  <SharePointConnectionsPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/integrations/sharepoint/folder-mappings"
              element={
                <PermissionGuard permission="sharepoint:configure">
                  <SharePointFolderMappingsPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/integrations/sharepoint/metadata-mappings"
              element={
                <PermissionGuard permission="sharepoint:configure">
                  <SharePointMetadataMappingsPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/integrations/sharepoint/sync-profiles"
              element={
                <PermissionGuard permission="sharepoint:configure">
                  <SharePointSyncProfilesPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/integrations/sharepoint/subscriptions"
              element={
                <PermissionGuard permission="sharepoint:configure">
                  <GraphSubscriptionsPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/settings/notifications"
              element={
                <PermissionGuard permission="notifications:update_preferences">
                  <NotificationSettingsPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/admin/notifications/templates"
              element={
                <PermissionGuard permission="notifications:manage_templates">
                  <NotificationTemplatesPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/admin/notifications/rules"
              element={
                <PermissionGuard permission="notifications:manage_rules">
                  <NotificationRulesPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/admin/notifications/deliveries"
              element={
                <PermissionGuard permission="notifications:view_deliveries">
                  <NotificationDeliveriesPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/admin/system-health"
              element={
                <PermissionGuard permission="system_health:view">
                  <SystemHealthPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/admin/background-jobs"
              element={
                <PermissionGuard permission="background_jobs:manage">
                  <BackgroundJobsPage />
                </PermissionGuard>
              }
            />
            <Route
              path="/admin/retention-policies"
              element={
                <PermissionGuard permission="retention_policies:manage">
                  <RetentionPoliciesPage />
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
