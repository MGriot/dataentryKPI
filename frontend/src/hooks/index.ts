import { useMemo } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import type { GlobalSplitPayload, KpiCreatePayload, SaveAnnualTargetsPayload } from '../services/api';
import type { VisibilityEntry } from '../types';
import { setSession } from '../utils/session';

/** Query key of the public sign-in/registration status (what the login screen shows). */
export const AUTH_STATUS_KEY = 'auth-status';
const SESSION_KEYS = new Set(['auth-me', AUTH_STATUS_KEY]);

/**
 * Saves on the server cascade (formula KPIs, periodic targets, history, badges...), so after
 * any data change every cached data query is marked stale. Only queries on screen refetch.
 */
export function invalidateData(qc: QueryClient) {
  return qc.invalidateQueries({ predicate: (query) => !SESSION_KEYS.has(String(query.queryKey[0])) });
}

function useDataMutation<TVars, TResult>(mutationFn: (vars: TVars) => Promise<TResult>) {
  const qc = useQueryClient();
  return useMutation({ mutationFn, onSuccess: () => invalidateData(qc) });
}

// --- Auth ---

export function useAuthStatus() {
  return useQuery({ queryKey: [AUTH_STATUS_KEY], queryFn: () => api.getAuthStatus(), staleTime: 0 });
}

export function useLogin() {
  return useMutation({
    mutationFn: ({ name, password }: { name: string; password: string }) => api.login(name, password),
    onSuccess: (res) => setSession(res.token, res.user),
    meta: { silent: true },
  });
}

export function useRegister() {
  return useMutation({
    mutationFn: (payload: { name: string; password: string; email?: string; color?: string }) => api.register(payload),
    onSuccess: (res) => setSession(res.token, res.user),
    meta: { silent: true },
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: ({ currentPassword, newPassword }: { currentPassword: string; newPassword: string }) =>
      api.changePassword(currentPassword, newPassword),
    meta: { silent: true },
  });
}

// --- Reads ---

export function useKpis(onlyVisible = false, plantId?: number | null) {
  return useQuery({ queryKey: ['kpis', onlyVisible, plantId ?? null], queryFn: () => api.getKpis(onlyVisible, plantId) });
}

export function useKpiTree() {
  return useQuery({ queryKey: ['kpi-tree'], queryFn: () => api.getKpiTree() });
}

export function usePlants(visibleOnly = false) {
  return useQuery({ queryKey: ['plants', visibleOnly], queryFn: () => api.getPlants(visibleOnly) });
}

export function useYears() {
  return useQuery({ queryKey: ['years'], queryFn: () => api.getYears() });
}

export function useGlobalSplits(year?: number) {
  return useQuery({ queryKey: ['global-splits', year ?? null], queryFn: () => api.getGlobalSplits(year) });
}

export function useAnnualTargetEntry(year: number, plantId: number | null, kpiId: number) {
  return useQuery({
    queryKey: ['annual-target-entry', year, plantId, kpiId],
    queryFn: () => api.getAnnualTargetEntry(year, plantId as number, kpiId),
    enabled: plantId !== null,
  });
}

export function useAnnualTargets(plantId: number | null, year: number) {
  return useQuery({
    queryKey: ['annual-targets', plantId, year],
    queryFn: () => api.getAnnualTargets(plantId as number, year),
    enabled: plantId !== null,
  });
}

export function usePeriodicTargetsAllPlants(kpiId: number | null, periodType: string, year: number) {
  return useQuery({
    queryKey: ['periodic-all-plants', kpiId, periodType, year],
    queryFn: () => api.getKpiPeriodicTargetsAllPlants(kpiId as number, periodType, year),
    enabled: kpiId !== null,
  });
}

export function useKpiVisibility(kpiId: number | null) {
  return useQuery({
    queryKey: ['kpi-visibility', kpiId],
    queryFn: () => api.getKpiVisibility(kpiId as number),
    enabled: kpiId !== null,
  });
}

export function useKpiDefinitionHistory(kpiId: number | null) {
  return useQuery({
    queryKey: ['kpi-definition-history', kpiId],
    queryFn: () => api.getKpiHistory(kpiId as number),
    enabled: kpiId !== null,
  });
}

export function useKpiTargetHistory(kpiId: number | null, plantId?: number) {
  return useQuery({
    queryKey: ['kpi-target-history', kpiId, plantId ?? null],
    queryFn: () => api.getKpiTargetHistory(kpiId as number, plantId),
    enabled: kpiId !== null,
  });
}

export function useUnitsOfMeasure() {
  return useQuery({ queryKey: ['units-of-measure'], queryFn: () => api.getUnitsOfMeasure() });
}

export function useKpiGlobalSplits(kpiId: number | null) {
  return useQuery({
    queryKey: ['kpi-global-splits', kpiId],
    queryFn: () => api.getGlobalSplitsForKpi(kpiId as number),
    enabled: kpiId !== null,
  });
}

export function useCurveWeightSuggestions(profile: string, logic: string, year?: number) {
  return useQuery({
    queryKey: ['curve-weight-suggestions', profile, logic, year ?? null],
    queryFn: () => api.getCurveWeightSuggestions(profile, logic, year),
    enabled: logic === 'Month' || logic === 'Quarter' || logic === 'Week',
  });
}

export function useUsers(activeOnly = false) {
  return useQuery({ queryKey: ['users', activeOnly], queryFn: () => api.getUsers(activeOnly) });
}

export function useUserApiKeys(userId: number | null) {
  return useQuery({
    queryKey: ['api-keys', userId],
    queryFn: () => api.getUserApiKeys(userId as number),
    enabled: userId !== null,
  });
}

// --- Writes (all refresh cached data on success; failures surface through the global error toast) ---

export const useCreateKpiNode = () =>
  useDataMutation(({ name, parentId }: { name: string; parentId?: number | null }) => api.addKpiNode(name, parentId));

export const useCreateKpiIndicator = () => useDataMutation((payload: KpiCreatePayload) => api.createKpiIndicator(payload));

export const useUpdateKpiSpec = () =>
  useDataMutation(({ kpiId, dataUpdates }: { kpiId: number; dataUpdates: Record<string, unknown> }) =>
    api.updateKpiSpec(kpiId, dataUpdates)
  );

export const useSoftDeleteKpi = () => useDataMutation((kpiId: number) => api.softDeleteKpi(kpiId));

export const useUpdateKpiVisibility = () =>
  useDataMutation(({ kpiId, visibilityData }: { kpiId: number; visibilityData: VisibilityEntry[] }) =>
    api.updateKpiVisibility(kpiId, visibilityData)
  );

export const useSaveAnnualTargets = () => useDataMutation((payload: SaveAnnualTargetsPayload) => api.saveAnnualTargets(payload));

export const useCreatePlant = () =>
  useDataMutation((payload: { name: string; description?: string; visible?: boolean; color?: string }) => api.createPlant(payload));

export const useUpdatePlant = () =>
  useDataMutation(({ plantId, payload }: { plantId: number; payload: { name: string; description?: string; visible: boolean; color: string } }) =>
    api.updatePlant(plantId, payload)
  );

export const useDeletePlant = () =>
  useDataMutation(({ plantId, force }: { plantId: number; force: boolean }) => api.deletePlant(plantId, force));

export const useCreateGlobalSplit = () => useDataMutation((payload: GlobalSplitPayload) => api.createGlobalSplit(payload));

export const useUpdateGlobalSplit = () =>
  useDataMutation(({ splitId, payload }: { splitId: number; payload: Partial<GlobalSplitPayload> }) =>
    api.updateGlobalSplit(splitId, payload)
  );

export const useDeleteGlobalSplit = () => useDataMutation((splitId: number) => api.deleteGlobalSplit(splitId));

export const useSetKpiGlobalSplit = () =>
  useDataMutation(({ kpiId, globalSplitId }: { kpiId: number; globalSplitId: number | null }) =>
    api.setKpiGlobalSplit(kpiId, globalSplitId)
  );

export const useCreateUnitOfMeasure = () => useDataMutation((name: string) => api.createUnitOfMeasure(name));

export const useCreateUser = () =>
  useDataMutation((payload: { name: string; password: string; email?: string; color?: string; is_admin?: boolean }) =>
    api.createUser(payload)
  );

export const useUpdateUser = () =>
  useDataMutation(
    ({ userId, payload }: { userId: number; payload: { name: string; email?: string; color?: string; is_active: boolean; is_admin?: boolean } }) =>
      api.updateUser(userId, payload)
  );

export const useResetUserPassword = () =>
  useDataMutation(({ userId, newPassword }: { userId: number; newPassword: string }) => api.resetUserPassword(userId, newPassword));

export const useCreateApiKey = () =>
  useDataMutation(({ userId, label }: { userId: number; label: string }) => api.createUserApiKey(userId, label));

export const useRevokeApiKey = () => useDataMutation((keyId: number) => api.revokeApiKey(keyId));

/** Years with data plus a window around the current year, newest last. */
export function useYearOptions(extra: number[] = []): number[] {
  const { data: dataYears = [] } = useYears();
  return useMemo(() => {
    const current = new Date().getFullYear();
    const years = new Set<number>([...Array.from({ length: 10 }, (_, i) => current - 3 + i), ...dataYears.map((y) => y.year), ...extra]);
    return Array.from(years).sort((a, b) => a - b);
  }, [dataYears, extra]);
}
