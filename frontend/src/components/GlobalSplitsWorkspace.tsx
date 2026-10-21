import React, { useMemo, useRef, useState } from 'react';
import { GitFork, Upload, Cpu, Save, Plus, CheckCircle2, Trash2, Loader2, Pencil, X } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { DISTRIBUTION_PROFILE_OPTIONS } from '../types';
import type { GlobalSplit, MultivariateAnalysisResult } from '../types';
import { useCreateGlobalSplit, useCurveWeightSuggestions, useDeleteGlobalSplit, useGlobalSplits, useUpdateGlobalSplit, useYearOptions } from '../hooks';
import { api, errorMessage } from '../services/api';
import { normalizeWeightKeys, parseWeights, periodKeysFor, weightsTotal } from '../utils/splits';

const PROFILE_LABEL = Object.fromEntries(DISTRIBUTION_PROFILE_OPTIONS.map((o) => [o.value, o.label]));
const NO_SPLITS: GlobalSplit[] = [];

interface GlobalSplitsWorkspaceProps {
  selectedYear: number;
}

export const GlobalSplitsWorkspace: React.FC<GlobalSplitsWorkspaceProps> = ({ selectedYear }) => {
  const { data: splits = NO_SPLITS, isLoading } = useGlobalSplits(selectedYear);
  const createSplit = useCreateGlobalSplit();
  const updateSplit = useUpdateGlobalSplit();
  const deleteSplit = useDeleteGlobalSplit();
  const yearExtras = useMemo(() => [selectedYear], [selectedYear]);
  const yearOptions = useYearOptions(yearExtras);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [splitName, setSplitName] = useState('');
  const [selectedLogic, setSelectedLogic] = useState('Month');
  const [selectedProfile, setSelectedProfile] = useState('even_distribution');
  // null = untouched: show the selected curve's suggested weights.
  const [editedWeights, setEditedWeights] = useState<Record<string, string> | null>(null);
  const [createSaved, setCreateSaved] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [appliesToAllYears, setAppliesToAllYears] = useState(false);
  const [selectedYears, setSelectedYears] = useState<number[] | null>(null);
  const yearsShown = selectedYears ?? [selectedYear];

  const periodKeys = periodKeysFor(selectedLogic, selectedYear);
  const { data: curveSuggestions } = useCurveWeightSuggestions(selectedProfile, selectedLogic);
  const weights: Record<string, string> = useMemo(() => {
    if (editedWeights) return editedWeights;
    return Object.fromEntries(Object.entries(curveSuggestions || {}).map(([k, v]) => [k, String(v)]));
  }, [editedWeights, curveSuggestions]);
  const total = weightsTotal(weights);

  const touch = () => {
    setCreateSaved(false);
    setFormError(null);
  };

  const toggleYear = (y: number) => {
    setSelectedYears(yearsShown.includes(y) ? yearsShown.filter((x) => x !== y) : [...yearsShown, y].sort());
    touch();
  };

  const resetForm = () => {
    setEditingId(null);
    setSplitName('');
    setSelectedLogic('Month');
    setSelectedProfile('even_distribution');
    setEditedWeights(null);
    setAppliesToAllYears(false);
    setSelectedYears(null);
    setFormError(null);
  };

  const handleEditSplit = (s: GlobalSplit) => {
    setEditingId(s.id);
    setSplitName(s.name);
    setSelectedLogic(s.repartition_logic);
    setSelectedProfile(s.distribution_profile);
    setEditedWeights(
      Object.fromEntries(Object.entries(normalizeWeightKeys(s.repartition_logic, s.repartition_values || {})).map(([k, v]) => [k, String(v)]))
    );
    const hasYears = !!s.years && s.years.length > 0;
    setAppliesToAllYears(!hasYears);
    setSelectedYears(hasYears ? s.years! : null);
    touch();
  };

  const handleDelete = (s: GlobalSplit) => {
    if (!window.confirm(`Delete split "${s.name}"? KPIs using it fall back to an even split and are recalculated.`)) return;
    deleteSplit.mutate(s.id, { onSuccess: () => { if (editingId === s.id) resetForm(); } });
  };

  const handleSave = () => {
    if (!splitName.trim()) return setFormError('Give the template a name.');
    if (!appliesToAllYears && yearsShown.length === 0) return setFormError('Pick at least one year, or "All years".');
    const parsed = parseWeights(weights, periodKeys);
    if (typeof parsed === 'string') return setFormError(parsed);
    const payload = {
      name: splitName.trim(),
      repartition_logic: selectedLogic,
      repartition_values: parsed,
      distribution_profile: selectedProfile,
      profile_params: {},
      years: appliesToAllYears ? [] : yearsShown,
    };
    if (editingId !== null) {
      updateSplit.mutate({ splitId: editingId, payload }, { onSuccess: () => setCreateSaved(true) });
    } else {
      createSplit.mutate(payload, { onSuccess: () => { resetForm(); setCreateSaved(true); } });
    }
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

  const splitList = (raw: string) => raw.split(',').map((c) => c.trim()).filter(Boolean);

  const handleRunPredictor = async () => {
    if (!selectedFile) return setAnalysisError('Choose a CSV or Excel file first.');
    if (splitList(targetCols).length === 0) return setAnalysisError('Enter at least one target column.');
    setRunning(true);
    setAnalysisError(null);
    setAnalysisResult(null);
    setPublishSaved(false);
    try {
      setAnalysisResult(await api.runMultivariateAnalysis(selectedFile, splitList(targetCols), splitList(featureCols), dateCol.trim(), periodType));
    } catch (e) {
      setAnalysisError(errorMessage(e));
    } finally {
      setRunning(false);
    }
  };

  const handlePublish = () => {
    if (!analysisResult || !publishName.trim()) return;
    createSplit.mutate(
      {
        name: publishName.trim(),
        repartition_logic: analysisResult.period_type,
        repartition_values: analysisResult.weights,
        distribution_profile: 'even_distribution',
        profile_params: { source: 'multivariate_ml', winning_model: analysisResult.winning_model, r_squared: analysisResult.r_squared },
        years: [selectedYear],
      },
      { onSuccess: () => setPublishSaved(true) }
    );
  };

  const saving = createSplit.isPending || updateSplit.isPending;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      <div className="glass-card" style={{ padding: '1.25rem' }}>
        <h2 className="page-title">
          <GitFork color="var(--accent-primary)" aria-hidden="true" /> Global Split Templates & ML Seasonality Predictor
        </h2>
        <p className="page-subtitle">
          Reusable seasonal weight curves for KPIs (assign them in KPI Explorer), or derive weights from historical drivers.
        </p>
      </div>

      <section className="card" aria-labelledby="splits-list-title">
        <h3 id="splits-list-title" style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>Templates available in {selectedYear}</h3>
        {isLoading ? (
          <div className="field-hint">Loading...</div>
        ) : splits.length === 0 ? (
          <div className="field-hint">No templates for this year yet.</div>
        ) : (
          <ul style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {splits.map((s) => (
              <li key={s.id} className="list-row">
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
                  <strong>{s.name}</strong>
                  <span className="badge badge-blue">{s.repartition_logic}</span>
                  <span className="badge badge-purple">{PROFILE_LABEL[s.distribution_profile] || s.distribution_profile}</span>
                  {!s.years || s.years.length === 0 ? <span className="badge badge-green">All years</span> : <span className="badge badge-green">{s.years.join(', ')}</span>}
                </div>
                <div style={{ display: 'flex', gap: '0.4rem' }}>
                  <button type="button" className="btn btn-secondary" style={{ fontSize: '0.75rem' }} onClick={() => handleEditSplit(s)}>
                    <Pencil size={12} aria-hidden="true" /> Edit<span className="sr-only"> {s.name}</span>
                  </button>
                  <button type="button" className="btn btn-danger" style={{ fontSize: '0.75rem' }} onClick={() => handleDelete(s)} disabled={deleteSplit.isPending}>
                    <Trash2 size={12} aria-hidden="true" /> Delete<span className="sr-only"> {s.name}</span>
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="grid-2">
        <section className="card" aria-labelledby="split-form-title">
          <h3 id="split-form-title" style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              {editingId !== null ? <Pencil size={16} color="var(--accent-primary)" aria-hidden="true" /> : <Plus size={16} color="var(--accent-primary)" aria-hidden="true" />}
              {editingId !== null ? `Editing "${splitName}"` : 'New split template'}
            </span>
            {editingId !== null && (
              <button type="button" className="btn btn-secondary" style={{ fontSize: '0.75rem' }} onClick={resetForm}>
                <X size={12} aria-hidden="true" /> Cancel
              </button>
            )}
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            <div>
              <label htmlFor="split-name" className="field-label">Template name</label>
              <input id="split-name" type="text" placeholder="e.g. Summer shutdown 2026" value={splitName} onChange={(e) => { setSplitName(e.target.value); touch(); }} className="select-control" style={{ width: '100%' }} />
            </div>

            <fieldset>
              <legend className="field-label">Applies to years</legend>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem', cursor: 'pointer', marginBottom: '0.5rem' }}>
                <input type="checkbox" checked={appliesToAllYears} onChange={(e) => { setAppliesToAllYears(e.target.checked); touch(); }} />
                All years
              </label>
              {!appliesToAllYears && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                  {yearOptions.map((y) => (
                    <button
                      key={y}
                      type="button"
                      aria-pressed={yearsShown.includes(y)}
                      onClick={() => toggleYear(y)}
                      className={yearsShown.includes(y) ? 'btn btn-primary' : 'btn btn-secondary'}
                      style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
                    >
                      {y}
                    </button>
                  ))}
                </div>
              )}
            </fieldset>

            <div className="grid-2">
              <div>
                <label htmlFor="split-logic" className="field-label">Weights per</label>
                <select id="split-logic" className="select-control" style={{ width: '100%' }} value={selectedLogic} onChange={(e) => { setSelectedLogic(e.target.value); setEditedWeights(null); touch(); }}>
                  <option value="Month">Month</option>
                  <option value="Quarter">Quarter</option>
                  <option value="Week">ISO week</option>
                </select>
              </div>
              <div>
                <label htmlFor="split-profile" className="field-label">Day shape within each period</label>
                <select id="split-profile" className="select-control" style={{ width: '100%' }} value={selectedProfile} onChange={(e) => { setSelectedProfile(e.target.value); touch(); }}>
                  {DISTRIBUTION_PROFILE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
            </div>

            <fieldset>
              <legend className="field-label">
                Weights (% of the annual target){selectedLogic === 'Week' ? ' -- week numbers apply to every year' : ''}
              </legend>
              <div className={`weights-grid weights-${selectedLogic.toLowerCase()}`}>
                {periodKeys.map((k) => (
                  <div key={k}>
                    <label htmlFor={`w-${k}`} className="weight-label">{selectedLogic === 'Month' ? k.slice(0, 3) : k}</label>
                    <input
                      id={`w-${k}`}
                      type="number"
                      min={0}
                      step="any"
                      placeholder="0"
                      value={weights[k] ?? ''}
                      onChange={(e) => { setEditedWeights({ ...weights, [k]: e.target.value }); touch(); }}
                      className="weight-input"
                    />
                  </div>
                ))}
              </div>
              <div className="field-hint" style={{ marginTop: '0.4rem', color: Math.abs(total - 100) > 0.5 ? 'var(--accent-warning)' : undefined }} aria-live="polite">
                Total: {total.toFixed(2)}%{Math.abs(total - 100) > 0.5 ? ' -- weights will be scaled to 100%' : ''}
              </div>
            </fieldset>

            {formError && <p role="alert" style={{ color: 'var(--accent-danger)', fontSize: '0.8rem' }}>{formError}</p>}

            <button type="button" className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? <Loader2 size={16} className="spin" aria-hidden="true" /> : createSaved ? <CheckCircle2 size={16} aria-hidden="true" /> : <Save size={16} aria-hidden="true" />}
              {createSaved ? 'Saved' : editingId !== null ? 'Save changes' : 'Save template'}
            </button>
          </div>
        </section>

        <section className="card" aria-labelledby="ml-title">
          <h3 id="ml-title" style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Cpu size={16} color="var(--accent-purple)" aria-hidden="true" /> ML Seasonality Predictor (OLS / Ridge / Random Forest)
          </h3>

          <input ref={fileInputRef} id="ml-file" type="file" accept=".csv,.xlsx,.xls" className="sr-only" onChange={(e) => setSelectedFile(e.target.files?.[0] || null)} />
          <button type="button" className="upload-zone" onClick={() => fileInputRef.current?.click()}>
            <Upload size={28} color="var(--accent-primary)" aria-hidden="true" />
            <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>{selectedFile ? selectedFile.name : 'Choose a historical data file (CSV / Excel)'}</span>
            <span className="field-hint">A date column, target column(s), and optional driver columns (weather, market index, ...)</span>
          </button>

          <div className="grid-2" style={{ marginBottom: '0.75rem' }}>
            <div>
              <label htmlFor="ml-date" className="field-label">Date column</label>
              <input id="ml-date" className="select-control" style={{ width: '100%' }} value={dateCol} onChange={(e) => setDateCol(e.target.value)} />
            </div>
            <div>
              <label htmlFor="ml-period" className="field-label">Period</label>
              <select id="ml-period" className="select-control" style={{ width: '100%' }} value={periodType} onChange={(e) => setPeriodType(e.target.value)}>
                <option value="Month">Month</option>
                <option value="Quarter">Quarter</option>
                <option value="Week">ISO week</option>
              </select>
            </div>
          </div>
          <div style={{ marginBottom: '0.75rem' }}>
            <label htmlFor="ml-targets" className="field-label">Target column(s), comma separated</label>
            <input id="ml-targets" className="select-control" style={{ width: '100%' }} value={targetCols} onChange={(e) => setTargetCols(e.target.value)} />
          </div>
          <div style={{ marginBottom: '1rem' }}>
            <label htmlFor="ml-features" className="field-label">Driver column(s), comma separated (optional)</label>
            <input id="ml-features" className="select-control" style={{ width: '100%' }} value={featureCols} onChange={(e) => setFeatureCols(e.target.value)} placeholder="e.g. temperature, market_index" />
          </div>

          {analysisError && <p role="alert" style={{ color: 'var(--accent-danger)', fontSize: '0.8rem', marginBottom: '0.75rem' }}>{analysisError}</p>}

          <button type="button" className="btn btn-secondary" style={{ width: '100%' }} onClick={handleRunPredictor} disabled={running}>
            {running ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Cpu size={16} aria-hidden="true" />}
            {running ? 'Racing models...' : 'Race models & calculate weights'}
          </button>
        </section>
      </div>

      {analysisResult && (
        <section className="card" aria-labelledby="ml-result-title">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
            <div>
              <h3 id="ml-result-title" style={{ fontSize: '1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <CheckCircle2 size={16} color="var(--accent-success)" aria-hidden="true" /> Best model: {analysisResult.winning_model} (R² = {analysisResult.r_squared.toFixed(3)})
              </h3>
              <div className="field-hint">Weights for {analysisResult.plot_data.length} {analysisResult.period_type.toLowerCase()} periods.</div>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <label htmlFor="ml-publish-name" className="sr-only">New template name</label>
              <input id="ml-publish-name" type="text" placeholder="New template name..." value={publishName} onChange={(e) => { setPublishName(e.target.value); setPublishSaved(false); }} className="select-control" />
              <button type="button" className="btn btn-primary" onClick={handlePublish} disabled={createSplit.isPending || !publishName.trim()}>
                {publishSaved ? <CheckCircle2 size={14} aria-hidden="true" /> : <Save size={14} aria-hidden="true" />} {publishSaved ? `Published for ${selectedYear}` : `Publish as template for ${selectedYear}`}
              </button>
            </div>
          </div>

          <div style={{ height: '320px', width: '100%' }} role="img" aria-label="Actual vs predicted seasonal profile with confidence band">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={analysisResult.plot_data}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="period" stroke="var(--text-muted)" />
                <YAxis stroke="var(--text-muted)" />
                <Tooltip
                  contentStyle={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)' }}
                  formatter={(value) => (typeof value === 'number' ? value.toFixed(3) : value)}
                />
                <Legend />
                <Line type="monotone" dataKey="Actual_Target" name="Historical (share of mean)" stroke="var(--text-secondary)" strokeDasharray="4 4" />
                <Line type="monotone" dataKey="Predicted_Fit" name="Model fit" stroke="var(--accent-primary)" strokeWidth={2} />
                <Line type="monotone" dataKey="CI_Upper" name="95th percentile" stroke="var(--accent-purple)" strokeWidth={1} dot={false} />
                <Line type="monotone" dataKey="CI_Lower" name="5th percentile" stroke="var(--accent-teal)" strokeWidth={1} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}
    </div>
  );
};
