import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import type { SaveAnnualTargetsPayload } from '../services/api';
import type { KpiDetailedSpec, VisibilityEntry } from '../types';
import { setSession } from '../utils/session';

export function useLogin() {
  return useMutation({
    mutationFn: ({ name, password }: { name: string; password: string }) => api.login(name, password),
    onSuccess: (res) => setSession(res.token, res.user),
  });
}

export function useRegister() {
  return useMutation({
    mutationFn: (payload: { name: string; password: string; email?: string; color?: string }) => api.register(payload),
    onSuccess: (res) => setSession(res.token, res.user),
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: ({ currentPassword, newPassword }: { currentPassword: string; newPassword: string }) =>
      api.changePassword(currentPassword, newPassword),
  });
}

export function useKpis(onlyVisible = false, plantId?: number) {
  return useQuery({ queryKey: ['kpis', onlyVisible, plantId], queryFn: () => api.getKpis(onlyVisible, plantId) });
}

export function useKpiTree(rootId?: number) {
  return useQuery({ queryKey: ['kpi-tree', rootId], queryFn: () => api.getKpiTree(rootId) });
}

export function usePlants(visibleOnly = false) {
  return useQuery({ queryKey: ['plants', visibleOnly], queryFn: () => api.getPlants(visibleOnly) });
}

export function useYears() {
  return useQuery({ queryKey: ['years'], queryFn: () => api.getYears() });
}

export function useGlobalSplits(year?: number) {
  return useQuery({ queryKey: ['global-splits', year], queryFn: () => api.getGlobalSplits(year) });
}

export function useAnnualTargetEntry(year: number, plantId: number | null, kpiId: number, enabled = true) {
  return useQuery({
    queryKey: ['annual-target-entry', year, plantId, kpiId],
    queryFn: () => api.getAnnualTargetEntry(year, plantId as number, kpiId),
    enabled: enabled && plantId !== null,
  });
}

export function useKpiVisibility(kpiId: number | null) {
  return useQuery({
    queryKey: ['kpi-visibility', kpiId],
    queryFn: () => api.getKpiVisibility(kpiId as number),
    enabled: kpiId !== null,
  });
}

export function useInvalidateAll() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ['kpis'] });
    qc.invalidateQueries({ queryKey: ['kpi-tree'] });
    qc.invalidateQueries({ queryKey: ['plants'] });
    qc.invalidateQueries({ queryKey: ['global-splits'] });
    qc.invalidateQueries({ queryKey: ['years'] });
  };
}

export function useCreateKpiNode() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ name, parentId, customLevelLabel }: { name: string; parentId?: number | null; customLevelLabel?: string }) =>
      api.addKpiNode(name, parentId, customLevelLabel),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['kpi-tree'] }),
  });
}

export function useCreateKpiIndicator() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<KpiDetailedSpec> & { node_id: number; name: string }) => api.createKpiIndicator(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['kpi-tree'] });
      qc.invalidateQueries({ queryKey: ['kpis'] });
    },
  });
}

export function useUpdateKpiSpec() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ kpiId, dataUpdates }: { kpiId: number; dataUpdates: Record<string, any> }) => api.updateKpiSpec(kpiId, dataUpdates),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['kpi-tree'] });
      qc.invalidateQueries({ queryKey: ['kpis'] });
    },
  });
}

export function useSoftDeleteKpi() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (kpiId: number) => api.softDeleteKpi(kpiId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['kpi-tree'] });
      qc.invalidateQueries({ queryKey: ['kpis'] });
    },
  });
}

export function useUpdateKpiVisibility() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ kpiId, visibilityData }: { kpiId: number; visibilityData: VisibilityEntry[] }) =>
      api.updateKpiVisibility(kpiId, visibilityData),
    onSuccess: (_data, vars) => qc.invalidateQueries({ queryKey: ['kpi-visibility', vars.kpiId] }),
  });
}

export function useSaveAnnualTargets() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: SaveAnnualTargetsPayload) => api.saveAnnualTargets(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['annual-target-entry'] }),
  });
}

export function useCreatePlant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name: string; description?: string; visible?: boolean; color?: string }) => api.createPlant(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['plants'] }),
  });
}

export function useUpdatePlant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ plantId, payload }: { plantId: number; payload: { name: string; description?: string; visible: boolean; color: string } }) =>
      api.updatePlant(plantId, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['plants'] }),
  });
}

export function useCreateGlobalSplit() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Parameters<typeof api.createGlobalSplit>[0]) => api.createGlobalSplit(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['global-splits'] }),
  });
}

export function useUpdateGlobalSplit() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ splitId, payload }: { splitId: number; payload: Parameters<typeof api.updateGlobalSplit>[1] }) =>
      api.updateGlobalSplit(splitId, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['global-splits'] }),
  });
}

export function useDeleteGlobalSplit() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (splitId: number) => api.deleteGlobalSplit(splitId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['global-splits'] }),
  });
}

export function useUsers(activeOnly = false) {
  return useQuery({ queryKey: ['users', activeOnly], queryFn: () => api.getUsers(activeOnly) });
}

export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name: string; password: string; email?: string; color?: string }) => api.createUser(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  });
}

export function useUpdateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, payload }: { userId: number; payload: { name: string; email?: string; color?: string; is_active: boolean } }) =>
      api.updateUser(userId, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  });
}

export function useUserApiKeys(userId: number | null) {
  return useQuery({
    queryKey: ['api-keys', userId],
    queryFn: () => api.getUserApiKeys(userId as number),
    enabled: userId !== null,
  });
}

export function useCreateApiKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, label }: { userId: number; label: string }) => api.createUserApiKey(userId, label),
    onSuccess: (_data, vars) => qc.invalidateQueries({ queryKey: ['api-keys', vars.userId] }),
  });
}

export function useRevokeApiKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (keyId: number) => api.revokeApiKey(keyId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['api-keys'] }),
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
    queryKey: ['kpi-target-history', kpiId, plantId],
    queryFn: () => api.getKpiTargetHistory(kpiId as number, plantId),
    enabled: kpiId !== null,
  });
}
