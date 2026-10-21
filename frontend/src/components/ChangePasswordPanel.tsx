import React, { useState } from 'react';
import { KeyRound, Save, Loader2, CheckCircle2, AlertTriangle } from 'lucide-react';
import { useChangePassword } from '../hooks';
import { errorMessage } from '../services/api';

export const ChangePasswordPanel: React.FC = () => {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const changePassword = useChangePassword();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setMessage(null);
    if (newPassword !== confirmPassword) return setMessage({ type: 'error', text: "New password and confirmation don't match." });
    if (newPassword.length < 8) return setMessage({ type: 'error', text: 'New password must be at least 8 characters.' });
    changePassword.mutate(
      { currentPassword, newPassword },
      {
        onSuccess: () => {
          setMessage({ type: 'success', text: 'Password updated. Your other sessions were signed out.' });
          setCurrentPassword('');
          setNewPassword('');
          setConfirmPassword('');
        },
        onError: (err) => setMessage({ type: 'error', text: errorMessage(err) }),
      }
    );
  };

  const field = (id: string, label: string, value: string, set: (v: string) => void, autoComplete: string, minLength?: number) => (
    <div>
      <label htmlFor={id} className="field-label">{label}</label>
      <input id={id} type="password" autoComplete={autoComplete} value={value} onChange={(e) => set(e.target.value)} className="select-control" style={{ width: '100%' }} minLength={minLength} required />
    </div>
  );

  return (
    <section className="card" aria-labelledby="password-title">
      <h3 id="password-title" className="sub-panel-title" style={{ marginBottom: '1rem', fontSize: '1rem' }}>
        <KeyRound size={16} color="var(--accent-primary)" aria-hidden="true" /> Change your password
      </h3>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxWidth: '360px' }}>
        {field('pw-current', 'Current password', currentPassword, setCurrentPassword, 'current-password')}
        {field('pw-new', 'New password', newPassword, setNewPassword, 'new-password', 8)}
        {field('pw-confirm', 'Confirm new password', confirmPassword, setConfirmPassword, 'new-password', 8)}

        {message && (
          <div
            role={message.type === 'error' ? 'alert' : 'status'}
            style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem', color: message.type === 'error' ? 'var(--accent-danger)' : 'var(--accent-success)' }}
          >
            {message.type === 'error' ? <AlertTriangle size={14} aria-hidden="true" /> : <CheckCircle2 size={14} aria-hidden="true" />}
            {message.text}
          </div>
        )}

        <button type="submit" className="btn btn-primary" disabled={changePassword.isPending}>
          {changePassword.isPending ? <Loader2 size={14} className="spin" aria-hidden="true" /> : <Save size={14} aria-hidden="true" />} Update password
        </button>
      </form>
    </section>
  );
};
