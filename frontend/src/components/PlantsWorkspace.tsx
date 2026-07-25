import React, { useState } from 'react';
import { Factory, Plus, Eye, EyeOff, X, Save, Loader2 } from 'lucide-react';
import type { Plant } from '../types';
import { useCreatePlant, useUpdatePlant } from '../hooks';

interface PlantsWorkspaceProps {
  plants: Plant[];
}

const emptyForm = { name: '', description: '', color: '#3b82f6', visible: true };

export const PlantsWorkspace: React.FC<PlantsWorkspaceProps> = ({ plants }) => {
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const createPlant = useCreatePlant();
  const updatePlant = useUpdatePlant();

  const handleCreate = () => {
    if (!form.name.trim()) return;
    createPlant.mutate(form, {
      onSuccess: () => {
        setForm(emptyForm);
        setShowForm(false);
      },
    });
  };

  const toggleVisibility = (plant: Plant) => {
    updatePlant.mutate({
      plantId: plant.id,
      payload: { name: plant.name, description: plant.description || '', visible: !plant.visible, color: plant.color },
    });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      <div className="glass-card" style={{ padding: '1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ fontSize: '1.15rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Factory color="var(--accent-primary)" /> Manufacturing Facilities & Plants
          </h2>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Manage organizational entities, visibility switches, and badge accent colors.
          </p>
        </div>

        <button className="btn btn-primary" onClick={() => setShowForm((v) => !v)}>
          {showForm ? <X size={16} /> : <Plus size={16} />} {showForm ? 'Cancel' : 'Add Facility'}
        </button>
      </div>

      {showForm && (
        <div className="card">
          <div className="grid-3" style={{ marginBottom: '0.85rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Name:</label>
              <input className="select-control" style={{ width: '100%' }} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Description:</label>
              <input className="select-control" style={{ width: '100%' }} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Badge Color:</label>
              <input type="color" style={{ width: '100%', height: '34px', background: 'transparent', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)' }} value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })} />
            </div>
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', marginBottom: '0.85rem', cursor: 'pointer' }}>
            <input type="checkbox" checked={form.visible} onChange={(e) => setForm({ ...form, visible: e.target.checked })} /> Visible
          </label>
          <button className="btn btn-primary" onClick={handleCreate} disabled={createPlant.isPending || !form.name.trim()}>
            {createPlant.isPending ? <Loader2 size={14} className="spin" /> : <Save size={14} />} Save Facility
          </button>
        </div>
      )}

      <div className="card">
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ background: 'var(--bg-primary)', borderBottom: '1px solid var(--border-color)', textAlign: 'left' }}>
                <th style={{ padding: '0.75rem' }}>ID</th>
                <th style={{ padding: '0.75rem' }}>Facility Name</th>
                <th style={{ padding: '0.75rem' }}>Description</th>
                <th style={{ padding: '0.75rem' }}>Color Badge</th>
                <th style={{ padding: '0.75rem' }}>Visibility</th>
              </tr>
            </thead>
            <tbody>
              {plants.map((plant) => (
                <tr key={plant.id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <td style={{ padding: '0.75rem', color: 'var(--text-muted)' }}>#{plant.id}</td>
                  <td style={{ padding: '0.75rem', fontWeight: 600, color: plant.color }}>🏭 {plant.name}</td>
                  <td style={{ padding: '0.75rem', color: 'var(--text-secondary)' }}>{plant.description || 'Manufacturing facility'}</td>
                  <td style={{ padding: '0.75rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ width: 16, height: 16, borderRadius: '50%', background: plant.color, border: '1px solid #fff' }} />
                      <code>{plant.color}</code>
                    </div>
                  </td>
                  <td style={{ padding: '0.75rem' }}>
                    <button
                      className={`btn ${plant.visible ? 'btn-secondary' : 'btn-danger'}`}
                      style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
                      onClick={() => toggleVisibility(plant)}
                      disabled={updatePlant.isPending}
                    >
                      {plant.visible ? <Eye size={12} /> : <EyeOff size={12} />}
                      {plant.visible ? 'Visible' : 'Hidden'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
