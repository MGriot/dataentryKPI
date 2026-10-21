import { Suspense, lazy, useEffect, useState, useSyncExternalStore } from 'react';
import type { ReactNode } from 'react';
import { MutationCache, QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import { AlertTriangle, Loader2, RefreshCw } from 'lucide-react';
import { Header } from './components/Header';
import { LoginScreen } from './components/LoginScreen';
import { Toasts } from './components/Toasts';
import { notifyError } from './utils/toast';
import { TargetEntryWorkspace } from './components/TargetEntryWorkspace';
import { KpiManagerWorkspace } from './components/KpiManagerWorkspace';
import { PlantsWorkspace } from './components/PlantsWorkspace';
import { SettingsWorkspace } from './components/SettingsWorkspace';
import { AUTH_STATUS_KEY, invalidateData, useKpis, useKpiTree, usePlants } from './hooks';
import { ApiError, api, errorMessage } from './services/api';
import { getSessionToken, subscribeToSession } from './utils/session';
import type { User } from './types';

// The chart-heavy tabs (recharts) load on demand to keep the initial bundle small.
const GlobalSplitsWorkspace = lazy(() => import('./components/GlobalSplitsWorkspace').then((m) => ({ default: m.GlobalSplitsWorkspace })));
const AnalysisWorkspace = lazy(() => import('./components/AnalysisWorkspace').then((m) => ({ default: m.AnalysisWorkspace })));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
    },
  },
  // Every failed save surfaces to the user, unless the form shows the error itself (meta.silent).
  mutationCache: new MutationCache({
    onError: (error, _vars, _ctx, mutation) => {
      if (!mutation.meta?.silent) notifyError(errorMessage(error));
    },
  }),
});

export type TabId = 'target-entry' | 'kpi-manager' | 'global-splits' | 'analysis' | 'plants' | 'settings';

function Workspace({ currentUser }: { currentUser: User }) {
  const [activeTab, setActiveTab] = useState<TabId>('target-entry');
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear());
  const [selectedPlantId, setSelectedPlantId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const { data: plants = [] } = usePlants();
  const effectivePlantId = plants.some((p) => p.id === selectedPlantId) ? selectedPlantId : (plants[0]?.id ?? null);
  // Target Entry lists the KPIs enabled for the chosen facility; everything else sees all KPIs
  // (KPI Explorer must list KPIs disabled for a plant so they can be re-enabled).
  const { data: plantKpis = [] } = useKpis(false, effectivePlantId);
  const { data: allKpis = [] } = useKpis(false);
  const { data: tree = [] } = useKpiTree();

  return (
    <div className="app-container">
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        selectedYear={selectedYear}
        setSelectedYear={setSelectedYear}
        selectedPlantId={effectivePlantId}
        setSelectedPlantId={setSelectedPlantId}
        plants={plants}
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
        onRefresh={() => invalidateData(queryClient)}
        currentUser={currentUser}
      />

      <div className="main-workspace">
        <main className="workspace-content" id="main">
          <Suspense fallback={<Loader2 size={24} className="spin" color="var(--accent-primary)" aria-label="Loading" />}>
          {activeTab === 'target-entry' && (
            <TargetEntryWorkspace
              kpis={plantKpis}
              plants={plants}
              selectedYear={selectedYear}
              selectedPlantId={effectivePlantId}
              searchQuery={searchQuery}
            />
          )}
          {activeTab === 'kpi-manager' && <KpiManagerWorkspace tree={tree} kpis={allKpis} plants={plants} />}
          {activeTab === 'global-splits' && <GlobalSplitsWorkspace selectedYear={selectedYear} />}
          {activeTab === 'analysis' && (
            <AnalysisWorkspace kpis={allKpis} plants={plants} selectedYear={selectedYear} selectedPlantId={effectivePlantId} />
          )}
          {activeTab === 'plants' && <PlantsWorkspace plants={plants} />}
          {activeTab === 'settings' && <SettingsWorkspace currentUser={currentUser} />}
          </Suspense>
        </main>
      </div>
    </div>
  );
}

function FullScreen({ children }: { children: ReactNode }) {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-primary)' }}>
      {children}
    </div>
  );
}

function AuthGate() {
  const token = useSyncExternalStore(subscribeToSession, getSessionToken);

  // Signing out (here or in another tab) drops every cached query, so the next user never
  // sees the previous user's data. The login screen's own status query is already mounted
  // and fetching by the time this runs: removing it would discard its result.
  useEffect(() => {
    if (token) return;
    queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== AUTH_STATUS_KEY });
    queryClient.getMutationCache().clear();
  }, [token]);

  const meQuery = useQuery({
    queryKey: ['auth-me', token],
    queryFn: () => api.getMe(),
    enabled: !!token,
    retry: false,
  });

  if (!token) return <LoginScreen />;
  if (meQuery.isLoading) {
    return (
      <FullScreen>
        <Loader2 size={28} className="spin" color="var(--accent-primary)" aria-label="Loading" />
      </FullScreen>
    );
  }
  if (meQuery.isError) {
    // A 401 already cleared the session (-> login screen). Anything else is the server being
    // unreachable: keep the session and offer a retry instead of logging the user out.
    return (
      <FullScreen>
        <div className="card" style={{ maxWidth: 420, textAlign: 'center' }}>
          <AlertTriangle size={28} color="var(--accent-warning)" style={{ margin: '0 auto 0.75rem' }} aria-hidden="true" />
          <h2 style={{ fontSize: '1.05rem', marginBottom: '0.5rem' }}>Can't reach the server</h2>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>{errorMessage(meQuery.error)}</p>
          <button type="button" className="btn btn-primary" onClick={() => meQuery.refetch()}>
            <RefreshCw size={14} aria-hidden="true" /> Try again
          </button>
        </div>
      </FullScreen>
    );
  }
  if (!meQuery.data) return <LoginScreen />;
  return <Workspace currentUser={meQuery.data} />;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthGate />
      <Toasts />
    </QueryClientProvider>
  );
}

export default App;
