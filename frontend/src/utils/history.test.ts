import { describe, expect, it } from 'vitest';
import { describeDefinitionChange } from './history';
import type { DefinitionHistoryEntry } from '../types';

const entry = (change_type: string, old_value?: unknown, new_value?: unknown): DefinitionHistoryEntry => ({
  id: 1, kpi_id: 2, changed_at: '2026-10-20T10:00:00Z', changed_by: 'ann', change_type, old_value, new_value,
});

describe('describeDefinitionChange', () => {
  it('names the fields an update changed, with short values', () => {
    const text = describeDefinitionChange(entry('UPDATE',
      { unit_of_measure: 'h', description: 'x', is_calculated: 0, formula_string: null },
      { unit_of_measure: 'kWh', description: 'x', is_calculated: 1, formula_string: '([3] / [4]) * 100 + [5] - [6] * [7] + [8]' }));
    expect(text).toBe('changed unit of measure (h -> kWh), formula string');
  });

  it('describes create, delete and no-op saves', () => {
    expect(describeDefinitionChange(entry('CREATE', null, { name: 'OEE' }))).toBe('created the KPI');
    expect(describeDefinitionChange(entry('SOFT_DELETE'))).toBe('deleted the KPI');
    expect(describeDefinitionChange(entry('UPDATE', { owner: 'a', description: null }, { owner: 'a', description: '' }))).toBe('saved without changes');
  });
});
