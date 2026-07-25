import axios from 'axios';
import { describe, expect, it } from 'vitest';

import { extractionParamsSerializer } from './extractionApi';
import { terminalExtractionStatuses } from '../types/extraction';

describe('extraction API query serialization', () => {
  it('serializes terminal status filters as repeated status parameters', () => {
    const uri = axios.getUri({
      url: '/extractions',
      params: { status: terminalExtractionStatuses },
      paramsSerializer: extractionParamsSerializer,
    });
    const query = new URL(uri, 'http://localhost').searchParams;

    expect(query.getAll('status')).toEqual([...terminalExtractionStatuses]);
    expect(query.has('status[]')).toBe(false);
  });
});
