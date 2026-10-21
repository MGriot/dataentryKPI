import React, { useRef, useState } from 'react';
import { Layers, Folder, Plus, Trash2, Code, Shield, Save, Loader2, CheckCircle2, Gauge, History, SplitSquareHorizontal } from 'lucide-react';
import type { GlobalSplit, KpiNode, KpiDetailedSpec, Plant, VisibilityEntry } from '../types';
import { CALC_TYPE_OPTIONS, parseTargetLabels, targetLabel } from '../types';
import { buildSpecUpdate, initialForm } from '../utils/forms';
import { describeDefinitionChange } from '../utils/history';
import type { SpecForm } from '../utils/forms';
import {
  useCreateKpiNode,
  useCreateKpiIndicator,
  useUpdateKpiSpec,
  useSoftDeleteKpi,
  useKpiVisibility,
  useUpdateKpiVisibility,
  useKpiDefinitionHistory,
  useKpiTargetHistory,
  useUnitsOfMeasure,
  useCreateUnitOfMeasure,
  useGlobalSplits,
  useKpiGlobalSplits,
  useSetKpiGlobalSplit,
} from '../hooks';

// Stable empty defaults: `data = []` would create a new array every render.
const NO_SPLITS: GlobalSplit[] = [];
const NO_OVERRIDES: VisibilityEntry[] = [];

interface KpiManagerWorkspaceProps {
  tree: KpiNode[];
  kpis: KpiDetailedSpec[];
  plants: Plant[];
}

interface KpiTreeNodeProps {
  node: KpiNode;
  depth: number;
  kpis: KpiDetailedSpec[];
  selectedNodeId: number | null;
  selectedKpiId: number | null;
  onSelectNode: (id: number) => void;
  onSelectKpi: (id: number) => void;
}

const KpiTreeNode: React.FC<KpiTreeNodeProps> = ({ node, depth, kpis, selectedNodeId, selectedKpiId, onSelectNode, onSelectKpi }) => {
  const nodeKpis = kpis.filter((k) => k.node_id === node.id);
  const nodeSelected = selectedNodeId === node.id;
  return (
    <li style={{ listStyle: 'none', marginBottom: '0.35rem' }}>
      <button
        type="button"
        className={`tree-item tree-folder ${nodeSelected ? 'selected' : ''}`}
        aria-pressed={nodeSelected}
        onClick={() => onSelectNode(node.id)}
        style={{ marginLeft: `${depth * 0.9}rem` }}
      >
        <Folder size={14} aria-hidden="true" /> {node.name}
      </button>

      {nodeKpis.length > 0 && (
        <ul style={{ paddingLeft: `${1.25 + depth * 0.9}rem`, marginTop: '0.25rem', display: 'flex', flexDirection: 'column', gap: '2px' }}>
          {nodeKpis.map((kpi) => (
            <li key={kpi.id} style={{ listStyle: 'none' }}>
              <button
                type="button"
                className={`tree-item tree-kpi ${selectedKpiId === kpi.id ? 'selected' : ''}`}
                aria-current={selectedKpiId === kpi.id ? 'true' : undefined}
                onClick={() => onSelectKpi(kpi.id)}
              >
                • {kpi.indicator_name}
              </button>
            </li>
          ))}
        </ul>
      )}

      {(node.children || []).length > 0 && (
        <ul>
          {(node.children || []).map((child) => (
            <KpiTreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
              kpis={kpis}
              selectedNodeId={selectedNodeId}
              selectedKpiId={selectedKpiId}
              onSelectNode={onSelectNode}
              onSelectKpi={onSelectKpi}
            />
          ))}
        </ul>
      )}
    </li>
  );
};

const KpiInspector: React.FC<{ kpi: KpiDetailedSpec; kpis: KpiDetailedSpec[]; plants: Plant[]; onDeleted: () => void }> = ({ kpi, kpis, plants, onDeleted }) => {
  const updateSpec = useUpdateKpiSpec();
  const softDelete = useSoftDeleteKpi();
  const formulaTextareaRef = useRef<HTMLTextAreaElement>(null);

  // Keyed by KPI id in the parent, so the form initializes once per selected KPI and refetches
  // never overwrite unsaved edits.
  const [form, setForm] = useState<SpecForm>(() => initialForm(kpi));
  const [targetLabels, setTargetLabels] = useState<Record<string, string>>(() => parseTargetLabels(kpi.target_labels));
  const [specSaved, setSpecSaved] = useState(false);
  const [specError, setSpecError] = useState<string | null>(null);

  const edit = (patch: Partial<SpecForm>) => {
    setForm((f) => ({ ...f, ...patch }));
    setSpecSaved(false);
    setSpecError(null);
  };

  const { data: unitsOfMeasure = [] } = useUnitsOfMeasure();
  const createUnit = useCreateUnitOfMeasure();
  const [newUnitName, setNewUnitName] = useState('');
  const [addingUnit, setAddingUnit] = useState(false);

  const { data: allGlobalSplits = NO_SPLITS } = useGlobalSplits();
  const { data: assignedSplits = NO_SPLITS, isSuccess: splitsLoaded } = useKpiGlobalSplits(kpi.id);
  const setKpiGlobalSplit = useSetKpiGlobalSplit();
  const [pendingSplitId, setPendingSplitId] = useState<number | null | undefined>(undefined);
  const [splitSaved, setSplitSaved] = useState(false);
  const shownSplitId = pendingSplitId !== undefined ? pendingSplitId : (assignedSplits[0]?.id ?? null);

  const [showHistory, setShowHistory] = useState(false);
  const { data: definitionHistory = [] } = useKpiDefinitionHistory(showHistory ? kpi.id : null);
  const { data: targetHistory = [] } = useKpiTargetHistory(showHistory ? kpi.id : null);
  const savedLabels = parseTargetLabels(kpi.target_labels);
  const plantName = (plantId: number) => plants.find((p) => p.id === plantId)?.name ?? `plant #${plantId}`;

  const { data: visibilityOverrides = NO_OVERRIDES } = useKpiVisibility(kpi.id);
  const updateVisibility = useUpdateKpiVisibility();
  const [pendingVisibility, setPendingVisibility] = useState<Record<number, boolean>>({});
  const [visibilitySaved, setVisibilitySaved] = useState(false);
  const isEnabledFor = (plantId: number) =>
    pendingVisibility[plantId] ?? visibilityOverrides.find((v) => v.plant_id === plantId)?.is_enabled ?? true;

  const handleSaveSpec = () => {
    const update = buildSpecUpdate(form, targetLabels);
    if (typeof update === 'string') {
      setSpecError(update);
      return;
    }
    updateSpec.mutate({ kpiId: kpi.id, dataUpdates: update }, { onSuccess: () => setSpecSaved(true) });
  };

  const handleDelete = () => {
    if (!window.confirm(`Delete "${kpi.indicator_name}"? It disappears everywhere; its targets and history are kept.`)) return;
    softDelete.mutate(kpi.id, { onSuccess: onDeleted });
  };

  const insertAtCursor = (text: string, cursorOffset = text.length) => {
    const el = formulaTextareaRef.current;
    const current = form.formula_string;
    const start = el?.selectionStart ?? current.length;
    const end = el?.selectionEnd ?? current.length;
    edit({ formula_string: current.slice(0, start) + text + current.slice(end) });
    requestAnimationFrame(() => {
      if (!el) return;
      el.focus();
      el.setSelectionRange(start + cursorOffset, start + cursorOffset);
    });
  };

  const insertFunction = (name: string) => {
    const el = formulaTextareaRef.current;
    const inner = el ? form.formula_string.slice(el.selectionStart, el.selectionEnd) : '';
    const text = `${name}(${inner})`;
    insertAtCursor(text, inner ? text.length : name.length + 1);
  };

  const handleAddUnit = () => {
    if (!newUnitName.trim()) return;
    createUnit.mutate(newUnitName.trim(), {
      onSuccess: (unit) => {
        edit({ unit_of_measure: unit.name });
        setNewUnitName('');
        setAddingUnit(false);
      },
    });
  };

  const handleSaveSplit = () => {
    setKpiGlobalSplit.mutate(
      { kpiId: kpi.id, globalSplitId: shownSplitId },
      { onSuccess: () => { setSplitSaved(true); setPendingSplitId(undefined); } }
    );
  };

  const handleSaveVisibility = () => {
    updateVisibility.mutate(
      { kpiId: kpi.id, visibilityData: plants.map((p) => ({ plant_id: p.id, is_enabled: isEnabledFor(p.id) })) },
      { onSuccess: () => { setVisibilitySaved(true); setPendingVisibility({}); } }
    );
  };

  const id = (field: string) => `kpi-${kpi.id}-${field}`;
  const targetCountNum = Math.min(Math.max(Number(form.target_count) || 1, 1), 10);

  return (
    <div className="card">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', gap: '1rem', flexWrap: 'wrap' }}>
        <div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: 700 }}>{kpi.indicator_name}</h2>
          <div className="field-hint">
            Specification ID #{kpi.id} • Indicator ID #{kpi.indicator_id}
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button type="button" className="btn btn-primary" onClick={handleSaveSpec} disabled={updateSpec.isPending}>
            {updateSpec.isPending ? <Loader2 size={14} className="spin" aria-hidden="true" /> : specSaved ? <CheckCircle2 size={14} aria-hidden="true" /> : <Save size={14} aria-hidden="true" />}
            {specSaved ? 'Saved' : 'Save Spec'}
          </button>
          <button type="button" className="btn btn-danger" onClick={handleDelete} disabled={softDelete.isPending}>
            <Trash2 size={14} aria-hidden="true" /> Delete KPI
          </button>
        </div>
      </div>
      {specError && (
        <p role="alert" style={{ color: 'var(--accent-danger)', fontSize: '0.8rem', marginBottom: '0.75rem' }}>
          {specError}
        </p>
      )}

      <div className="grid-2" style={{ marginBottom: '1rem' }}>
        <div>
          <label htmlFor={id('description')} className="field-label">Description</label>
          <input id={id('description')} type="text" value={form.description} onChange={(e) => edit({ description: e.target.value })} className="select-control" style={{ width: '100%' }} />
        </div>

        <div>
          <label htmlFor={addingUnit ? id('new-unit') : id('unit')} className="field-label">Unit of measure</label>
          {!addingUnit ? (
            <div style={{ display: 'flex', gap: '0.4rem' }}>
              <select id={id('unit')} className="select-control" style={{ flex: 1 }} value={form.unit_of_measure} onChange={(e) => edit({ unit_of_measure: e.target.value })}>
                <option value="">No unit</option>
                {unitsOfMeasure.map((u) => (
                  <option key={u.id} value={u.name}>{u.name}</option>
                ))}
                {form.unit_of_measure && !unitsOfMeasure.some((u) => u.name === form.unit_of_measure) && (
                  <option value={form.unit_of_measure}>{form.unit_of_measure}</option>
                )}
              </select>
              <button type="button" className="btn btn-secondary" style={{ whiteSpace: 'nowrap' }} onClick={() => setAddingUnit(true)}>
                <Plus size={14} aria-hidden="true" /> New unit
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', gap: '0.4rem' }}>
              <input
                id={id('new-unit')}
                type="text"
                autoFocus
                placeholder="e.g. Metric Tons"
                value={newUnitName}
                onChange={(e) => setNewUnitName(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleAddUnit(); } }}
                className="select-control"
                style={{ flex: 1 }}
              />
              <button type="button" className="btn btn-primary" onClick={handleAddUnit} disabled={createUnit.isPending} aria-label="Add unit">
                {createUnit.isPending ? <Loader2 size={14} className="spin" aria-hidden="true" /> : <CheckCircle2 size={14} aria-hidden="true" />}
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => { setAddingUnit(false); setNewUnitName(''); }}>
                Cancel
              </button>
            </div>
          )}
        </div>

        <div>
          <label htmlFor={id('calc')} className="field-label">Aggregation type</label>
          <select id={id('calc')} className="select-control" style={{ width: '100%' }} value={form.calculation_type} onChange={(e) => edit({ calculation_type: e.target.value })}>
            {CALC_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor={id('direction')} className="field-label">Directional goal</label>
          <select id={id('direction')} className="select-control" style={{ width: '100%' }} value={form.direction} onChange={(e) => edit({ direction: e.target.value })}>
            <option value="Higher is Better">Higher is Better (e.g. Yield)</option>
            <option value="Lower is Better">Lower is Better (e.g. Scrap)</option>
            <option value="Range">Range (e.g. Temperature)</option>
          </select>
        </div>

        <div>
          <label htmlFor={id('target-count')} className="field-label">Number of targets</label>
          <input
            id={id('target-count')}
            type="number"
            min={1}
            max={10}
            step={1}
            value={form.target_count}
            onChange={(e) => edit({ target_count: e.target.value })}
            className="select-control"
            style={{ width: '100%' }}
            aria-describedby={id('target-count-hint')}
          />
          <div id={id('target-count-hint')} className="field-hint">How many target scenarios (Base, Stretch, ...) Target Entry shows for this KPI.</div>
        </div>

        <div>
          <label htmlFor={id('granularity')} className="field-label">Target granularity (informational)</label>
          <select id={id('granularity')} className="select-control" style={{ width: '100%' }} value={form.target_granularity} onChange={(e) => edit({ target_granularity: e.target.value })}>
            {['Daily', 'Weekly', 'Monthly', 'Quarterly', 'Yearly'].map((g) => (
              <option key={g} value={g}>{g}</option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor={id('owner')} className="field-label">Owner</label>
          <input id={id('owner')} type="text" value={form.owner} onChange={(e) => edit({ owner: e.target.value })} className="select-control" style={{ width: '100%' }} placeholder="Responsible person/team..." />
        </div>

        <div>
          <label htmlFor={id('time-filter')} className="field-label">Actuals time filter</label>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <select id={id('time-filter')} className="select-control" style={{ flex: 1 }} value={form.time_filter_type} onChange={(e) => edit({ time_filter_type: e.target.value })}>
              <option value="None">None</option>
              <option value="Rolling">Rolling window</option>
            </select>
            {form.time_filter_type === 'Rolling' && (
              <input
                type="number"
                min={1}
                aria-label="Rolling window in days"
                placeholder="Days"
                value={form.time_filter_value}
                onChange={(e) => edit({ time_filter_value: e.target.value })}
                className="select-control"
                style={{ width: '90px' }}
              />
            )}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'flex-end' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', cursor: 'pointer', paddingBottom: '0.4rem' }}>
            <input type="checkbox" checked={form.visible} onChange={(e) => edit({ visible: e.target.checked })} />
            Visible by default
          </label>
        </div>
      </div>

      <section className="sub-panel" aria-labelledby={id('split-title')}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
          <h3 id={id('split-title')} className="sub-panel-title">
            <SplitSquareHorizontal size={16} color="var(--accent-primary)" aria-hidden="true" /> Repartition / split template
          </h3>
          <button type="button" className="btn btn-secondary" style={{ fontSize: '0.75rem' }} onClick={handleSaveSplit} disabled={setKpiGlobalSplit.isPending || !splitsLoaded}>
            {setKpiGlobalSplit.isPending ? <Loader2 size={12} className="spin" aria-hidden="true" /> : splitSaved ? <CheckCircle2 size={12} aria-hidden="true" /> : <Save size={12} aria-hidden="true" />}
            {splitSaved ? 'Saved' : 'Save split'}
          </button>
        </div>
        <p className="field-hint" style={{ marginBottom: '0.75rem' }}>
          How this KPI's annual targets break down into days, weeks, months and quarters. Templates are defined on the Global
          Splits & ML page. Saving recalculates this KPI's stored targets.
        </p>
        <label htmlFor={id('split')} className="sr-only">Split template</label>
        <select
          id={id('split')}
          className="select-control"
          style={{ width: '100%' }}
          value={shownSplitId ?? 'none'}
          disabled={!splitsLoaded}
          onChange={(e) => { setPendingSplitId(e.target.value === 'none' ? null : Number(e.target.value)); setSplitSaved(false); }}
        >
          <option value="none">None (even distribution across the year)</option>
          {allGlobalSplits.map((gs) => (
            <option key={gs.id} value={gs.id}>
              ⭐ {gs.name}{gs.years && gs.years.length > 0 ? ` (${gs.years.join(', ')})` : ''}
            </option>
          ))}
        </select>
      </section>

      <section className="sub-panel" aria-labelledby={id('labels-title')}>
        <h3 id={id('labels-title')} className="sub-panel-title" style={{ marginBottom: '0.75rem' }}>
          <Layers size={16} color="var(--accent-primary)" aria-hidden="true" /> Target scenario names
        </h3>
        <p className="field-hint" style={{ marginBottom: '0.75rem' }}>
          Names shown in Target Entry for each of this KPI's {targetCountNum} target{targetCountNum > 1 ? 's' : ''}. Leave blank to use the default.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '0.75rem' }}>
          {Array.from({ length: targetCountNum }, (_, i) => i + 1).map((tn) => (
            <div key={tn}>
              <label htmlFor={id(`label-${tn}`)} className="field-label">Target {tn}</label>
              <input
                id={id(`label-${tn}`)}
                type="text"
                value={targetLabels[String(tn)] || ''}
                placeholder={targetLabel(tn)}
                onChange={(e) => { setTargetLabels({ ...targetLabels, [String(tn)]: e.target.value }); setSpecSaved(false); }}
                className="select-control"
                style={{ width: '100%' }}
              />
            </div>
          ))}
        </div>
      </section>

      <section className="sub-panel" aria-labelledby={id('thresholds-title')}>
        <h3 id={id('thresholds-title')} className="sub-panel-title" style={{ marginBottom: '0.75rem', color: 'var(--accent-warning)' }}>
          <Gauge size={16} aria-hidden="true" /> Performance alert thresholds
        </h3>
        <div className="grid-3">
          <div>
            <label htmlFor={id('warn')} className="field-label">Warning margin (0-1)</label>
            <input id={id('warn')} type="number" step="0.01" min={0} max={1} value={form.warning_margin} onChange={(e) => edit({ warning_margin: e.target.value })} className="select-control" style={{ width: '100%' }} />
          </div>
          <div>
            <label htmlFor={id('err')} className="field-label">Error margin (0-1)</label>
            <input id={id('err')} type="number" step="0.01" min={0} max={1} value={form.error_margin} onChange={(e) => edit({ error_margin: e.target.value })} className="select-control" style={{ width: '100%' }} />
          </div>
          {form.direction === 'Range' && (
            <>
              <div>
                <label htmlFor={id('min')} className="field-label">Min target (range)</label>
                <input id={id('min')} type="number" step="any" value={form.min_target} onChange={(e) => edit({ min_target: e.target.value })} className="select-control" style={{ width: '100%' }} />
              </div>
              <div>
                <label htmlFor={id('max')} className="field-label">Max target (range)</label>
                <input id={id('max')} type="number" step="any" value={form.max_target} onChange={(e) => edit({ max_target: e.target.value })} className="select-control" style={{ width: '100%' }} />
              </div>
            </>
          )}
        </div>
      </section>

      <section className="sub-panel" aria-labelledby={id('formula-title')}>
        <h3 id={id('formula-title')} className="sub-panel-title" style={{ marginBottom: '0.5rem', color: 'var(--accent-purple)' }}>
          <Code size={16} aria-hidden="true" /> Formula
        </h3>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginBottom: '0.5rem', alignItems: 'center' }}>
          <select
            className="select-control"
            aria-label="Insert a KPI reference"
            style={{ fontSize: '0.75rem', flex: '1 1 200px' }}
            value=""
            onChange={(e) => { if (e.target.value) insertAtCursor(`[${e.target.value}]`); }}
          >
            <option value="">+ Insert KPI reference...</option>
            {kpis.filter((k) => k.id !== kpi.id).map((k) => (
              <option key={k.id} value={k.id}>{k.indicator_name} (#{k.id})</option>
            ))}
          </select>
          {['+', '-', '*', '/', '(', ')'].map((sym) => (
            <button key={sym} type="button" className="btn btn-secondary mono" aria-label={`Insert ${sym}`} onClick={() => insertAtCursor(sym)}>
              {sym}
            </button>
          ))}
          {['abs', 'min', 'max', 'round'].map((fn) => (
            <button key={fn} type="button" className="btn btn-secondary mono" onClick={() => insertFunction(fn)}>
              {fn}()
            </button>
          ))}
        </div>

        <label htmlFor={id('formula')} className="sr-only">Formula expression</label>
        <textarea
          id={id('formula')}
          ref={formulaTextareaRef}
          value={form.formula_string}
          onChange={(e) => edit({ formula_string: e.target.value })}
          placeholder="e.g. [12] / [7] -- leave empty for a manually entered KPI"
          rows={3}
          className="formula-input"
          aria-describedby={id('formula-hint')}
        />
        <div id={id('formula-hint')} className="field-hint" style={{ marginTop: '4px' }}>
          <code>[id]</code> is another KPI's value (Specification ID). Allowed: numbers, <code>+ - * / % **</code>, parentheses,{' '}
          <code>abs</code>, <code>min</code>, <code>max</code>, <code>round</code>. A KPI with a formula is calculated automatically (target N from
          its inputs' target N) and can't be typed in Target Entry.
        </div>
      </section>

      <section className="sub-panel" aria-labelledby={id('visibility-title')}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
          <h3 id={id('visibility-title')} className="sub-panel-title">
            <Shield size={16} color="var(--accent-primary)" aria-hidden="true" /> Facility enablement
          </h3>
          <button type="button" className="btn btn-secondary" style={{ fontSize: '0.75rem' }} onClick={handleSaveVisibility} disabled={updateVisibility.isPending}>
            {updateVisibility.isPending ? <Loader2 size={12} className="spin" aria-hidden="true" /> : visibilitySaved ? <CheckCircle2 size={12} aria-hidden="true" /> : <Save size={12} aria-hidden="true" />}
            {visibilitySaved ? 'Saved' : 'Save visibility'}
          </button>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '0.75rem' }}>
          {plants.map((plant) => (
            <label key={plant.id} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={isEnabledFor(plant.id)}
                onChange={(e) => { setPendingVisibility({ ...pendingVisibility, [plant.id]: e.target.checked }); setVisibilitySaved(false); }}
              />
              <span aria-hidden="true" style={{ width: 10, height: 10, borderRadius: '50%', background: plant.color }} />
              {plant.name}
            </label>
          ))}
        </div>
      </section>

      <section className="sub-panel" style={{ marginBottom: 0 }}>
        <button
          type="button"
          className="link-button sub-panel-title"
          aria-expanded={showHistory}
          aria-controls={id('history')}
          onClick={() => setShowHistory((v) => !v)}
        >
          <History size={16} color="var(--accent-teal)" aria-hidden="true" /> Audit history {showHistory ? '(hide)' : '(show who changed what)'}
        </button>

        {showHistory && (
          <div id={id('history')} style={{ marginTop: '0.75rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
              <div className="field-hint" style={{ marginBottom: '0.4rem' }}>Target value edits:</div>
              {targetHistory.length === 0 ? (
                <div className="field-hint">No target edits recorded yet.</div>
              ) : (
                <ul className="history-list">
                  {targetHistory.map((h) => (
                    <li key={h.id}>
                      <span className="muted">{new Date(h.changed_at).toLocaleString()}</span> <strong>{h.changed_by}</strong>{' '}
                      set {targetLabel(h.target_number, savedLabels)} ({plantName(h.plant_id)}, {h.period_start.slice(0, 4)}) to <strong>{h.new_value ?? 'n/a'}</strong> (was {h.old_value ?? 'n/a'})
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div>
              <div className="field-hint" style={{ marginBottom: '0.4rem' }}>Definition changes:</div>
              {definitionHistory.length === 0 ? (
                <div className="field-hint">No definition changes recorded yet.</div>
              ) : (
                <ul className="history-list">
                  {definitionHistory.map((h) => (
                    <li key={h.id}>
                      <span className="muted">{new Date(h.changed_at).toLocaleString()}</span> <strong>{h.changed_by}</strong> {describeDefinitionChange(h)}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </section>
    </div>
  );
};

export const KpiManagerWorkspace: React.FC<KpiManagerWorkspaceProps> = ({ tree, kpis, plants }) => {
  const [chosenKpiId, setChosenKpiId] = useState<number | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<number | null>(null);
  const [newNodeName, setNewNodeName] = useState('');
  const [newKpiName, setNewKpiName] = useState('');
  const createNode = useCreateKpiNode();
  const createKpi = useCreateKpiIndicator();

  // Fall back to the first KPI when nothing (or a since-deleted KPI) is selected.
  const selectedKpi = kpis.find((k) => k.id === chosenKpiId) ?? kpis[0];

  const handleCreateNode = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNodeName.trim()) return;
    createNode.mutate({ name: newNodeName.trim(), parentId: selectedNodeId }, { onSuccess: () => setNewNodeName('') });
  };

  const handleCreateKpi = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKpiName.trim() || selectedNodeId === null) return;
    createKpi.mutate(
      { node_id: selectedNodeId, name: newKpiName.trim(), calculation_type: 'Sum', direction: 'Higher is Better' },
      { onSuccess: (res) => { setNewKpiName(''); setChosenKpiId(res.kpi_id); } }
    );
  };

  const selectedNodeName = (() => {
    const find = (nodes: KpiNode[]): KpiNode | undefined => {
      for (const n of nodes) {
        if (n.id === selectedNodeId) return n;
        const hit = find(n.children || []);
        if (hit) return hit;
      }
      return undefined;
    };
    return find(tree)?.name;
  })();

  return (
    <div className="explorer-layout">
      <div className="glass-card" style={{ padding: '1rem', display: 'flex', flexDirection: 'column' }}>
        <h2 className="sub-panel-title" style={{ marginBottom: '0.75rem' }}>
          <Layers size={16} color="var(--accent-primary)" aria-hidden="true" /> Hierarchy
        </h2>

        <form onSubmit={handleCreateNode} style={{ marginBottom: '0.35rem', display: 'flex', gap: '0.5rem' }}>
          <label htmlFor="new-folder" className="sr-only">New folder name</label>
          <input id="new-folder" type="text" placeholder="New folder..." value={newNodeName} onChange={(e) => setNewNodeName(e.target.value)} className="select-control" style={{ flex: 1 }} />
          <button type="submit" className="btn btn-secondary" disabled={createNode.isPending || !newNodeName.trim()}>
            <Plus size={14} aria-hidden="true" /> Add
          </button>
        </form>
        <div className="field-hint" style={{ marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', gap: '0.5rem' }}>
          <span>{selectedNodeId === null ? 'Creates a top-level folder.' : `Creates a sub-folder in "${selectedNodeName}".`}</span>
          {selectedNodeId !== null && (
            <button type="button" className="link-button" onClick={() => setSelectedNodeId(null)}>Clear selection</button>
          )}
        </div>

        <div style={{ flex: 1, overflowY: 'auto' }}>
          {tree.length === 0 && <div className="field-hint" style={{ textAlign: 'center', padding: '1rem 0' }}>No folders yet. Add one above to get started.</div>}
          <ul aria-label="KPI folders">
            {tree.map((node) => (
              <KpiTreeNode
                key={node.id}
                node={node}
                depth={0}
                kpis={kpis}
                selectedNodeId={selectedNodeId}
                selectedKpiId={selectedKpi?.id ?? null}
                onSelectNode={setSelectedNodeId}
                onSelectKpi={setChosenKpiId}
              />
            ))}
          </ul>
        </div>

        <form onSubmit={handleCreateKpi} style={{ marginTop: '1rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-color)' }}>
          <label htmlFor="new-kpi" className="field-hint" style={{ display: 'block', marginBottom: '0.35rem' }}>
            {selectedNodeId === null ? 'Select a folder to add a KPI to it' : `New KPI in "${selectedNodeName}"`}
          </label>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <input id="new-kpi" type="text" placeholder="KPI name..." value={newKpiName} onChange={(e) => setNewKpiName(e.target.value)} disabled={selectedNodeId === null} className="select-control" style={{ flex: 1 }} />
            <button type="submit" className="btn btn-primary" disabled={selectedNodeId === null || !newKpiName.trim() || createKpi.isPending}>
              <Plus size={14} aria-hidden="true" /> KPI
            </button>
          </div>
        </form>
      </div>

      <div>
        {selectedKpi ? (
          <KpiInspector key={selectedKpi.id} kpi={selectedKpi} kpis={kpis} plants={plants} onDeleted={() => setChosenKpiId(null)} />
        ) : (
          <div className="card empty-state">
            <Layers size={36} aria-hidden="true" />
            <h2>No KPIs yet</h2>
            <p>Create a folder, select it, and add a KPI.</p>
          </div>
        )}
      </div>
    </div>
  );
};
