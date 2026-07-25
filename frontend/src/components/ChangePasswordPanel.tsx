import React, { useState } from 'react';
import { KeyRound, Save, Loader2, CheckCircle2, AlertTriangle } from 'lucide-react';
import { useChangePassword } from '../hooks';

export const ChangePasswordPanel: React.FC = () => {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const changePassword = useChangePassword();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setMessage(null);
    if (newPassword !== confirmPassword) {
      setMessage({ type: 'error', text: "New password and confirmation don't match." });
      return;
    }
    if (newPassword.length < 8) {
      setMessage({ type: 'error', text: 'New password must be at least 8 characters.' });
      return;
    }
    changePassword.mutate(
      { currentPassword, newPassword },
      {
        onSuccess: () => {
          setMessage({ type: 'success', text: 'Password updated.' });
          setCurrentPassword('');
          setNewPassword('');
          setConfirmPassword('');
        },
        onError: (e: any) => setMessage({ type: 'error', text: e.message.replace(/^API Error \d+: /, '') }),
      }
    );
  };

  return (
    <div className="card">
      <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <KeyRound size={16} color="var(--accent-primary)" /> Password Management
      </h3>

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxWidth: '360px' }}>
        <div>
          <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Current Password</label>
          <input
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            className="select-control"
            style={{ width: '100%' }}
            required
          />
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>New Password</label>
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className="select-control"
            style={{ width: '100%' }}
            minLength={8}
            required
          />
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Confirm New Password</label>
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="select-control"
            style={{ width: '100%' }}
            minLength={8}
            required
          />
        </div>

        {message && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              fontSize: '0.8rem',
              color: message.type === 'error' ? 'var(--accent-danger)' : 'var(--accent-success)',
            }}
          >
            {message.type === 'error' ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}
            {message.text}
          </div>
        )}

        <button type="submit" className="btn btn-primary" disabled={changePassword.isPending}>
          {changePassword.isPending ? <Loader2 size={14} className="spin" /> : <Save size={14} />} Update Password
        </button>
      </form>
    </div>
  );
};
