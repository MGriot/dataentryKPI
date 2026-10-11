import React, { useState } from 'react';
import { Users, Plus, KeyRound, Copy, Trash2, CheckCircle2, ShieldCheck, Save } from 'lucide-react';
import {
  useUsers,
  useCreateUser,
  useUpdateUser,
  useResetUserPassword,
  useUserApiKeys,
  useCreateApiKey,
  useRevokeApiKey,
} from '../hooks';
import type { NewApiKeyResult, User } from '../types';
import { notifyError } from '../utils/toast';

const UserEditor: React.FC<{ user: User; isSelf: boolean }> = ({ user, isSelf }) => {
  const updateUser = useUpdateUser();
  const resetPassword = useResetUserPassword();
  const [name, setName] = useState(user.name);
  const [email, setEmail] = useState(user.email || '');
  const [isAdmin, setIsAdmin] = useState(!!user.is_admin);
  const [isActive, setIsActive] = useState(user.is_active);
  const [newPassword, setNewPassword] = useState('');
  const [saved, setSaved] = useState<string | null>(null);

  const save = (e: React.FormEvent) => {
    e.preventDefault();
    updateUser.mutate(
      { userId: user.id, payload: { name: name.trim(), email: email.trim(), color: user.color, is_active: isActive, is_admin: isAdmin } },
      { onSuccess: () => setSaved('Profile saved.') }
    );
  };

  const reset = () => {
    if (newPassword.length < 8) return;
    resetPassword.mutate({ userId: user.id, newPassword }, { onSuccess: () => { setNewPassword(''); setSaved('Password reset; the user was signed out everywhere.'); } });
  };

  return (
    <form onSubmit={save} className="sub-panel" style={{ marginTop: '0.75rem' }} aria-label={`Edit ${user.name}`}>
      <div className="grid-2" style={{ marginBottom: '0.6rem' }}>
        <div>
          <label htmlFor={`u-${user.id}-name`} className="field-label">Name</label>
          <input id={`u-${user.id}-name`} className="select-control" style={{ width: '100%' }} value={name} onChange={(e) => { setName(e.target.value); setSaved(null); }} required />
        </div>
        <div>
          <label htmlFor={`u-${user.id}-email`} className="field-label">Email</label>
          <input id={`u-${user.id}-email`} type="email" className="select-control" style={{ width: '100%' }} value={email} onChange={(e) => { setEmail(e.target.value); setSaved(null); }} />
        </div>
      </div>
      <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginBottom: '0.6rem', fontSize: '0.85rem' }}>
        <label style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
          <input type="checkbox" checked={isAdmin} onChange={(e) => { setIsAdmin(e.target.checked); setSaved(null); }} /> Administrator
        </label>
        <label style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
          <input type="checkbox" checked={isActive} disabled={isSelf} onChange={(e) => { setIsActive(e.target.checked); setSaved(null); }} /> Active (can sign in)
        </label>
      </div>
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <button type="submit" className="btn btn-primary" disabled={updateUser.isPending || !name.trim()}>
          <Save size={14} aria-hidden="true" /> Save user
        </button>
        {!isSelf && (
          <>
            <label htmlFor={`u-${user.id}-pw`} className="sr-only">New password for {user.name}</label>
            <input
              id={`u-${user.id}-pw`}
              type="password"
              autoComplete="new-password"
              placeholder="New password (8+ chars)"
              className="select-control"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
            <button type="button" className="btn btn-secondary" onClick={reset} disabled={newPassword.length < 8 || resetPassword.isPending}>
              Reset password
            </button>
          </>
        )}
      </div>
      {saved && <p role="status" className="field-hint" style={{ color: 'var(--accent-success)', marginTop: '0.4rem' }}>{saved}</p>}
    </form>
  );
};

export const UsersAdminPanel: React.FC<{ currentUser: User }> = ({ currentUser }) => {
  const isAdmin = !!currentUser.is_admin;
  const { data: users = [] } = useUsers();
  const createUser = useCreateUser();
  const [newUserName, setNewUserName] = useState('');
  const [newUserEmail, setNewUserEmail] = useState('');
  const [newUserPassword, setNewUserPassword] = useState('');
  const [chosenUserId, setChosenUserId] = useState<number | null>(null);
  // Non-admins can only ever manage their own keys.
  const selectedUserId = isAdmin ? (chosenUserId ?? currentUser.id) : currentUser.id;
  const selectedUser = users.find((u) => u.id === selectedUserId) ?? (selectedUserId === currentUser.id ? currentUser : undefined);

  const { data: apiKeys = [] } = useUserApiKeys(selectedUserId);
  const createApiKey = useCreateApiKey();
  const revokeApiKey = useRevokeApiKey();
  const [newKeyLabel, setNewKeyLabel] = useState('');
  const [revealedKey, setRevealedKey] = useState<(NewApiKeyResult & { userId: number }) | null>(null);
  const [copied, setCopied] = useState(false);
  const shownKey = revealedKey && revealedKey.userId === selectedUserId ? revealedKey : null;

  const handleCreateUser = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUserName.trim() || newUserPassword.length < 8) return;
    createUser.mutate(
      { name: newUserName.trim(), password: newUserPassword, email: newUserEmail.trim() },
      { onSuccess: (res) => { setNewUserName(''); setNewUserEmail(''); setNewUserPassword(''); setChosenUserId(res.id); } }
    );
  };

  const handleCreateKey = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKeyLabel.trim()) return;
    createApiKey.mutate(
      { userId: selectedUserId, label: newKeyLabel.trim() },
      { onSuccess: (res) => { setRevealedKey({ ...res, userId: selectedUserId }); setCopied(false); setNewKeyLabel(''); } }
    );
  };

  const copyKey = async (raw: string) => {
    try {
      await navigator.clipboard.writeText(raw);
      setCopied(true);
    } catch {
      notifyError('Could not copy to the clipboard -- select the key and copy it manually.');
    }
  };

  return (
    <div className="grid-2">
      {isAdmin ? (
        <section className="card" aria-labelledby="users-title">
          <h3 id="users-title" className="sub-panel-title" style={{ marginBottom: '1rem', fontSize: '1rem' }}>
            <Users size={16} color="var(--accent-primary)" aria-hidden="true" /> Users
          </h3>
          <ul style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', marginBottom: '1rem' }}>
            {users.map((u) => (
              <li key={u.id}>
                <button
                  type="button"
                  className={`list-row list-button ${selectedUserId === u.id ? 'selected' : ''}`}
                  aria-pressed={selectedUserId === u.id}
                  onClick={() => setChosenUserId(u.id)}
                >
                  <span aria-hidden="true" style={{ width: 10, height: 10, borderRadius: '50%', background: u.color, flexShrink: 0 }} />
                  <span style={{ fontWeight: 600 }}>{u.name}</span>
                  {u.email && <span className="muted">{u.email}</span>}
                  <span style={{ marginLeft: 'auto', display: 'flex', gap: '0.3rem' }}>
                    {u.is_admin && <span className="badge badge-blue"><ShieldCheck size={11} aria-hidden="true" /> Admin</span>}
                    {!u.is_active && <span className="badge badge-purple">Inactive</span>}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {selectedUser && users.some((u) => u.id === selectedUser.id) && (
            <UserEditor key={selectedUser.id} user={selectedUser} isSelf={selectedUser.id === currentUser.id} />
          )}

          <form onSubmit={handleCreateUser} style={{ marginTop: '1rem' }} aria-labelledby="new-user-title">
            <div id="new-user-title" className="field-hint" style={{ marginBottom: '0.4rem' }}>
              Create an account (the person can change the password after signing in):
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <label htmlFor="new-user-name" className="sr-only">Name</label>
                <input id="new-user-name" type="text" placeholder="Name" value={newUserName} onChange={(e) => setNewUserName(e.target.value)} className="select-control" style={{ flex: 1 }} />
                <label htmlFor="new-user-email" className="sr-only">Email</label>
                <input id="new-user-email" type="email" placeholder="Email (optional)" value={newUserEmail} onChange={(e) => setNewUserEmail(e.target.value)} className="select-control" style={{ flex: 1 }} />
              </div>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <label htmlFor="new-user-password" className="sr-only">Temporary password</label>
                <input
                  id="new-user-password"
                  type="password"
                  autoComplete="new-password"
                  placeholder="Temporary password (8+ chars)"
                  value={newUserPassword}
                  onChange={(e) => setNewUserPassword(e.target.value)}
                  className="select-control"
                  style={{ flex: 1 }}
                  minLength={8}
                />
                <button type="submit" className="btn btn-primary" disabled={!newUserName.trim() || newUserPassword.length < 8 || createUser.isPending}>
                  <Plus size={14} aria-hidden="true" /> Create
                </button>
              </div>
            </div>
          </form>
        </section>
      ) : null}

      <section className="card" aria-labelledby="keys-title">
        <h3 id="keys-title" className="sub-panel-title" style={{ marginBottom: '1rem', fontSize: '1rem' }}>
          <KeyRound size={16} color="var(--accent-purple)" aria-hidden="true" /> MCP API keys{selectedUser ? ` -- ${selectedUser.name}` : ''}
        </h3>
        <p className="field-hint" style={{ marginBottom: '0.75rem' }}>
          Keys let AI tools (Claude Desktop/Code, ...) use the MCP server as this user. Everything written with a key is recorded under this user's name.
        </p>

        {shownKey && (
          <div className="key-reveal" role="status">
            <div className="sub-panel-title" style={{ marginBottom: '0.4rem', color: 'var(--accent-success)' }}>
              <CheckCircle2 size={14} aria-hidden="true" /> Key created -- copy it now, it won't be shown again
            </div>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <code className="key-value">{shownKey.raw_key}</code>
              <button type="button" className="btn btn-secondary" style={{ fontSize: '0.7rem' }} onClick={() => copyKey(shownKey.raw_key)} aria-label="Copy API key">
                <Copy size={12} aria-hidden="true" /> {copied ? 'Copied' : 'Copy'}
              </button>
            </div>
          </div>
        )}

        <ul style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', marginBottom: '1rem' }}>
          {apiKeys.map((k) => (
            <li key={k.id} className="list-row">
              <div>
                <div style={{ fontSize: '0.85rem', fontWeight: 600 }}>{k.label}</div>
                <div className="field-hint">
                  <code>{k.key_prefix}...</code> &middot; {k.last_used_at ? `last used ${new Date(k.last_used_at).toLocaleDateString()}` : 'never used'}
                </div>
              </div>
              {k.is_active ? (
                <button
                  type="button"
                  className="btn btn-danger"
                  style={{ fontSize: '0.7rem' }}
                  onClick={() => { if (window.confirm(`Revoke key "${k.label}"? Tools using it stop working.`)) revokeApiKey.mutate(k.id); }}
                >
                  <Trash2 size={12} aria-hidden="true" /> Revoke<span className="sr-only"> {k.label}</span>
                </button>
              ) : (
                <span className="badge badge-purple">Revoked</span>
              )}
            </li>
          ))}
          {apiKeys.length === 0 && <li className="field-hint">No API keys yet.</li>}
        </ul>

        <form onSubmit={handleCreateKey} style={{ display: 'flex', gap: '0.5rem' }}>
          <label htmlFor="new-key-label" className="sr-only">Key label</label>
          <input id="new-key-label" type="text" placeholder="Key label, e.g. 'Claude Desktop'" value={newKeyLabel} onChange={(e) => setNewKeyLabel(e.target.value)} className="select-control" style={{ flex: 1 }} />
          <button type="submit" className="btn btn-primary" disabled={!newKeyLabel.trim() || createApiKey.isPending}>
            <Plus size={14} aria-hidden="true" /> Create key
          </button>
        </form>
      </section>
    </div>
  );
};
