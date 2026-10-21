import React, { useRef, useState } from 'react';
import { Settings, Download, Upload, Database, AlertTriangle, CheckCircle2, FileSpreadsheet } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { api, errorMessage } from '../services/api';
import { invalidateData } from '../hooks';
import type { User } from '../types';
import { UsersAdminPanel } from './UsersAdminPanel';
import { ChangePasswordPanel } from './ChangePasswordPanel';

const CSV_TABLES = ['Plants', 'KPI Hierarchy', 'KPI Definitions', 'Plant Visibility', 'Annual Targets', 'Periodic Targets'];

export const SettingsWorkspace: React.FC<{ currentUser: User }> = ({ currentUser }) => {
  const qc = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [confirmRestore, setConfirmRestore] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const run = async (key: string, fn: () => Promise<string>) => {
    setBusy(key);
    setMessage(null);
    try {
      setMessage({ type: 'success', text: await fn() });
    } catch (e) {
      setMessage({ type: 'error', text: errorMessage(e) });
    } finally {
      setBusy(null);
    }
  };

  const handleRestoreFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file || !confirmRestore) return;
    run('restore', async () => {
      const result = await api.restoreFromBackup(file);
      await invalidateData(qc); // everything on screen changed
      setConfirmRestore(false);
      return `${result.detail} A snapshot of the previous data was saved on the server (${result.snapshot}).`;
    });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      <div className="glass-card" style={{ padding: '1.25rem' }}>
        <h2 className="page-title">
          <Settings color="var(--accent-primary)" aria-hidden="true" /> Data Utilities & Accounts
        </h2>
        <p className="page-subtitle">CSV exports, full backups, your password, and MCP API keys.</p>
      </div>

      {message && (
        <div
          role={message.type === 'error' ? 'alert' : 'status'}
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
          {message.type === 'error' ? <AlertTriangle size={16} aria-hidden="true" /> : <CheckCircle2 size={16} aria-hidden="true" />}
          {message.text}
        </div>
      )}

      <div className="grid-2">
        <section className="card" aria-labelledby="csv-title">
          <h3 id="csv-title" className="sub-panel-title" style={{ marginBottom: '1rem', fontSize: '1rem' }}>
            <FileSpreadsheet size={16} color="var(--accent-primary)" aria-hidden="true" /> CSV exports
          </h3>
          <button
            type="button"
            className="btn btn-secondary"
            style={{ width: '100%', marginBottom: '0.75rem' }}
            disabled={busy === 'lean'}
            onClick={() => run('lean', async () => { await api.downloadLeanExport(); return 'Lean export downloaded.'; })}
          >
            <Download size={14} aria-hidden="true" /> {busy === 'lean' ? 'Exporting...' : 'Export lean CSV (BI-friendly)'}
          </button>
          <div className="field-hint" style={{ marginBottom: '0.5rem' }}>Export a single table:</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
            {CSV_TABLES.map((table) => (
              <button
                key={table}
                type="button"
                className="btn btn-secondary"
                style={{ fontSize: '0.75rem' }}
                disabled={busy === `csv-${table}`}
                onClick={() => run(`csv-${table}`, async () => { await api.downloadCsvTable(table); return `${table} exported.`; })}
              >
                <Download size={12} aria-hidden="true" /> {table}
              </button>
            ))}
          </div>
        </section>

        <section className="card" aria-labelledby="backup-title">
          <h3 id="backup-title" className="sub-panel-title" style={{ marginBottom: '1rem', fontSize: '1rem' }}>
            <Database size={16} color="var(--accent-purple)" aria-hidden="true" /> Backup & restore
          </h3>
          <button
            type="button"
            className="btn btn-primary"
            style={{ width: '100%', marginBottom: '1.25rem' }}
            disabled={busy === 'backup'}
            onClick={() => run('backup', async () => { await api.downloadFullBackup(); return 'Full backup ZIP downloaded.'; })}
          >
            <Download size={14} aria-hidden="true" /> {busy === 'backup' ? 'Building backup...' : 'Download full backup (ZIP)'}
          </button>

          {currentUser.is_admin ? (
            <div className="danger-zone">
              <div className="sub-panel-title" style={{ marginBottom: '0.5rem' }}>
                <AlertTriangle size={14} color="var(--accent-danger)" aria-hidden="true" /> Restore from backup
              </div>
              <p className="field-hint" style={{ marginBottom: '0.5rem' }}>
                Replaces ALL KPI data (folders, KPIs, targets, splits, facilities, history) with the backup's contents. The server
                keeps a snapshot of the current data first. User accounts are not affected.
              </p>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem', marginBottom: '0.75rem', cursor: 'pointer' }}>
                <input type="checkbox" checked={confirmRestore} onChange={(e) => setConfirmRestore(e.target.checked)} />
                I understand this replaces the current data.
              </label>
              <input ref={fileInputRef} type="file" accept=".zip" className="sr-only" aria-label="Backup ZIP file" onChange={handleRestoreFile} />
              <button
                type="button"
                className="btn btn-danger"
                style={{ width: '100%' }}
                disabled={!confirmRestore || busy === 'restore'}
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload size={14} aria-hidden="true" /> {busy === 'restore' ? 'Restoring...' : 'Choose ZIP & restore'}
              </button>
            </div>
          ) : (
            <p className="field-hint">Restoring a backup is limited to administrators.</p>
          )}
        </section>
      </div>

      <ChangePasswordPanel />
      <UsersAdminPanel currentUser={currentUser} />
    </div>
  );
};
