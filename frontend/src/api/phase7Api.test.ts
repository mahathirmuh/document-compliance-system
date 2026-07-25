import axios from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock('./client', () => ({
  apiClient: apiClientMock,
}));

import {
  exportLanguageResults,
  languageDetectionParamsSerializer,
  listLanguageBlocks,
  listLanguageDetectionDocuments,
  startLanguageDetection,
} from './languageDetectionApi';
import { exportOCR, getOCRPage, ocrParamsSerializer, startOCR } from './ocrApi';
import { languageDocument, phase7Ids } from '../test/phase7Fixtures';
import { terminalOCRJobStatuses } from '../types/ocr';

describe('Phase 7 API contracts', () => {
  beforeEach(() => {
    apiClientMock.get.mockReset();
    apiClientMock.post.mockReset();
  });

  it('serializes OCR status filters as repeated parameters', () => {
    const uri = axios.getUri({
      url: '/ocr/jobs',
      params: { status: terminalOCRJobStatuses },
      paramsSerializer: ocrParamsSerializer,
    });
    const query = new URL(uri, 'http://localhost').searchParams;

    expect(query.getAll('status')).toEqual([...terminalOCRJobStatuses]);
    expect(query.has('status[]')).toBe(false);
  });

  it('queues OCR with the exact camelCase PDF contract', async () => {
    const queued = {
      jobId: phase7Ids.job,
      status: 'QUEUED',
      progress: 0,
      pageNumbers: [2],
      documentFileId: phase7Ids.file,
      runId: null,
    };
    apiClientMock.post.mockResolvedValue({
      data: { success: true, message: 'Queued', data: queued, errors: null },
    });

    await expect(
      startOCR({
        documentFileId: phase7Ids.file,
        extractionRunId: phase7Ids.extractionRun,
        languageProfile: 'AUTO_MULTILINGUAL',
        pageNumbers: [2],
        preprocessingProfile: 'STANDARD',
        force: false,
      }),
    ).resolves.toEqual(queued);
    expect(apiClientMock.post).toHaveBeenCalledWith('/ocr/jobs', {
      documentFileId: phase7Ids.file,
      extractionRunId: phase7Ids.extractionRun,
      languageProfile: 'AUTO_MULTILINGUAL',
      pageNumbers: [2],
      preprocessingProfile: 'STANDARD',
      force: false,
    });
  });

  it('uses the dedicated OCR page-detail and export endpoints', async () => {
    apiClientMock.get
      .mockResolvedValueOnce({
        data: {
          success: true,
          message: 'OK',
          data: { page: { pageNumber: 2 }, blocks: [] },
          errors: null,
        },
      })
      .mockResolvedValueOnce({
        data: new Blob(['ocr']),
        headers: { 'content-disposition': 'attachment; filename="ocr.txt"' },
      });

    await expect(getOCRPage(phase7Ids.run, 2)).resolves.toEqual({
      page: { pageNumber: 2 },
      blocks: [],
    });
    expect(apiClientMock.get).toHaveBeenNthCalledWith(
      1,
      `/ocr/runs/${phase7Ids.run}/pages/2`,
      {},
    );
    await expect(exportOCR(phase7Ids.run, 'txt')).resolves.toEqual(
      expect.objectContaining({ fileName: 'ocr.txt' }),
    );
    expect(apiClientMock.get).toHaveBeenNthCalledWith(
      2,
      `/ocr/runs/${phase7Ids.run}/export`,
      expect.objectContaining({ params: { format: 'txt' }, responseType: 'blob' }),
    );
  });

  it('queues merged-content language detection with nullable OCR provenance', async () => {
    const queued = {
      jobId: phase7Ids.languageJob,
      status: 'QUEUED',
      progress: 0,
      documentFileId: phase7Ids.file,
      extractionRunId: phase7Ids.extractionRun,
      ocrRunId: null,
      reusedExistingResult: false,
      runId: null,
    };
    apiClientMock.post.mockResolvedValue({
      data: { success: true, message: 'Queued', data: queued, errors: null },
    });

    await expect(
      startLanguageDetection({
        documentFileId: phase7Ids.file,
        extractionRunId: phase7Ids.extractionRun,
        ocrRunId: null,
        force: false,
      }),
    ).resolves.toEqual(queued);
    expect(apiClientMock.post).toHaveBeenCalledWith('/language-detection/jobs', {
      documentFileId: phase7Ids.file,
      extractionRunId: phase7Ids.extractionRun,
      ocrRunId: null,
      force: false,
    });
  });

  it('lists current document files independently from job history', async () => {
    const result = {
      items: [languageDocument],
      page: 1,
      pageSize: 20,
      totalItems: 1,
      totalPages: 1,
    };
    apiClientMock.get.mockResolvedValue({
      data: { success: true, message: 'OK', data: result, errors: null },
    });
    const params = {
      search: 'MTI-HRM',
      status: 'NOT_STARTED' as const,
      page: 1,
      pageSize: 20,
      sortBy: 'documentCode' as const,
      sortOrder: 'asc' as const,
    };

    await expect(listLanguageDetectionDocuments(params)).resolves.toEqual(result);
    expect(apiClientMock.get).toHaveBeenCalledWith('/language-detection/documents', {
      params,
    });
  });

  it('forwards every language block filter without array suffixes', async () => {
    apiClientMock.get.mockResolvedValue({
      data: {
        success: true,
        message: 'OK',
        data: { items: [], page: 1, pageSize: 100, totalItems: 0, totalPages: 0 },
        errors: null,
      },
    });
    const params = {
      languageCode: 'mixed' as const,
      sourceType: 'OCR' as const,
      containerId: phase7Ids.container,
      minimumConfidence: 0.55,
      maximumConfidence: 0.75,
      isMixed: true,
      eligibilityStatus: 'ELIGIBLE' as const,
      search: 'document',
      page: 1,
      pageSize: 100,
    };

    await listLanguageBlocks(phase7Ids.languageRun, params);
    expect(apiClientMock.get).toHaveBeenCalledWith(
      `/language-detection/runs/${phase7Ids.languageRun}/blocks`,
      { params },
    );
    const uri = axios.getUri({
      url: '/language-detection/jobs',
      params: { status: ['COMPLETED', 'FAILED'] },
      paramsSerializer: languageDetectionParamsSerializer,
    });
    expect(new URL(uri, 'http://localhost').searchParams.getAll('status')).toEqual([
      'COMPLETED',
      'FAILED',
    ]);
  });

  it('exports language results only as JSON or XLSX blobs', async () => {
    apiClientMock.get.mockResolvedValue({
      data: new Blob(['language']),
      headers: { 'content-disposition': 'attachment; filename="language.xlsx"' },
    });

    await expect(exportLanguageResults(phase7Ids.languageRun, 'xlsx')).resolves.toEqual(
      expect.objectContaining({ fileName: 'language.xlsx' }),
    );
    expect(apiClientMock.get).toHaveBeenCalledWith(
      `/language-detection/runs/${phase7Ids.languageRun}/export`,
      expect.objectContaining({ params: { format: 'xlsx' }, responseType: 'blob' }),
    );
  });
});
