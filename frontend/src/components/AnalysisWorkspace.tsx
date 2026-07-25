import React, { useEffect, useMemo, useState } from 'react';
import { BarChart3, TrendingUp, Download, Loader2 } from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';
import type { KpiDetailedSpec, Plant } from '../types';
import { useQuery } from '@tanstack/react-query';
import { api } from '../services/api';

interface AnalysisWorkspaceProps {
  kpis: KpiDetailedSpec[];
  plants: Plant[];
  selectedYear: number;
  selectedPlantId: number | null;
}

function targetValue(entry: any, targetNumber: number): number | null {
  const tv = entry?.target_values?.find((t: any) => t.target_number === targetNumber);
  return tv ? tv.target_value : null;
}

export const AnalysisWorkspace: React.FC<AnalysisWorkspaceProps> = ({ kpis, selectedYear, selectedPlantId }) => {
  const [chartKpiId, setChartKpiId] = useState<number | null>(kpis[0]?.id ?? null);
  const [exporting, setExporting] = useState(false);

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

  const { data: chartRecords = [] } = useQuery({
    queryKey: ['periodic-all-plants', chartKpiId, selectedYear],
    queryFn: () => api.getKpiPeriodicTargetsAllPlants(chartKpiId as number, 'Month', selectedYear),
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
      if (!byPeriod[rec.period]) byPeriod[rec.period] = { period: rec.period };
      byPeriod[rec.period][rec.plant_name] = rec.target_value;
      plantNames.add(rec.plant_name);
    }
    const monthOrder = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
    const rows = Object.values(byPeriod).sort((a: any, b: any) => monthOrder.indexOf(a.period) - monthOrder.indexOf(b.period));
    return { rows, plantNames: Array.from(plantNames) };
  }, [chartRecords]);

  const seriesColors = ['var(--accent-primary)', 'var(--accent-teal)', 'var(--accent-purple)', 'var(--accent-warning)', 'var(--accent-success)'];

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
            <TrendingUp size={16} color="var(--accent-primary)" /> Monthly Target Allocations Across Facilities
          </h3>
          <select className="select-control" value={chartKpiId ?? ''} onChange={(e) => setChartKpiId(Number(e.target.value))}>
            {kpis.map((k) => (
              <option key={k.id} value={k.id}>
                {k.indicator_name}
              </option>
            ))}
          </select>
        </div>

        <div style={{ height: '320px', width: '100%' }}>
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
                <th style={{ padding: '0.6rem' }}>{selectedYear} Target 1</th>
                <th style={{ padding: '0.6rem' }}>{selectedYear - 1} Target 1</th>
              </tr>
            </thead>
            <tbody>
              {kpis.map((kpi) => {
                const cur = targetValue(currentByKpi[kpi.id], 1);
                const prior = targetValue(priorByKpi[kpi.id], 1);
                return (
                  <tr key={kpi.id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                    <td style={{ padding: '0.6rem', fontWeight: 600 }}>{kpi.indicator_name}</td>
                    <td style={{ padding: '0.6rem', color: 'var(--text-muted)' }}>{kpi.hierarchy_path || '-'}</td>
                    <td style={{ padding: '0.6rem' }}>
                      <span className="badge badge-blue">{kpi.unit_of_measure || 'Units'}</span>
                    </td>
                    <td style={{ padding: '0.6rem' }}>{kpi.calculation_type}</td>
                    <td style={{ padding: '0.6rem', fontWeight: 700, color: 'var(--accent-primary)' }}>
                      {cur !== null ? cur.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}
                    </td>
                    <td style={{ padding: '0.6rem', color: 'var(--text-secondary)' }}>
                      {prior !== null ? prior.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}
                    </td>
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
