import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { FindingsTrendPanel } from './FindingsReportPage';

describe('FindingsReportPage trend', () => {
  it('renders the scoped findings trend returned by the report API', () => {
    render(
      <FindingsTrendPanel
        items={[
          { period: '2026-05', count: 4 },
          { period: '2026-06', count: 9 },
          { period: '2026-07', count: 6 },
        ]}
      />,
    );

    expect(screen.getByText('Findings Trend')).toBeInTheDocument();
    expect(
      screen.getByRole('img', {
        name: 'Finding count trend by reporting period',
      }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText('2026-06: 9 findings')).toBeInTheDocument();
    expect(screen.getByText('2026-07')).toBeInTheDocument();
  });
});
