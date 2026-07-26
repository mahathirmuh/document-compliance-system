import axios from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  patch: vi.fn(),
}));

vi.mock('./client', () => ({
  apiClient: apiClientMock,
}));

import {
  complianceParamsSerializer,
  exportCompliance,
  listDetectedSections,
  listComplianceJobs,
  listTranslationGroups,
  startComplianceValidation,
} from './complianceApi';
import {
  acceptFindingRisk,
  bulkActionFindings,
  markFalsePositive,
  resolveFinding,
  returnFindingToOpen,
} from './findingApi';
import { sectionDefinitionApi } from './sectionDefinitionApi';
import { complianceJob, phase8Ids } from '../test/phase8Fixtures';

describe('Phase 8 API contracts', () => {
  beforeEach(() => {
    apiClientMock.get.mockReset();
    apiClientMock.post.mockReset();
    apiClientMock.put.mockReset();
    apiClientMock.patch.mockReset();
  });

  it('queues validation with explicit compatible source provenance', async () => {
    const payload = {
      documentFileId: phase8Ids.file,
      extractionRunId: phase8Ids.extraction,
      ocrRunId: null,
      languageDetectionRunId: phase8Ids.language,
      validationRuleId: phase8Ids.rule,
      force: false,
    };
    const queued = {
      jobId: phase8Ids.job,
      status: 'QUEUED',
      progress: 0,
      documentFileId: phase8Ids.file,
      runId: null,
      reusedExistingResult: false,
    };
    apiClientMock.post.mockResolvedValue({
      data: { success: true, message: 'Queued', data: queued, errors: null },
    });

    await expect(startComplianceValidation(payload)).resolves.toEqual(queued);
    expect(apiClientMock.post).toHaveBeenCalledWith('/compliance/jobs', payload);
  });

  it('uses repeated status query parameters and the exact job list endpoint', async () => {
    const result = {
      items: [complianceJob],
      page: 1,
      pageSize: 20,
      totalItems: 1,
      totalPages: 1,
    };
    apiClientMock.get.mockResolvedValue({
      data: { success: true, message: 'OK', data: result, errors: null },
    });
    const params = {
      status: ['QUEUED', 'VALIDATING_LANGUAGES'] as const,
      complianceStatus: 'COMPLIANT' as const,
      page: 1,
      pageSize: 20,
    };

    await expect(listComplianceJobs(params)).resolves.toEqual(result);
    expect(apiClientMock.get).toHaveBeenCalledWith(
      '/compliance/jobs',
      expect.objectContaining({ params, paramsSerializer: complianceParamsSerializer }),
    );
    const uri = axios.getUri({
      url: '/compliance/jobs',
      params,
      paramsSerializer: complianceParamsSerializer,
    });
    expect(new URL(uri, 'http://localhost').searchParams.getAll('status')).toEqual([
      'QUEUED',
      'VALIDATING_LANGUAGES',
    ]);
    expect(new URL(uri, 'http://localhost').searchParams.get('complianceStatus')).toBe(
      'COMPLIANT',
    );
  });

  it('exports compliance only through the run-scoped JSON/XLSX endpoint', async () => {
    apiClientMock.get.mockResolvedValue({
      data: new Blob(['compliance']),
      headers: {
        'content-disposition': 'attachment; filename="compliance.xlsx"',
      },
    });

    await expect(exportCompliance(phase8Ids.run, 'xlsx')).resolves.toEqual(
      expect.objectContaining({ fileName: 'compliance.xlsx' }),
    );
    expect(apiClientMock.get).toHaveBeenCalledWith(
      `/compliance/runs/${phase8Ids.run}/export`,
      expect.objectContaining({ params: { format: 'xlsx' }, responseType: 'blob' }),
    );
  });

  it('loads one bounded server page for sections and filtered translation groups', async () => {
    const sectionsPage = {
      items: [{ id: 'section-20' }],
      page: 2,
      pageSize: 20,
      totalItems: 41,
      totalPages: 3,
    };
    const groupsPage = {
      items: [{ id: 'group-1' }],
      page: 1,
      pageSize: 50,
      totalItems: 1,
      totalPages: 1,
    };
    apiClientMock.get
      .mockResolvedValueOnce({
        data: {
          success: true,
          message: 'OK',
          data: sectionsPage,
          errors: null,
        },
      })
      .mockResolvedValueOnce({
        data: {
          success: true,
          message: 'OK',
          data: groupsPage,
          errors: null,
        },
      });

    await expect(
      listDetectedSections(phase8Ids.run, { page: 2, pageSize: 20 }),
    ).resolves.toEqual(sectionsPage);
    await expect(
      listTranslationGroups(phase8Ids.run, {
        page: 1,
        pageSize: 50,
        isComplete: false,
        isOrderValid: false,
        lowConfidence: true,
        detectedSectionId: phase8Ids.section,
        containerId: 'body-container-id',
      }),
    ).resolves.toEqual(groupsPage);
    expect(apiClientMock.get).toHaveBeenNthCalledWith(
      1,
      `/compliance/runs/${phase8Ids.run}/sections`,
      expect.objectContaining({ params: { page: 2, pageSize: 20 } }),
    );
    expect(apiClientMock.get).toHaveBeenNthCalledWith(
      2,
      `/compliance/runs/${phase8Ids.run}/translation-groups`,
      expect.objectContaining({
        params: {
          page: 1,
          pageSize: 50,
          isComplete: false,
          isOrderValid: false,
          lowConfidence: true,
          detectedSectionId: phase8Ids.section,
          containerId: 'body-container-id',
        },
      }),
    );
  });

  it('sends mandatory comments and reasons to distinct finding transitions', async () => {
    apiClientMock.post.mockResolvedValue({
      data: { success: true, message: 'OK', data: {}, errors: null },
    });

    await resolveFinding(phase8Ids.finding, { comment: 'Corrected in Rev.003.' });
    await returnFindingToOpen(phase8Ids.finding, {
      comment: 'Needs additional review.',
    });
    await markFalsePositive(phase8Ids.finding, {
      reason: 'Approved exception.',
    });
    await acceptFindingRisk(phase8Ids.finding, {
      reason: 'Temporary waiver.',
      expiryDate: '2026-12-31',
    });

    expect(apiClientMock.post).toHaveBeenNthCalledWith(
      1,
      `/findings/${phase8Ids.finding}/resolve`,
      { comment: 'Corrected in Rev.003.' },
    );
    expect(apiClientMock.post).toHaveBeenNthCalledWith(
      2,
      `/findings/${phase8Ids.finding}/return-to-open`,
      { comment: 'Needs additional review.' },
    );
    expect(apiClientMock.post).toHaveBeenNthCalledWith(
      3,
      `/findings/${phase8Ids.finding}/false-positive`,
      { reason: 'Approved exception.' },
    );
    expect(apiClientMock.post).toHaveBeenNthCalledWith(
      4,
      `/findings/${phase8Ids.finding}/accept-risk`,
      { reason: 'Temporary waiver.', expiryDate: '2026-12-31' },
    );
  });

  it('uses one authoritative bulk request for assign and review actions', async () => {
    apiClientMock.post
      .mockResolvedValueOnce({
        data: {
          success: true,
          message: 'OK',
          data: {
            action: 'ASSIGN',
            processedCount: 2,
            findingIds: [phase8Ids.finding, 'finding-2'],
          },
          errors: null,
        },
      })
      .mockResolvedValueOnce({
        data: {
          success: true,
          message: 'OK',
          data: {
            action: 'REVIEW',
            processedCount: 2,
            findingIds: [phase8Ids.finding, 'finding-2'],
          },
          errors: null,
        },
      });

    await bulkActionFindings({
      action: 'ASSIGN',
      findingIds: [phase8Ids.finding, 'finding-2'],
      assignedTo: 'reviewer-id',
    });
    await bulkActionFindings({
      action: 'REVIEW',
      findingIds: [phase8Ids.finding, 'finding-2'],
      comment: 'Bulk triage confirmed.',
    });

    expect(apiClientMock.post).toHaveBeenNthCalledWith(1, '/findings/bulk-actions', {
      action: 'ASSIGN',
      findingIds: [phase8Ids.finding, 'finding-2'],
      assignedTo: 'reviewer-id',
    });
    expect(apiClientMock.post).toHaveBeenNthCalledWith(2, '/findings/bulk-actions', {
      action: 'REVIEW',
      findingIds: [phase8Ids.finding, 'finding-2'],
      comment: 'Bulk triage confirmed.',
    });
  });

  it('uses the section match tester and scoped export endpoints', async () => {
    apiClientMock.post.mockResolvedValue({
      data: {
        success: true,
        message: 'OK',
        data: {
          matched: true,
          canonicalCode: 'RESPONSIBILITY',
          languageCode: 'id',
          matchType: 'EXACT',
          confidence: 1,
        },
        errors: null,
      },
    });
    apiClientMock.get.mockResolvedValue({
      data: new Blob(['sections']),
      headers: { 'content-disposition': 'attachment; filename="sections.xlsx"' },
    });

    await sectionDefinitionApi.testMatch({
      headingText: '2. TANGGUNG JAWAB',
      profileId: 'profile-id',
    });
    expect(apiClientMock.post).toHaveBeenCalledWith(
      '/master-data/section-definitions/test-match',
      {
        headingText: '2. TANGGUNG JAWAB',
        profileId: 'profile-id',
      },
    );
    await expect(sectionDefinitionApi.exportXlsx('profile-id')).resolves.toEqual(
      expect.objectContaining({ fileName: 'sections.xlsx' }),
    );
    expect(apiClientMock.get).toHaveBeenCalledWith(
      '/master-data/section-definitions/export',
      expect.objectContaining({ params: { profileId: 'profile-id' } }),
    );
  });
});
