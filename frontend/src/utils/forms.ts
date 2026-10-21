import type { KpiDetailedSpec } from '../types';
import type { AnnualTargetValueInput } from '../services/api';

/**
 * The targets to send for a card: only boxes with a valid number (blank boxes are left out so
 * stored values are kept). Returns an error message instead if any box holds something invalid.
 */
export function buildTargetsPayload(values: Record<number, string>, targetCount: number): AnnualTargetValueInput[] | string {
  const targets: AnnualTargetValueInput[] = [];
  for (let tn = 1; tn <= targetCount; tn++) {
    const raw = (values[tn] ?? '').trim();
    if (raw === '') continue;
    const value = Number(raw);
    if (!Number.isFinite(value)) return `Target ${tn} is not a valid number.`;
    targets.push({ target_number: tn, target_value: value });
  }
  if (targets.length === 0) return 'Enter at least one target value.';
  return targets;
}

export interface SpecForm {
  description: string;
  unit_of_measure: string;
  calculation_type: string;
  direction: string;
  formula_string: string;
  target_count: string;
  visible: boolean;
  owner: string;
  target_granularity: string;
  time_filter_type: string;
  time_filter_value: string;
  warning_margin: string;
  error_margin: string;
  min_target: string;
  max_target: string;
}

export function initialForm(kpi: KpiDetailedSpec): SpecForm {
  let threshold: Record<string, unknown> = {};
  try {
    const parsed = kpi.threshold_json ? JSON.parse(kpi.threshold_json) : {};
    threshold = parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    threshold = {};
  }
  const str = (v: unknown, fallback: string) => (v === undefined || v === null ? fallback : String(v));
  return {
    description: kpi.description || '',
    unit_of_measure: kpi.unit_of_measure || '',
    calculation_type: kpi.calculation_type || 'Sum',
    direction: kpi.direction || 'Higher is Better',
    formula_string: kpi.formula_string || '',
    target_count: String(kpi.target_count || 1),
    visible: kpi.visible ?? true,
    owner: kpi.owner || '',
    target_granularity: kpi.target_granularity || 'Monthly',
    time_filter_type: (kpi.time_filter_type || 'None').toLowerCase() === 'rolling' ? 'Rolling' : 'None',
    time_filter_value: kpi.time_filter_value || '',
    warning_margin: str(threshold.warning_margin, '0.05'),
    error_margin: str(threshold.error_margin, '0.15'),
    min_target: str(threshold.min_target, ''),
    max_target: str(threshold.max_target, ''),
  };
}

/** Validated spec update payload, or an error message. */
export function buildSpecUpdate(form: SpecForm, targetLabels: Record<string, string>): Record<string, unknown> | string {
  const count = Number(form.target_count);
  if (!Number.isInteger(count) || count < 1 || count > 10) return 'Number of targets must be a whole number from 1 to 10.';
  const margins: Record<string, number> = {};
  for (const key of ['warning_margin', 'error_margin'] as const) {
    const v = Number(form[key]);
    if (form[key].trim() === '' || !Number.isFinite(v) || v < 0 || v > 1) return `${key.replace('_', ' ')} must be a number between 0 and 1.`;
    margins[key] = v;
  }
  const threshold: Record<string, number> = { ...margins };
  if (form.direction === 'Range') {
    for (const key of ['min_target', 'max_target'] as const) {
      if (form[key].trim() === '') continue;
      const v = Number(form[key]);
      if (!Number.isFinite(v)) return `${key.replace('_', ' ')} must be a number.`;
      threshold[key] = v;
    }
  }
  if (form.time_filter_type === 'Rolling') {
    const days = Number(form.time_filter_value);
    if (!Number.isInteger(days) || days < 1) return 'Rolling window must be a whole number of days.';
  }
  const labels = Object.fromEntries(Object.entries(targetLabels).filter(([, v]) => v.trim() !== ''));
  return {
    description: form.description,
    unit_of_measure: form.unit_of_measure || null,
    calculation_type: form.calculation_type,
    direction: form.direction,
    formula_string: form.formula_string.trim() || null,
    target_count: count,
    visible: form.visible,
    owner: form.owner || null,
    target_granularity: form.target_granularity,
    time_filter_type: form.time_filter_type,
    time_filter_value: form.time_filter_type === 'None' ? null : form.time_filter_value,
    threshold_json: JSON.stringify(threshold),
    target_labels: JSON.stringify(labels),
  };
}
