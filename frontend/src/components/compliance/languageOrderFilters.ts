export interface LanguageOrderFiltersValue {
  completeness: 'ALL' | 'COMPLETE' | 'INCOMPLETE';
  orderInvalidOnly: boolean;
  lowConfidenceOnly: boolean;
  detectedSectionId: string;
  containerId: string;
}

export const emptyLanguageOrderFilters: LanguageOrderFiltersValue = {
  completeness: 'ALL',
  orderInvalidOnly: false,
  lowConfidenceOnly: false,
  detectedSectionId: '',
  containerId: '',
};
