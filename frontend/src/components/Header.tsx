import React from 'react';
import { Target, Layers, GitFork, BarChart3, Factory, Settings, Search, RefreshCw } from 'lucide-react';
import type { Plant, User } from '../types';
import { UserMenu } from './UserMenu';

interface HeaderProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
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
  const years = Array.from({ length: 10 }, (_, i) => new Date().getFullYear() - 3 + i);

  return (
    <header className="header-bar">
      <div className="logo-section">
        <Target className="logo-icon" />
        <span className="logo-text">KPI Target Manager</span>
      </div>

      <nav className="nav-tabs">
        <button
          className={`nav-tab ${activeTab === 'target-entry' ? 'active' : ''}`}
          onClick={() => setActiveTab('target-entry')}
        >
          <Target size={16} /> Target Entry
        </button>

        <button
          className={`nav-tab ${activeTab === 'kpi-manager' ? 'active' : ''}`}
          onClick={() => setActiveTab('kpi-manager')}
        >
          <Layers size={16} /> KPI Explorer
        </button>

        <button
          className={`nav-tab ${activeTab === 'global-splits' ? 'active' : ''}`}
          onClick={() => setActiveTab('global-splits')}
        >
          <GitFork size={16} /> Global Splits & ML
        </button>

        <button
          className={`nav-tab ${activeTab === 'analysis' ? 'active' : ''}`}
          onClick={() => setActiveTab('analysis')}
        >
          <BarChart3 size={16} /> Analysis & Results
        </button>

        <button
          className={`nav-tab ${activeTab === 'plants' ? 'active' : ''}`}
          onClick={() => setActiveTab('plants')}
        >
          <Factory size={16} /> Facilities
        </button>

        <button
          className={`nav-tab ${activeTab === 'settings' ? 'active' : ''}`}
          onClick={() => setActiveTab('settings')}
        >
          <Settings size={16} /> Data Utilities
        </button>
      </nav>

      <div className="header-controls">
        <div style={{ position: 'relative' }}>
          <Search size={14} style={{ position: 'absolute', left: 10, top: 10, color: 'var(--text-muted)' }} />
          <input
            type="text"
            placeholder="Quick search..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              paddingLeft: '30px',
              paddingRight: '10px',
              paddingTop: '6px',
              paddingBottom: '6px',
              background: 'var(--bg-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-primary)',
              fontSize: '0.85rem',
              width: '180px',
            }}
          />
        </div>

        <select
          className="select-control"
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
          value={selectedPlantId ?? ''}
          onChange={(e) => setSelectedPlantId(Number(e.target.value))}
        >
          {plants.map((p) => (
            <option key={p.id} value={p.id}>
              🏭 {p.name}
            </option>
          ))}
        </select>

        <button className="btn btn-secondary" onClick={onRefresh} title="Reload Data">
          <RefreshCw size={14} />
        </button>

        <UserMenu user={currentUser} />
      </div>
    </header>
  );
};
