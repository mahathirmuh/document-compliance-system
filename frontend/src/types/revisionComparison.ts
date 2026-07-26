import type { DocumentUserSummary } from './document';
import type { PaginatedData } from './masterData';

export const revisionChangeTypes = [
  'ADDED',
  'REMOVED',
  'MODIFIED',
  'MOVED',
  'UNCHANGED',
  'SPLIT',
  'MERGED',
] as const;
export type RevisionChangeType = (typeof revisionChangeTypes)[number];

export type RevisionEntityType =
  | 'SECTION'
  | 'CONTAINER'
  | 'TRANSLATION_GROUP'
  | 'PARAGRAPH'
  | 'TABLE'
  | 'TABLE_ROW'
  | 'TABLE_CELL'
  | 'XLSX_CELL'
  | 'PDF_BLOCK'
  | 'HEADING';

export const revisionComparisonJobStatuses = [
  'QUEUED',
  'LOADING_REVISIONS',
  'ALIGNING_SECTIONS',
  'ALIGNING_GROUPS',
  'COMPARING_CONTENT',
  'COMPARING_LANGUAGES',
  'COMPARING_FINDINGS',
  'CALCULATING_SUMMARY',
  'PERSISTING',
  'COMPLETED',
  'PARTIALLY_COMPLETED',
  'FAILED',
  'CANCEL_REQUESTED',
  'CANCELLED',
] as const;
export type RevisionComparisonJobStatus =
  (typeof revisionComparisonJobStatuses)[number];
export type RevisionComparisonClassification =
  'IMPROVED' | 'REGRESSED' | 'UNCHANGED' | 'MIXED';
export type RevisionComparisonExportFormat = 'json' | 'xlsx' | 'pdf';
export type RevisionComparisonJobType = 'INITIAL' | 'REANALYSIS' | 'MANUAL';

export const terminalRevisionComparisonJobStatuses: readonly RevisionComparisonJobStatus[] =
  ['COMPLETED', 'PARTIALLY_COMPLETED', 'FAILED', 'CANCELLED'];

export const isTerminalRevisionComparisonJobStatus = (
  status: RevisionComparisonJobStatus,
): boolean => terminalRevisionComparisonJobStatuses.includes(status);

export interface RevisionComparisonRequest {
  documentId: string;
  baseRevisionId: string;
  targetRevisionId: string;
  force?: boolean;
}

export interface RevisionComparisonQueuedResult {
  jobId: string;
  status: RevisionComparisonJobStatus;
  progress: number;
  comparisonId: string | null;
  reusedExistingResult: boolean;
}

export interface RevisionComparisonJob {
  id: string;
  documentId: string;
  baseRevisionId: string;
  targetRevisionId: string;
  baseDocumentFileId: string;
  targetDocumentFileId: string;
  jobType: RevisionComparisonJobType;
  status: RevisionComparisonJobStatus;
  progress: number;
  currentStage: string | null;
  requestedBy: string | DocumentUserSummary | null;
  requestedAt: string;
  startedAt: string | null;
  completedAt: string | null;
  failedAt: string | null;
  cancelledAt: string | null;
  errorCode: string | null;
  errorMessage: string | null;
  prerequisiteIssues?: readonly string[];
  resultSummary: {
    comparisonId?: string | null;
    totalChanges?: number;
    classification?: RevisionComparisonClassification;
  } | null;
  document?: {
    id: string;
    baseDocumentCode: string;
    title?: string;
  } | null;
  baseRevision?: { id: string; revisionCode: string } | null;
  targetRevision?: { id: string; revisionCode: string } | null;
}

export interface RevisionComparisonJobListParams {
  page: number;
  pageSize: number;
  status?: RevisionComparisonJobStatus | readonly RevisionComparisonJobStatus[];
  documentId?: string;
  departmentId?: string;
}

export type RevisionComparisonJobList = PaginatedData<RevisionComparisonJob>;

export interface RevisionComparison {
  id: string;
  revisionComparisonJobId: string;
  documentId: string;
  baseRevisionId: string;
  targetRevisionId: string;
  baseDocumentFileId: string;
  targetDocumentFileId: string;
  baseExtractionRunId: string | null;
  targetExtractionRunId: string | null;
  baseComplianceRunId: string | null;
  targetComplianceRunId: string | null;
  baseSimilarityRunId: string | null;
  targetSimilarityRunId: string | null;
  baseGlossaryRunId: string | null;
  targetGlossaryRunId: string | null;
  baseRevisionCode?: string;
  targetRevisionCode?: string;
  status: 'COMPLETED' | 'PARTIALLY_COMPLETED' | 'FAILED';
  totalChanges: number;
  addedBlocks: number;
  removedBlocks: number;
  modifiedBlocks: number;
  movedBlocks: number;
  unchangedBlocks: number;
  addedSections: number;
  removedSections: number;
  modifiedSections: number;
  addedTranslationGroups: number;
  removedTranslationGroups: number;
  modifiedTranslationGroups: number;
  complianceScoreChange: number | null;
  similarityScoreChange: number | null;
  glossaryViolationChange?: number | null;
  newFindings: number;
  removedFindings: number;
  repeatedFindings: number;
  severityChangeCount: number;
  classification: RevisionComparisonClassification;
  baseContentHash: string | null;
  targetContentHash: string | null;
  languageCoverageChange: Readonly<Record<string, unknown>>;
  summary: Readonly<Record<string, unknown>>;
  warnings: readonly unknown[];
  requestedBy: string | DocumentUserSummary | null;
  startedAt: string | null;
  completedAt: string | null;
  createdAt: string;
}

export interface RevisionComparisonSummary {
  comparisonId: string;
  classification: RevisionComparisonClassification;
  totalChanges: number;
  added: number;
  removed: number;
  modified: number;
  moved: number;
  unchanged: number;
  complianceScoreChange: number | null;
  similarityScoreChange: number | null;
  similarityChange?: number | null;
  glossaryViolationChange?: number | null;
  newFindings: number;
  noLongerReproduced: number;
  summary: Readonly<Record<string, unknown>>;
  warnings: readonly unknown[];
  keyRegressions?: readonly string[];
  keyImprovements?: readonly string[];
}

export interface RevisionChange {
  id: string;
  revisionComparisonId: string;
  changeType: RevisionChangeType;
  entityType: RevisionEntityType;
  baseSectionId: string | null;
  targetSectionId: string | null;
  baseContainerId: string | null;
  targetContainerId: string | null;
  baseTranslationGroupId: string | null;
  targetTranslationGroupId: string | null;
  baseBlockId: string | null;
  targetBlockId: string | null;
  sectionName?: string | null;
  languageCode: 'id' | 'en' | 'zh' | null;
  sourceReferenceBase: string | null;
  sourceReferenceTarget: string | null;
  baseTextSnapshot: string | null;
  targetTextSnapshot: string | null;
  textSimilarity: number | null;
  structuralSimilarity: number | null;
  alignmentConfidence: number | null;
  characterChangeCount: number;
  wordChangeCount: number;
  metadata?: Record<string, unknown> | null;
  createdAt: string;
}

export interface RevisionChangeListParams {
  page: number;
  pageSize: number;
  changeType?: RevisionChangeType;
  entityType?: RevisionEntityType;
  languageCode?: 'id' | 'en' | 'zh';
  sectionId?: string;
  search?: string;
}

export type RevisionChangeList = PaginatedData<RevisionChange>;

export interface RevisionSectionChange {
  sectionKey: string;
  added: number;
  removed: number;
  modified: number;
  moved: number;
  unchanged: number;
}

export interface RevisionLanguageChange {
  languageCode: 'id' | 'en' | 'zh' | 'unknown';
  baseCount: number;
  targetCount: number;
  baseCoverage: number | null;
  targetCoverage: number | null;
  coverageChange: number | null;
  additions: number;
  removals: number;
  modifications: number;
  basePresence: boolean;
  targetPresence: boolean;
  regression: boolean;
  fixedMissingLanguage: boolean;
}

export type RevisionFindingComparisonStatus =
  | 'NEW'
  | 'NO_LONGER_REPRODUCED'
  | 'REPEATED'
  | 'SEVERITY_INCREASED'
  | 'SEVERITY_DECREASED'
  | 'STATUS_CHANGED'
  | 'UNCHANGED';

export interface RevisionFindingChange {
  findingKey: string;
  findingCode: string;
  baseSeverity: string | null;
  targetSeverity: string | null;
  comparisonStatus: RevisionFindingComparisonStatus;
  baseStatus: string | null;
  targetStatus: string | null;
  section: string | null;
  language: string | null;
  location: string | null;
}

export interface RevisionSectionChangeList {
  comparisonId: string;
  items: readonly RevisionSectionChange[];
}
export interface RevisionLanguageChangeList {
  comparisonId: string;
  items: readonly RevisionLanguageChange[];
  groupsAdded: number;
  groupsRemoved: number;
  groupsModified: number;
}
export interface RevisionFindingChangeList {
  comparisonId: string;
  items: readonly RevisionFindingChange[];
  summary: Readonly<Record<string, number>>;
}

export type RevisionComparisonHistory = PaginatedData<RevisionComparison>;

export interface RevisionComparisonDownload {
  blob: Blob;
  fileName: string | null;
}
