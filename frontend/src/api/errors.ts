import axios from 'axios';

import type { ApiResponse } from '../types/auth';

const stableErrorMessages: Readonly<Record<string, string>> = {
  COMPLIANCE_SOURCE_NOT_AVAILABLE:
    'The physical document source is not available for validation.',
  COMPLIANCE_EXTRACTION_REQUIRED:
    'Extract the current document file before running compliance validation.',
  COMPLIANCE_OCR_REQUIRED:
    'Complete OCR for this scanned PDF before running compliance validation.',
  COMPLIANCE_LANGUAGE_DETECTION_REQUIRED:
    'Complete language detection before running compliance validation.',
  COMPLIANCE_RULE_NOT_FOUND:
    'Assign an active validation rule to this revision before validating it.',
  COMPLIANCE_RULE_INVALID:
    'The assigned validation rule is incomplete or has invalid scoring weights.',
  COMPLIANCE_ACTIVE_JOB_EXISTS:
    'A compliance validation is already active for this document file.',
  COMPLIANCE_CONTEXT_BUILD_FAILED:
    'The validation inputs are not compatible. Re-run extraction, OCR, or language detection.',
  COMPLIANCE_SECTION_DETECTION_FAILED:
    'Document sections could not be detected reliably. Review the source and section aliases.',
  COMPLIANCE_GROUPING_FAILED:
    'The document structure could not be grouped reliably for multilingual checks.',
  COMPLIANCE_VALIDATION_FAILED:
    'Compliance validation could not be completed. The source file was not changed.',
  COMPLIANCE_PERSISTENCE_FAILED:
    'The validation result could not be saved. No partial official result was published.',
  COMPLIANCE_TIMEOUT:
    'Validation exceeded its processing limit. Try again or review the document size.',
  COMPLIANCE_CANCELLED: 'The compliance validation was cancelled.',
  COMPLIANCE_RESULT_NOT_FOUND:
    'The compliance result was not found or is outside your department scope.',
  FINDING_NOT_FOUND: 'The finding was not found or is outside your department scope.',
  FINDING_INVALID_STATUS_TRANSITION:
    'This action is not available from the finding’s current status. Refresh the page.',
  FINDING_REVIEW_COMMENT_REQUIRED: 'Enter a review comment to start review.',
  FINDING_RESOLUTION_COMMENT_REQUIRED: 'Enter a resolution comment.',
  FINDING_FALSE_POSITIVE_REASON_REQUIRED:
    'Enter a reason before marking this finding as a false positive.',
  FINDING_ACCEPT_RISK_REASON_REQUIRED:
    'Enter a reason and expiry date before accepting this risk.',
  FINDING_REOPEN_REASON_REQUIRED: 'Enter a reason before reopening this finding.',
  FINDING_ASSIGNMENT_INVALID: 'Select a valid user for this finding assignment.',
  FINDING_DEPARTMENT_SCOPE_DENIED:
    'You cannot access findings outside your assigned department scope.',
  SHAREPOINT_DISABLED:
    'SharePoint integration is disabled. Contact an administrator if synchronisation is required.',
  SHAREPOINT_CONNECTION_FAILED:
    'The SharePoint connection is unavailable. Review connection health and permissions.',
  SHAREPOINT_PERMISSION_DENIED:
    'Microsoft Graph denied this operation. The application may need site permission or admin consent.',
  SHAREPOINT_SYNC_ACTIVE:
    'A SharePoint synchronisation is already active for this resource.',
  SHAREPOINT_CONFLICT:
    'Local and remote changes conflict. Review the conflict before continuing.',
  SHAREPOINT_RATE_LIMITED:
    'Microsoft Graph is temporarily throttling requests. Retry after the advised delay.',
  NOTIFICATION_CHANNEL_DISABLED:
    'This notification channel is disabled by system configuration.',
  NOTIFICATION_RETRY_EXHAUSTED: 'This notification reached its maximum retry count.',
  RATE_LIMIT_EXCEEDED:
    'Too many requests were submitted. Wait for the retry window before trying again.',
  FILE_QUARANTINED:
    'This file is quarantined and cannot be downloaded, processed, or synchronised.',
  MALWARE_SCANNER_UNAVAILABLE:
    'The malware scanner is unavailable. File access is blocked by the configured safety policy.',
  WORKER_UNAVAILABLE:
    'The required background worker is unavailable. Check system health before retrying.',
};

export const getApiErrorCode = (error: unknown): string | null => {
  if (!axios.isAxiosError<ApiResponse<null>>(error)) {
    return null;
  }
  return error.response?.data.errors?.[0]?.code ?? null;
};

export const getApiErrorMessage = (error: unknown, fallbackMessage: string): string => {
  if (axios.isAxiosError<ApiResponse<null>>(error)) {
    const response = error.response?.data;
    const errorCode = response?.errors?.[0]?.code;
    if (errorCode && stableErrorMessages[errorCode]) {
      return stableErrorMessages[errorCode];
    }
    return response?.errors?.[0]?.message || response?.message || fallbackMessage;
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return fallbackMessage;
};
