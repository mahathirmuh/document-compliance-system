import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
}));

vi.mock('./client', () => ({
  apiClient: apiClientMock,
}));

import {
  createReportSchedule,
  generateAdvancedReport,
  runReportSchedule,
} from './advancedReportingApi';
import {
  confirmGlossaryImport,
  exportGlossary,
  testGlossaryMatch,
} from './glossaryApi';
import {
  exportRevisionComparison,
  startRevisionComparison,
} from './revisionComparisonApi';
import {
  exportSimilarity,
  listSimilarityResults,
  startSimilarity,
} from './similarityApi';

const response = <T>(data: T) => ({
  data: { success: true, message: 'OK', data, errors: null },
});

describe('Phase 9 API contracts', () => {
  beforeEach(() => {
    apiClientMock.get.mockReset();
    apiClientMock.post.mockReset();
    apiClientMock.put.mockReset();
  });

  it('queues local similarity and sends every server-side result filter', async () => {
    const queued = {
      id: 'similarity-job-id',
      status: 'QUEUED' as const,
      progress: 0,
      documentFileId: 'file-id',
      runId: null,
      reusedExistingResult: false,
    };
    apiClientMock.post.mockResolvedValue(response(queued));
    apiClientMock.get.mockResolvedValue(
      response({
        items: [],
        page: 1,
        pageSize: 50,
        totalItems: 0,
        totalPages: 0,
      }),
    );

    await expect(
      startSimilarity({
        documentFileId: 'file-id',
        complianceRunId: 'compliance-run-id',
        force: false,
      }),
    ).resolves.toEqual(queued);
    expect(apiClientMock.post).toHaveBeenCalledWith('/similarity/jobs', {
      documentFileId: 'file-id',
      complianceRunId: 'compliance-run-id',
      force: false,
    });

    const filters = {
      page: 1,
      pageSize: 50,
      sourceLanguage: 'id' as const,
      targetLanguage: 'zh' as const,
      similarityCategory: 'LOW' as const,
      minimumScore: 0.2,
      maximumScore: 0.7,
      hasNumberMismatch: true,
      hasNegationMismatch: true,
      findingSeverity: 'MAJOR' as const,
      search: 'bounded source',
    };
    await listSimilarityResults('similarity-run-id', filters);
    expect(apiClientMock.get).toHaveBeenCalledWith(
      '/similarity/runs/similarity-run-id/results',
      expect.objectContaining({ params: filters }),
    );
  });

  it('exports similarity through a private run-scoped download', async () => {
    apiClientMock.get.mockResolvedValue({
      data: new Blob(['similarity']),
      headers: {
        'content-disposition': 'attachment; filename="translation-similarity.xlsx"',
      },
    });

    await expect(exportSimilarity('similarity-run-id', 'xlsx')).resolves.toEqual(
      expect.objectContaining({ fileName: 'translation-similarity.xlsx' }),
    );
    expect(apiClientMock.get).toHaveBeenCalledWith(
      '/similarity/runs/similarity-run-id/export',
      expect.objectContaining({
        params: { format: 'xlsx' },
        responseType: 'blob',
      }),
    );
  });

  it('confirms the exact previewed glossary workbook and explicit import mode', async () => {
    const file = new File(['workbook'], 'glossary.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
    const imported = {
      mode: 'UPSERT' as const,
      totalRows: 4,
      created: { terms: 1 },
      updated: { translations: 1 },
      skipped: {},
    };
    apiClientMock.post.mockResolvedValue(response(imported));

    await expect(confirmGlossaryImport({ file, mode: 'UPSERT' })).resolves.toEqual(
      imported,
    );
    const [, body] = apiClientMock.post.mock.calls[0] as [string, FormData];
    expect(apiClientMock.post).toHaveBeenCalledWith(
      '/glossary/import/confirm',
      expect.any(FormData),
    );
    expect(body.get('file')).toBe(file);
    expect(body.get('mode')).toBe('UPSERT');
  });

  it('returns exception-aware glossary matcher results and scoped exports', async () => {
    const match = {
      glossaryTermId: 'term-id',
      glossaryTranslationId: 'translation-id',
      glossaryVariantId: null,
      termCode: 'APD',
      conceptName: 'Alat Pelindung Diri',
      languageCode: 'id' as const,
      matchedText: 'APD',
      normalisedMatchedText: 'apd',
      startOffset: 0,
      endOffset: 3,
      matchType: 'EXACT',
      isPreferred: true,
      isForbidden: false,
      isAllowedVariant: false,
      exceptionApplied: true,
      exceptionId: 'exception-id',
      exceptionType: 'IGNORE_TERM' as const,
    };
    apiClientMock.post.mockResolvedValue(
      response({
        profileIds: ['profile-id'],
        totalMatches: 1,
        matches: [match],
        warnings: [],
      }),
    );
    apiClientMock.get.mockResolvedValue({
      data: new Blob(['glossary']),
      headers: { 'content-disposition': 'attachment; filename="glossary.json"' },
    });

    await expect(
      testGlossaryMatch({
        text: 'APD wajib digunakan.',
        languageCode: 'id',
        profileIds: ['profile-id'],
      }),
    ).resolves.toEqual([match]);
    expect(apiClientMock.post).toHaveBeenCalledWith('/glossary/test-match', {
      text: 'APD wajib digunakan.',
      languageCode: 'id',
      profileIds: ['profile-id'],
    });

    await exportGlossary('json', {
      profileIds: ['profile-id'],
      includeInactive: true,
    });
    expect(apiClientMock.get).toHaveBeenCalledWith(
      '/glossary/export',
      expect.objectContaining({
        params: {
          format: 'json',
          profileIds: ['profile-id'],
          includeInactive: true,
        },
      }),
    );
  });

  it('starts and exports an immutable revision comparison', async () => {
    const queued = {
      jobId: 'comparison-job-id',
      status: 'QUEUED' as const,
      progress: 0,
      comparisonId: null,
      reusedExistingResult: false,
    };
    apiClientMock.post.mockResolvedValue(response(queued));
    apiClientMock.get.mockResolvedValue({
      data: new Blob(['revision']),
      headers: {
        'content-disposition': 'attachment; filename="revision-comparison.pdf"',
      },
    });

    await expect(
      startRevisionComparison({
        documentId: 'document-id',
        baseRevisionId: 'revision-1',
        targetRevisionId: 'revision-2',
        force: false,
      }),
    ).resolves.toEqual(queued);
    expect(apiClientMock.post).toHaveBeenCalledWith('/revision-comparisons/jobs', {
      documentId: 'document-id',
      baseRevisionId: 'revision-1',
      targetRevisionId: 'revision-2',
      force: false,
    });

    await exportRevisionComparison('comparison-id', 'pdf');
    expect(apiClientMock.get).toHaveBeenCalledWith(
      '/revision-comparisons/comparison-id/export',
      expect.objectContaining({
        params: { format: 'pdf' },
        responseType: 'blob',
      }),
    );
  });

  it('uses one output format per report job and multiple formats per schedule', async () => {
    const job = {
      id: 'report-job-id',
      reportType: 'LANGUAGE_QUALITY' as const,
      reportName: 'Language quality',
      outputFormat: 'xlsx' as const,
      status: 'QUEUED' as const,
      snapshotStatus: 'GENERATING' as const,
      progress: 0,
      currentStage: null,
      requestedAt: '2026-07-26T01:00:00Z',
      startedAt: null,
      completedAt: null,
      errorCode: null,
      errorMessage: null,
    };
    const schedule = {
      id: 'schedule-id',
      name: 'Monthly quality',
      reportType: 'LANGUAGE_QUALITY' as const,
      filters: {},
      formats: ['xlsx', 'pdf'] as const,
      scheduleType: 'MONTHLY' as const,
      cronExpression: null,
      timezone: 'Asia/Makassar',
      isActive: true,
      lastRunAt: null,
      nextRunAt: null,
      createdBy: 'user-id',
      updatedBy: 'user-id',
      createdAt: '2026-07-26T01:00:00Z',
      updatedAt: '2026-07-26T01:00:00Z',
    };
    apiClientMock.post
      .mockResolvedValueOnce(response(job))
      .mockResolvedValueOnce(response(schedule))
      .mockResolvedValueOnce(
        response({ scheduleId: 'schedule-id', jobIds: ['report-job-id'] }),
      );

    const generatePayload = {
      reportType: 'LANGUAGE_QUALITY' as const,
      reportName: 'Language quality',
      filters: { languagePairs: ['id-en'] },
      outputFormat: 'xlsx' as const,
      includeCharts: true,
      includeDetailedTables: true,
    };
    await generateAdvancedReport(generatePayload);
    expect(apiClientMock.post).toHaveBeenNthCalledWith(
      1,
      '/reports/generate',
      generatePayload,
    );

    const schedulePayload = {
      name: 'Monthly quality',
      reportType: 'LANGUAGE_QUALITY' as const,
      filters: {},
      formats: ['xlsx', 'pdf'] as const,
      scheduleType: 'MONTHLY' as const,
      cronExpression: null,
      timezone: 'Asia/Makassar',
    };
    await createReportSchedule(schedulePayload);
    expect(apiClientMock.post).toHaveBeenNthCalledWith(
      2,
      '/reports/schedules',
      schedulePayload,
    );
    await expect(runReportSchedule('schedule-id')).resolves.toEqual({
      scheduleId: 'schedule-id',
      jobIds: ['report-job-id'],
    });
  });
});
