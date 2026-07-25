import { useEffect, useState } from 'react';
import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { Header } from './components/Header';
import { LoginScreen } from './components/LoginScreen';
import { TargetEntryWorkspace } from './components/TargetEntryWorkspace';
import { KpiManagerWorkspace } from './components/KpiManagerWorkspace';
import { GlobalSplitsWorkspace } from './components/GlobalSplitsWorkspace';
import { AnalysisWorkspace } from './components/AnalysisWorkspace';
import { PlantsWorkspace } from './components/PlantsWorkspace';
import { SettingsWorkspace } from './components/SettingsWorkspace';
import { useKpis, useKpiTree, usePlants } from './hooks';
import { api } from './services/api';
import { getSessionToken, clearSession, SESSION_EVENT } from './utils/session';
import type { User } from './types';

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: false } },
});

function Workspace({ currentUser }: { currentUser: User }) {
  const [activeTab, setActiveTab] = useState('target-entry');
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear());
  const [selectedPlantId, setSelectedPlantId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const qc = useQueryClient();

  const { data: plants = [] } = usePlants();
  const { data: kpis = [] } = useKpis(false, selectedPlantId ?? undefined);
  const { data: tree = [] } = useKpiTree();

  const effectivePlantId = selectedPlantId ?? plants[0]?.id ?? null;

  const handleRefresh = () => qc.invalidateQueries();

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
        onRefresh={handleRefresh}
        currentUser={currentUser}
      />

      <div className="main-workspace">
        <main className="workspace-content">
          {activeTab === 'target-entry' && (
            <TargetEntryWorkspace
              kpis={kpis}
              plants={plants}
              selectedYear={selectedYear}
              selectedPlantId={effectivePlantId}
              searchQuery={searchQuery}
            />
          )}
          {activeTab === 'kpi-manager' && (
            <KpiManagerWorkspace tree={tree} kpis={kpis} plants={plants} />
          )}
          {activeTab === 'global-splits' && <GlobalSplitsWorkspace selectedYear={selectedYear} />}
          {activeTab === 'analysis' && (
            <AnalysisWorkspace kpis={kpis} plants={plants} selectedYear={selectedYear} selectedPlantId={effectivePlantId} />
          )}
          {activeTab === 'plants' && <PlantsWorkspace plants={plants} />}
          {activeTab === 'settings' && <SettingsWorkspace />}
        </main>
      </div>
    </div>
  );
}

function FullScreenLoader() {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-primary)' }}>
      <Loader2 size={28} className="spin" color="var(--accent-primary)" />
    </div>
  );
}

function AuthGate() {
  const [, bump] = useState(0);
  useEffect(() => {
    const onChange = () => bump((n) => n + 1);
    window.addEventListener(SESSION_EVENT, onChange);
    return () => window.removeEventListener(SESSION_EVENT, onChange);
  }, []);

  const token = getSessionToken();
  const meQuery = useQuery({
    queryKey: ['auth-me', token],
    queryFn: () => api.getMe(),
    enabled: !!token,
    retry: false,
  });

  useEffect(() => {
    if (meQuery.isError) clearSession();
  }, [meQuery.isError]);

  if (!token) return <LoginScreen />;
  if (meQuery.isLoading) return <FullScreenLoader />;
  if (meQuery.isError || !meQuery.data) return <LoginScreen />;

  return <Workspace currentUser={meQuery.data} />;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthGate />
    </QueryClientProvider>
  );
}

export default App;
