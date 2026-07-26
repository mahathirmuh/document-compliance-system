import { expect, test, type Page, type Request, type Route } from '@playwright/test';

import { complianceRun as complianceRunFixture } from '../src/test/phase8Fixtures';
import {
  languageRun as languageRunFixture,
  languageSummary as languageSummaryFixture,
  ocrRun as ocrRunFixture,
} from '../src/test/phase7Fixtures';
import { extractionRun as extractionRunFixture } from '../src/test/extractionFixtures';
import { permissions } from '../src/types/auth';

const ids = {
  user: '10000000-0000-4000-8000-000000000001',
  department: '10000000-0000-4000-8000-000000000002',
  section: '10000000-0000-4000-8000-000000000003',
  documentType: '10000000-0000-4000-8000-000000000004',
  documentStatus: '10000000-0000-4000-8000-000000000005',
  validationRule: '10000000-0000-4000-8000-000000000006',
  document: '10000000-0000-4000-8000-000000000007',
  revision: '10000000-0000-4000-8000-000000000008',
  file: '10000000-0000-4000-8000-000000000009',
  uploadSession: '10000000-0000-4000-8000-000000000010',
  uploadItem: '10000000-0000-4000-8000-000000000011',
  extractionJob: '10000000-0000-4000-8000-000000000012',
  extractionRun: '10000000-0000-4000-8000-000000000013',
  ocrJob: '10000000-0000-4000-8000-000000000014',
  ocrRun: '10000000-0000-4000-8000-000000000015',
  languageJob: '10000000-0000-4000-8000-000000000016',
  languageRun: '10000000-0000-4000-8000-000000000017',
  complianceJob: '10000000-0000-4000-8000-000000000018',
  complianceRun: '10000000-0000-4000-8000-000000000019',
  similarityJob: '10000000-0000-4000-8000-000000000020',
  similarityRun: '10000000-0000-4000-8000-000000000021',
  glossaryJobAndRun: '10000000-0000-4000-8000-000000000022',
  connection: '10000000-0000-4000-8000-000000000023',
  folderMapping: '10000000-0000-4000-8000-000000000024',
  syncProfile: '10000000-0000-4000-8000-000000000025',
  pushJob: '10000000-0000-4000-8000-000000000026',
  incrementalJob: '10000000-0000-4000-8000-000000000027',
  syncItem: '10000000-0000-4000-8000-000000000028',
  conflict: '10000000-0000-4000-8000-000000000029',
  notification: '10000000-0000-4000-8000-000000000030',
  reportJob: '10000000-0000-4000-8000-000000000031',
  reportSnapshot: '10000000-0000-4000-8000-000000000032',
} as const;

const timestamp = '2026-07-26T12:30:00+08:00';
const laterTimestamp = '2026-07-26T12:35:00+08:00';

interface MockState {
  loggedIn: boolean;
  documentCreated: boolean;
  uploaded: boolean;
  extracted: boolean;
  ocrCompleted: boolean;
  languageDetected: boolean;
  complianceCompleted: boolean;
  similarityCompleted: boolean;
  glossaryCompleted: boolean;
  sharePointPushed: boolean;
  incrementalSyncCompleted: boolean;
  conflictCreated: boolean;
  conflictResolved: boolean;
  notificationRead: boolean;
  reportGenerated: boolean;
  calls: MockCall[];
  unhandled: string[];
}

interface MockCall {
  method: string;
  path: string;
  body: unknown;
}

const emptyPage = <T>(items: T[] = []) => ({
  items,
  page: 1,
  pageSize: 20,
  totalItems: items.length,
  totalPages: items.length > 0 ? 1 : 0,
});

const user = {
  id: ids.user,
  name: 'Phase 10 Administrator',
  email: 'phase10@example.test',
  role: 'SUPER_ADMIN',
  departmentId: null,
  isActive: true,
} as const;

const department = {
  id: ids.department,
  code: 'HRM',
  name: 'Human Resources',
};

const section = {
  id: ids.section,
  code: 'DOC',
  name: 'Document Control',
  departmentId: ids.department,
};

const documentType = {
  id: ids.documentType,
  code: 'POL',
  name: 'Policy',
  requiresSection: false,
  defaultValidationRuleId: ids.validationRule,
};

const documentStatus = {
  id: ids.documentStatus,
  code: 'DRAFT',
  name: 'Draft',
  isInitial: true,
};

const validationRule = {
  id: ids.validationRule,
  code: 'TRI-LANG',
  name: 'Trilingual Policy',
  documentTypeId: ids.documentType,
  isDefault: true,
};

const revision = {
  id: ids.revision,
  documentId: ids.document,
  revisionCode: 'Rev.000',
  revisionNumber: 0,
  fullDocumentCode: 'MTI-HRM-POL-010_Rev.000',
  documentStatusId: ids.documentStatus,
  validationRuleId: ids.validationRule,
  status: documentStatus,
  validationRule: {
    id: ids.validationRule,
    code: validationRule.code,
    name: validationRule.name,
  },
  issueDate: '2026-07-26',
  effectiveDate: null,
  reviewDate: null,
  expiryDate: null,
  sharepointUrl: null,
  externalReference: null,
  remarks: 'Phase 10 deterministic E2E revision',
  isCurrent: true,
  isSuperseded: false,
  supersededAt: null,
  supersededByRevisionId: null,
  createdAt: timestamp,
  updatedAt: timestamp,
};

const documentDetail = {
  id: ids.document,
  companyCode: 'MTI',
  departmentId: ids.department,
  sectionId: null,
  documentTypeId: ids.documentType,
  documentNumber: '010',
  baseDocumentCode: 'MTI-HRM-POL-010',
  title: 'Phase 10 Trilingual Policy',
  description: 'Stateful Playwright validation document.',
  ownerDepartmentId: ids.department,
  documentOwnerName: 'Document Control',
  currentRevisionId: ids.revision,
  department,
  section: null,
  documentType: {
    id: ids.documentType,
    code: documentType.code,
    name: documentType.name,
  },
  ownerDepartment: department,
  currentRevision: revision,
  revisions: [revision],
  isArchived: false,
  archivedAt: null,
  archivedBy: null,
  archiveReason: null,
  createdBy: user,
  updatedBy: user,
  createdAt: timestamp,
  updatedAt: timestamp,
};

const physicalFile = {
  id: ids.file,
  documentId: ids.document,
  documentRevisionId: ids.revision,
  originalFilename: 'MTI-HRM-POL-010_Rev.000.pdf',
  sanitizedFilename: 'MTI-HRM-POL-010_Rev.000.pdf',
  fileExtension: 'pdf',
  mimeType: 'application/pdf',
  detectedMimeType: 'application/pdf',
  fileSize: 217,
  sha256Hash: 'a'.repeat(64),
  storageProvider: 'HYBRID',
  fileStatus: 'AVAILABLE',
  isPrimary: true,
  isCurrent: true,
  uploadedBy: user,
  uploadedAt: timestamp,
  replacedAt: null,
  replacedByFileId: null,
  deletedAt: null,
  deletionReason: null,
  baseDocumentCode: documentDetail.baseDocumentCode,
  documentTitle: documentDetail.title,
  revisionCode: revision.revisionCode,
  fullDocumentCode: revision.fullDocumentCode,
};

const extractionDocument = {
  id: ids.document,
  baseDocumentCode: documentDetail.baseDocumentCode,
  title: documentDetail.title,
  departmentId: ids.department,
};

const extractionRevision = {
  id: ids.revision,
  revisionCode: revision.revisionCode,
  fullDocumentCode: revision.fullDocumentCode,
};

const extractionFile = {
  id: ids.file,
  filename: physicalFile.originalFilename,
  extension: 'pdf',
  sha256Hash: physicalFile.sha256Hash,
};

const extractionRun = {
  ...extractionRunFixture,
  runId: ids.extractionRun,
  extractionJobId: ids.extractionJob,
  document: extractionDocument,
  revision: extractionRevision,
  file: extractionFile,
  status: 'OCR_REQUIRED',
  hasSelectableText: false,
  requiresOcr: true,
  warnings: ['SCANNED_PDF_REQUIRES_OCR'],
};

const ocrRun = {
  ...ocrRunFixture,
  runId: ids.ocrRun,
  ocrJobId: ids.ocrJob,
  document: extractionDocument,
  revision: extractionRevision,
  file: extractionFile,
  sourceExtractionRunId: ids.extractionRun,
};

const languageSummary = {
  ...languageSummaryFixture,
  runId: ids.languageRun,
  languagePresence: {
    id: 'PRESENT',
    en: 'PRESENT',
    zh: 'PRESENT',
  },
};

const languageRun = {
  ...languageRunFixture,
  ...languageSummary,
  documentFileId: ids.file,
  documentId: ids.document,
  documentRevisionId: ids.revision,
  extractionRunId: ids.extractionRun,
  ocrRunId: ids.ocrRun,
  jobId: ids.languageJob,
};

const complianceRun = {
  ...complianceRunFixture,
  id: ids.complianceRun,
  complianceJobId: ids.complianceJob,
  documentId: ids.document,
  documentRevisionId: ids.revision,
  documentFileId: ids.file,
  extractionRunId: ids.extractionRun,
  ocrRunId: ids.ocrRun,
  languageDetectionRunId: ids.languageRun,
  validationRuleId: ids.validationRule,
  document: {
    ...extractionDocument,
    departmentName: department.name,
  },
  revision: extractionRevision,
  file: {
    id: ids.file,
    filename: physicalFile.originalFilename,
    fileExtension: 'pdf',
  },
  validationRule: {
    id: ids.validationRule,
    code: validationRule.code,
    name: validationRule.name,
    version: 1,
  },
};

const complianceSummary = {
  runId: ids.complianceRun,
  status: 'COMPLETED',
  complianceStatus: 'NEEDS_REVIEW',
  complianceScore: 82.5,
  requiredLanguages: ['id', 'en', 'zh'],
  languagePresence: {
    id: 'PRESENT',
    en: 'PRESENT',
    zh: 'PRESENT',
  },
  languageCoverage: { id: 34, en: 33, zh: 33 },
  languageMetrics: [],
  missingLanguages: [],
  requiredSections: 3,
  detectedSections: 3,
  completeSections: 3,
  missingSections: [],
  translationGroups: {
    total: 4,
    complete: 4,
    incomplete: 0,
    lowConfidence: 1,
  },
  findings: {
    total: 1,
    critical: 0,
    major: 0,
    minor: 1,
    information: 0,
    open: 1,
  },
  warnings: ['One translation group requires human review.'],
  prerequisiteErrors: [],
};

const complianceScore = {
  documentCode: { earned: 10, maximum: 10 },
  languagePresence: { earned: 25, maximum: 25 },
  languageCoverage: { earned: 15, maximum: 15 },
  sectionCompleteness: { earned: 20, maximum: 20 },
  languageOrder: { earned: 10, maximum: 10 },
  translationGroups: { earned: 12.5, maximum: 15 },
  tableCompleteness: { earned: 5, maximum: 5 },
  penalties: { major: 0, minor: 0 },
  scoreCap: null,
  scoreCapReason: null,
  finalScore: 82.5,
};

const similarityRun = {
  id: ids.similarityRun,
  similarityJobId: ids.similarityJob,
  documentId: ids.document,
  documentRevisionId: ids.revision,
  documentFileId: ids.file,
  complianceRunId: ids.complianceRun,
  languageDetectionRunId: ids.languageRun,
  providerName: 'Local deterministic mock',
  provider: 'sentence-transformers',
  modelName: 'mock-multilingual-model',
  modelVersion: 'e2e',
  status: 'COMPLETED',
  sourceContentHash: 'b'.repeat(64),
  translationGroupCount: 4,
  eligibleGroupCount: 4,
  analysedGroupCount: 4,
  skippedGroupCount: 0,
  failedGroupCount: 0,
  averageSimilarity: 0.91,
  minimumSimilarity: 0.79,
  maximumSimilarity: 0.98,
  idEnAverageSimilarity: 0.93,
  idZhAverageSimilarity: 0.89,
  enZhAverageSimilarity: 0.9,
  highSimilarityGroups: 3,
  reviewSimilarityGroups: 1,
  lowSimilarityGroups: 0,
  unavailableSimilarityGroups: 0,
  numberMismatchCount: 0,
  dateMismatchCount: 0,
  measurementMismatchCount: 0,
  referenceMismatchCount: 0,
  negationMismatchCount: 0,
  warnings: [],
  metrics: {
    translationQualityStatus: 'HIGH_QUALITY',
    translationQualityScore: 91,
  },
  requestedBy: user,
  startedAt: timestamp,
  completedAt: laterTimestamp,
  createdAt: timestamp,
  document: extractionDocument,
  revision: extractionRevision,
  file: {
    id: ids.file,
    filename: physicalFile.originalFilename,
    fileExtension: 'pdf',
  },
};

const similarityJob = {
  id: ids.similarityJob,
  documentId: ids.document,
  documentRevisionId: ids.revision,
  documentFileId: ids.file,
  complianceRunId: ids.complianceRun,
  languageDetectionRunId: ids.languageRun,
  jobType: 'INITIAL_SIMILARITY',
  status: 'COMPLETED',
  progress: 100,
  currentStage: 'PERSISTING',
  provider: 'sentence-transformers',
  providerName: 'Local deterministic mock',
  modelName: 'mock-multilingual-model',
  sourceContentHash: 'b'.repeat(64),
  attemptNumber: 1,
  maximumAttempts: 2,
  retryCount: 0,
  requestedBy: user,
  requestedAt: timestamp,
  startedAt: timestamp,
  completedAt: laterTimestamp,
  failedAt: null,
  cancelledAt: null,
  errorCode: null,
  errorMessage: null,
  errorDetails: null,
  resultSummary: {
    runId: ids.similarityRun,
    averageSimilarity: 0.91,
    lowSimilarityGroups: 0,
    findingCount: 0,
  },
  createdAt: timestamp,
  updatedAt: laterTimestamp,
  document: extractionDocument,
  revision: extractionRevision,
  file: {
    id: ids.file,
    filename: physicalFile.originalFilename,
    fileExtension: 'pdf',
  },
};

const glossaryRun = {
  id: ids.glossaryJobAndRun,
  jobId: ids.glossaryJobAndRun,
  documentId: ids.document,
  documentRevisionId: ids.revision,
  documentFileId: ids.file,
  complianceRunId: ids.complianceRun,
  languageDetectionRunId: ids.languageRun,
  glossaryProfileIds: ['10000000-0000-4000-8000-000000000040'],
  profileSnapshots: [
    {
      id: '10000000-0000-4000-8000-000000000040',
      code: 'CORP-TRI',
      name: 'Corporate Trilingual Terms',
    },
  ],
  jobType: 'INITIAL',
  status: 'COMPLETED',
  progress: 100,
  currentStage: 'PERSISTING',
  sourceContentHash: 'c'.repeat(64),
  totalTerms: 14,
  matchedTerms: 12,
  preferredTermMatches: 12,
  forbiddenTermMatches: 0,
  missingRequiredTranslations: 0,
  inconsistentTerms: 0,
  exceptionAppliedCount: 0,
  totalFindings: 0,
  metrics: { glossaryQualityScore: 100 },
  warnings: [],
  errorCode: null,
  errorMessage: null,
  requestedBy: ids.user,
  requestedAt: timestamp,
  startedAt: timestamp,
  completedAt: laterTimestamp,
  failedAt: null,
  cancelRequestedAt: null,
  cancelledAt: null,
  createdAt: timestamp,
  updatedAt: laterTimestamp,
};

const connection = {
  id: ids.connection,
  name: 'Mock SharePoint connection',
  description: 'No Microsoft tenant is contacted by this E2E fixture.',
  tenantIdReference: 'mock-secret-reference',
  siteHostname: 'contoso.sharepoint.com',
  sitePath: '/sites/document-control',
  siteId: 'mock-site-id',
  driveId: 'mock-drive-id',
  libraryName: 'Controlled Documents',
  rootFolderPath: '/Phase10',
  authMode: 'CERTIFICATE',
  status: 'CONNECTED',
  isDefault: true,
  isActive: true,
  lastTestedAt: timestamp,
  lastTestStatus: 'MOCK_ONLY',
  lastTestMessage: 'Deterministic Playwright fixture; no tenant request was sent.',
  createdAt: timestamp,
  updatedAt: timestamp,
};

const syncProfile = {
  id: ids.syncProfile,
  name: 'Mock incremental document sync',
  description: 'Delta-enabled deterministic E2E profile',
  sharepointConnectionId: ids.connection,
  direction: 'BIDIRECTIONAL',
  scopeType: 'GLOBAL',
  departmentId: null,
  sectionId: null,
  documentTypeId: null,
  folderMappingId: ids.folderMapping,
  metadataMappingProfile: {},
  conflictPolicy: 'MANUAL',
  deletePolicy: 'IGNORE_REMOTE_DELETE',
  syncSchedule: null,
  deltaSyncEnabled: true,
  webhookEnabled: true,
  isActive: true,
  createdBy: ids.user,
  updatedBy: ids.user,
  createdAt: timestamp,
  updatedAt: laterTimestamp,
};

const completedSyncJob = (jobType: 'SINGLE_FILE_PUSH' | 'MANUAL_INCREMENTAL') => ({
  id: jobType === 'SINGLE_FILE_PUSH' ? ids.pushJob : ids.incrementalJob,
  syncProfileId: ids.syncProfile,
  sharepointConnectionId: ids.connection,
  jobType,
  direction: jobType === 'SINGLE_FILE_PUSH' ? 'OUTBOUND' : 'BIDIRECTIONAL',
  status: 'COMPLETED',
  progress: 100,
  currentStage: 'PERSISTING',
  scope: { documentFileId: ids.file },
  requestedBy: ids.user,
  requestedAt: timestamp,
  startedAt: timestamp,
  completedAt: laterTimestamp,
  failedAt: null,
  cancelledAt: null,
  attemptNumber: 1,
  maximumAttempts: 3,
  itemsDiscovered: 1,
  itemsProcessed: 1,
  itemsCreated: jobType === 'SINGLE_FILE_PUSH' ? 1 : 0,
  itemsUpdated: 0,
  itemsSkipped: 0,
  itemsConflicted: jobType === 'MANUAL_INCREMENTAL' ? 1 : 0,
  itemsFailed: 0,
  errorCode: null,
  errorMessage: null,
  resultSummary: { mock: true, tenantContacted: false },
  createdAt: timestamp,
  updatedAt: laterTimestamp,
});

const buildConflict = (state: MockState) => ({
  id: ids.conflict,
  syncJobId: ids.incrementalJob,
  syncItemId: ids.syncItem,
  documentId: ids.document,
  documentRevisionId: ids.revision,
  documentFileId: ids.file,
  remoteItemId: 'mock-remote-item',
  conflictType: 'BOTH_MODIFIED',
  status: state.conflictResolved ? 'RESOLVED' : 'OPEN',
  localVersion: {
    filename: physicalFile.originalFilename,
    path: '/local/controlled-documents',
    sha256Hash: physicalFile.sha256Hash,
    size: physicalFile.fileSize,
    modifiedAt: timestamp,
    modifiedBy: user.name,
    metadata: { title: documentDetail.title, source: 'LOCAL' },
  },
  remoteVersion: {
    filename: physicalFile.originalFilename,
    path: '/Phase10/MTI-HRM-POL-010_Rev.000.pdf',
    etag: '"mock-etag-2"',
    size: physicalFile.fileSize + 8,
    modifiedAt: laterTimestamp,
    modifiedBy: 'Mock SharePoint User',
    metadata: { title: 'Remote edited title', source: 'MOCK_GRAPH' },
  },
  detectedAt: laterTimestamp,
  assignedTo: null,
  resolution: state.conflictResolved ? 'KEEP_LOCAL' : null,
  resolvedBy: state.conflictResolved ? ids.user : null,
  resolvedAt: state.conflictResolved ? laterTimestamp : null,
  resolutionComment: state.conflictResolved
    ? 'Keep audited local version after deterministic review.'
    : null,
  resultDocumentFileId: state.conflictResolved ? ids.file : null,
  createdAt: laterTimestamp,
  updatedAt: laterTimestamp,
});

const reportJob = {
  id: ids.reportJob,
  reportType: 'COMPLIANCE_OVERVIEW',
  reportName: 'Phase 10 audit trail',
  outputFormat: 'xlsx',
  status: 'COMPLETED',
  snapshotStatus: 'AVAILABLE',
  progress: 100,
  currentStage: 'STORING_FILE',
  requestedAt: timestamp,
  startedAt: timestamp,
  completedAt: laterTimestamp,
  errorCode: null,
  errorMessage: null,
};

const reportSnapshot = {
  id: ids.reportSnapshot,
  reportType: 'COMPLIANCE_OVERVIEW',
  reportName: 'Phase 10 audit trail',
  filters: {},
  datasetHash: 'd'.repeat(64),
  status: 'AVAILABLE',
  jobStatus: 'COMPLETED',
  generatedBy: user,
  generatedAt: laterTimestamp,
  fileFormat: 'xlsx',
  fileSize: 32,
  expiresAt: '2027-07-26T12:35:00+08:00',
  metadata: {
    summary: {
      documents: 1,
      compliant: 0,
      needs_review: 1,
      sharepoint_conflicts_resolved: 1,
    },
    source: 'DETERMINISTIC_E2E_MOCK',
  },
  createdAt: laterTimestamp,
};

const initialState = (): MockState => ({
  loggedIn: false,
  documentCreated: false,
  uploaded: false,
  extracted: false,
  ocrCompleted: false,
  languageDetected: false,
  complianceCompleted: false,
  similarityCompleted: false,
  glossaryCompleted: false,
  sharePointPushed: false,
  incrementalSyncCompleted: false,
  conflictCreated: false,
  conflictResolved: false,
  notificationRead: false,
  reportGenerated: false,
  calls: [],
  unhandled: [],
});

const requestBody = (request: Request): unknown => {
  const contentType = request.headers()['content-type'] ?? '';
  if (!contentType.includes('application/json')) {
    return undefined;
  }
  try {
    return request.postDataJSON();
  } catch {
    return undefined;
  }
};

const fulfillJson = async (
  route: Route,
  data: unknown,
  message = 'Mock request completed',
): Promise<void> => {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    headers: {
      'x-request-id': 'phase10-playwright-mock',
    },
    body: JSON.stringify({
      success: true,
      message,
      data,
      errors: null,
    }),
  });
};

const installMockApi = async (page: Page): Promise<MockState> => {
  const state = initialState();

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const method = request.method();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api\/v1/, '') || '/';
    const body = requestBody(request);
    state.calls.push({ method, path, body });

    if (method === 'POST' && path === '/auth/login') {
      state.loggedIn = true;
      await fulfillJson(route, {
        accessToken: 'phase10-e2e-access-token',
        refreshToken: 'phase10-e2e-refresh-token',
        tokenType: 'bearer',
        expiresIn: 900,
        user,
        permissions: [...permissions],
      });
      return;
    }
    if (method === 'GET' && path === '/auth/me') {
      await fulfillJson(route, { user, permissions: [...permissions] });
      return;
    }
    if (method === 'GET' && path === '/health') {
      await fulfillJson(route, {
        status: 'healthy',
        service: 'document-compliance-api-e2e-mock',
        version: '1.0.0',
      });
      return;
    }

    if (method === 'GET' && path === '/notifications/unread-count') {
      await fulfillJson(route, {
        unreadCount: state.conflictResolved && !state.notificationRead ? 1 : 0,
      });
      return;
    }
    if (method === 'GET' && path === '/notifications') {
      const items = state.conflictResolved
        ? [
            {
              id: ids.notification,
              userId: ids.user,
              eventType: 'SHAREPOINT_CONFLICT_CREATED',
              title: 'SharePoint conflict resolved',
              message:
                'The deterministic incremental sync conflict was resolved with KEEP_LOCAL.',
              severity: 'WARNING',
              relatedEntityType: 'sharepoint_sync_conflict',
              relatedEntityId: ids.conflict,
              actionUrl: `/documents/sharepoint-conflicts/${ids.conflict}`,
              isRead: state.notificationRead,
              readAt: state.notificationRead ? laterTimestamp : null,
              dismissedAt: null,
              createdAt: laterTimestamp,
              expiresAt: null,
            },
          ]
        : [];
      await fulfillJson(route, emptyPage(items));
      return;
    }
    if (method === 'POST' && path === `/notifications/${ids.notification}/read`) {
      state.notificationRead = true;
      await fulfillJson(route, {
        notificationId: ids.notification,
        affectedCount: 1,
      });
      return;
    }

    if (method === 'GET' && path === '/documents/form-options') {
      await fulfillJson(route, {
        defaultCompanyCode: 'MTI',
        departments: [department],
        sections: [section],
        documentTypes: [documentType],
        documentStatuses: [documentStatus],
        validationRules: [validationRule],
      });
      return;
    }
    if (method === 'POST' && path === '/documents') {
      state.documentCreated = true;
      await fulfillJson(route, documentDetail, 'Document created');
      return;
    }
    if (method === 'GET' && path === '/documents') {
      await fulfillJson(
        route,
        emptyPage(
          state.documentCreated
            ? [
                {
                  ...documentDetail,
                  revisions: undefined,
                },
              ]
            : [],
        ),
      );
      return;
    }
    if (method === 'GET' && path === `/documents/${ids.document}/revisions`) {
      await fulfillJson(route, [revision]);
      return;
    }
    if (
      method === 'GET' &&
      path === `/documents/${ids.document}/revisions/${ids.revision}/files`
    ) {
      await fulfillJson(route, state.uploaded ? [physicalFile] : []);
      return;
    }
    if (method === 'GET' && path === `/documents/${ids.document}/files`) {
      await fulfillJson(route, state.uploaded ? [physicalFile] : []);
      return;
    }
    if (method === 'GET' && path === `/documents/${ids.document}`) {
      await fulfillJson(route, documentDetail);
      return;
    }

    if (method === 'POST' && path === '/document-files/upload') {
      await fulfillJson(route, {
        sessionId: ids.uploadSession,
        sessionType: 'SINGLE',
        status: 'PENDING_CONFIRMATION',
        totalFiles: 1,
        totalSize: physicalFile.fileSize,
        expiresAt: '2030-07-26T12:30:00+08:00',
        committedAt: null,
        cancelledAt: null,
        items: [
          {
            uploadItemId: ids.uploadItem,
            originalFilename: physicalFile.originalFilename,
            sanitizedFilename: physicalFile.sanitizedFilename,
            fileExtension: 'pdf',
            mimeType: 'application/pdf',
            detectedMimeType: 'application/pdf',
            fileSize: physicalFile.fileSize,
            sha256Hash: physicalFile.sha256Hash,
            identificationStatus: 'IDENTIFIED',
            proposedAction: 'ATTACH_TO_EXISTING_REVISION',
            parsedMetadata: {
              companyCode: 'MTI',
              departmentCode: department.code,
              sectionCode: null,
              documentTypeCode: documentType.code,
              documentNumber: documentDetail.documentNumber,
              revisionCode: revision.revisionCode,
              baseDocumentCode: documentDetail.baseDocumentCode,
              fullDocumentCode: revision.fullDocumentCode,
            },
            matchedDocument: {
              id: ids.document,
              baseDocumentCode: documentDetail.baseDocumentCode,
              title: documentDetail.title,
            },
            matchedRevision: {
              id: ids.revision,
              revisionCode: revision.revisionCode,
              fullDocumentCode: revision.fullDocumentCode,
            },
            duplicateWarning: null,
            warnings: [],
            errors: [],
            status: 'READY',
            quarantineReason: null,
          },
        ],
      });
      return;
    }
    if (
      method === 'POST' &&
      path === `/document-files/upload/${ids.uploadSession}/confirm`
    ) {
      state.uploaded = true;
      await fulfillJson(route, {
        sessionId: ids.uploadSession,
        status: 'COMMITTED',
        items: [
          {
            uploadItemId: ids.uploadItem,
            action: 'ATTACH_TO_EXISTING_REVISION',
            status: 'COMMITTED',
            documentId: ids.document,
            revisionId: ids.revision,
            documentFileId: ids.file,
            baseDocumentCode: documentDetail.baseDocumentCode,
            revisionCode: revision.revisionCode,
            fileStatus: 'AVAILABLE',
            error: null,
          },
        ],
        total: 1,
        committed: 1,
        skipped: 0,
        failed: 0,
        documentsCreated: 0,
        revisionsCreated: 0,
        filesAttached: 1,
        filesReplaced: 0,
        committedAt: timestamp,
      });
      return;
    }

    if (method === 'GET' && path === '/extractions') {
      await fulfillJson(route, emptyPage());
      return;
    }
    if (method === 'POST' && path === '/extractions') {
      state.extracted = true;
      await fulfillJson(route, {
        jobId: ids.extractionJob,
        status: 'OCR_REQUIRED',
        progress: 100,
        documentFileId: ids.file,
        reusedExistingResult: false,
        runId: ids.extractionRun,
      });
      return;
    }
    if (method === 'GET' && path === `/document-files/${ids.file}/extraction`) {
      await fulfillJson(route, state.extracted ? extractionRun : null);
      return;
    }

    if (method === 'GET' && path === '/ocr/jobs') {
      await fulfillJson(route, emptyPage());
      return;
    }
    if (method === 'POST' && path === '/ocr/jobs') {
      state.ocrCompleted = true;
      await fulfillJson(route, {
        jobId: ids.ocrJob,
        status: 'COMPLETED',
        progress: 100,
        pageNumbers: [1],
        documentFileId: ids.file,
        runId: ids.ocrRun,
      });
      return;
    }
    if (method === 'GET' && path === `/document-files/${ids.file}/ocr`) {
      await fulfillJson(route, state.ocrCompleted ? ocrRun : null);
      return;
    }

    if (method === 'GET' && path === '/language-detection/jobs') {
      await fulfillJson(route, emptyPage());
      return;
    }
    if (method === 'POST' && path === '/language-detection/jobs') {
      state.languageDetected = true;
      await fulfillJson(route, {
        jobId: ids.languageJob,
        status: 'COMPLETED',
        progress: 100,
        documentFileId: ids.file,
        extractionRunId: ids.extractionRun,
        ocrRunId: ids.ocrRun,
        runId: ids.languageRun,
        reusedExistingResult: false,
      });
      return;
    }
    if (method === 'GET' && path === `/document-files/${ids.file}/language-detection`) {
      await fulfillJson(route, state.languageDetected ? languageRun : null);
      return;
    }
    if (
      method === 'GET' &&
      path === `/language-detection/runs/${ids.languageRun}/summary`
    ) {
      await fulfillJson(route, languageSummary);
      return;
    }

    if (method === 'GET' && path === `/document-files/${ids.file}/compliance`) {
      await fulfillJson(route, state.complianceCompleted ? complianceRun : null);
      return;
    }
    if (method === 'GET' && path === `/document-files/${ids.file}/compliance-history`) {
      await fulfillJson(
        route,
        emptyPage(state.complianceCompleted ? [complianceRun] : []),
      );
      return;
    }
    if (method === 'POST' && path === '/compliance/jobs') {
      state.complianceCompleted = true;
      await fulfillJson(route, {
        jobId: ids.complianceJob,
        status: 'COMPLETED',
        progress: 100,
        documentFileId: ids.file,
        runId: ids.complianceRun,
        reusedExistingResult: false,
      });
      return;
    }
    if (method === 'GET' && path === `/compliance/runs/${ids.complianceRun}`) {
      await fulfillJson(route, complianceRun);
      return;
    }
    if (method === 'GET' && path === `/compliance/runs/${ids.complianceRun}/summary`) {
      await fulfillJson(route, complianceSummary);
      return;
    }
    if (
      method === 'GET' &&
      path === `/compliance/runs/${ids.complianceRun}/score-breakdown`
    ) {
      await fulfillJson(route, complianceScore);
      return;
    }

    if (method === 'GET' && path === `/document-files/${ids.file}/similarity`) {
      await fulfillJson(route, state.similarityCompleted ? similarityRun : null);
      return;
    }
    if (method === 'GET' && path === `/document-files/${ids.file}/similarity-history`) {
      await fulfillJson(
        route,
        emptyPage(state.similarityCompleted ? [similarityRun] : []),
      );
      return;
    }
    if (method === 'POST' && path === '/similarity/jobs') {
      state.similarityCompleted = true;
      await fulfillJson(route, {
        id: ids.similarityJob,
        jobId: ids.similarityJob,
        status: 'COMPLETED',
        progress: 100,
        documentFileId: ids.file,
        runId: ids.similarityRun,
        reusedExistingResult: false,
        message: 'Deterministic local similarity completed',
      });
      return;
    }
    if (method === 'GET' && path === '/similarity/jobs') {
      await fulfillJson(
        route,
        emptyPage(state.similarityCompleted ? [similarityJob] : []),
      );
      return;
    }
    if (method === 'GET' && path === `/similarity/runs/${ids.similarityRun}`) {
      await fulfillJson(route, similarityRun);
      return;
    }
    if (method === 'GET' && path === `/similarity/runs/${ids.similarityRun}/summary`) {
      await fulfillJson(route, {
        runId: ids.similarityRun,
        status: 'COMPLETED',
        averageSimilarity: 0.91,
        minimumSimilarity: 0.79,
        maximumSimilarity: 0.98,
        translationGroupCount: 4,
        eligibleGroupCount: 4,
        analysedGroupCount: 4,
        skippedGroupCount: 0,
        failedGroupCount: 0,
        categories: {
          HIGH: 3,
          ACCEPTABLE: 0,
          NEEDS_REVIEW: 1,
          LOW: 0,
          NOT_EVALUATED: 0,
        },
        pairAverages: { id_en: 0.93, id_zh: 0.89, en_zh: 0.9 },
        mismatches: {
          number: 0,
          date: 0,
          measurement: 0,
          reference: 0,
          negation: 0,
        },
        sectionCount: 0,
        findingCount: 0,
        qualityStatus: 'HIGH_QUALITY',
        warnings: [],
      });
      return;
    }
    if (method === 'GET' && path === `/similarity/runs/${ids.similarityRun}/sections`) {
      await fulfillJson(route, []);
      return;
    }
    if (method === 'GET' && path === `/similarity/runs/${ids.similarityRun}/results`) {
      await fulfillJson(route, emptyPage());
      return;
    }

    if (
      method === 'GET' &&
      path === `/document-files/${ids.file}/glossary-validation`
    ) {
      await fulfillJson(route, state.glossaryCompleted ? glossaryRun : null);
      return;
    }
    if (
      method === 'GET' &&
      path === `/document-files/${ids.file}/glossary-validation-history`
    ) {
      await fulfillJson(route, emptyPage(state.glossaryCompleted ? [glossaryRun] : []));
      return;
    }
    if (method === 'GET' && path === `/document-files/${ids.file}/glossary-history`) {
      await fulfillJson(route, emptyPage(state.glossaryCompleted ? [glossaryRun] : []));
      return;
    }
    if (method === 'POST' && path === '/glossary/validation/jobs') {
      state.glossaryCompleted = true;
      await fulfillJson(route, {
        jobId: ids.glossaryJobAndRun,
        runId: ids.glossaryJobAndRun,
        status: 'COMPLETED',
        progress: 100,
        documentFileId: ids.file,
        reusedExistingResult: false,
      });
      return;
    }
    if (
      method === 'GET' &&
      path === `/glossary/validation/jobs/${ids.glossaryJobAndRun}`
    ) {
      await fulfillJson(route, glossaryRun);
      return;
    }
    if (
      method === 'GET' &&
      path === `/glossary/validation/runs/${ids.glossaryJobAndRun}`
    ) {
      await fulfillJson(route, glossaryRun);
      return;
    }
    if (
      method === 'GET' &&
      path === `/glossary/validation/runs/${ids.glossaryJobAndRun}/summary`
    ) {
      await fulfillJson(route, {
        runId: ids.glossaryJobAndRun,
        status: 'COMPLETED',
        totalTerms: 14,
        matchedTerms: 12,
        preferredTermMatches: 12,
        forbiddenTermMatches: 0,
        missingRequiredTranslations: 0,
        inconsistentTerms: 0,
        exceptionAppliedCount: 0,
        totalFindings: 0,
        matchCount: 12,
        languageCounts: { id: 4, en: 4, zh: 4 },
        findingCounts: {},
        metrics: { glossaryQualityScore: 100 },
        warnings: [],
      });
      return;
    }
    if (
      method === 'GET' &&
      path === `/glossary/validation/runs/${ids.glossaryJobAndRun}/matches`
    ) {
      await fulfillJson(route, emptyPage());
      return;
    }
    if (
      method === 'GET' &&
      path === `/glossary/validation/runs/${ids.glossaryJobAndRun}/findings`
    ) {
      await fulfillJson(route, emptyPage());
      return;
    }
    if (method === 'GET' && path === '/glossary/profiles') {
      await fulfillJson(route, emptyPage());
      return;
    }

    if (method === 'GET' && path === `/document-files/${ids.file}/sharepoint/status`) {
      await fulfillJson(route, {
        documentFileId: ids.file,
        storageProvider: 'HYBRID',
        remoteSyncStatus: state.sharePointPushed ? 'SYNCED' : 'NOT_SYNCED',
        sharepointConnectionId: state.sharePointPushed ? ids.connection : null,
        remoteDriveId: state.sharePointPushed ? 'mock-drive-id' : null,
        remoteItemId: state.sharePointPushed ? 'mock-remote-item' : null,
        remotePath: state.sharePointPushed
          ? '/Phase10/MTI-HRM-POL-010_Rev.000.pdf'
          : null,
        remoteWebUrl: state.sharePointPushed
          ? 'https://contoso.sharepoint.com/sites/document-control/Phase10/MTI-HRM-POL-010_Rev.000.pdf'
          : null,
        remoteEtag: state.sharePointPushed ? '"mock-etag-1"' : null,
        remoteVersionId: state.sharePointPushed ? '1.0' : null,
        remoteLastModifiedAt: state.sharePointPushed ? laterTimestamp : null,
        remoteSize: state.sharePointPushed ? physicalFile.fileSize : null,
        lastSyncedAt: state.sharePointPushed ? laterTimestamp : null,
        syncErrorCode: null,
        syncErrorMessage: null,
      });
      return;
    }
    if (
      method === 'GET' &&
      path === `/document-files/${ids.file}/sharepoint/versions`
    ) {
      await fulfillJson(route, emptyPage());
      return;
    }
    if (method === 'POST' && path === `/document-files/${ids.file}/sharepoint/push`) {
      state.sharePointPushed = true;
      await fulfillJson(route, completedSyncJob('SINGLE_FILE_PUSH'));
      return;
    }

    if (method === 'GET' && path === '/integrations/sharepoint/connections') {
      await fulfillJson(route, emptyPage([connection]));
      return;
    }
    if (method === 'GET' && path === '/sharepoint/sync-profiles') {
      await fulfillJson(route, emptyPage([syncProfile]));
      return;
    }
    if (
      method === 'POST' &&
      path === `/sharepoint/sync-profiles/${ids.syncProfile}/run`
    ) {
      state.incrementalSyncCompleted = true;
      state.conflictCreated = true;
      await fulfillJson(route, completedSyncJob('MANUAL_INCREMENTAL'));
      return;
    }
    if (method === 'GET' && path === '/sharepoint/conflicts') {
      await fulfillJson(
        route,
        emptyPage(state.conflictCreated ? [buildConflict(state)] : []),
      );
      return;
    }
    if (method === 'GET' && path === `/sharepoint/conflicts/${ids.conflict}`) {
      await fulfillJson(route, buildConflict(state));
      return;
    }
    if (method === 'POST' && path === `/sharepoint/conflicts/${ids.conflict}/resolve`) {
      state.conflictResolved = true;
      await fulfillJson(route, buildConflict(state));
      return;
    }

    if (method === 'GET' && path === '/reports/jobs') {
      await fulfillJson(route, emptyPage(state.reportGenerated ? [reportJob] : []));
      return;
    }
    if (method === 'GET' && path === '/reports/snapshots') {
      await fulfillJson(
        route,
        emptyPage(state.reportGenerated ? [reportSnapshot] : []),
      );
      return;
    }
    if (method === 'POST' && path === '/reports/generate') {
      state.reportGenerated = true;
      await fulfillJson(route, reportJob);
      return;
    }
    if (method === 'GET' && path === `/reports/jobs/${ids.reportJob}`) {
      await fulfillJson(route, reportJob);
      return;
    }
    if (
      method === 'GET' &&
      path === `/reports/snapshots/${ids.reportSnapshot}/download`
    ) {
      await route.fulfill({
        status: 200,
        contentType:
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers: {
          'content-disposition': 'attachment; filename="phase10-audit-trail.xlsx"',
          'x-request-id': 'phase10-playwright-mock',
        },
        body: 'deterministic mock report, no production tenant data',
      });
      return;
    }

    state.unhandled.push(`${method} ${path}`);
    await route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({
        success: false,
        message: `Unhandled deterministic mock route: ${method} ${path}`,
        data: null,
        errors: [
          {
            field: null,
            code: 'E2E_MOCK_ROUTE_MISSING',
            message: `${method} ${path}`,
          },
        ],
      }),
    });
  });

  return state;
};

const findCall = (
  state: MockState,
  method: string,
  path: string,
): MockCall | undefined =>
  state.calls.find((call) => call.method === method && call.path === path);

test.describe('Phase 10 critical document lifecycle', () => {
  test('runs the trilingual workflow through deterministic Graph and SharePoint mocks', async ({
    page,
  }) => {
    const state = await installMockApi(page);

    await test.step('login through the real authentication screen', async () => {
      await page.goto('/login');
      await page.getByLabel('Email address').fill('phase10@example.test');
      await page
        .getByRole('textbox', { name: 'Password', exact: true })
        .fill('safe-e2e-password');
      await page.getByRole('button', { name: 'Sign in' }).click();

      await expect(page).toHaveURL(/\/dashboard$/);
      await expect(
        page.getByRole('heading', { name: 'Welcome, Phase 10 Administrator' }),
      ).toBeVisible();
    });

    await test.step('create the controlled document and initial revision', async () => {
      await page.goto('/documents/new');
      await expect(page.getByRole('heading', { name: 'Add Document' })).toBeVisible();

      await page.locator('select[name="departmentId"]').selectOption(ids.department);
      await page
        .locator('select[name="documentTypeId"]')
        .selectOption(ids.documentType);
      await page.locator('input[name="documentNumber"]').fill('010');
      await page.locator('input[name="title"]').fill('Phase 10 Trilingual Policy');
      await page
        .getByLabel('Description')
        .fill('Stateful Playwright validation document.');
      await page.getByRole('button', { name: 'Create Document' }).click();

      await expect(page).toHaveURL(new RegExp(`/documents/${ids.document}$`));
      await expect(
        page.getByRole('heading', { name: documentDetail.title }),
      ).toBeVisible();
    });

    await test.step('upload and identify a physical PDF', async () => {
      await page.goto(
        `/documents/upload?documentId=${ids.document}&revisionId=${ids.revision}`,
      );
      await page.getByLabel('Browse document files').setInputFiles({
        name: physicalFile.originalFilename,
        mimeType: 'application/pdf',
        buffer: Buffer.from('%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n'),
      });
      await page.getByRole('button', { name: 'Upload and Identify' }).click();

      await expect(page.getByText('Identification result')).toBeVisible();
      await page.getByRole('button', { name: 'Review Action' }).click();
      await expect(
        page.getByText('Attach to existing revision', { exact: true }),
      ).toBeVisible();
      await page.getByRole('button', { name: 'Continue to Metadata' }).click();
      await page.getByRole('button', { name: 'Confirm Upload' }).click();

      await expect(
        page.getByRole('heading', { name: 'Physical file committed' }),
      ).toBeVisible();
      await expect(page.getByText('AVAILABLE', { exact: true })).toBeVisible();
    });

    await test.step('extract content and run conditional OCR for the scanned PDF', async () => {
      await page.goto(`/documents/${ids.document}?tab=files`);
      await expect(
        page.getByRole('heading', { name: 'Content Extraction' }),
      ).toBeVisible();
      await page.getByRole('button', { name: 'Extract Content' }).click();
      await expect(page.getByText('Extraction queued', { exact: true })).toBeVisible();
      await expect(page.getByText('Yes', { exact: true })).toBeVisible();

      await page.getByRole('button', { name: 'intelligence' }).click();
      await page.getByRole('button', { name: 'Run OCR' }).click();
      await expect(page.getByRole('dialog', { name: 'Start OCR' })).toBeVisible();
      await page.getByRole('button', { name: 'Queue OCR' }).click();
      await expect(page.getByText('OCR queued', { exact: true })).toBeVisible();
    });

    await test.step('detect Indonesian, English, and Chinese content', async () => {
      const detectButton = page.getByRole('button', {
        name: 'Detect Languages',
      });
      await expect(detectButton).toBeVisible();
      await detectButton.click();
      await expect(
        page.getByText('Language detection queued', { exact: true }),
      ).toBeVisible();
      await expect(
        page.getByRole('link', { name: 'View Language Results' }),
      ).toBeVisible();
    });

    await test.step('validate multilingual compliance', async () => {
      await page.goto(`/documents/${ids.document}?tab=compliance`);
      await page.getByRole('link', { name: 'Validate Compliance' }).click();
      await expect(
        page.getByRole('heading', { name: documentDetail.title }),
      ).toBeVisible();
      await page.getByRole('button', { name: 'Run Validation' }).first().click();

      await expect(
        page.getByText('Compliance validation queued', { exact: true }),
      ).toBeVisible();
      await expect(page).toHaveURL(/runId=10000000-0000-4000-8000-000000000019/);
      await expect(page.getByText('82.5', { exact: true }).first()).toBeVisible();
    });

    await test.step('run translation similarity', async () => {
      await page.goto(
        `/documents/${ids.document}/revisions/${ids.revision}/similarity?fileId=${ids.file}`,
      );
      await page.getByRole('button', { name: 'Run Similarity' }).first().click();

      await expect(page).toHaveURL(/\/documents\/similarity-queue/);
      await expect(
        page.getByRole('heading', { name: 'Similarity Queue' }),
      ).toBeVisible();
      await expect(
        page.getByRole('cell', { name: 'COMPLETED', exact: true }),
      ).toBeVisible();
    });

    await test.step('validate the multilingual glossary', async () => {
      await page.goto(`/compliance/glossary?fileId=${ids.file}`);
      await page.getByRole('button', { name: 'Validate Glossary' }).click();

      await expect(
        page.getByText('Glossary validation queued', { exact: true }),
      ).toBeVisible();
      await expect(page.getByText('Terms Evaluated', { exact: true })).toBeVisible();
      await expect(page.getByText('14', { exact: true }).first()).toBeVisible();
    });

    await test.step('push the physical file to explicitly mocked SharePoint', async () => {
      await page.goto(`/documents/${ids.document}?tab=sharepoint`);
      await expect(page.getByText('NOT SYNCED', { exact: true })).toBeVisible();
      await page.getByRole('button', { name: 'Push to SharePoint' }).click();
      await expect(
        page.getByRole('dialog', { name: 'Confirm SharePoint file action' }),
      ).toBeVisible();
      await page.getByRole('button', { name: 'Queue Push' }).click();

      await expect(
        page.getByText('SharePoint push queued', { exact: true }),
      ).toBeVisible();
      await expect(page.getByText('SYNCED', { exact: true })).toBeVisible();
    });

    await test.step('run a delta-enabled incremental sync that creates a conflict', async () => {
      await page.goto('/integrations/sharepoint/sync-profiles');
      await expect(
        page.getByRole('heading', { name: 'SharePoint Sync Profiles' }),
      ).toBeVisible();
      await expect(
        page.getByText('Mock incremental document sync', { exact: true }),
      ).toBeVisible();
      await page.getByRole('button', { name: 'Run' }).click();
      await expect(
        page.getByText('SharePoint sync queued', { exact: true }),
      ).toBeVisible();

      await page.goto('/documents/sharepoint-conflicts');
      await expect(
        page.getByRole('heading', { name: 'SharePoint Conflicts' }),
      ).toBeVisible();
      await expect(page.getByText('BOTH MODIFIED', { exact: true })).toBeVisible();
      await page
        .getByRole('row')
        .filter({ hasText: 'BOTH MODIFIED' })
        .getByRole('link', { name: 'View', exact: true })
        .click();
    });

    await test.step('resolve the audited SharePoint conflict', async () => {
      await expect(
        page.getByRole('heading', { name: 'SharePoint Conflict Detail' }),
      ).toBeVisible();
      await page.getByLabel('Resolution option').selectOption('KEEP_LOCAL');
      await page
        .getByLabel('Resolution comment')
        .fill('Keep audited local version after deterministic review.');
      await page.getByRole('button', { name: 'Resolve Conflict' }).click();

      await expect(page.getByText('Conflict resolved', { exact: true })).toBeVisible();
      await expect(page.getByText('RESOLVED', { exact: true })).toBeVisible();
    });

    await test.step('receive and acknowledge the in-app notification', async () => {
      await page.reload();
      const bell = page.getByRole('button', {
        name: 'Notifications, 1 unread',
      });
      await expect(bell).toBeVisible();
      await bell.click();
      await expect(
        page.getByText('SharePoint conflict resolved', { exact: true }),
      ).toBeVisible();
      await page
        .getByRole('button', {
          name: /^SharePoint conflict resolved The deterministic/,
        })
        .click();
      await expect(page.getByRole('button', { name: 'Notifications' })).toBeVisible();
    });

    await test.step('generate and download an authenticated report snapshot', async () => {
      await page.goto('/reports/advanced-analytics');
      await expect(
        page.getByRole('heading', { name: 'Advanced Analytics' }),
      ).toBeVisible();
      await page.getByLabel('Report Name').fill('Phase 10 audit trail');
      await page.getByRole('button', { name: 'Generate' }).click();
      await expect(
        page.getByText('Advanced report queued', { exact: true }),
      ).toBeVisible();

      const downloadButton = page.getByRole('button', { name: 'Download' });
      await expect(downloadButton).toBeVisible();
      const downloadPromise = page.waitForEvent('download');
      await downloadButton.click();
      const download = await downloadPromise;
      expect(download.suggestedFilename()).toBe('phase10-audit-trail.xlsx');
    });

    await test.step('verify state transitions and canonical request contracts', async () => {
      expect(state).toMatchObject({
        loggedIn: true,
        documentCreated: true,
        uploaded: true,
        extracted: true,
        ocrCompleted: true,
        languageDetected: true,
        complianceCompleted: true,
        similarityCompleted: true,
        glossaryCompleted: true,
        sharePointPushed: true,
        incrementalSyncCompleted: true,
        conflictCreated: true,
        conflictResolved: true,
        notificationRead: true,
        reportGenerated: true,
      });

      expect(findCall(state, 'POST', '/extractions')?.body).toMatchObject({
        documentFileId: ids.file,
      });
      expect(findCall(state, 'POST', '/ocr/jobs')?.body).toMatchObject({
        documentFileId: ids.file,
        extractionRunId: ids.extractionRun,
      });
      expect(findCall(state, 'POST', '/language-detection/jobs')?.body).toMatchObject({
        documentFileId: ids.file,
        extractionRunId: ids.extractionRun,
        ocrRunId: ids.ocrRun,
      });
      expect(findCall(state, 'POST', '/compliance/jobs')?.body).toMatchObject({
        documentFileId: ids.file,
        extractionRunId: ids.extractionRun,
        ocrRunId: ids.ocrRun,
        languageDetectionRunId: ids.languageRun,
        validationRuleId: ids.validationRule,
      });
      expect(findCall(state, 'POST', '/similarity/jobs')?.body).toMatchObject({
        documentFileId: ids.file,
      });
      expect(findCall(state, 'POST', '/glossary/validation/jobs')?.body).toMatchObject({
        documentFileId: ids.file,
      });
      expect(
        findCall(state, 'POST', `/sharepoint/sync-profiles/${ids.syncProfile}/run`)
          ?.body,
      ).toEqual({ jobType: 'MANUAL_INCREMENTAL' });
      expect(
        findCall(state, 'POST', `/sharepoint/conflicts/${ids.conflict}/resolve`)?.body,
      ).toEqual({
        resolution: 'KEEP_LOCAL',
        comment: 'Keep audited local version after deterministic review.',
      });
      expect(findCall(state, 'POST', '/reports/generate')?.body).toMatchObject({
        reportName: 'Phase 10 audit trail',
        outputFormat: 'xlsx',
      });
      expect(state.unhandled).toEqual([]);
    });
  });
});
