import React, { useState } from 'react';
import { Factory, Plus, Eye, EyeOff, X, Save, Loader2, Pencil, Trash2 } from 'lucide-react';
import type { Plant } from '../types';
import { useCreatePlant, useDeletePlant, useUpdatePlant } from '../hooks';
import { ApiError } from '../services/api';

interface PlantsWorkspaceProps {
  plants: Plant[];
}

const emptyForm = { name: '', description: '', color: '#3b82f6', visible: true };
type PlantForm = typeof emptyForm;

export const PlantsWorkspace: React.FC<PlantsWorkspaceProps> = ({ plants }) => {
  const [editing, setEditing] = useState<number | 'new' | null>(null);
  const [form, setForm] = useState<PlantForm>(emptyForm);
  const createPlant = useCreatePlant();
  const updatePlant = useUpdatePlant();
  const deletePlant = useDeletePlant();
  const saving = createPlant.isPending || updatePlant.isPending;

  const openNew = () => {
    setForm(emptyForm);
    setEditing('new');
  };

  const openEdit = (plant: Plant) => {
    setForm({ name: plant.name, description: plant.description || '', color: plant.color, visible: plant.visible });
    setEditing(plant.id);
  };

  const close = () => {
    setEditing(null);
    setForm(emptyForm);
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    const payload = { ...form, name: form.name.trim() };
    if (editing === 'new') {
      createPlant.mutate(payload, { onSuccess: close });
    } else if (editing !== null) {
      updatePlant.mutate({ plantId: editing, payload }, { onSuccess: close });
    }
  };

  const toggleVisibility = (plant: Plant) => {
    updatePlant.mutate({
      plantId: plant.id,
      payload: { name: plant.name, description: plant.description || '', visible: !plant.visible, color: plant.color },
    });
  };

  const handleDelete = (plant: Plant) => {
    if (!window.confirm(`Delete facility "${plant.name}"?`)) return;
    deletePlant.mutate(
      { plantId: plant.id, force: false },
      {
        onError: (err) => {
          // 409: the facility still has targets/actuals -- offer to delete them too.
          if (err instanceof ApiError && err.status === 409 &&
              window.confirm(`"${plant.name}" has targets or actuals. Delete the facility AND all of its data? This cannot be undone.`)) {
            deletePlant.mutate({ plantId: plant.id, force: true });
          }
        },
      }
    );
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      <div className="glass-card" style={{ padding: '1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
        <div>
          <h2 className="page-title">
            <Factory color="var(--accent-primary)" aria-hidden="true" /> Facilities
          </h2>
          <p className="page-subtitle">Facilities, their visibility in Target Entry, and their chart colors.</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={editing === null ? openNew : close}>
          {editing === null ? <Plus size={16} aria-hidden="true" /> : <X size={16} aria-hidden="true" />} {editing === null ? 'Add facility' : 'Cancel'}
        </button>
      </div>

      {editing !== null && (
        <form className="card" onSubmit={handleSave} aria-label={editing === 'new' ? 'New facility' : 'Edit facility'}>
          <div className="grid-3" style={{ marginBottom: '0.85rem' }}>
            <div>
              <label htmlFor="plant-name" className="field-label">Name</label>
              <input id="plant-name" className="select-control" style={{ width: '100%' }} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required autoFocus />
            </div>
            <div>
              <label htmlFor="plant-description" className="field-label">Description</label>
              <input id="plant-description" className="select-control" style={{ width: '100%' }} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </div>
            <div>
              <label htmlFor="plant-color" className="field-label">Color</label>
              <input id="plant-color" type="color" className="color-input" value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })} />
            </div>
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', marginBottom: '0.85rem', cursor: 'pointer' }}>
            <input type="checkbox" checked={form.visible} onChange={(e) => setForm({ ...form, visible: e.target.checked })} /> Visible
          </label>
          <button type="submit" className="btn btn-primary" disabled={saving || !form.name.trim()}>
            {saving ? <Loader2 size={14} className="spin" aria-hidden="true" /> : <Save size={14} aria-hidden="true" />} Save facility
          </button>
        </form>
      )}

      <div className="card">
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">ID</th>
                <th scope="col">Facility</th>
                <th scope="col">Description</th>
                <th scope="col">Color</th>
                <th scope="col">Visibility</th>
                <th scope="col"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {plants.length === 0 && (
                <tr>
                  <td colSpan={6} className="muted">No facilities yet.</td>
                </tr>
              )}
              {plants.map((plant) => (
                <tr key={plant.id}>
                  <td className="muted">#{plant.id}</td>
                  <th scope="row">{plant.name}</th>
                  <td className="muted">{plant.description || '—'}</td>
                  <td>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span aria-hidden="true" style={{ width: 16, height: 16, borderRadius: '50%', background: plant.color, border: '1px solid var(--text-secondary)' }} />
                      <code>{plant.color}</code>
                    </span>
                  </td>
                  <td>
                    <button
                      type="button"
                      className={`btn ${plant.visible ? 'btn-secondary' : 'btn-danger'}`}
                      style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
                      onClick={() => toggleVisibility(plant)}
                      disabled={updatePlant.isPending}
                      aria-pressed={plant.visible}
                    >
                      {plant.visible ? <Eye size={12} aria-hidden="true" /> : <EyeOff size={12} aria-hidden="true" />}
                      {plant.visible ? 'Visible' : 'Hidden'}
                    </button>
                  </td>
                  <td>
                    <span style={{ display: 'inline-flex', gap: '0.4rem' }}>
                      <button type="button" className="btn btn-secondary" style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }} onClick={() => openEdit(plant)}>
                        <Pencil size={12} aria-hidden="true" /> Edit<span className="sr-only"> {plant.name}</span>
                      </button>
                      <button type="button" className="btn btn-danger" style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }} onClick={() => handleDelete(plant)} disabled={deletePlant.isPending}>
                        <Trash2 size={12} aria-hidden="true" /> Delete<span className="sr-only"> {plant.name}</span>
                      </button>
                    </span>
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
