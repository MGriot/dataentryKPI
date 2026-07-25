import React, { useRef, useState } from 'react';
import { Settings, Download, Upload, Database, AlertTriangle, CheckCircle2, FileSpreadsheet } from 'lucide-react';
import { api } from '../services/api';
import { UsersAdminPanel } from './UsersAdminPanel';
import { ChangePasswordPanel } from './ChangePasswordPanel';

const CSV_TABLES = ['Plants', 'KPI Hierarchy', 'KPI Definitions', 'Plant Visibility', 'Annual Targets', 'Periodic Targets'];

export const SettingsWorkspace: React.FC = () => {
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [confirmRestore, setConfirmRestore] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const run = async (key: string, fn: () => Promise<void>, successText: string) => {
    setBusy(key);
    setMessage(null);
    try {
      await fn();
      setMessage({ type: 'success', text: successText });
    } catch (e: any) {
      setMessage({ type: 'error', text: e.message || 'Operation failed' });
    } finally {
      setBusy(null);
    }
  };

  const handleRestoreFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!confirmRestore) {
      setMessage({ type: 'error', text: 'Please check the confirmation box before restoring a backup.' });
      e.target.value = '';
      return;
    }
    run(
      'restore',
      async () => {
        const result = await api.restoreFromBackup(file);
        setMessage({ type: 'success', text: result.detail });
      },
      'Restore completed.'
    );
    e.target.value = '';
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      <div className="glass-card" style={{ padding: '1.25rem' }}>
        <h2 style={{ fontSize: '1.15rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Settings color="var(--accent-primary)" /> Data Utilities & Backup
        </h2>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
          Export data to CSV, download a full ZIP backup, or restore from a previous backup.
        </p>
      </div>

      {message && (
        <div
          className="card"
          style={{
            padding: '0.85rem 1rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            borderColor: message.type === 'error' ? 'var(--accent-danger)' : 'var(--accent-success)',
            color: message.type === 'error' ? 'var(--accent-danger)' : 'var(--accent-success)',
          }}
        >
          {message.type === 'error' ? <AlertTriangle size={16} /> : <CheckCircle2 size={16} />}
          {message.text}
        </div>
      )}

      <div className="grid-2">
        <div className="card">
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <FileSpreadsheet size={16} color="var(--accent-primary)" /> CSV Exports
          </h3>

          <button
            className="btn btn-secondary"
            style={{ width: '100%', marginBottom: '0.75rem' }}
            disabled={busy === 'lean'}
            onClick={() => run('lean', () => api.downloadLeanExport(), 'Lean export downloaded.')}
          >
            <Download size={14} /> {busy === 'lean' ? 'Exporting...' : 'Export Lean CSV (BI-friendly)'}
          </button>

          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>Export a single table:</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
            {CSV_TABLES.map((table) => (
              <button
                key={table}
                className="btn btn-secondary"
                style={{ fontSize: '0.75rem' }}
                disabled={busy === `csv-${table}`}
                onClick={() => run(`csv-${table}`, () => api.downloadCsvTable(table), `${table} exported.`)}
              >
                <Download size={12} /> {table}
              </button>
            ))}
          </div>
        </div>

        <div className="card">
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Database size={16} color="var(--accent-purple)" /> System Backup & Restore
          </h3>

          <button
            className="btn btn-primary"
            style={{ width: '100%', marginBottom: '1.25rem' }}
            disabled={busy === 'backup'}
            onClick={() => run('backup', () => api.downloadFullBackup(), 'Full backup ZIP downloaded.')}
          >
            <Download size={14} /> {busy === 'backup' ? 'Building backup...' : 'Download Full Backup (ZIP)'}
          </button>

          <div
            style={{
              border: '1px solid var(--accent-danger)',
              borderRadius: 'var(--radius-sm)',
              padding: '0.85rem',
              background: 'rgba(239, 68, 68, 0.08)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.5rem' }}>
              <AlertTriangle size={14} color="var(--accent-danger)" /> Restore from Backup (destructive)
            </div>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
              Restoring appends records from a ZIP backup into the live database. This cannot be undone automatically.
            </p>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem', marginBottom: '0.75rem', cursor: 'pointer' }}>
              <input type="checkbox" checked={confirmRestore} onChange={(e) => setConfirmRestore(e.target.checked)} />
              I understand this will modify the live database.
            </label>
            <input ref={fileInputRef} type="file" accept=".zip" style={{ display: 'none' }} onChange={handleRestoreFile} />
            <button
              className="btn btn-danger"
              style={{ width: '100%' }}
              disabled={!confirmRestore || busy === 'restore'}
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload size={14} /> {busy === 'restore' ? 'Restoring...' : 'Upload ZIP & Restore'}
            </button>
          </div>
        </div>
      </div>

      <ChangePasswordPanel />

      <UsersAdminPanel />
    </div>
  );
};
