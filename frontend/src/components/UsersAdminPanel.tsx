import React, { useState } from 'react';
import { Users, Plus, KeyRound, Copy, Trash2, CheckCircle2 } from 'lucide-react';
import { useUsers, useCreateUser, useUserApiKeys, useCreateApiKey, useRevokeApiKey } from '../hooks';
import type { NewApiKeyResult } from '../types';

export const UsersAdminPanel: React.FC = () => {
  const { data: users = [] } = useUsers();
  const createUser = useCreateUser();
  const [newUserName, setNewUserName] = useState('');
  const [newUserEmail, setNewUserEmail] = useState('');
  const [newUserPassword, setNewUserPassword] = useState('');
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);

  const { data: apiKeys = [] } = useUserApiKeys(selectedUserId);
  const createApiKey = useCreateApiKey();
  const revokeApiKey = useRevokeApiKey();
  const [newKeyLabel, setNewKeyLabel] = useState('');
  const [revealedKey, setRevealedKey] = useState<NewApiKeyResult | null>(null);

  const selectedUser = users.find((u) => u.id === selectedUserId);

  const handleCreateUser = () => {
    if (!newUserName.trim() || newUserPassword.length < 8) return;
    createUser.mutate(
      { name: newUserName.trim(), password: newUserPassword, email: newUserEmail.trim() },
      { onSuccess: (res) => { setNewUserName(''); setNewUserEmail(''); setNewUserPassword(''); setSelectedUserId(res.id); } }
    );
  };

  const handleCreateKey = () => {
    if (!selectedUserId || !newKeyLabel.trim()) return;
    createApiKey.mutate(
      { userId: selectedUserId, label: newKeyLabel.trim() },
      {
        onSuccess: (res) => {
          setRevealedKey(res);
          setNewKeyLabel('');
        },
      }
    );
  };

  return (
    <div className="grid-2">
      <div className="card">
        <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Users size={16} color="var(--accent-primary)" /> Users
        </h3>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', marginBottom: '1rem' }}>
          {users.map((u) => (
            <div
              key={u.id}
              onClick={() => setSelectedUserId(u.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.5rem 0.75rem',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
                background: selectedUserId === u.id ? 'var(--bg-surface-hover)' : 'var(--bg-primary)',
                border: '1px solid var(--border-color)',
              }}
            >
              <span style={{ width: 10, height: 10, borderRadius: '50%', background: u.color, flexShrink: 0 }} />
              <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>{u.name}</span>
              {u.email && <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{u.email}</span>}
              {!u.is_active && <span className="badge badge-purple" style={{ marginLeft: 'auto' }}>Inactive</span>}
            </div>
          ))}
          {users.length === 0 && <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>No other users yet.</div>}
        </div>

        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
          Create an account for someone else (they can change the password themselves once logged in):
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <input
              type="text"
              placeholder="Name..."
              value={newUserName}
              onChange={(e) => setNewUserName(e.target.value)}
              className="select-control"
              style={{ flex: 1 }}
            />
            <input
              type="text"
              placeholder="Email (optional)"
              value={newUserEmail}
              onChange={(e) => setNewUserEmail(e.target.value)}
              className="select-control"
              style={{ flex: 1 }}
            />
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <input
              type="password"
              placeholder="Temporary password (min 8 chars)..."
              value={newUserPassword}
              onChange={(e) => setNewUserPassword(e.target.value)}
              className="select-control"
              style={{ flex: 1 }}
              minLength={8}
            />
            <button
              className="btn btn-primary"
              onClick={handleCreateUser}
              disabled={!newUserName.trim() || newUserPassword.length < 8 || createUser.isPending}
            >
              <Plus size={14} /> Create
            </button>
          </div>
        </div>
      </div>

      <div className="card">
        <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <KeyRound size={16} color="var(--accent-purple)" /> MCP API Keys {selectedUser && `-- ${selectedUser.name}`}
        </h3>

        {!selectedUser ? (
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Select a user to manage their API keys.</div>
        ) : (
          <>
            {revealedKey && (
              <div
                style={{
                  background: 'rgba(16, 185, 129, 0.1)',
                  border: '1px solid var(--accent-success)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '0.75rem',
                  marginBottom: '1rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, fontSize: '0.8rem', marginBottom: '0.4rem', color: 'var(--accent-success)' }}>
                  <CheckCircle2 size={14} /> Key created -- copy it now, it won't be shown again
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <code style={{ flex: 1, fontSize: '0.75rem', wordBreak: 'break-all', background: 'var(--bg-primary)', padding: '0.4rem', borderRadius: '4px' }}>
                    {revealedKey.raw_key}
                  </code>
                  <button className="btn btn-secondary" style={{ fontSize: '0.7rem' }} onClick={() => navigator.clipboard.writeText(revealedKey.raw_key)}>
                    <Copy size={12} />
                  </button>
                </div>
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', marginBottom: '1rem' }}>
              {apiKeys.map((k) => (
                <div
                  key={k.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0.5rem 0.75rem',
                    background: 'var(--bg-primary)',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--border-color)',
                  }}
                >
                  <div>
                    <div style={{ fontSize: '0.85rem', fontWeight: 600 }}>{k.label}</div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                      <code>{k.key_prefix}...</code> &middot; {k.last_used_at ? `last used ${new Date(k.last_used_at).toLocaleDateString()}` : 'never used'}
                    </div>
                  </div>
                  {k.is_active ? (
                    <button className="btn btn-danger" style={{ fontSize: '0.7rem' }} onClick={() => revokeApiKey.mutate(k.id)}>
                      <Trash2 size={12} /> Revoke
                    </button>
                  ) : (
                    <span className="badge badge-purple">Revoked</span>
                  )}
                </div>
              ))}
              {apiKeys.length === 0 && <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>No API keys yet.</div>}
            </div>

            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <input
                type="text"
                placeholder="Key label, e.g. 'Claude Desktop'"
                value={newKeyLabel}
                onChange={(e) => setNewKeyLabel(e.target.value)}
                className="select-control"
                style={{ flex: 1 }}
              />
              <button className="btn btn-primary" onClick={handleCreateKey} disabled={!newKeyLabel.trim() || createApiKey.isPending}>
                <Plus size={14} /> Create Key
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
