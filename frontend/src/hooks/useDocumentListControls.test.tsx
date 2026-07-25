import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router';
import { describe, expect, it } from 'vitest';

import { useDocumentListControls } from './useDocumentListControls';

function Harness() {
  const controls = useDocumentListControls(false);
  const location = useLocation();
  return (
    <>
      <output aria-label="document params">{JSON.stringify(controls.params)}</output>
      <output aria-label="document query">{location.search}</output>
      <button type="button" onClick={controls.resetFilters}>
        Reset
      </button>
    </>
  );
}

describe('useDocumentListControls', () => {
  it('hydrates valid URL state and resets filters back to page one', () => {
    render(
      <MemoryRouter
        initialEntries={[
          '/documents?page=3&departmentId=department-1&sortBy=effectiveDate&sortOrder=asc',
        ]}
      >
        <Harness />
      </MemoryRouter>,
    );

    expect(screen.getByLabelText('document params')).toHaveTextContent(
      '"departmentId":"department-1"',
    );
    expect(screen.getByLabelText('document params')).toHaveTextContent('"page":3');

    fireEvent.click(screen.getByRole('button', { name: 'Reset' }));

    const query = new URLSearchParams(
      screen.getByLabelText('document query').textContent ?? '',
    );
    expect(query.has('departmentId')).toBe(false);
    expect(query.has('page')).toBe(false);
    expect(query.get('sortBy')).toBe('effectiveDate');
    expect(query.get('sortOrder')).toBe('asc');
  });
});
