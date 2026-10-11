import React, { useState } from 'react';
import { Target, Loader2, AlertTriangle } from 'lucide-react';
import { useAuthStatus, useLogin, useRegister } from '../hooks';
import { errorMessage } from '../services/api';

export const LoginScreen: React.FC = () => {
  const { data: status } = useAuthStatus();
  const registrationOpen = status?.registration_open ?? false;
  const firstRun = status ? !status.has_users : false;

  const [chosenMode, setChosenMode] = useState<'login' | 'register'>('login');
  const mode = firstRun ? 'register' : registrationOpen ? chosenMode : 'login';
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');

  const login = useLogin();
  const register = useRegister();
  const pending = login.isPending || register.isPending;
  const error = mode === 'login' ? login.error : register.error;

  const switchMode = (next: 'login' | 'register') => {
    setChosenMode(next);
    login.reset();
    register.reset();
  };

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
    <main
      style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-primary)' }}
    >
      <div className="card" style={{ width: '360px', padding: '2rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.5rem' }}>
          <Target color="var(--accent-primary)" size={28} aria-hidden="true" />
          <div>
            <h1 style={{ fontWeight: 700, fontSize: '1.1rem' }}>KPI Target Manager</h1>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              {firstRun ? 'Create the first account -- it will be the administrator' : mode === 'login' ? 'Sign in to continue' : 'Create your profile'}
            </div>
          </div>
        </div>

        {registrationOpen && !firstRun && (
          <div className="nav-tabs" role="tablist" style={{ marginTop: '1.25rem', width: '100%' }}>
            {(['login', 'register'] as const).map((m) => (
              <button
                key={m}
                type="button"
                role="tab"
                aria-selected={mode === m}
                className={`nav-tab ${mode === m ? 'active' : ''}`}
                style={{ flex: 1, justifyContent: 'center' }}
                onClick={() => switchMode(m)}
              >
                {m === 'login' ? 'Sign In' : 'Register'}
              </button>
            ))}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem', marginTop: '1.25rem' }}>
          <div>
            <label htmlFor="login-name" className="field-label">Name</label>
            <input
              id="login-name"
              type="text"
              autoComplete="username"
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
              <label htmlFor="login-email" className="field-label">Email (optional)</label>
              <input
                id="login-email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="select-control"
                style={{ width: '100%' }}
              />
            </div>
          )}

          <div>
            <label htmlFor="login-password" className="field-label">Password</label>
            <input
              id="login-password"
              type="password"
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="select-control"
              style={{ width: '100%' }}
              minLength={mode === 'register' ? 8 : undefined}
              aria-describedby={mode === 'register' ? 'login-password-hint' : undefined}
              required
            />
            {mode === 'register' && (
              <div id="login-password-hint" className="field-hint">At least 8 characters.</div>
            )}
          </div>

          {error && (
            <div role="alert" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem', color: 'var(--accent-danger)' }}>
              <AlertTriangle size={14} aria-hidden="true" /> {errorMessage(error)}
            </div>
          )}

          <button type="submit" className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }} disabled={pending}>
            {pending ? <Loader2 size={16} className="spin" aria-hidden="true" /> : null}
            {mode === 'login' ? 'Sign In' : 'Create Account'}
          </button>

          {!registrationOpen && status && (
            <p className="field-hint" style={{ textAlign: 'center' }}>
              Need an account? Ask an administrator to create one for you.
            </p>
          )}
        </form>
      </div>
    </main>
  );
};
