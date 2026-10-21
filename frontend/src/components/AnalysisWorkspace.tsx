import React, { useMemo, useState } from 'react';
import { BarChart3, TrendingUp, Download, Loader2 } from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';
import type { AnnualTargetEntry, KpiDetailedSpec, Plant } from '../types';
import { targetLabel, parseTargetLabels } from '../types';
import { useAnnualTargets, usePeriodicTargetsAllPlants } from '../hooks';
import { api, errorMessage } from '../services/api';
import { notifyError } from '../utils/toast';

interface AnalysisWorkspaceProps {
  kpis: KpiDetailedSpec[];
  plants: Plant[];
  selectedYear: number;
  selectedPlantId: number | null;
}

type Granularity = 'Day' | 'Week' | 'Month' | 'Quarter' | 'Year';

const GRANULARITY_OPTIONS: { value: Granularity; label: string }[] = [
  { value: 'Day', label: 'Daily' },
  { value: 'Week', label: 'Weekly' },
  { value: 'Month', label: 'Monthly' },
  { value: 'Quarter', label: 'Quarterly' },
  { value: 'Year', label: 'Yearly' },
];

const NO_ENTRIES: AnnualTargetEntry[] = [];
const SERIES_COLORS = ['var(--accent-primary)', 'var(--accent-teal)', 'var(--accent-purple)', 'var(--accent-warning)', 'var(--accent-success)'];

function targetValue(entry: AnnualTargetEntry | undefined, targetNumber: number): number | null {
  return entry?.target_values?.find((t) => t.target_number === targetNumber)?.target_value ?? null;
}

function fmt(n: number | null) {
  return n !== null ? n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—';
}

export const AnalysisWorkspace: React.FC<AnalysisWorkspaceProps> = ({ kpis, plants, selectedYear, selectedPlantId }) => {
  const [chosenKpiId, setChosenKpiId] = useState<number | null>(null);
  const [chartGranularity, setChartGranularity] = useState<Granularity>('Month');
  const [chartFacilityId, setChartFacilityId] = useState<number | 'all'>('all');
  const [exporting, setExporting] = useState(false);
  const chartKpiId = kpis.some((k) => k.id === chosenKpiId) ? chosenKpiId : (kpis[0]?.id ?? null);
  const chartKpi = kpis.find((k) => k.id === chartKpiId);
  const selectedPlant = plants.find((p) => p.id === selectedPlantId);

  const { data: currentYearTargets = NO_ENTRIES } = useAnnualTargets(selectedPlantId, selectedYear);
  const { data: priorYearTargets = NO_ENTRIES } = useAnnualTargets(selectedPlantId, selectedYear - 1);
  // Follows the header year; the API returns periods in chronological order.
  const { data: chartRecords = [], isFetching: chartLoading } = usePeriodicTargetsAllPlants(chartKpiId, chartGranularity, selectedYear);

  const currentByKpi = useMemo(() => new Map(currentYearTargets.map((t) => [t.kpi_id, t])), [currentYearTargets]);
  const priorByKpi = useMemo(() => new Map(priorYearTargets.map((t) => [t.kpi_id, t])), [priorYearTargets]);

  const chartData = useMemo(() => {
    const byPeriod = new Map<string, Record<string, string | number>>();
    const plantNames: string[] = [];
    for (const rec of chartRecords) {
      if (rec.target_number !== 1) continue;
      if (chartFacilityId !== 'all' && rec.plant_id !== chartFacilityId) continue;
      const name = rec.plant_name || `Plant #${rec.plant_id}`;
      if (!byPeriod.has(rec.period)) byPeriod.set(rec.period, { period: rec.period });
      byPeriod.get(rec.period)![name] = rec.target_value;
      if (!plantNames.includes(name)) plantNames.push(name);
    }
    return { rows: Array.from(byPeriod.values()), plantNames };
  }, [chartRecords, chartFacilityId]);

  const maxTargetCount = useMemo(() => Math.max(1, ...kpis.map((k) => k.target_count || 1)), [kpis]);

  const handleExport = async () => {
    setExporting(true);
    try {
      await api.downloadCsvTable('Periodic Targets');
    } catch (e) {
      notifyError(`Export failed: ${errorMessage(e)}`);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      <div className="glass-card" style={{ padding: '1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h2 className="page-title">
            <BarChart3 color="var(--accent-primary)" aria-hidden="true" /> Target Distribution & Multi-Plant Analysis
          </h2>
          <p className="page-subtitle">Target breakdowns across facilities for {selectedYear} (change the year in the header).</p>
        </div>
        <button type="button" className="btn btn-secondary" onClick={handleExport} disabled={exporting}>
          {exporting ? <Loader2 size={14} className="spin" aria-hidden="true" /> : <Download size={14} aria-hidden="true" />} Export periodic targets (CSV)
        </button>
      </div>

      <section className="card" aria-labelledby="chart-title">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
          <h3 id="chart-title" style={{ fontSize: '1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <TrendingUp size={16} color="var(--accent-primary)" aria-hidden="true" /> {chartKpi ? `${chartKpi.indicator_name} -- Target 1, ${selectedYear}` : 'Target allocations'}
          </h3>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <select className="select-control" aria-label="KPI" value={chartKpiId ?? ''} onChange={(e) => setChosenKpiId(Number(e.target.value))} disabled={kpis.length === 0}>
              {kpis.map((k) => (
                <option key={k.id} value={k.id}>{k.indicator_name}</option>
              ))}
            </select>
            <select className="select-control" aria-label="Granularity" value={chartGranularity} onChange={(e) => setChartGranularity(e.target.value as Granularity)}>
              {GRANULARITY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            <select className="select-control" aria-label="Facility filter" value={chartFacilityId} onChange={(e) => setChartFacilityId(e.target.value === 'all' ? 'all' : Number(e.target.value))}>
              <option value="all">All facilities</option>
              {plants.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
        </div>

        <div style={{ height: '320px', width: '100%', position: 'relative' }}>
          {chartLoading && (
            <div className="chart-overlay">
              <Loader2 size={16} className="spin" aria-hidden="true" /> Loading...
            </div>
          )}
          {!chartLoading && chartData.rows.length === 0 ? (
            <div className="chart-overlay">No periodic targets for this selection yet.</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData.rows}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="period" stroke="var(--text-muted)" />
                <YAxis stroke="var(--text-muted)" />
                <Tooltip contentStyle={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)' }} />
                <Legend />
                {chartData.plantNames.map((name, idx) => (
                  <Bar key={name} dataKey={name} fill={SERIES_COLORS[idx % SERIES_COLORS.length]} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </section>

      <section className="card" aria-labelledby="matrix-title">
        <h3 id="matrix-title" style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>
          Annual targets -- {selectedPlant?.name ?? 'no facility selected'}
        </h3>
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">KPI</th>
                <th scope="col">Folder</th>
                <th scope="col">Unit</th>
                <th scope="col">Aggregation</th>
                {Array.from({ length: maxTargetCount }, (_, i) => i + 1).map((tn) => (
                  <th scope="col" key={`cur-${tn}`}>{selectedYear} T{tn}</th>
                ))}
                {Array.from({ length: maxTargetCount }, (_, i) => i + 1).map((tn) => (
                  <th scope="col" key={`prior-${tn}`}>{selectedYear - 1} T{tn}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {kpis.map((kpi) => {
                const targetCount = kpi.target_count || 1;
                const customLabels = parseTargetLabels(kpi.target_labels);
                return (
                  <tr key={kpi.id}>
                    <th scope="row">{kpi.indicator_name}</th>
                    <td className="muted">{kpi.hierarchy_path || '-'}</td>
                    <td>{kpi.unit_of_measure ? <span className="badge badge-blue">{kpi.unit_of_measure}</span> : '—'}</td>
                    <td>{kpi.calculation_type}</td>
                    {Array.from({ length: maxTargetCount }, (_, i) => i + 1).map((tn) => (
                      <td key={`cur-${kpi.id}-${tn}`} title={tn <= targetCount ? targetLabel(tn, customLabels) : undefined} style={{ fontWeight: 700, color: 'var(--accent-primary)' }}>
                        {tn <= targetCount ? fmt(targetValue(currentByKpi.get(kpi.id), tn)) : '—'}
                      </td>
                    ))}
                    {Array.from({ length: maxTargetCount }, (_, i) => i + 1).map((tn) => (
                      <td key={`prior-${kpi.id}-${tn}`} className="muted">
                        {tn <= targetCount ? fmt(targetValue(priorByKpi.get(kpi.id), tn)) : '—'}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};
