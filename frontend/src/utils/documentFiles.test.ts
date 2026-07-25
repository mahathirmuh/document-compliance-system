import { describe, expect, it } from 'vitest';

import { estimateBatchFileProgress } from './documentFiles';

describe('estimateBatchFileProgress', () => {
  it('distributes aggregate loaded bytes cumulatively by file size and order', () => {
    const files = [
      new File(['a'.repeat(25)], 'first.pdf'),
      new File(['b'.repeat(75)], 'second.pdf'),
    ];

    expect(estimateBatchFileProgress(files, 25)).toEqual([100, 0]);
    expect(estimateBatchFileProgress(files, 50)).toEqual([100, 33]);
    expect(estimateBatchFileProgress(files, 100)).toEqual([100, 100]);
  });

  it('clamps out-of-range aggregate progress', () => {
    const files = [new File(['one'], 'one.pdf')];

    expect(estimateBatchFileProgress(files, -20)).toEqual([0]);
    expect(estimateBatchFileProgress(files, 120)).toEqual([100]);
  });
});
