import React, { useMemo, useRef, useState } from 'react';
import { GitFork, Upload, Cpu, Save, Plus, CheckCircle2, Trash2, Loader2 } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { DISTRIBUTION_PROFILE_OPTIONS } from '../types';
import type { MultivariateAnalysisResult } from '../types';
import { useCreateGlobalSplit, useDeleteGlobalSplit, useGlobalSplits } from '../hooks';
import { api } from '../services/api';

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const QUARTERS = ['Q1', 'Q2', 'Q3', 'Q4'];

interface GlobalSplitsWorkspaceProps {
  selectedYear: number;
}

export const GlobalSplitsWorkspace: React.FC<GlobalSplitsWorkspaceProps> = ({ selectedYear }) => {
  const { data: splits = [], isLoading } = useGlobalSplits(selectedYear);
  const createSplit = useCreateGlobalSplit();
  const deleteSplit = useDeleteGlobalSplit();

  const [splitName, setSplitName] = useState('');
  const [selectedLogic, setSelectedLogic] = useState('Month');
  const [selectedProfile, setSelectedProfile] = useState('annual_progressive');
  const [weights, setWeights] = useState<Record<string, number>>({});
  const [createSaved, setCreateSaved] = useState(false);

  const periodKeys = selectedLogic === 'Month' ? MONTHS : selectedLogic === 'Quarter' ? QUARTERS : [];

  const handleCreateSplit = () => {
    if (!splitName.trim()) return;
    createSplit.mutate(
      {
        name: splitName.trim(),
        repartition_logic: selectedLogic,
        repartition_values: weights,
        distribution_profile: selectedProfile,
        profile_params: {},
        years: [selectedYear],
      } as any,
      {
        onSuccess: () => {
          setCreateSaved(true);
          setSplitName('');
          setWeights({});
        },
      }
    );
  };

  // --- Multivariate ML predictor ---
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [targetCols, setTargetCols] = useState('target_value');
  const [featureCols, setFeatureCols] = useState('');
  const [dateCol, setDateCol] = useState('date');
  const [periodType, setPeriodType] = useState('Month');
  const [running, setRunning] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<MultivariateAnalysisResult | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [publishName, setPublishName] = useState('');
  const [publishSaved, setPublishSaved] = useState(false);

  const handleRunPredictor = async () => {
    if (!selectedFile) {
      setAnalysisError('Please choose a CSV/Excel file first.');
      return;
    }
    setRunning(true);
    setAnalysisError(null);
    setAnalysisResult(null);
    try {
      const result = await api.runMultivariateAnalysis(
        selectedFile,
        targetCols.split(',').map((c) => c.trim()).filter(Boolean),
        featureCols.split(',').map((c) => c.trim()).filter(Boolean),
        dateCol.trim(),
        periodType
      );
      setAnalysisResult(result);
    } catch (e: any) {
      setAnalysisError(e.message || 'Analysis failed');
    } finally {
      setRunning(false);
    }
  };

  const handlePublish = () => {
    if (!analysisResult || !publishName.trim()) return;
    createSplit.mutate(
      {
        name: publishName.trim(),
        repartition_logic: periodType,
        repartition_values: analysisResult.weights,
        distribution_profile: 'even_distribution',
        profile_params: { source: 'multivariate_ml', winning_model: analysisResult.winning_model, r_squared: analysisResult.r_squared },
        years: [selectedYear],
      } as any,
      { onSuccess: () => setPublishSaved(true) }
    );
  };

  const chartData = useMemo(() => analysisResult?.plot_data || [], [analysisResult]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      <div className="glass-card" style={{ padding: '1.25rem' }}>
        <h2 style={{ fontSize: '1.15rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <GitFork color="var(--accent-primary)" /> Global Split Templates & ML Seasonality Predictor
        </h2>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
          Define reusable seasonal weight curves or use multivariate regression to calculate weights from historical drivers.
        </p>
      </div>

      {/* Existing Global Splits */}
      <div className="card">
        <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>Global Splits for {selectedYear}</h3>
        {isLoading ? (
          <div style={{ color: 'var(--text-muted)' }}>Loading...</div>
        ) : splits.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No global splits defined for this year yet.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {splits.map((s: any) => (
              <div
                key={s.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.6rem 0.85rem',
                  background: 'var(--bg-primary)',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-color)',
                }}
              >
                <div>
                  <strong>{s.name}</strong>{' '}
                  <span className="badge badge-blue" style={{ marginLeft: '0.5rem' }}>
                    {s.repartition_logic}
                  </span>{' '}
                  <span className="badge badge-purple">{s.distribution_profile}</span>
                </div>
                <button className="btn btn-danger" style={{ fontSize: '0.75rem' }} onClick={() => deleteSplit.mutate(s.id)}>
                  <Trash2 size={12} /> Delete
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="grid-2">
        {/* Left Column: Create Global Split Template */}
        <div className="card">
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Plus size={16} color="var(--accent-primary)" /> Create Global Split Template
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Template Name:</label>
              <input
                type="text"
                placeholder="e.g. Q1 Peak Shutdown Split 2026"
                value={splitName}
                onChange={(e) => { setSplitName(e.target.value); setCreateSaved(false); }}
                className="select-control"
                style={{ width: '100%' }}
              />
            </div>

            <div className="grid-2">
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Repartition Logic:</label>
                <select className="select-control" style={{ width: '100%' }} value={selectedLogic} onChange={(e) => { setSelectedLogic(e.target.value); setWeights({}); }}>
                  <option value="Month">Monthly Breakdown</option>
                  <option value="Quarter">Quarterly Breakdown</option>
                  <option value="Week">Weekly Breakdown</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Profile Curve:</label>
                <select className="select-control" style={{ width: '100%' }} value={selectedProfile} onChange={(e) => setSelectedProfile(e.target.value)}>
                  {DISTRIBUTION_PROFILE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {periodKeys.length > 0 && (
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>Weights (% of Annual Target):</div>
                <div style={{ display: 'grid', gridTemplateColumns: `repeat(${selectedLogic === 'Month' ? 6 : 4}, 1fr)`, gap: '0.5rem' }}>
                  {periodKeys.map((k) => (
                    <div key={k}>
                      <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>{k.slice(0, 3)}:</span>
                      <input
                        type="number"
                        placeholder="0.0"
                        value={weights[k] ?? ''}
                        onChange={(e) => setWeights({ ...weights, [k]: parseFloat(e.target.value) })}
                        style={{
                          width: '100%',
                          background: 'var(--bg-primary)',
                          border: '1px solid var(--border-color)',
                          borderRadius: '4px',
                          padding: '0.25rem 0.4rem',
                          color: 'var(--text-primary)',
                          fontSize: '0.8rem',
                        }}
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}

            <button className="btn btn-primary" style={{ marginTop: '0.5rem' }} onClick={handleCreateSplit} disabled={createSplit.isPending}>
              {createSplit.isPending ? <Loader2 size={16} className="spin" /> : createSaved ? <CheckCircle2 size={16} /> : <Save size={16} />}
              {createSaved ? 'Saved' : 'Save Global Split Template'}
            </button>
          </div>
        </div>

        {/* Right Column: ML Seasonality Predictor Dataset Upload */}
        <div className="card">
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Cpu size={16} color="var(--accent-purple)" /> ML Seasonality Predictor (OLS / Ridge / Random Forest)
          </h3>

          <input ref={fileInputRef} type="file" accept=".csv,.xlsx,.xls" style={{ display: 'none' }} onChange={(e) => setSelectedFile(e.target.files?.[0] || null)} />
          <div
            onClick={() => fileInputRef.current?.click()}
            style={{
              border: '2px dashed var(--border-color)',
              borderRadius: 'var(--radius-md)',
              padding: '1.5rem',
              textAlign: 'center',
              cursor: 'pointer',
              background: 'var(--bg-primary)',
              marginBottom: '1rem',
            }}
          >
            <Upload size={28} style={{ margin: '0 auto 0.5rem auto', color: 'var(--accent-primary)' }} />
            <div style={{ fontSize: '0.85rem', fontWeight: 600 }}>
              {selectedFile ? selectedFile.name : 'Upload Historical Drivers CSV/Excel'}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              Includes a date column, target column(s), and driver variables (weather, market sales, etc.)
            </div>
          </div>

          <div className="grid-2" style={{ marginBottom: '0.75rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '2px' }}>Date Column:</label>
              <input className="select-control" style={{ width: '100%' }} value={dateCol} onChange={(e) => setDateCol(e.target.value)} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '2px' }}>Period Type:</label>
              <select className="select-control" style={{ width: '100%' }} value={periodType} onChange={(e) => setPeriodType(e.target.value)}>
                <option value="Day">Day</option>
                <option value="Week">Week</option>
                <option value="Month">Month</option>
                <option value="Quarter">Quarter</option>
              </select>
            </div>
          </div>
          <div style={{ marginBottom: '0.75rem' }}>
            <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '2px' }}>Target Column(s), comma separated:</label>
            <input className="select-control" style={{ width: '100%' }} value={targetCols} onChange={(e) => setTargetCols(e.target.value)} />
          </div>
          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '2px' }}>Driver / Feature Column(s), comma separated (optional):</label>
            <input className="select-control" style={{ width: '100%' }} value={featureCols} onChange={(e) => setFeatureCols(e.target.value)} placeholder="e.g. temperature, market_index" />
          </div>

          {analysisError && <div style={{ color: 'var(--accent-danger)', fontSize: '0.8rem', marginBottom: '0.75rem' }}>{analysisError}</div>}

          <button className="btn btn-secondary" style={{ width: '100%' }} onClick={handleRunPredictor} disabled={running}>
            {running ? <Loader2 size={16} className="spin" /> : <Cpu size={16} />}
            {running ? 'Racing models...' : 'Race Models & Calculate Weights'}
          </button>
        </div>
      </div>

      {/* Seasonality Weights Plot & Model Results */}
      {analysisResult && (
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
            <div>
              <h3 style={{ fontSize: '1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <CheckCircle2 size={16} color="var(--accent-success)" /> Best Fitted Model: {analysisResult.winning_model} (R² = {analysisResult.r_squared.toFixed(3)})
              </h3>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Weights computed across {chartData.length} historical periods.</div>
            </div>

            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <input
                type="text"
                placeholder="New split name..."
                value={publishName}
                onChange={(e) => { setPublishName(e.target.value); setPublishSaved(false); }}
                className="select-control"
              />
              <button className="btn btn-primary" onClick={handlePublish} disabled={createSplit.isPending || !publishName.trim()}>
                {publishSaved ? <CheckCircle2 size={14} /> : <Save size={14} />} {publishSaved ? 'Published' : 'Publish as Global Split'}
              </button>
            </div>
          </div>

          <div style={{ height: '320px', width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="period_idx" stroke="var(--text-muted)" />
                <YAxis stroke="var(--text-muted)" />
                <Tooltip contentStyle={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)' }} />
                <Legend />
                <Line type="monotone" dataKey="Actual_Target" stroke="var(--text-muted)" strokeDasharray="4 4" />
                <Line type="monotone" dataKey="Predicted_Fit" stroke="var(--accent-primary)" strokeWidth={2} />
                <Line type="monotone" dataKey="CI_Upper" stroke="var(--accent-purple)" strokeWidth={1} dot={false} />
                <Line type="monotone" dataKey="CI_Lower" stroke="var(--accent-teal)" strokeWidth={1} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
};
