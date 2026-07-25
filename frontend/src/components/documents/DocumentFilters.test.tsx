import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { DocumentFilters, type DocumentFilterValues } from './DocumentFilters';

const emptyFilters: DocumentFilterValues = {
  search: '',
  departmentId: '',
  sectionId: '',
  documentTypeId: '',
  documentStatusId: '',
  revisionCode: '',
  hasSharePointUrl: undefined,
  createdFrom: '',
  createdTo: '',
  effectiveFrom: '',
  effectiveTo: '',
};

const department = {
  id: '11111111-1111-4111-8111-111111111111',
  code: 'HRM',
  name: 'Human Resource',
  isActive: true,
};
const section = {
  id: '22222222-2222-4222-8222-222222222222',
  code: 'IER',
  name: 'Industrial Relations',
  isActive: true,
};

describe('DocumentFilters', () => {
  afterEach(() => vi.useRealTimers());

  it('debounces search changes for 400 milliseconds', () => {
    vi.useFakeTimers();
    const onChange = vi.fn();
    render(
      <DocumentFilters
        values={emptyFilters}
        departments={[department]}
        sections={[]}
        documentTypes={[]}
        documentStatuses={[]}
        onChange={onChange}
        onReset={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText('Search documents'), {
      target: { value: 'policy' },
    });
    act(() => vi.advanceTimersByTime(399));
    expect(onChange).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(1));
    expect(onChange).toHaveBeenCalledWith({ search: 'policy' });
  });

  it('requires a department before section filtering and clears section on change', () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <DocumentFilters
        values={emptyFilters}
        departments={[department]}
        sections={[section]}
        documentTypes={[]}
        documentStatuses={[]}
        onChange={onChange}
        onReset={vi.fn()}
      />,
    );
    expect(screen.getByLabelText('Filter by section')).toBeDisabled();

    fireEvent.change(screen.getByLabelText('Filter by department'), {
      target: { value: department.id },
    });
    expect(onChange).toHaveBeenCalledWith({
      departmentId: department.id,
      sectionId: '',
    });

    rerender(
      <DocumentFilters
        values={{ ...emptyFilters, departmentId: department.id }}
        departments={[department]}
        sections={[section]}
        documentTypes={[]}
        documentStatuses={[]}
        onChange={onChange}
        onReset={vi.fn()}
      />,
    );
    expect(screen.getByLabelText('Filter by section')).toBeEnabled();
  });
});
