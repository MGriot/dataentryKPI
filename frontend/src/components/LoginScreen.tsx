import React, { useState } from 'react';
import { Target, Loader2, AlertTriangle } from 'lucide-react';
import { useLogin, useRegister } from '../hooks';

export const LoginScreen: React.FC = () => {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');

  const login = useLogin();
  const register = useRegister();
  const pending = login.isPending || register.isPending;
  const error = login.error || register.error;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !password) return;
    if (mode === 'login') {
      login.mutate({ name: name.trim(), password });
    } else {
      register.mutate({ name: name.trim(), password, email: email.trim() });
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--bg-primary)',
      }}
    >
      <div className="card" style={{ width: '360px', padding: '2rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.5rem' }}>
          <Target color="var(--accent-primary)" size={28} />
          <div>
            <div style={{ fontWeight: 700, fontSize: '1.1rem' }}>KPI Target Manager</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              {mode === 'login' ? 'Sign in to continue' : 'Create your profile'}
            </div>
          </div>
        </div>

        <div className="nav-tabs" style={{ marginTop: '1.25rem', marginBottom: '1.25rem', width: '100%' }}>
          <button
            type="button"
            className={`nav-tab ${mode === 'login' ? 'active' : ''}`}
            style={{ flex: 1, justifyContent: 'center' }}
            onClick={() => setMode('login')}
          >
            Sign In
          </button>
          <button
            type="button"
            className={`nav-tab ${mode === 'register' ? 'active' : ''}`}
            style={{ flex: 1, justifyContent: 'center' }}
            onClick={() => setMode('register')}
          >
            Register
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="select-control"
              style={{ width: '100%' }}
              autoFocus
              required
            />
          </div>

          {mode === 'register' && (
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                Email (optional)
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="select-control"
                style={{ width: '100%' }}
              />
            </div>
          )}

          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="select-control"
              style={{ width: '100%' }}
              minLength={mode === 'register' ? 8 : undefined}
              required
            />
            {mode === 'register' && (
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px' }}>At least 8 characters.</div>
            )}
          </div>

          {error && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem', color: 'var(--accent-danger)' }}>
              <AlertTriangle size={14} /> {(error as Error).message.replace(/^API Error \d+: /, '')}
            </div>
          )}

          <button type="submit" className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }} disabled={pending}>
            {pending ? <Loader2 size={16} className="spin" /> : null}
            {mode === 'login' ? 'Sign In' : 'Create Account'}
          </button>
        </form>
      </div>
    </div>
  );
};
