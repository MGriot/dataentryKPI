import React, { useEffect, useState } from 'react';
import { Target, Calendar, Save, History, Sliders, Layers, Globe, Loader2, CheckCircle2 } from 'lucide-react';
import type { KpiDetailedSpec, Plant } from '../types';
import { REPARTITION_LOGIC_OPTIONS, DISTRIBUTION_PROFILE_OPTIONS, targetLabel, parseTargetLabels } from '../types';
import { useAnnualTargetEntry, useGlobalSplits, useSaveAnnualTargets } from '../hooks';
import type { AnnualTargetValueInput } from '../services/api';

interface TargetEntryWorkspaceProps {
  kpis: KpiDetailedSpec[];
  selectedYear: number;
  selectedPlantId: number | null;
  plants: Plant[];
  searchQuery: string;
}

function formatNum(n: number | null | undefined): string {
  if (n === null || n === undefined) return 'n/a';
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

interface CardProps {
  kpi: KpiDetailedSpec;
  year: number;
  plantId: number;
  plants: Plant[];
  broadcastAll: boolean;
}

const TargetEntryCard: React.FC<CardProps> = ({ kpi, year, plantId, plants, broadcastAll }) => {
  const targetCount = kpi.target_count || 1;
  const customTargetLabels = parseTargetLabels(kpi.target_labels);
  const { data: currentEntry } = useAnnualTargetEntry(year, plantId, kpi.id);
  const { data: y1Entry } = useAnnualTargetEntry(year - 1, plantId, kpi.id);
  const { data: y2Entry } = useAnnualTargetEntry(year - 2, plantId, kpi.id);
  const { data: globalSplits = [] } = useGlobalSplits(year);
  const saveMutation = useSaveAnnualTargets();

  const [values, setValues] = useState<Record<number, string>>({});
  const [logic, setLogic] = useState('Year');
  const [profile, setProfile] = useState('even_distribution');
  const [globalSplitId, setGlobalSplitId] = useState<number | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (currentEntry) {
      const nextValues: Record<number, string> = {};
      for (const tv of currentEntry.target_values || []) {
        nextValues[tv.target_number] = tv.target_value != null ? String(tv.target_value) : '';
      }
      setValues(nextValues);
      setLogic(currentEntry.repartition_logic || 'Year');
      setProfile(currentEntry.distribution_profile || 'even_distribution');
      setGlobalSplitId(currentEntry.global_split_id ?? null);
    }
  }, [currentEntry]);

  const handleValueChange = (targetNumber: number, value: string) => {
    setValues((prev) => ({ ...prev, [targetNumber]: value }));
    setSaved(false);
  };

  const handleSave = () => {
    const targets: AnnualTargetValueInput[] = Array.from({ length: targetCount }, (_, i) => i + 1).map((tn) => ({
      target_number: tn,
      target_value: values[tn] !== undefined && values[tn] !== '' ? parseFloat(values[tn]) : null,
      is_manual: true,
    }));

    const plantIds = broadcastAll ? plants.filter((p) => p.visible).map((p) => p.id) : plantId;

    saveMutation.mutate(
      {
        year,
        plant_id: plantIds,
        targets_data_map: {
          [kpi.id]: {
            repartition_logic: logic,
            distribution_profile: profile,
            global_split_id: globalSplitId,
            targets,
          },
        },
        initiator_kpi_spec_id: kpi.id,
      },
      { onSuccess: () => setSaved(true) }
    );
  };

  const y1Val = y1Entry?.target_values?.find((t: any) => t.target_number === 1)?.target_value ?? null;
  const y2Val = y2Entry?.target_values?.find((t: any) => t.target_number === 2)?.target_value ?? null;
  const y2Val1 = y2Entry?.target_values?.find((t: any) => t.target_number === 1)?.target_value ?? null;

  return (
    <div className="card" style={{ position: 'relative' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '1rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600 }}>{kpi.indicator_name}</h3>
            {kpi.is_calculated && <span className="badge badge-purple">Formula Derived</span>}
            <span className="badge badge-green">{kpi.unit_of_measure || 'Units'}</span>
            <span className="badge badge-blue">{targetCount} target{targetCount > 1 ? 's' : ''}</span>
          </div>
          {kpi.hierarchy_path && (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>{kpi.hierarchy_path}</div>
          )}
          {kpi.description && (
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>💡 {kpi.description}</div>
          )}
        </div>

        <button className="btn btn-primary" style={{ fontSize: '0.8rem' }} onClick={handleSave} disabled={saveMutation.isPending}>
          {saveMutation.isPending ? <Loader2 size={14} className="spin" /> : saved ? <CheckCircle2 size={14} /> : <Save size={14} />}
          {saveMutation.isPending ? 'Saving...' : saved ? 'Saved & Repartitioned' : broadcastAll ? 'Save to All Facilities' : 'Save'}
        </button>
      </div>

      {/* Dynamic target scenario grid: one block per target_count */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${Math.min(targetCount, 3)}, 1fr)`,
          gap: '1rem',
          marginBottom: '1rem',
        }}
      >
        {Array.from({ length: targetCount }, (_, i) => i + 1).map((tn) => (
          <div
            key={tn}
            style={{ background: 'var(--bg-primary)', padding: '0.75rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <span style={{ fontWeight: 600, fontSize: '0.85rem', color: tn === 1 ? 'var(--accent-primary)' : 'var(--accent-purple)' }}>
                {targetLabel(tn, customTargetLabels)}
              </span>
              {tn === 1 && <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Granularity: {kpi.target_granularity || 'Monthly'}</span>}
            </div>

            <input
              type="number"
              placeholder="Enter target value..."
              value={values[tn] ?? ''}
              disabled={kpi.is_calculated}
              onChange={(e) => handleValueChange(tn, e.target.value)}
              style={{
                width: '100%',
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-sm)',
                padding: '0.5rem',
                color: 'var(--text-primary)',
                fontSize: '1rem',
                fontWeight: 600,
              }}
            />

            {tn === 1 && (
              <div style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                <span>
                  <History size={12} style={{ verticalAlign: 'middle' }} /> Y-1 ({year - 1}): <strong style={{ color: 'var(--text-secondary)' }}>{formatNum(y1Val)}</strong>
                </span>
                <span>
                  Y-2 ({year - 2}): <strong style={{ color: 'var(--text-secondary)' }}>{formatNum(y2Val1)}</strong>
                </span>
              </div>
            )}
            {tn === 2 && (
              <div style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                <span>
                  Y-2 T2 ({year - 2}): <strong style={{ color: 'var(--text-secondary)' }}>{formatNum(y2Val)}</strong>
                </span>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Repartition & Seasonal Curve Controls */}
      <div style={{ background: 'rgba(0, 0, 0, 0.2)', padding: '0.75rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
          <Sliders size={14} /> Repartition & Seasonality Settings
        </div>

        <div className="grid-3">
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '2px' }}>Global Split Template:</label>
            <select
              className="select-control"
              style={{ width: '100%' }}
              value={globalSplitId ?? 'none'}
              onChange={(e) => setGlobalSplitId(e.target.value === 'none' ? null : Number(e.target.value))}
            >
              <option value="none">None (Custom)</option>
              {globalSplits.map((gs) => (
                <option key={gs.id} value={gs.id}>
                  ⭐ {gs.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '2px' }}>Repartition Logic:</label>
            <select className="select-control" style={{ width: '100%' }} value={logic} onChange={(e) => setLogic(e.target.value)}>
              {REPARTITION_LOGIC_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '2px' }}>Distribution Profile Curve:</label>
            <select className="select-control" style={{ width: '100%' }} value={profile} onChange={(e) => setProfile(e.target.value)}>
              {DISTRIBUTION_PROFILE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>
    </div>
  );
};

export const TargetEntryWorkspace: React.FC<TargetEntryWorkspaceProps> = ({ kpis, selectedYear, selectedPlantId, plants, searchQuery }) => {
  const [broadcastAll, setBroadcastAll] = useState(false);

  const filteredKpis = kpis.filter(
    (k) =>
      k.indicator_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (k.hierarchy_path && k.hierarchy_path.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const currentPlant = plants.find((p) => p.id === selectedPlantId);

  if (!selectedPlantId) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>
        <Target size={36} style={{ margin: '0 auto 1rem auto', opacity: 0.5 }} />
        <h3>No facility selected</h3>
        <p>Choose a facility from the header to begin entering targets.</p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      <div className="glass-card" style={{ padding: '1rem 1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, color: 'var(--accent-primary)' }}>
            <Calendar size={18} /> Year: {selectedYear}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, color: currentPlant?.color || 'var(--text-primary)' }}>
            <Target size={18} /> Facility: {currentPlant?.name || 'Unknown'}
          </div>
          <span className="badge badge-blue">{filteredKpis.length} Indicators Listed</span>
        </div>

        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', cursor: 'pointer' }}>
          <input type="checkbox" checked={broadcastAll} onChange={(e) => setBroadcastAll(e.target.checked)} />
          <Globe size={14} /> Apply saves to all visible facilities
        </label>
      </div>

      {filteredKpis.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>
          <Layers size={36} style={{ margin: '0 auto 1rem auto', opacity: 0.5 }} />
          <h3>No matching KPI indicators found</h3>
          <p>Try searching for a different keyword or update plant visibility settings.</p>
        </div>
      ) : (
        filteredKpis.map((kpi) => (
          <TargetEntryCard key={kpi.id} kpi={kpi} year={selectedYear} plantId={selectedPlantId} plants={plants} broadcastAll={broadcastAll} />
        ))
      )}
    </div>
  );
};
