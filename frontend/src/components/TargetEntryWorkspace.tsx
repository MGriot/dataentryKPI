import React, { useEffect, useState } from 'react';
import { Target, Calendar, Save, History, Layers, Globe, Loader2, CheckCircle2, Sigma } from 'lucide-react';
import type { AnnualTargetEntry, KpiDetailedSpec, Plant } from '../types';
import { targetLabel, parseTargetLabels } from '../types';
import { useAnnualTargetEntry, useKpiGlobalSplits, useSaveAnnualTargets } from '../hooks';
import { buildTargetsPayload } from '../utils/forms';

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

function valueOf(entry: AnnualTargetEntry | null | undefined, targetNumber: number): number | null {
  return entry?.target_values?.find((t) => t.target_number === targetNumber)?.target_value ?? null;
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
  const isCalculated = !!kpi.is_calculated;
  const customTargetLabels = parseTargetLabels(kpi.target_labels);
  const entryQuery = useAnnualTargetEntry(year, plantId, kpi.id);
  const { data: y1Entry } = useAnnualTargetEntry(year - 1, plantId, kpi.id);
  const { data: y2Entry } = useAnnualTargetEntry(year - 2, plantId, kpi.id);
  const { data: assignedSplits = [] } = useKpiGlobalSplits(kpi.id);
  const saveMutation = useSaveAnnualTargets();

  const [values, setValues] = useState<Record<number, string>>({});
  const [saved, setSaved] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  // Load (or clear) the inputs whenever the year/plant/KPI or the stored entry changes, so values
  // from a previous selection can never be saved into a year or facility that has no data.
  const currentEntry = entryQuery.data;
  const entryLoaded = entryQuery.isSuccess;
  useEffect(() => {
    if (!entryLoaded) return;
    const next: Record<number, string> = {};
    for (const tv of currentEntry?.target_values ?? []) {
      next[tv.target_number] = tv.target_value != null ? String(tv.target_value) : '';
    }
    setValues(next);
    setSaved(false);
    setLocalError(null);
  }, [currentEntry, entryLoaded, year, plantId, kpi.id]);

  const handleValueChange = (targetNumber: number, value: string) => {
    setValues((prev) => ({ ...prev, [targetNumber]: value }));
    setSaved(false);
    setLocalError(null);
  };

  const handleSave = () => {
    const targets = buildTargetsPayload(values, targetCount);
    if (typeof targets === 'string') {
      setLocalError(targets);
      return;
    }
    const visiblePlants = plants.filter((p) => p.visible);
    if (broadcastAll) {
      const ok = window.confirm(
        `Save ${kpi.indicator_name} for ${year} to all ${visiblePlants.length} visible facilities? This replaces their current values.`
      );
      if (!ok) return;
    }
    saveMutation.mutate(
      {
        year,
        plant_id: broadcastAll ? visiblePlants.map((p) => p.id) : plantId,
        targets_data_map: { [kpi.id]: { targets } },
        initiator_kpi_spec_id: kpi.id,
      },
      { onSuccess: () => setSaved(true) }
    );
  };

  const splitName = assignedSplits[0]?.name;

  return (
    <section className="card" aria-labelledby={`kpi-${kpi.id}-title`}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '1rem', gap: '1rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
            <h3 id={`kpi-${kpi.id}-title`} style={{ fontSize: '1.05rem', fontWeight: 600 }}>{kpi.indicator_name}</h3>
            {isCalculated && (
              <span className="badge badge-purple" title={kpi.formula_string || 'Calculated from a formula'}>
                <Sigma size={12} aria-hidden="true" /> Formula derived
              </span>
            )}
            {kpi.unit_of_measure && <span className="badge badge-green">{kpi.unit_of_measure}</span>}
            <span className="badge badge-blue">{targetCount} target{targetCount > 1 ? 's' : ''}</span>
            <span className="badge badge-purple" title="The split is assigned in KPI Explorer">
              {splitName ? `⭐ ${splitName}` : 'Even split (default)'}
            </span>
          </div>
          {kpi.hierarchy_path && <div className="field-hint">{kpi.hierarchy_path}</div>}
          {kpi.description && (
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>💡 {kpi.description}</div>
          )}
        </div>

        {!isCalculated && (
          <button
            type="button"
            className="btn btn-primary"
            style={{ fontSize: '0.8rem', whiteSpace: 'nowrap' }}
            onClick={handleSave}
            disabled={saveMutation.isPending || !entryLoaded}
          >
            {saveMutation.isPending ? <Loader2 size={14} className="spin" aria-hidden="true" /> : saved ? <CheckCircle2 size={14} aria-hidden="true" /> : <Save size={14} aria-hidden="true" />}
            {saveMutation.isPending ? 'Saving...' : saved ? 'Saved & repartitioned' : broadcastAll ? 'Save to all facilities' : 'Save'}
          </button>
        )}
      </div>

      {isCalculated && (
        <p className="field-hint" style={{ marginBottom: '0.75rem' }}>
          Calculated automatically from <code>{kpi.formula_string || 'its formula'}</code> whenever its inputs are saved.
        </p>
      )}
      {localError && (
        <p role="alert" style={{ color: 'var(--accent-danger)', fontSize: '0.8rem', marginBottom: '0.75rem' }}>
          {localError}
        </p>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(targetCount, 3)}, 1fr)`, gap: '1rem' }}>
        {Array.from({ length: targetCount }, (_, i) => i + 1).map((tn) => {
          const inputId = `target-${kpi.id}-${tn}`;
          return (
            <div
              key={tn}
              style={{ background: 'var(--bg-primary)', padding: '0.75rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                <label htmlFor={inputId} style={{ fontWeight: 600, fontSize: '0.85rem', color: tn === 1 ? 'var(--accent-primary)' : 'var(--accent-purple)' }}>
                  {targetLabel(tn, customTargetLabels)}
                </label>
                {tn === 1 && <span className="field-hint">Granularity: {kpi.target_granularity || 'Monthly'}</span>}
              </div>

              <input
                id={inputId}
                type="number"
                inputMode="decimal"
                step="any"
                placeholder={isCalculated ? 'Calculated' : entryLoaded ? 'Enter annual target...' : 'Loading...'}
                value={values[tn] ?? ''}
                readOnly={isCalculated}
                disabled={!entryLoaded}
                onChange={(e) => handleValueChange(tn, e.target.value)}
                className="target-input"
              />

              <div style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem' }} className="field-hint">
                <span>
                  <History size={12} style={{ verticalAlign: 'middle' }} aria-hidden="true" /> {year - 1}:{' '}
                  <strong style={{ color: 'var(--text-secondary)' }}>{formatNum(valueOf(y1Entry, tn))}</strong>
                </span>
                <span>
                  {year - 2}: <strong style={{ color: 'var(--text-secondary)' }}>{formatNum(valueOf(y2Entry, tn))}</strong>
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
};

export const TargetEntryWorkspace: React.FC<TargetEntryWorkspaceProps> = ({ kpis, selectedYear, selectedPlantId, plants, searchQuery }) => {
  const [broadcastAll, setBroadcastAll] = useState(false);
  const query = searchQuery.trim().toLowerCase();
  const filteredKpis = kpis.filter(
    (k) => k.indicator_name.toLowerCase().includes(query) || (k.hierarchy_path || '').toLowerCase().includes(query)
  );
  const currentPlant = plants.find((p) => p.id === selectedPlantId);

  if (!selectedPlantId) {
    return (
      <div className="card empty-state">
        <Target size={36} aria-hidden="true" />
        <h2>No facility yet</h2>
        <p>Add a facility on the Facilities tab, then choose it in the header to enter targets.</p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      <div className="glass-card" style={{ padding: '1rem 1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, color: 'var(--accent-primary)' }}>
            <Calendar size={18} aria-hidden="true" /> Year: {selectedYear}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600 }}>
            <span aria-hidden="true" style={{ width: 10, height: 10, borderRadius: '50%', background: currentPlant?.color }} />
            Facility: {currentPlant?.name || 'Unknown'}
          </div>
          <span className="badge badge-blue">{filteredKpis.length} indicators</span>
        </div>

        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', cursor: 'pointer' }}>
          <input type="checkbox" checked={broadcastAll} onChange={(e) => setBroadcastAll(e.target.checked)} />
          <Globe size={14} aria-hidden="true" /> Apply saves to all visible facilities
        </label>
      </div>

      {filteredKpis.length === 0 ? (
        <div className="card empty-state">
          <Layers size={36} aria-hidden="true" />
          <h2>No matching KPI indicators</h2>
          <p>Create KPIs in KPI Explorer, try another search, or check this facility's KPI visibility.</p>
        </div>
      ) : (
        filteredKpis.map((kpi) => (
          <TargetEntryCard key={kpi.id} kpi={kpi} year={selectedYear} plantId={selectedPlantId} plants={plants} broadcastAll={broadcastAll} />
        ))
      )}
    </div>
  );
};
