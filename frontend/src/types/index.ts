export interface KpiNode {
  id: number;
  name: string;
  parent_id?: number | null;
  node_type?: 'group' | 'subgroup' | 'folder';
  custom_level_label?: string | null;
  is_active?: number;
  children?: KpiNode[];
  indicators?: KpiDetailedSpec[];
}

export interface KpiDetailedSpec {
  id: number;
  indicator_id: number;
  indicator_name: string;
  node_id: number;
  hierarchy_path?: string;
  description?: string;
  calculation_type: 'Sum' | 'Average' | 'Last' | 'Min' | 'Max' | 'Count' | 'Incremental';
  unit_of_measure?: string;
  visible: boolean;
  formula_json?: string;
  formula_string?: string;
  is_calculated: boolean;
  default_distribution_profile?: string;
  owner?: string;
  direction?: 'Higher is Better' | 'Lower is Better' | 'Range';
  threshold_json?: string;
  target_granularity?: 'Daily' | 'Weekly' | 'Monthly' | 'Quarterly' | 'Yearly';
  target_count?: number;
  time_filter_type?: string;
  time_filter_value?: string;
  target_labels?: string;
}

export interface Plant {
  id: number;
  name: string;
  description?: string;
  visible: boolean;
  color: string;
  is_active?: boolean;
}

export interface AnnualTargetValue {
  id?: number;
  annual_target_id?: number;
  target_number: number;
  target_value: number;
  is_manual?: boolean;
  is_formula_based?: boolean;
  formula?: string;
  formula_inputs?: string;
}

export interface AnnualTargetEntry {
  id?: number;
  year: number;
  plant_id: number;
  kpi_id: number;
  repartition_logic?: string;
  repartition_values?: string;
  distribution_profile?: string;
  profile_params?: string;
  global_split_id?: number | null;
  target_values?: AnnualTargetValue[];
  [key: string]: any;
}

export interface UnitOfMeasure {
  id: number;
  name: string;
}

export interface GlobalSplit {
  id: number;
  name: string;
  year?: number;
  years?: number[];
  repartition_logic: string;
  repartition_values: Record<string, number>;
  distribution_profile: string;
  profile_params: Record<string, any>;
}

export interface KpiTemplate {
  id: number;
  name: string;
  description?: string;
}

export interface TemplateDefinedIndicator {
  id: number;
  template_id: number;
  indicator_name_in_template: string;
  default_description?: string;
  default_calculation_type: string;
  default_unit_of_measure?: string;
  default_visible: boolean;
}

export interface GlobalSplitIndicatorLink {
  id: number;
  global_split_id: number;
  indicator_id: number;
  override_distribution_profile?: string | null;
}

export interface VisibilityEntry {
  plant_id?: number;
  kpi_id?: number;
  is_enabled: boolean;
}

export interface MultivariateAnalysisResult {
  weights: Record<string, number>;
  coefficients: Record<string, number>;
  r_squared: number;
  plot_data: Array<Record<string, number>>;
  winning_model: string;
}

export interface PeriodicTargetRecord {
  period: string;
  Target: number;
}

export interface PeriodicTargetAllPlantsRecord {
  year: number;
  plant_id: number;
  plant_name: string;
  kpi_id: number;
  target_number: number;
  period: string;
  target_value: number;
}

export interface User {
  id: number;
  name: string;
  email?: string;
  color: string;
  is_active: boolean;
  created_at: string;
}

export interface ApiKey {
  id: number;
  user_id: number;
  label: string;
  key_prefix: string;
  created_at: string;
  last_used_at?: string | null;
  is_active: boolean;
}

export interface NewApiKeyResult {
  id: number;
  label: string;
  key_prefix: string;
  raw_key: string;
}

export interface DefinitionHistoryEntry {
  id: number;
  kpi_id: number;
  changed_at: string;
  changed_by: string;
  change_type: string;
  old_value?: any;
  new_value?: any;
}

export interface TargetHistoryEntry {
  id: number;
  kpi_id: number;
  plant_id: number;
  target_number: number;
  period_start: string;
  period_end: string;
  old_value: number | null;
  new_value: number | null;
  changed_at: string;
  changed_by: string;
}

export const DISTRIBUTION_PROFILE_OPTIONS = [
  { value: 'even_distribution', label: 'Uniform / Even' },
  { value: 'annual_progressive', label: 'Annual Progressive' },
  { value: 'annual_progressive_weekday_bias', label: 'Annual Progressive (Weekday Bias)' },
  { value: 'true_annual_sinusoidal', label: 'Sinusoidal Seasonal Curve' },
  { value: 'event_based_spikes_or_dips', label: 'Event Based (Shutdowns)' },
];

export const REPARTITION_LOGIC_OPTIONS = ['Year', 'Month', 'Quarter', 'Week'];

export const TARGET_NUMBER_LABELS: Record<number, string> = {
  1: 'Target 1 (Base)',
  2: 'Target 2 (Stretch)',
};

export function targetLabel(n: number, customLabels?: Record<string, string> | null): string {
  const custom = customLabels?.[String(n)];
  if (custom && custom.trim()) return custom;
  return TARGET_NUMBER_LABELS[n] || `Target ${n}`;
}

export function parseTargetLabels(raw?: string | null): Record<string, string> {
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}
