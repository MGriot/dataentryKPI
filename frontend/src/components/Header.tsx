import React, { useMemo } from 'react';
import { Target, Layers, GitFork, BarChart3, Factory, Settings, Search, RefreshCw } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { Plant, User } from '../types';
import type { TabId } from '../App';
import { useYearOptions } from '../hooks';
import { UserMenu } from './UserMenu';

interface HeaderProps {
  activeTab: TabId;
  setActiveTab: (tab: TabId) => void;
  selectedYear: number;
  setSelectedYear: (year: number) => void;
  selectedPlantId: number | null;
  setSelectedPlantId: (id: number) => void;
  plants: Plant[];
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  onRefresh: () => void;
  currentUser: User;
}

const TABS: { id: TabId; label: string; icon: LucideIcon }[] = [
  { id: 'target-entry', label: 'Target Entry', icon: Target },
  { id: 'kpi-manager', label: 'KPI Explorer', icon: Layers },
  { id: 'global-splits', label: 'Global Splits & ML', icon: GitFork },
  { id: 'analysis', label: 'Analysis & Results', icon: BarChart3 },
  { id: 'plants', label: 'Facilities', icon: Factory },
  { id: 'settings', label: 'Data Utilities', icon: Settings },
];

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  setActiveTab,
  selectedYear,
  setSelectedYear,
  selectedPlantId,
  setSelectedPlantId,
  plants,
  searchQuery,
  setSearchQuery,
  onRefresh,
  currentUser,
}) => {
  const yearExtras = useMemo(() => [selectedYear], [selectedYear]);
  const years = useYearOptions(yearExtras);

  return (
    <header className="header-bar">
      <div className="logo-section">
        <Target className="logo-icon" aria-hidden="true" />
        <span className="logo-text">KPI Target Manager</span>
      </div>

      <nav className="nav-tabs" aria-label="Sections">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            className={`nav-tab ${activeTab === id ? 'active' : ''}`}
            aria-current={activeTab === id ? 'page' : undefined}
            onClick={() => setActiveTab(id)}
          >
            <Icon size={16} aria-hidden="true" /> {label}
          </button>
        ))}
      </nav>

      <div className="header-controls">
        <div style={{ position: 'relative' }}>
          <Search size={14} aria-hidden="true" style={{ position: 'absolute', left: 10, top: 10, color: 'var(--text-muted)' }} />
          <input
            type="search"
            aria-label="Search KPIs"
            placeholder="Quick search..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="select-control"
            style={{ paddingLeft: '30px', width: '180px', cursor: 'text' }}
          />
        </div>

        <select
          className="select-control"
          aria-label="Year"
          value={selectedYear}
          onChange={(e) => setSelectedYear(Number(e.target.value))}
        >
          {years.map((y) => (
            <option key={y} value={y}>
              📅 {y}
            </option>
          ))}
        </select>

        <select
          className="select-control"
          aria-label="Facility"
          value={selectedPlantId ?? ''}
          onChange={(e) => setSelectedPlantId(Number(e.target.value))}
          disabled={plants.length === 0}
        >
          {plants.length === 0 && <option value="">No facilities yet</option>}
          {plants.map((p) => (
            <option key={p.id} value={p.id}>
              🏭 {p.name}
            </option>
          ))}
        </select>

        <button type="button" className="btn btn-secondary" onClick={onRefresh} aria-label="Reload data" title="Reload data">
          <RefreshCw size={14} aria-hidden="true" />
        </button>

        <UserMenu user={currentUser} />
      </div>
    </header>
  );
};
