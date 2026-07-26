import type {
  KpiNode,
  KpiDetailedSpec,
  Plant,
  GlobalSplit,
  GlobalSplitIndicatorLink,
  UnitOfMeasure,
  KpiTemplate,
  TemplateDefinedIndicator,
  VisibilityEntry,
  MultivariateAnalysisResult,
  PeriodicTargetRecord,
  PeriodicTargetAllPlantsRecord,
  User,
  ApiKey,
  NewApiKeyResult,
  DefinitionHistoryEntry,
  TargetHistoryEntry,
} from '../types';
import { getSessionToken, clearSession } from '../utils/session';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function authHeaders(): Record<string, string> {
  const token = getSessionToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function handleUnauthorized(res: Response) {
  if (res.status === 401) {
    // Session expired/revoked server-side -- drop it so the app falls back to the login screen.
    clearSession();
  }
}

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    headers: { 'Content-Type': 'application/json', ...authHeaders(), ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    await handleUnauthorized(res);
    const errText = await res.text();
    throw new Error(`API Error ${res.status}: ${errText || res.statusText}`);
  }
  return res.json();
}

async function fetchBlob(url: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}${url}`, { headers: { ...authHeaders() } });
  if (!res.ok) {
    await handleUnauthorized(res);
    const errText = await res.text();
    throw new Error(`API Error ${res.status}: ${errText || res.statusText}`);
  }
  return res.blob();
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export interface AnnualTargetValueInput {
  target_number: number;
  target_value: number | null;
  is_manual?: boolean;
  is_formula_based?: boolean;
  formula?: string | null;
  formula_inputs?: any;
}

export interface AnnualTargetKpiInput {
  repartition_logic?: string | null;
  repartition_values?: Record<string, any>;
  distribution_profile?: string | null;
  profile_params?: Record<string, any>;
  global_split_id?: number | null;
  targets: AnnualTargetValueInput[];
}

export interface SaveAnnualTargetsPayload {
  year: number;
  plant_id: number | number[];
  targets_data_map: Record<string, AnnualTargetKpiInput>;
  initiator_kpi_spec_id?: number | null;
}

export const api = {
  // KPI Tree & Specifications
  getKpis: (onlyVisible = false, plantId?: number) =>
    fetchJson<KpiDetailedSpec[]>(`/kpis?only_visible=${onlyVisible}${plantId ? `&plant_id=${plantId}` : ''}`),

  getKpiTree: (rootId?: number) =>
    fetchJson<KpiNode[]>(`/kpis/tree${rootId ? `?root_id=${rootId}` : ''}`),

  getKpiById: (kpiId: number, plantId?: number) =>
    fetchJson<KpiDetailedSpec>(`/kpis/${kpiId}${plantId ? `?plant_id=${plantId}` : ''}`),

  createKpiIndicator: (payload: Partial<KpiDetailedSpec> & { node_id: number; name: string }) =>
    fetchJson<{ indicator_id: number; kpi_id: number; name: string }>('/kpis', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateKpiSpec: (kpiId: number, dataUpdates: Record<string, any>) =>
    fetchJson<{ status: string; kpi_id: number }>(`/kpis/${kpiId}`, {
      method: 'PUT',
      body: JSON.stringify({ data_updates: dataUpdates }),
    }),

  addKpiNode: (name: string, parentId?: number | null, customLevelLabel?: string) =>
    fetchJson<{ node_id: number; name: string }>('/kpis/nodes', {
      method: 'POST',
      body: JSON.stringify({ name, parent_id: parentId, custom_level_label: customLevelLabel }),
    }),

  softDeleteKpi: (kpiId: number) =>
    fetchJson<{ status: string; kpi_id: number }>(`/kpis/${kpiId}`, {
      method: 'DELETE',
    }),

  getKpiHistory: (kpiId: number) =>
    fetchJson<DefinitionHistoryEntry[]>(`/kpis/${kpiId}/history`),

  getKpiTargetHistory: (kpiId: number, plantId?: number) =>
    fetchJson<TargetHistoryEntry[]>(`/kpis/${kpiId}/target-history${plantId ? `?plant_id=${plantId}` : ''}`),

  getKpiVisibility: (kpiId: number) =>
    fetchJson<VisibilityEntry[]>(`/kpis/${kpiId}/visibility`),

  updateKpiVisibility: (kpiId: number, visibilityData: VisibilityEntry[]) =>
    fetchJson<{ status: string }>(`/kpis/${kpiId}/visibility`, {
      method: 'PUT',
      body: JSON.stringify({ visibility_data: visibilityData }),
    }),

  // Plants
  getPlants: (visibleOnly = false) =>
    fetchJson<Plant[]>(`/plants?visible_only=${visibleOnly}`),

  createPlant: (payload: { name: string; description?: string; visible?: boolean; color?: string }) =>
    fetchJson<{ plant_id: number; name: string }>('/plants', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updatePlant: (plantId: number, payload: { name: string; description?: string; visible: boolean; color: string }) =>
    fetchJson<{ status: string }>(`/plants/${plantId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),

  deletePlant: (plantId: number, force = false) =>
    fetchJson<{ status: string }>(`/plants/${plantId}?force=${force}`, { method: 'DELETE' }),

  // Targets (legacy simple system)
  getTargets: (kpiId?: number, plantId?: number) =>
    fetchJson<any[]>(`/targets?${kpiId ? `kpi_id=${kpiId}&` : ''}${plantId ? `plant_id=${plantId}` : ''}`),

  saveTargetValue: (payload: {
    kpi_id: number;
    plant_id: number;
    target_number: number;
    period_start: string;
    period_end: string;
    target_value: number;
  }) =>
    fetchJson<{ status: string }>('/targets', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getLeanTargets: () => fetchJson<any[]>('/targets/lean'),

  // Annual targets + repartition engine (primary Target Entry save path)
  getAnnualTargetEntry: (year: number, plantId: number, kpiId: number) =>
    fetchJson<any | null>(`/targets/annual-entry?year=${year}&plant_id=${plantId}&kpi_id=${kpiId}`),

  getAnnualTargets: (plantId: number, year: number) =>
    fetchJson<any[]>(`/targets/annual?plant_id=${plantId}&year=${year}`),

  getAvailableTargetNumbers: (year: number, plantId: number, kpiId: number) =>
    fetchJson<number[]>(`/targets/available-numbers?year=${year}&plant_id=${plantId}&kpi_id=${kpiId}`),

  saveAnnualTargets: (payload: SaveAnnualTargetsPayload) =>
    fetchJson<{ status: string }>('/targets/annual', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getKpiPeriodicTargets: (kpiId: number, plantId: number, year: number, periodType: string, targetNumber: number) =>
    fetchJson<PeriodicTargetRecord[]>(
      `/kpis/${kpiId}/periodic-targets?plant_id=${plantId}&year=${year}&period_type=${periodType}&target_number=${targetNumber}`
    ),

  getKpiPeriodicTargetsAllPlants: (kpiId: number, periodType: string, year?: number) =>
    fetchJson<PeriodicTargetAllPlantsRecord[]>(
      `/kpis/${kpiId}/periodic-targets/all-plants?period_type=${periodType}${year ? `&year=${year}` : ''}`
    ),

  // Global Splits
  getGlobalSplits: (year?: number) =>
    fetchJson<GlobalSplit[]>(`/global-splits${year ? `?year=${year}` : ''}`),

  getGlobalSplit: (splitId: number) =>
    fetchJson<GlobalSplit>(`/global-splits/${splitId}`),

  createGlobalSplit: (payload: Partial<GlobalSplit> & { name: string; repartition_logic: string; distribution_profile: string; years?: number[] }) =>
    fetchJson<{ split_id: number; name: string }>('/global-splits', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateGlobalSplit: (splitId: number, payload: Partial<GlobalSplit> & { years?: number[] }) =>
    fetchJson<{ status: string }>(`/global-splits/${splitId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),

  deleteGlobalSplit: (splitId: number) =>
    fetchJson<{ status: string }>(`/global-splits/${splitId}`, { method: 'DELETE' }),

  getCurveWeightSuggestions: (profile: string, logic: string, year?: number) =>
    fetchJson<Record<string, number>>(
      `/global-splits/curve-preview?profile=${encodeURIComponent(profile)}&logic=${encodeURIComponent(logic)}${year ? `&year=${year}` : ''}`
    ),

  getGlobalSplitIndicators: (splitId: number) =>
    fetchJson<GlobalSplitIndicatorLink[]>(`/global-splits/${splitId}/indicators`),

  updateGlobalSplitIndicators: (splitId: number, indicators: Array<{ indicator_id: number; override_distribution_profile?: string | null }>) =>
    fetchJson<{ status: string }>(`/global-splits/${splitId}/indicators`, {
      method: 'PUT',
      body: JSON.stringify({ indicators }),
    }),

  getGlobalSplitsForKpi: (kpiId: number) =>
    fetchJson<GlobalSplit[]>(`/kpis/${kpiId}/global-splits`),

  setKpiGlobalSplit: (kpiId: number, globalSplitId: number | null) =>
    fetchJson<{ status: string; kpi_id: number; global_split_id: number | null }>(`/kpis/${kpiId}/global-split`, {
      method: 'PUT',
      body: JSON.stringify({ global_split_id: globalSplitId }),
    }),

  // Units of Measure registry
  getUnitsOfMeasure: () => fetchJson<UnitOfMeasure[]>('/units-of-measure'),

  createUnitOfMeasure: (name: string) =>
    fetchJson<UnitOfMeasure>('/units-of-measure', {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),

  // Multivariate seasonality analysis
  runMultivariateAnalysis: async (
    file: File,
    targetCols: string[],
    featureCols: string[],
    dateCol: string,
    periodType: string
  ): Promise<MultivariateAnalysisResult> => {
    const form = new FormData();
    form.append('file', file);
    form.append('target_cols', JSON.stringify(targetCols));
    form.append('feature_cols', JSON.stringify(featureCols));
    form.append('date_col', dateCol);
    form.append('period_type', periodType);
    const res = await fetch(`${API_BASE}/analysis/multivariate`, { method: 'POST', body: form, headers: authHeaders() });
    if (!res.ok) {
      await handleUnauthorized(res);
      const errText = await res.text();
      throw new Error(`API Error ${res.status}: ${errText || res.statusText}`);
    }
    return res.json();
  },

  // Templates
  getTemplates: () => fetchJson<KpiTemplate[]>('/templates'),
  createTemplate: (name: string, description = '') =>
    fetchJson<{ template_id: number; name: string }>('/templates', {
      method: 'POST',
      body: JSON.stringify({ name, description }),
    }),
  deleteTemplate: (templateId: number) =>
    fetchJson<{ status: string }>(`/templates/${templateId}`, { method: 'DELETE' }),
  getTemplateIndicators: (templateId: number) =>
    fetchJson<TemplateDefinedIndicator[]>(`/templates/${templateId}/indicators`),
  addTemplateIndicator: (templateId: number, payload: Omit<TemplateDefinedIndicator, 'id' | 'template_id'>) =>
    fetchJson<{ status: string }>(`/templates/${templateId}/indicators`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // Data utilities: CSV export & ZIP backup/restore
  getYears: () => fetchJson<Array<{ year: number }>>('/years'),

  downloadLeanExport: async () => downloadBlob(await fetchBlob('/export/lean'), 'lean_target_data.csv'),

  downloadCsvTable: async (tableKey: string) =>
    downloadBlob(await fetchBlob(`/export/csv/${encodeURIComponent(tableKey)}`), `${tableKey.replace(/\s+/g, '_')}.csv`),

  downloadFullBackup: async () => downloadBlob(await fetchBlob('/export/all'), 'kpi_backup.zip'),

  restoreFromBackup: async (file: File) => {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${API_BASE}/import/restore`, { method: 'POST', body: form, headers: authHeaders() });
    if (!res.ok) {
      await handleUnauthorized(res);
      const errText = await res.text();
      throw new Error(`API Error ${res.status}: ${errText || res.statusText}`);
    }
    return res.json() as Promise<{ status: string; detail: string }>;
  },

  // Auth (login required before anything else works)
  register: (payload: { name: string; password: string; email?: string; color?: string }) =>
    fetchJson<{ token: string; expires_at: string; user: User }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  login: (name: string, password: string) =>
    fetchJson<{ token: string; expires_at: string; user: User }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ name, password }),
    }),

  logout: () => fetchJson<{ status: string }>('/auth/logout', { method: 'POST' }),

  getMe: () => fetchJson<User>('/auth/me'),

  changePassword: (currentPassword: string, newPassword: string) =>
    fetchJson<{ status: string }>('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    }),

  // Users (named profiles for audit attribution) & MCP API keys
  getUsers: (activeOnly = false) => fetchJson<User[]>(`/users?active_only=${activeOnly}`),

  createUser: (payload: { name: string; password: string; email?: string; color?: string }) =>
    fetchJson<{ id: number; name: string }>('/users', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateUser: (userId: number, payload: { name: string; email?: string; color?: string; is_active: boolean }) =>
    fetchJson<{ status: string }>(`/users/${userId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),

  getUserApiKeys: (userId: number) => fetchJson<ApiKey[]>(`/users/${userId}/api-keys`),

  createUserApiKey: (userId: number, label: string) =>
    fetchJson<NewApiKeyResult>(`/users/${userId}/api-keys`, {
      method: 'POST',
      body: JSON.stringify({ label }),
    }),

  revokeApiKey: (keyId: number) => fetchJson<{ status: string }>(`/api-keys/${keyId}`, { method: 'DELETE' }),
};
