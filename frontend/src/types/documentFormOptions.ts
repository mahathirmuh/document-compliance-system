export interface DocumentFormBaseOption {
  id: string;
  code: string;
  name: string;
}

export type DocumentFormDepartmentOption = DocumentFormBaseOption;

export interface DocumentFormSectionOption extends DocumentFormBaseOption {
  departmentId: string;
}

export interface DocumentFormTypeOption extends DocumentFormBaseOption {
  requiresSection: boolean;
  defaultValidationRuleId: string | null;
}

export interface DocumentFormStatusOption extends DocumentFormBaseOption {
  isInitial: boolean;
}

export interface DocumentFormValidationRuleOption extends DocumentFormBaseOption {
  documentTypeId: string | null;
  isDefault: boolean;
}

export interface DocumentFormOptions {
  defaultCompanyCode: string;
  departments: DocumentFormDepartmentOption[];
  sections: DocumentFormSectionOption[];
  documentTypes: DocumentFormTypeOption[];
  documentStatuses: DocumentFormStatusOption[];
  validationRules: DocumentFormValidationRuleOption[];
}
