import React, { useEffect, useMemo, useState } from 'react';
import { BarChart3, TrendingUp, Download, Loader2 } from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';
import type { KpiDetailedSpec, Plant } from '../types';
import { targetLabel, parseTargetLabels } from '../types';
import { useQuery } from '@tanstack/react-query';
import { api } from '../services/api';
import { useYears } from '../hooks';

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

const MONTH_ORDER = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const QUARTER_ORDER = ['Q1', 'Q2', 'Q3', 'Q4'];

function periodSortKey(granularity: Granularity, period: string): number | string {
  if (granularity === 'Month') return MONTH_ORDER.indexOf(period);
  if (granularity === 'Quarter') return QUARTER_ORDER.indexOf(period);
  // Day (ISO date) and Week ("YYYY-Wnn") both sort correctly as plain strings.
  return period;
}

function targetValue(entry: any, targetNumber: number): number | null {
  const tv = entry?.target_values?.find((t: any) => t.target_number === targetNumber);
  return tv ? tv.target_value : null;
}

export const AnalysisWorkspace: React.FC<AnalysisWorkspaceProps> = ({ kpis, plants, selectedYear, selectedPlantId }) => {
  const [chartKpiId, setChartKpiId] = useState<number | null>(kpis[0]?.id ?? null);
  const [chartGranularity, setChartGranularity] = useState<Granularity>('Month');
  const [chartYear, setChartYear] = useState<number>(selectedYear);
  const [chartFacilityId, setChartFacilityId] = useState<number | 'all'>('all');
  const [exporting, setExporting] = useState(false);

  const { data: years = [] } = useYears();

  useEffect(() => {
    if (!chartKpiId && kpis.length > 0) setChartKpiId(kpis[0].id);
  }, [kpis, chartKpiId]);

  const { data: currentYearTargets = [] } = useQuery({
    queryKey: ['annual-targets', selectedPlantId, selectedYear],
    queryFn: () => api.getAnnualTargets(selectedPlantId as number, selectedYear),
    enabled: selectedPlantId !== null,
  });

  const { data: priorYearTargets = [] } = useQuery({
    queryKey: ['annual-targets', selectedPlantId, selectedYear - 1],
    queryFn: () => api.getAnnualTargets(selectedPlantId as number, selectedYear - 1),
    enabled: selectedPlantId !== null,
  });

  const { data: chartRecords = [], isFetching: chartLoading } = useQuery({
    queryKey: ['periodic-all-plants', chartKpiId, chartGranularity, chartYear],
    queryFn: () => api.getKpiPeriodicTargetsAllPlants(chartKpiId as number, chartGranularity, chartYear),
    enabled: chartKpiId !== null,
  });

  const currentByKpi = useMemo(() => {
    const map: Record<number, any> = {};
    for (const t of currentYearTargets) map[t.kpi_id] = t;
    return map;
  }, [currentYearTargets]);

  const priorByKpi = useMemo(() => {
    const map: Record<number, any> = {};
    for (const t of priorYearTargets) map[t.kpi_id] = t;
    return map;
  }, [priorYearTargets]);

  const chartData = useMemo(() => {
    const byPeriod: Record<string, any> = {};
    const plantNames = new Set<string>();
    for (const rec of chartRecords) {
      if (chartFacilityId !== 'all' && rec.plant_id !== chartFacilityId) continue;
      if (!byPeriod[rec.period]) byPeriod[rec.period] = { period: rec.period };
      byPeriod[rec.period][rec.plant_name] = rec.target_value;
      plantNames.add(rec.plant_name);
    }
    const rows = Object.values(byPeriod).sort(
      (a: any, b: any) => {
        const ka = periodSortKey(chartGranularity, a.period);
        const kb = periodSortKey(chartGranularity, b.period);
        return ka < kb ? -1 : ka > kb ? 1 : 0;
      }
    );
    return { rows, plantNames: Array.from(plantNames) };
  }, [chartRecords, chartFacilityId, chartGranularity]);

  const seriesColors = ['var(--accent-primary)', 'var(--accent-teal)', 'var(--accent-purple)', 'var(--accent-warning)', 'var(--accent-success)'];

  const maxTargetCount = useMemo(() => Math.max(1, ...kpis.map((k) => k.target_count || 1)), [kpis]);

  const handleExport = async () => {
    setExporting(true);
    try {
      await api.downloadCsvTable('Periodic Targets');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      <div className="glass-card" style={{ padding: '1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h2 style={{ fontSize: '1.15rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <BarChart3 color="var(--accent-primary)" /> Target Distribution & Multi-Plant Analysis
          </h2>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Compare target distributions across facilities and inspect target breakdowns for {selectedYear}.
          </p>
        </div>

        <button className="btn btn-secondary" onClick={handleExport} disabled={exporting}>
          {exporting ? <Loader2 size={14} className="spin" /> : <Download size={14} />} Export Periodic Targets CSV
        </button>
      </div>

      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <TrendingUp size={16} color="var(--accent-primary)" /> Target Allocations Across Facilities
          </h3>

          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <select className="select-control" value={chartKpiId ?? ''} onChange={(e) => setChartKpiId(Number(e.target.value))}>
              {kpis.map((k) => (
                <option key={k.id} value={k.id}>
                  {k.indicator_name}
                </option>
              ))}
            </select>

            <select className="select-control" value={chartGranularity} onChange={(e) => setChartGranularity(e.target.value as Granularity)}>
              {GRANULARITY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>

            <select className="select-control" value={chartYear} onChange={(e) => setChartYear(Number(e.target.value))}>
              {(years.length > 0 ? years.map((y) => y.year) : [selectedYear]).map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>

            <select className="select-control" value={chartFacilityId} onChange={(e) => setChartFacilityId(e.target.value === 'all' ? 'all' : Number(e.target.value))}>
              <option value="all">All Facilities</option>
              {plants.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div style={{ height: '320px', width: '100%', position: 'relative' }}>
          {chartLoading && (
            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              <Loader2 size={16} className="spin" style={{ marginRight: '0.5rem' }} /> Loading...
            </div>
          )}
          {!chartLoading && chartData.rows.length === 0 ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              No periodic target data for this selection yet.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData.rows}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="period" stroke="var(--text-muted)" />
                <YAxis stroke="var(--text-muted)" />
                <Tooltip contentStyle={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)' }} />
                <Legend />
                {chartData.plantNames.map((name, idx) => (
                  <Bar key={name} dataKey={name} fill={seriesColors[idx % seriesColors.length]} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <div className="card">
        <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>KPI Target Summary Matrix</h3>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ background: 'var(--bg-primary)', borderBottom: '1px solid var(--border-color)', textAlign: 'left' }}>
                <th style={{ padding: '0.6rem' }}>KPI Indicator</th>
                <th style={{ padding: '0.6rem' }}>Hierarchy Path</th>
                <th style={{ padding: '0.6rem' }}>Unit</th>
                <th style={{ padding: '0.6rem' }}>Aggregation</th>
                {Array.from({ length: maxTargetCount }, (_, i) => i + 1).map((tn) => (
                  <th key={`cur-${tn}`} style={{ padding: '0.6rem' }}>
                    {selectedYear} Target {tn}
                  </th>
                ))}
                {Array.from({ length: maxTargetCount }, (_, i) => i + 1).map((tn) => (
                  <th key={`prior-${tn}`} style={{ padding: '0.6rem' }}>
                    {selectedYear - 1} Target {tn}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {kpis.map((kpi) => {
                const targetCount = kpi.target_count || 1;
                const customLabels = parseTargetLabels(kpi.target_labels);
                return (
                  <tr key={kpi.id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                    <td style={{ padding: '0.6rem', fontWeight: 600 }}>{kpi.indicator_name}</td>
                    <td style={{ padding: '0.6rem', color: 'var(--text-muted)' }}>{kpi.hierarchy_path || '-'}</td>
                    <td style={{ padding: '0.6rem' }}>
                      <span className="badge badge-blue">{kpi.unit_of_measure || 'Units'}</span>
                    </td>
                    <td style={{ padding: '0.6rem' }}>{kpi.calculation_type}</td>
                    {Array.from({ length: maxTargetCount }, (_, i) => i + 1).map((tn) => {
                      if (tn > targetCount) return <td key={`cur-${kpi.id}-${tn}`} style={{ padding: '0.6rem', color: 'var(--text-muted)' }}>—</td>;
                      const cur = targetValue(currentByKpi[kpi.id], tn);
                      return (
                        <td key={`cur-${kpi.id}-${tn}`} title={targetLabel(tn, customLabels)} style={{ padding: '0.6rem', fontWeight: 700, color: 'var(--accent-primary)' }}>
                          {cur !== null ? cur.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}
                        </td>
                      );
                    })}
                    {Array.from({ length: maxTargetCount }, (_, i) => i + 1).map((tn) => {
                      if (tn > targetCount) return <td key={`prior-${kpi.id}-${tn}`} style={{ padding: '0.6rem', color: 'var(--text-muted)' }}>—</td>;
                      const prior = targetValue(priorByKpi[kpi.id], tn);
                      return (
                        <td key={`prior-${kpi.id}-${tn}`} title={targetLabel(tn, customLabels)} style={{ padding: '0.6rem', color: 'var(--text-secondary)' }}>
                          {prior !== null ? prior.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
