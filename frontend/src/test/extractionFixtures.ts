import type { ExtractionJob, ExtractionJobDetail } from '../types/extraction';
import type {
  ExtractedBlock,
  ExtractedContainer,
  ExtractedTable,
  ExtractionRun,
  ExtractionRunHistoryItem,
} from '../types/extractedContent';

export const extractionIds = {
  job: '11111111-1111-4111-8111-111111111111',
  run: '22222222-2222-4222-8222-222222222222',
  document: '33333333-3333-4333-8333-333333333333',
  revision: '44444444-4444-4444-8444-444444444444',
  file: '55555555-5555-4555-8555-555555555555',
  container: '66666666-6666-4666-8666-666666666666',
  secondContainer: '77777777-7777-4777-8777-777777777777',
  block: '88888888-8888-4888-8888-888888888888',
  table: '99999999-9999-4999-8999-999999999999',
} as const;

const document = {
  id: extractionIds.document,
  baseDocumentCode: 'MTI-HRM-SOP-001',
  title: 'Document Control Procedure',
  departmentId: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
};

const revision = {
  id: extractionIds.revision,
  revisionCode: 'Rev.000',
  fullDocumentCode: 'MTI-HRM-SOP-001_Rev.000',
};

const file = {
  id: extractionIds.file,
  filename: 'MTI-HRM-SOP-001_Rev.000.pdf',
  extension: 'pdf' as const,
  sha256Hash: 'a'.repeat(64),
};

export const queuedExtractionJob: ExtractionJob = {
  id: extractionIds.job,
  document,
  revision,
  file,
  jobType: 'INITIAL_EXTRACTION',
  status: 'EXTRACTING',
  progress: 45,
  currentStage: 'Extracting page 9 of 20',
  requestedBy: {
    id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
    name: 'Document Controller',
  },
  requestedAt: '2026-07-25T12:00:00+08:00',
  startedAt: '2026-07-25T12:00:03+08:00',
  completedAt: null,
  cancelledAt: null,
  runId: null,
  resultSummary: null,
};

export const failedExtractionJob: ExtractionJobDetail = {
  ...queuedExtractionJob,
  status: 'FAILED',
  progress: 12,
  currentStage: 'Extraction failed',
  attemptNumber: 1,
  maximumAttempts: 3,
  failedAt: '2026-07-25T12:00:10+08:00',
  error: {
    code: 'PDF_PASSWORD_REQUIRED',
    message: 'This PDF is password-protected and cannot be extracted.',
  },
};

export const extractionRun: ExtractionRun = {
  runId: extractionIds.run,
  extractionJobId: extractionIds.job,
  document,
  revision,
  file,
  status: 'COMPLETED',
  extractorType: 'PDF',
  extractorVersion: '1.0.0',
  sourceSha256Hash: 'a'.repeat(64),
  sourceFileSize: 4096,
  contentHash: 'b'.repeat(64),
  totalPages: 2,
  totalSheets: 0,
  totalBlocks: 2,
  totalParagraphs: 0,
  totalTables: 0,
  totalCells: 0,
  totalCharacters: 53,
  totalWords: 8,
  hasSelectableText: true,
  requiresOcr: false,
  warnings: [],
  metadata: { producer: 'Generated test fixture' },
  startedAt: '2026-07-25T12:00:03+08:00',
  completedAt: '2026-07-25T12:00:15+08:00',
  createdAt: '2026-07-25T12:00:15+08:00',
  isLatest: true,
};

export const pdfContainers: ExtractedContainer[] = [
  {
    id: extractionIds.container,
    extractionRunId: extractionIds.run,
    containerType: 'PDF_PAGE',
    containerIndex: 1,
    name: 'Page 1',
    title: 'Page 1',
    characterCount: 26,
    wordCount: 3,
    metadata: { pageNumber: 1, width: 595, height: 842 },
    createdAt: '2026-07-25T12:00:15+08:00',
  },
  {
    id: extractionIds.secondContainer,
    extractionRunId: extractionIds.run,
    containerType: 'PDF_PAGE',
    containerIndex: 2,
    name: 'Page 2',
    title: 'Page 2',
    characterCount: 27,
    wordCount: 3,
    metadata: { pageNumber: 2, width: 595, height: 842 },
    createdAt: '2026-07-25T12:00:15+08:00',
  },
];

export const extractedBlocks: ExtractedBlock[] = [
  {
    id: extractionIds.block,
    extractionRunId: extractionIds.run,
    containerId: extractionIds.container,
    parentBlockId: null,
    blockType: 'HEADING',
    blockOrder: 1,
    sourceReference: 'PDF:page=1:block=1',
    text: 'Document Control Procedure',
    normalisedText: 'Document Control Procedure',
    styleName: 'Heading 1',
    headingLevel: 1,
    location: { page: 1, bbox: [72, 110, 520, 140] },
    metadata: {},
    characterCount: 26,
    wordCount: 3,
    createdAt: '2026-07-25T12:00:15+08:00',
  },
  {
    id: 'aaaaaaaa-1111-4111-8111-111111111111',
    extractionRunId: extractionIds.run,
    containerId: extractionIds.container,
    parentBlockId: null,
    blockType: 'PARAGRAPH',
    blockOrder: 2,
    sourceReference: 'PDF:page=1:block=2',
    text: 'A safe <script>alert(1)</script> document control paragraph.',
    normalisedText: 'A safe <script>alert(1)</script> document control paragraph.',
    styleName: null,
    headingLevel: null,
    location: { page: 1, bbox: [72, 150, 520, 190] },
    metadata: {},
    characterCount: 58,
    wordCount: 6,
    createdAt: '2026-07-25T12:00:15+08:00',
  },
];

export const extractedTable: ExtractedTable = {
  id: extractionIds.table,
  extractionRunId: extractionIds.run,
  containerId: extractionIds.container,
  sourceReference: 'DOCX:table=1',
  tableIndex: 1,
  rowCount: 1,
  columnCount: 2,
  metadata: { style: 'Table Grid' },
  cells: [
    {
      id: 'bbbbbbbb-1111-4111-8111-111111111111',
      extractedTableId: extractionIds.table,
      rowIndex: 0,
      columnIndex: 0,
      rowSpan: 1,
      columnSpan: 1,
      coordinate: null,
      text: 'Code',
      normalisedText: 'Code',
      metadata: {},
      createdAt: '2026-07-25T12:00:15+08:00',
    },
    {
      id: 'cccccccc-1111-4111-8111-111111111111',
      extractedTableId: extractionIds.table,
      rowIndex: 0,
      columnIndex: 1,
      rowSpan: 1,
      columnSpan: 1,
      coordinate: null,
      text: 'Title',
      normalisedText: 'Title',
      metadata: {},
      createdAt: '2026-07-25T12:00:15+08:00',
    },
  ],
  createdAt: '2026-07-25T12:00:15+08:00',
};

export const extractionHistoryItem: ExtractionRunHistoryItem = {
  id: extractionIds.run,
  extractionJobId: extractionIds.job,
  extractorType: 'PDF',
  extractorVersion: '1.0.0',
  status: 'COMPLETED',
  sourceSha256Hash: 'a'.repeat(64),
  contentHash: 'b'.repeat(64),
  summary: extractionRun,
  requestedBy: {
    id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
    name: 'Document Controller',
  },
  reExtractionReason: null,
  warnings: [],
  completedAt: '2026-07-25T12:00:15+08:00',
  isLatest: true,
};
