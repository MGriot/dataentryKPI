import React, { useEffect, useRef, useState } from 'react';
import { Layers, Folder, Plus, Trash2, Code, Shield, Save, Loader2, CheckCircle2, Gauge, History } from 'lucide-react';
import type { KpiNode, KpiDetailedSpec, Plant } from '../types';
import { DISTRIBUTION_PROFILE_OPTIONS, parseTargetLabels, targetLabel } from '../types';
import {
  useCreateKpiNode,
  useCreateKpiIndicator,
  useUpdateKpiSpec,
  useSoftDeleteKpi,
  useKpiVisibility,
  useUpdateKpiVisibility,
  useKpiDefinitionHistory,
  useKpiTargetHistory,
} from '../hooks';

interface KpiManagerWorkspaceProps {
  tree: KpiNode[];
  kpis: KpiDetailedSpec[];
  plants: Plant[];
}

export const KpiManagerWorkspace: React.FC<KpiManagerWorkspaceProps> = ({ tree, kpis, plants }) => {
  const [selectedKpiId, setSelectedKpiId] = useState<number | null>(kpis[0]?.id || null);
  const [newNodeName, setNewNodeName] = useState('');
  const [newKpiName, setNewKpiName] = useState('');
  const [selectedNodeId, setSelectedNodeId] = useState<number>(tree[0]?.id || 1);

  const createNode = useCreateKpiNode();
  const createKpi = useCreateKpiIndicator();
  const updateSpec = useUpdateKpiSpec();
  const softDelete = useSoftDeleteKpi();

  const selectedKpi = kpis.find((k) => k.id === selectedKpiId);
  const formulaTextareaRef = useRef<HTMLTextAreaElement>(null);

  const [form, setForm] = useState({
    description: '',
    unit_of_measure: '',
    calculation_type: 'Sum',
    direction: 'Higher is Better',
    formula_string: '',
    target_count: 1,
    visible: true,
    owner: '',
    target_granularity: 'Monthly',
    default_distribution_profile: '',
    time_filter_type: 'None',
    time_filter_value: '',
    warning_margin: 0.05,
    error_margin: 0.15,
    min_target: '',
    max_target: '',
  });
  const [specSaved, setSpecSaved] = useState(false);
  const [targetLabels, setTargetLabels] = useState<Record<string, string>>({});

  useEffect(() => {
    if (selectedKpi) {
      let threshold: any = {};
      try {
        threshold = selectedKpi.threshold_json ? JSON.parse(selectedKpi.threshold_json) : {};
      } catch {
        threshold = {};
      }
      setTargetLabels(parseTargetLabels(selectedKpi.target_labels));
      setForm({
        description: selectedKpi.description || '',
        unit_of_measure: selectedKpi.unit_of_measure || '',
        calculation_type: selectedKpi.calculation_type || 'Sum',
        direction: selectedKpi.direction || 'Higher is Better',
        formula_string: selectedKpi.formula_string || '',
        target_count: selectedKpi.target_count || 1,
        visible: selectedKpi.visible ?? true,
        owner: selectedKpi.owner || '',
        target_granularity: selectedKpi.target_granularity || 'Monthly',
        default_distribution_profile: selectedKpi.default_distribution_profile || '',
        time_filter_type: selectedKpi.time_filter_type || 'None',
        time_filter_value: selectedKpi.time_filter_value || '',
        warning_margin: threshold.warning_margin ?? 0.05,
        error_margin: threshold.error_margin ?? 0.15,
        min_target: threshold.min_target ?? '',
        max_target: threshold.max_target ?? '',
      });
      setSpecSaved(false);
    }
  }, [selectedKpi?.id]);

  const [showHistory, setShowHistory] = useState(false);
  const { data: definitionHistory = [] } = useKpiDefinitionHistory(showHistory ? selectedKpiId : null);
  const { data: targetHistory = [] } = useKpiTargetHistory(showHistory ? selectedKpiId : null);

  const { data: visibilityOverrides = [] } = useKpiVisibility(selectedKpiId);
  const updateVisibility = useUpdateKpiVisibility();
  const [visibilityState, setVisibilityState] = useState<Record<number, boolean>>({});
  const [visibilitySaved, setVisibilitySaved] = useState(false);

  useEffect(() => {
    const next: Record<number, boolean> = {};
    for (const p of plants) next[p.id] = true;
    for (const v of visibilityOverrides) next[v.plant_id as number] = v.is_enabled;
    setVisibilityState(next);
    setVisibilitySaved(false);
  }, [visibilityOverrides, selectedKpiId, plants.length]);

  const handleCreateNode = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNodeName.trim()) return;
    createNode.mutate({ name: newNodeName.trim(), parentId: selectedNodeId });
    setNewNodeName('');
  };

  const handleCreateKpi = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKpiName.trim()) return;
    createKpi.mutate({
      node_id: selectedNodeId,
      name: newKpiName.trim(),
      calculation_type: 'Sum',
      unit_of_measure: 'Units',
      direction: 'Higher is Better',
    } as any);
    setNewKpiName('');
  };

  const handleSaveSpec = () => {
    if (!selectedKpi) return;
    const threshold: Record<string, number> = {
      warning_margin: Number(form.warning_margin) || 0,
      error_margin: Number(form.error_margin) || 0,
    };
    if (form.direction === 'Range') {
      if (form.min_target !== '') threshold.min_target = Number(form.min_target);
      if (form.max_target !== '') threshold.max_target = Number(form.max_target);
    }

    updateSpec.mutate(
      {
        kpiId: selectedKpi.id,
        dataUpdates: {
          description: form.description,
          unit_of_measure: form.unit_of_measure,
          calculation_type: form.calculation_type,
          direction: form.direction,
          formula_string: form.formula_string || null,
          target_count: Number(form.target_count) || 1,
          visible: form.visible,
          owner: form.owner || null,
          target_granularity: form.target_granularity,
          default_distribution_profile: form.default_distribution_profile || null,
          time_filter_type: form.time_filter_type,
          time_filter_value: form.time_filter_type === 'None' ? null : form.time_filter_value,
          threshold_json: JSON.stringify(threshold),
          target_labels: JSON.stringify(targetLabels),
        },
      },
      { onSuccess: () => setSpecSaved(true) }
    );
  };

  const insertIntoFormula = (text: string) => {
    const el = formulaTextareaRef.current;
    const current = form.formula_string;
    const start = el?.selectionStart ?? current.length;
    const end = el?.selectionEnd ?? current.length;
    const next = current.slice(0, start) + text + current.slice(end);
    setForm({ ...form, formula_string: next });
    setSpecSaved(false);
    requestAnimationFrame(() => {
      if (!el) return;
      el.focus();
      const cursor = start + text.length;
      el.setSelectionRange(cursor, cursor);
    });
  };

  const insertFunction = (name: string) => {
    const el = formulaTextareaRef.current;
    const current = form.formula_string;
    const start = el?.selectionStart ?? current.length;
    const end = el?.selectionEnd ?? current.length;
    const inner = current.slice(start, end);
    const text = `${name}(${inner})`;
    const next = current.slice(0, start) + text + current.slice(end);
    setForm({ ...form, formula_string: next });
    setSpecSaved(false);
    requestAnimationFrame(() => {
      if (!el) return;
      el.focus();
      const cursor = inner ? start + text.length : start + name.length + 1;
      el.setSelectionRange(cursor, cursor);
    });
  };

  const handleSaveVisibility = () => {
    if (!selectedKpi) return;
    updateVisibility.mutate(
      {
        kpiId: selectedKpi.id,
        visibilityData: plants.map((p) => ({ plant_id: p.id, is_enabled: visibilityState[p.id] ?? true })),
      },
      { onSuccess: () => setVisibilitySaved(true) }
    );
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '1.25rem', height: '100%' }}>
      {/* Left Column: KPI Hierarchy Tree */}
      <div className="glass-card" style={{ padding: '1rem', display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600 }}>
            <Layers size={16} color="var(--accent-primary)" /> Hierarchy Tree
          </div>
        </div>

        <form onSubmit={handleCreateNode} style={{ marginBottom: '1rem', display: 'flex', gap: '0.5rem' }}>
          <input
            type="text"
            placeholder="New folder/group..."
            value={newNodeName}
            onChange={(e) => setNewNodeName(e.target.value)}
            style={{
              flex: 1,
              background: 'var(--bg-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-sm)',
              padding: '0.35rem 0.6rem',
              fontSize: '0.8rem',
              color: 'var(--text-primary)',
            }}
          />
          <button type="submit" className="btn btn-secondary" style={{ padding: '0.35rem 0.6rem' }}>
            <Plus size={14} /> Add
          </button>
        </form>

        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          {tree.map((node) => (
            <div key={node.id} style={{ marginBottom: '0.5rem' }}>
              <div
                onClick={() => setSelectedNodeId(node.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.4rem 0.6rem',
                  borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer',
                  background: selectedNodeId === node.id ? 'var(--bg-surface-hover)' : 'transparent',
                  color: selectedNodeId === node.id ? 'var(--accent-primary)' : 'var(--text-primary)',
                  fontWeight: 500,
                  fontSize: '0.85rem',
                }}
              >
                <Folder size={14} /> {node.name}
              </div>

              <div style={{ paddingLeft: '1.25rem', marginTop: '0.25rem', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                {kpis
                  .filter((k) => k.node_id === node.id)
                  .map((kpi) => (
                    <div
                      key={kpi.id}
                      onClick={() => setSelectedKpiId(kpi.id)}
                      style={{
                        padding: '0.3rem 0.5rem',
                        fontSize: '0.8rem',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        background: selectedKpiId === kpi.id ? 'var(--accent-primary)' : 'transparent',
                        color: selectedKpiId === kpi.id ? '#ffffff' : 'var(--text-secondary)',
                      }}
                    >
                      • {kpi.indicator_name}
                    </div>
                  ))}
              </div>
            </div>
          ))}
        </div>

        <form onSubmit={handleCreateKpi} style={{ marginTop: '1rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-color)' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>New Indicator in Folder #{selectedNodeId}:</div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <input
              type="text"
              placeholder="Indicator name..."
              value={newKpiName}
              onChange={(e) => setNewKpiName(e.target.value)}
              style={{
                flex: 1,
                background: 'var(--bg-primary)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-sm)',
                padding: '0.35rem 0.6rem',
                fontSize: '0.8rem',
                color: 'var(--text-primary)',
              }}
            />
            <button type="submit" className="btn btn-primary" style={{ padding: '0.35rem 0.6rem' }}>
              <Plus size={14} /> KPI
            </button>
          </div>
        </form>
      </div>

      {/* Right Column: KPI Specification Inspector */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        {selectedKpi ? (
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <div>
                <h2 style={{ fontSize: '1.2rem', fontWeight: 700 }}>{selectedKpi.indicator_name}</h2>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  Specification ID #{selectedKpi.id} • Indicator ID #{selectedKpi.indicator_id}
                </div>
              </div>

              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button className="btn btn-primary" onClick={handleSaveSpec} disabled={updateSpec.isPending}>
                  {updateSpec.isPending ? <Loader2 size={14} className="spin" /> : specSaved ? <CheckCircle2 size={14} /> : <Save size={14} />}
                  {specSaved ? 'Saved' : 'Save Spec'}
                </button>
                <button className="btn btn-danger" onClick={() => selectedKpi && softDelete.mutate(selectedKpi.id)}>
                  <Trash2 size={14} /> Soft Delete KPI
                </button>
              </div>
            </div>

            <div className="grid-2" style={{ marginBottom: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Description:</label>
                <input
                  type="text"
                  value={form.description}
                  onChange={(e) => { setForm({ ...form, description: e.target.value }); setSpecSaved(false); }}
                  className="select-control"
                  style={{ width: '100%' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Unit of Measure:</label>
                <input
                  type="text"
                  value={form.unit_of_measure}
                  onChange={(e) => { setForm({ ...form, unit_of_measure: e.target.value }); setSpecSaved(false); }}
                  className="select-control"
                  style={{ width: '100%' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Calculation Aggregation Type:</label>
                <select
                  className="select-control"
                  style={{ width: '100%' }}
                  value={form.calculation_type}
                  onChange={(e) => { setForm({ ...form, calculation_type: e.target.value }); setSpecSaved(false); }}
                >
                  <option value="Sum">Sum (Cumulative / Incremental)</option>
                  <option value="Incremental">Incremental</option>
                  <option value="Average">Average / Mean</option>
                  <option value="Last">Last Non-Null Value</option>
                  <option value="Min">Minimum</option>
                  <option value="Max">Maximum</option>
                  <option value="Count">Event Count</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Directional Goal:</label>
                <select
                  className="select-control"
                  style={{ width: '100%' }}
                  value={form.direction}
                  onChange={(e) => { setForm({ ...form, direction: e.target.value }); setSpecSaved(false); }}
                >
                  <option value="Higher is Better">Higher is Better (e.g. Yield)</option>
                  <option value="Lower is Better">Lower is Better (e.g. Scrap)</option>
                  <option value="Range">Range (e.g. Temperature)</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                  Number of Targets (Target Count):
                </label>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={form.target_count}
                  onChange={(e) => { setForm({ ...form, target_count: Number(e.target.value) }); setSpecSaved(false); }}
                  className="select-control"
                  style={{ width: '100%' }}
                />
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                  Controls how many target scenarios (Base, Stretch, ...) appear in Target Entry for this KPI.
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Target Granularity:</label>
                <select
                  className="select-control"
                  style={{ width: '100%' }}
                  value={form.target_granularity}
                  onChange={(e) => { setForm({ ...form, target_granularity: e.target.value }); setSpecSaved(false); }}
                >
                  <option value="Daily">Daily</option>
                  <option value="Weekly">Weekly</option>
                  <option value="Monthly">Monthly</option>
                  <option value="Quarterly">Quarterly</option>
                  <option value="Yearly">Yearly</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Default Distribution Profile:</label>
                <select
                  className="select-control"
                  style={{ width: '100%' }}
                  value={form.default_distribution_profile}
                  onChange={(e) => { setForm({ ...form, default_distribution_profile: e.target.value }); setSpecSaved(false); }}
                >
                  <option value="">Inherit / None</option>
                  {DISTRIBUTION_PROFILE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Owner:</label>
                <input
                  type="text"
                  value={form.owner}
                  onChange={(e) => { setForm({ ...form, owner: e.target.value }); setSpecSaved(false); }}
                  className="select-control"
                  style={{ width: '100%' }}
                  placeholder="Responsible person/team..."
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Time Filter:</label>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <select
                    className="select-control"
                    style={{ flex: 1 }}
                    value={form.time_filter_type}
                    onChange={(e) => { setForm({ ...form, time_filter_type: e.target.value }); setSpecSaved(false); }}
                  >
                    <option value="None">None</option>
                    <option value="rolling">Rolling window</option>
                  </select>
                  {form.time_filter_type === 'rolling' && (
                    <input
                      type="number"
                      placeholder="Days"
                      value={form.time_filter_value}
                      onChange={(e) => { setForm({ ...form, time_filter_value: e.target.value }); setSpecSaved(false); }}
                      className="select-control"
                      style={{ width: '90px' }}
                    />
                  )}
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'flex-end' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', cursor: 'pointer', paddingBottom: '0.4rem' }}>
                  <input
                    type="checkbox"
                    checked={form.visible}
                    onChange={(e) => { setForm({ ...form, visible: e.target.checked }); setSpecSaved(false); }}
                  />
                  Default Visible
                </label>
              </div>
            </div>

            <div style={{ background: 'var(--bg-primary)', padding: '1rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', marginBottom: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.75rem' }}>
                <Layers size={16} color="var(--accent-primary)" /> Target Scenario Names
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
                Names shown in Target Entry for each of this KPI's {form.target_count} target{Number(form.target_count) > 1 ? 's' : ''}. Leave blank to use the default.
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '0.75rem' }}>
                {Array.from({ length: Number(form.target_count) || 1 }, (_, i) => i + 1).map((tn) => (
                  <div key={tn}>
                    <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Target {tn}:</label>
                    <input
                      type="text"
                      value={targetLabels[String(tn)] || ''}
                      placeholder={targetLabel(tn)}
                      onChange={(e) => {
                        setTargetLabels({ ...targetLabels, [String(tn)]: e.target.value });
                        setSpecSaved(false);
                      }}
                      className="select-control"
                      style={{ width: '100%' }}
                    />
                  </div>
                ))}
              </div>
            </div>

            <div style={{ background: 'var(--bg-primary)', padding: '1rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', marginBottom: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.75rem', color: 'var(--accent-warning)' }}>
                <Gauge size={16} /> Performance Alert Thresholds
              </div>
              <div className="grid-3">
                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Warning Margin (0-1):</label>
                  <input
                    type="number"
                    step="0.01"
                    min={0}
                    max={1}
                    value={form.warning_margin}
                    onChange={(e) => { setForm({ ...form, warning_margin: Number(e.target.value) }); setSpecSaved(false); }}
                    className="select-control"
                    style={{ width: '100%' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Error Margin (0-1):</label>
                  <input
                    type="number"
                    step="0.01"
                    min={0}
                    max={1}
                    value={form.error_margin}
                    onChange={(e) => { setForm({ ...form, error_margin: Number(e.target.value) }); setSpecSaved(false); }}
                    className="select-control"
                    style={{ width: '100%' }}
                  />
                </div>
                {form.direction === 'Range' && (
                  <>
                    <div>
                      <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Min Target (Range):</label>
                      <input
                        type="number"
                        value={form.min_target}
                        onChange={(e) => { setForm({ ...form, min_target: e.target.value }); setSpecSaved(false); }}
                        className="select-control"
                        style={{ width: '100%' }}
                      />
                    </div>
                    <div>
                      <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Max Target (Range):</label>
                      <input
                        type="number"
                        value={form.max_target}
                        onChange={(e) => { setForm({ ...form, max_target: e.target.value }); setSpecSaved(false); }}
                        className="select-control"
                        style={{ width: '100%' }}
                      />
                    </div>
                  </>
                )}
              </div>
            </div>

            <div style={{ background: 'var(--bg-primary)', padding: '1rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', marginBottom: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.5rem', color: 'var(--accent-purple)' }}>
                <Code size={16} /> Formula Specification
              </div>

              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginBottom: '0.5rem', alignItems: 'center' }}>
                <select
                  className="select-control"
                  style={{ fontSize: '0.75rem', flex: '1 1 200px' }}
                  value=""
                  onChange={(e) => {
                    if (e.target.value) insertIntoFormula(`[${e.target.value}]`);
                    e.target.value = '';
                  }}
                >
                  <option value="">+ Insert KPI reference...</option>
                  {kpis
                    .filter((k) => k.id !== selectedKpi?.id)
                    .map((k) => (
                      <option key={k.id} value={k.id}>
                        {k.indicator_name} (#{k.id})
                      </option>
                    ))}
                </select>

                {['+', '-', '*', '/', '(', ')'].map((sym) => (
                  <button
                    key={sym}
                    type="button"
                    className="btn btn-secondary"
                    style={{ padding: '0.3rem 0.6rem', fontFamily: 'monospace', fontSize: '0.85rem' }}
                    onClick={() => insertIntoFormula(sym)}
                  >
                    {sym}
                  </button>
                ))}

                {['abs', 'min', 'max', 'round'].map((fn) => (
                  <button
                    key={fn}
                    type="button"
                    className="btn btn-secondary"
                    style={{ padding: '0.3rem 0.6rem', fontFamily: 'monospace', fontSize: '0.8rem' }}
                    onClick={() => insertFunction(fn)}
                  >
                    {fn}()
                  </button>
                ))}
              </div>

              <textarea
                ref={formulaTextareaRef}
                value={form.formula_string}
                onChange={(e) => { setForm({ ...form, formula_string: e.target.value }); setSpecSaved(false); }}
                placeholder="Formula expression, e.g. [12] + [7] * 0.5 -- use the KPI picker above to insert [id] references"
                rows={3}
                style={{
                  width: '100%',
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-sm)',
                  color: '#60a5fa',
                  fontFamily: 'monospace',
                  padding: '0.5rem',
                  fontSize: '0.85rem',
                }}
              />
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                <code>[id]</code> references another KPI's value by its Specification ID (shown in the picker). Supported functions: <code>abs</code>, <code>min</code>, <code>max</code>, <code>round</code>.
              </div>
            </div>

            <div style={{ background: 'var(--bg-primary)', padding: '1rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, fontSize: '0.85rem' }}>
                  <Shield size={16} color="var(--accent-primary)" /> Facility Enablement Matrix
                </div>
                <button className="btn btn-secondary" style={{ fontSize: '0.75rem' }} onClick={handleSaveVisibility} disabled={updateVisibility.isPending}>
                  {updateVisibility.isPending ? <Loader2 size={12} className="spin" /> : visibilitySaved ? <CheckCircle2 size={12} /> : <Save size={12} />}
                  {visibilitySaved ? 'Saved' : 'Save Visibility'}
                </button>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat( auto-fill, minmax(180px, 1fr) )', gap: '0.75rem' }}>
                {plants.map((plant) => (
                  <label key={plant.id} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={visibilityState[plant.id] ?? true}
                      onChange={(e) => {
                        setVisibilityState({ ...visibilityState, [plant.id]: e.target.checked });
                        setVisibilitySaved(false);
                      }}
                    />
                    <span style={{ color: plant.color }}>🏭 {plant.name}</span>
                  </label>
                ))}
              </div>
            </div>

            <div style={{ background: 'var(--bg-primary)', padding: '1rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', marginTop: '1rem' }}>
              <div
                onClick={() => setShowHistory((v) => !v)}
                style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, fontSize: '0.85rem', cursor: 'pointer' }}
              >
                <History size={16} color="var(--accent-teal)" /> Audit History {showHistory ? '(hide)' : '(show who changed what)'}
              </div>

              {showHistory && (
                <div style={{ marginTop: '0.75rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  <div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>Target value edits:</div>
                    {targetHistory.length === 0 ? (
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>No target edits recorded yet.</div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem', maxHeight: '160px', overflowY: 'auto' }}>
                        {targetHistory.map((h) => (
                          <div key={h.id} style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', gap: '0.5rem' }}>
                            <span style={{ color: 'var(--text-muted)' }}>{new Date(h.changed_at).toLocaleString()}</span>
                            <strong>{h.changed_by}</strong>
                            <span>set Target {h.target_number} (plant #{h.plant_id}, {h.period_start.slice(0, 4)}) to <strong>{h.new_value ?? 'n/a'}</strong> (was {h.old_value ?? 'n/a'})</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>Spec definition changes:</div>
                    {definitionHistory.length === 0 ? (
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>No definition changes recorded yet.</div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem', maxHeight: '160px', overflowY: 'auto' }}>
                        {definitionHistory.map((h) => (
                          <div key={h.id} style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', gap: '0.5rem' }}>
                            <span style={{ color: 'var(--text-muted)' }}>{new Date(h.changed_at).toLocaleString()}</span>
                            <strong>{h.changed_by}</strong>
                            <span>{h.change_type}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="card" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>
            <Layers size={36} style={{ margin: '0 auto 1rem auto', opacity: 0.5 }} />
            <h3>Select a KPI indicator to inspect specification</h3>
          </div>
        )}
      </div>
    </div>
  );
};
