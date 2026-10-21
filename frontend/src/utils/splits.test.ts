import { describe, expect, it } from 'vitest';
import { normalizeWeightKeys, parseWeights, weekKeys, weightsTotal } from './splits';

describe('split weight helpers', () => {
  it('builds year-agnostic ISO week keys', () => {
    expect(weekKeys(2026)).toHaveLength(53);
    expect(weekKeys(2025)).toHaveLength(52);
    expect(weekKeys(2025)[0]).toBe('W01');
  });

  it('normalizes legacy week keys', () => {
    expect(normalizeWeightKeys('Week', { '2026-W05': 2, W5: 1, 'W12': 3, bogus: 9 })).toEqual({ W05: 3, W12: 3 });
    expect(normalizeWeightKeys('Month', { January: 1 })).toEqual({ January: 1 });
  });

  it('parses weights without NaN', () => {
    expect(parseWeights({ Q1: '10', Q2: '', Q3: '30', Q4: '60' }, ['Q1', 'Q2', 'Q3', 'Q4'])).toEqual({ Q1: 10, Q2: 0, Q3: 30, Q4: 60 });
    expect(parseWeights({ Q1: '-1' }, ['Q1'])).toMatch(/0 or more/);
    expect(parseWeights({ Q1: 'abc' }, ['Q1'])).toMatch(/0 or more/);
    expect(parseWeights({}, ['Q1'])).toMatch(/at least one/);
    expect(weightsTotal({ a: '10', b: 'x', c: '', d: '2.5' })).toBe(12.5);
  });
});
