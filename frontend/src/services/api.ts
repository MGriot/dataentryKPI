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
  AnnualTargetEntry,
  AuthStatus,
} from '../types';
import { getSessionToken, clearSession } from '../utils/session';

// Same-origin by default: nginx (container) and the Vite dev server proxy /api to the backend,
// so the app works from any host. Override with VITE_API_URL to call the API directly.
export const API_BASE = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '');

/** An HTTP error from the API, with the server's `detail` message when it sent one. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/** A user-facing message for any error thrown by the API client. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof TypeError) return 'Could not reach the server. Check your connection and try again.';
  if (error instanceof Error) return error.message;
  return 'Something went wrong.';
}

function authHeaders(): Record<string, string> {
  const token = getSessionToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function detailFrom(body: string, fallback: string): string {
  try {
    const parsed = JSON.parse(body);
    const detail = parsed?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      // FastAPI validation errors: [{loc: [...], msg: '...'}]
      return detail.map((d) => `${(d.loc || []).filter((p: unknown) => p !== 'body').join('.')}: ${d.msg}`).join('; ');
    }
  } catch {
    // not JSON
  }
  return body || fallback;
}

async function request(url: string, options: RequestInit = {}, json = true): Promise<Response> {
  const headers: Record<string, string> = {
    ...(json ? { 'Content-Type': 'application/json' } : {}),
    ...authHeaders(),
    ...((options.headers as Record<string, string>) || {}),
  };
  const res = await fetch(`${API_BASE}${url}`, { ...options, headers });
  if (!res.ok) {
    // Only an actual 401 means the session is gone; network errors and 5xx must not log users out.
    if (res.status === 401 && getSessionToken()) clearSession();
    throw new ApiError(res.status, detailFrom(await res.text(), res.statusText || `HTTP ${res.status}`));
  }
  return res;
}

export async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  return (await request(url, options)).json();
}

async function fetchBlob(url: string): Promise<Blob> {
  return (await request(url, {}, false)).blob();
}

async function postForm<T>(url: string, form: FormData): Promise<T> {
  return (await request(url, { method: 'POST', body: form }, false)).json();
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
  target_value: number;
}

export interface AnnualTargetKpiInput {
  targets: AnnualTargetValueInput[];
}

export interface SaveAnnualTargetsPayload {
  year: number;
  plant_id: number | number[];
  targets_data_map: Record<string, AnnualTargetKpiInput>;
  initiator_kpi_spec_id?: number | null;
}

export interface GlobalSplitPayload {
  name: string;
  repartition_logic: string;
  repartition_values: Record<string, number>;
  distribution_profile: string;
  profile_params?: Record<string, unknown>;
  years?: number[];
}

export interface KpiCreatePayload {
  node_id: number;
  name: string;
  calculation_type?: string;
  unit_of_measure?: string | null;
  direction?: string;
}

const q = encodeURIComponent;

export const api = {
  // KPI Tree & Specifications
  getKpis: (onlyVisible = false, plantId?: number | null) =>
    fetchJson<KpiDetailedSpec[]>(`/kpis?only_visible=${onlyVisible}${plantId ? `&plant_id=${plantId}` : ''}`),

  getKpiTree: () => fetchJson<KpiNode[]>('/kpis/tree'),

  createKpiIndicator: (payload: KpiCreatePayload) =>
    fetchJson<{ indicator_id: number; kpi_id: number; name: string }>('/kpis', { method: 'POST', body: JSON.stringify(payload) }),

  updateKpiSpec: (kpiId: number, dataUpdates: Record<string, unknown>) =>
    fetchJson<{ status: string; kpi_id: number }>(`/kpis/${kpiId}`, {
      method: 'PUT',
      body: JSON.stringify({ data_updates: dataUpdates }),
    }),

  addKpiNode: (name: string, parentId?: number | null, customLevelLabel?: string) =>
    fetchJson<{ node_id: number; name: string }>('/kpis/nodes', {
      method: 'POST',
      body: JSON.stringify({ name, parent_id: parentId ?? null, custom_level_label: customLevelLabel }),
    }),

  softDeleteKpi: (kpiId: number) => fetchJson<{ status: string; kpi_id: number }>(`/kpis/${kpiId}`, { method: 'DELETE' }),

  getKpiHistory: (kpiId: number) => fetchJson<DefinitionHistoryEntry[]>(`/kpis/${kpiId}/history`),

  getKpiTargetHistory: (kpiId: number, plantId?: number) =>
    fetchJson<TargetHistoryEntry[]>(`/kpis/${kpiId}/target-history${plantId ? `?plant_id=${plantId}` : ''}`),

  getKpiVisibility: (kpiId: number) => fetchJson<VisibilityEntry[]>(`/kpis/${kpiId}/visibility`),

  updateKpiVisibility: (kpiId: number, visibilityData: VisibilityEntry[]) =>
    fetchJson<{ status: string }>(`/kpis/${kpiId}/visibility`, {
      method: 'PUT',
      body: JSON.stringify({ visibility_data: visibilityData }),
    }),

  // Plants
  getPlants: (visibleOnly = false) => fetchJson<Plant[]>(`/plants?visible_only=${visibleOnly}`),

  createPlant: (payload: { name: string; description?: string; visible?: boolean; color?: string }) =>
    fetchJson<{ plant_id: number; name: string }>('/plants', { method: 'POST', body: JSON.stringify(payload) }),

  updatePlant: (plantId: number, payload: { name: string; description?: string; visible: boolean; color: string }) =>
    fetchJson<{ status: string }>(`/plants/${plantId}`, { method: 'PUT', body: JSON.stringify(payload) }),

  deletePlant: (plantId: number, force = false) =>
    fetchJson<{ status: string }>(`/plants/${plantId}?force=${force}`, { method: 'DELETE' }),

  // Annual targets + repartition engine
  getAnnualTargetEntry: (year: number, plantId: number, kpiId: number) =>
    fetchJson<AnnualTargetEntry | null>(`/targets/annual-entry?year=${year}&plant_id=${plantId}&kpi_id=${kpiId}`),

  getAnnualTargets: (plantId: number, year: number) =>
    fetchJson<AnnualTargetEntry[]>(`/targets/annual?plant_id=${plantId}&year=${year}`),

  saveAnnualTargets: (payload: SaveAnnualTargetsPayload) =>
    fetchJson<{ status: string }>('/targets/annual', { method: 'POST', body: JSON.stringify(payload) }),

  getKpiPeriodicTargets: (kpiId: number, plantId: number, year: number, periodType: string, targetNumber: number) =>
    fetchJson<PeriodicTargetRecord[]>(
      `/kpis/${kpiId}/periodic-targets?plant_id=${plantId}&year=${year}&period_type=${q(periodType)}&target_number=${targetNumber}`
    ),

  getKpiPeriodicTargetsAllPlants: (kpiId: number, periodType: string, year?: number) =>
    fetchJson<PeriodicTargetAllPlantsRecord[]>(
      `/kpis/${kpiId}/periodic-targets/all-plants?period_type=${q(periodType)}${year ? `&year=${year}` : ''}`
    ),

  // Global Splits
  getGlobalSplits: (year?: number) => fetchJson<GlobalSplit[]>(`/global-splits${year ? `?year=${year}` : ''}`),

  createGlobalSplit: (payload: GlobalSplitPayload) =>
    fetchJson<{ split_id: number; name: string }>('/global-splits', { method: 'POST', body: JSON.stringify(payload) }),

  updateGlobalSplit: (splitId: number, payload: Partial<GlobalSplitPayload>) =>
    fetchJson<{ status: string }>(`/global-splits/${splitId}`, { method: 'PUT', body: JSON.stringify(payload) }),

  deleteGlobalSplit: (splitId: number) => fetchJson<{ status: string }>(`/global-splits/${splitId}`, { method: 'DELETE' }),

  getCurveWeightSuggestions: (profile: string, logic: string, year?: number) =>
    fetchJson<Record<string, number>>(
      `/global-splits/curve-preview?profile=${q(profile)}&logic=${q(logic)}${year ? `&year=${year}` : ''}`
    ),

  getGlobalSplitIndicators: (splitId: number) => fetchJson<GlobalSplitIndicatorLink[]>(`/global-splits/${splitId}/indicators`),

  getGlobalSplitsForKpi: (kpiId: number) => fetchJson<GlobalSplit[]>(`/kpis/${kpiId}/global-splits`),

  setKpiGlobalSplit: (kpiId: number, globalSplitId: number | null) =>
    fetchJson<{ status: string; kpi_id: number; global_split_id: number | null }>(`/kpis/${kpiId}/global-split`, {
      method: 'PUT',
      body: JSON.stringify({ global_split_id: globalSplitId }),
    }),

  // Units of Measure registry
  getUnitsOfMeasure: () => fetchJson<UnitOfMeasure[]>('/units-of-measure'),

  createUnitOfMeasure: (name: string) =>
    fetchJson<UnitOfMeasure>('/units-of-measure', { method: 'POST', body: JSON.stringify({ name }) }),

  // Multivariate seasonality analysis
  runMultivariateAnalysis: (file: File, targetCols: string[], featureCols: string[], dateCol: string, periodType: string) => {
    const form = new FormData();
    form.append('file', file);
    form.append('target_cols', JSON.stringify(targetCols));
    form.append('feature_cols', JSON.stringify(featureCols));
    form.append('date_col', dateCol);
    form.append('period_type', periodType);
    return postForm<MultivariateAnalysisResult>('/analysis/multivariate', form);
  },

  // Templates
  getTemplates: () => fetchJson<KpiTemplate[]>('/templates'),
  getTemplateIndicators: (templateId: number) => fetchJson<TemplateDefinedIndicator[]>(`/templates/${templateId}/indicators`),

  // Data utilities: CSV export & ZIP backup/restore
  getYears: () => fetchJson<Array<{ year: number }>>('/years'),

  downloadLeanExport: async () => downloadBlob(await fetchBlob('/export/lean'), 'lean_target_data.csv'),

  downloadCsvTable: async (tableKey: string) =>
    downloadBlob(await fetchBlob(`/export/csv/${q(tableKey)}`), `${tableKey.replace(/\s+/g, '_')}.csv`),

  downloadFullBackup: async () => downloadBlob(await fetchBlob('/export/all'), 'kpi_backup.zip'),

  restoreFromBackup: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return postForm<{ status: string; detail: string; snapshot: string; warnings: string[] }>('/import/restore', form);
  },

  // Auth
  getAuthStatus: () => fetchJson<AuthStatus>('/auth/status'),

  register: (payload: { name: string; password: string; email?: string; color?: string }) =>
    fetchJson<{ token: string; expires_at: string; user: User }>('/auth/register', { method: 'POST', body: JSON.stringify(payload) }),

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

  // Users & MCP API keys
  getUsers: (activeOnly = false) => fetchJson<User[]>(`/users?active_only=${activeOnly}`),

  createUser: (payload: { name: string; password: string; email?: string; color?: string; is_admin?: boolean }) =>
    fetchJson<{ id: number; name: string }>('/users', { method: 'POST', body: JSON.stringify(payload) }),

  updateUser: (userId: number, payload: { name: string; email?: string; color?: string; is_active: boolean; is_admin?: boolean }) =>
    fetchJson<{ status: string }>(`/users/${userId}`, { method: 'PUT', body: JSON.stringify(payload) }),

  resetUserPassword: (userId: number, newPassword: string) =>
    fetchJson<{ status: string }>(`/users/${userId}/reset-password`, {
      method: 'POST',
      body: JSON.stringify({ new_password: newPassword }),
    }),

  getUserApiKeys: (userId: number) => fetchJson<ApiKey[]>(`/users/${userId}/api-keys`),

  createUserApiKey: (userId: number, label: string) =>
    fetchJson<NewApiKeyResult>(`/users/${userId}/api-keys`, { method: 'POST', body: JSON.stringify({ label }) }),

  revokeApiKey: (keyId: number) => fetchJson<{ status: string }>(`/api-keys/${keyId}`, { method: 'DELETE' }),
};
