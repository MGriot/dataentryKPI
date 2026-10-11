import { describe, expect, it } from 'vitest';
import { buildSpecUpdate, buildTargetsPayload, initialForm } from './forms';
import type { KpiDetailedSpec } from '../types';

describe('buildTargetsPayload', () => {
  it('sends only filled boxes, as numbers', () => {
    expect(buildTargetsPayload({ 1: '120000', 2: '' }, 2)).toEqual([{ target_number: 1, target_value: 120000 }]);
    expect(buildTargetsPayload({ 1: '0', 2: '-5.5' }, 2)).toEqual([
      { target_number: 1, target_value: 0 },
      { target_number: 2, target_value: -5.5 },
    ]);
  });

  it('never sends NaN or values beyond the target count', () => {
    expect(buildTargetsPayload({ 1: 'abc' }, 1)).toMatch(/not a valid number/);
    expect(buildTargetsPayload({ 1: '5', 3: '9' }, 2)).toEqual([{ target_number: 1, target_value: 5 }]);
  });

  it('refuses an all-empty save instead of writing zeros', () => {
    expect(buildTargetsPayload({}, 2)).toMatch(/at least one/);
  });
});

const kpi = {
  id: 1, indicator_id: 1, indicator_name: 'X', node_id: 1, calculation_type: 'Sum', visible: true, is_calculated: false,
  threshold_json: '{"warning_margin": 0.1}', time_filter_type: 'rolling', time_filter_value: '30',
} as KpiDetailedSpec;

describe('buildSpecUpdate', () => {
  it('round-trips the form into a valid payload', () => {
    const update = buildSpecUpdate(initialForm(kpi), { '1': 'Budget', '2': ' ' });
    expect(update).toMatchObject({ target_count: 1, time_filter_type: 'Rolling', formula_string: null, target_labels: '{"1":"Budget"}' });
    expect(JSON.parse((update as Record<string, string>).threshold_json)).toEqual({ warning_margin: 0.1, error_margin: 0.15 });
  });

  it('rejects bad numbers instead of silently saving 0', () => {
    const form = initialForm(kpi);
    expect(buildSpecUpdate({ ...form, target_count: '' }, {})).toMatch(/1 to 10/);
    expect(buildSpecUpdate({ ...form, target_count: '2.5' }, {})).toMatch(/1 to 10/);
    expect(buildSpecUpdate({ ...form, warning_margin: '' }, {})).toMatch(/between 0 and 1/);
    expect(buildSpecUpdate({ ...form, time_filter_value: 'x' }, {})).toMatch(/whole number of days/);
  });
});
