import React from 'react';
import { LogOut, ShieldCheck } from 'lucide-react';
import type { User } from '../types';
import { api } from '../services/api';
import { clearSession } from '../utils/session';

interface UserMenuProps {
  user: User;
}

export const UserMenu: React.FC<UserMenuProps> = ({ user }) => {
  const handleLogout = async () => {
    try {
      await api.logout();
    } catch {
      // even if the network call fails, still drop the local session
    }
    clearSession();
  };

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
        padding: '0.3rem 0.6rem',
        borderRadius: 'var(--radius-sm)',
        border: '1px solid var(--border-color)',
        background: 'var(--bg-primary)',
      }}
    >
      <span aria-hidden="true" style={{ width: 8, height: 8, borderRadius: '50%', background: user.color || 'var(--accent-primary)' }} />
      <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>{user.name}</span>
      {user.is_admin && (
        <span className="badge badge-blue" title="Administrator">
          <ShieldCheck size={12} aria-hidden="true" /> Admin
        </span>
      )}
      <button
        type="button"
        className="btn btn-secondary"
        style={{ padding: '0.2rem 0.4rem' }}
        onClick={handleLogout}
        aria-label="Log out"
        title="Log out"
      >
        <LogOut size={12} aria-hidden="true" />
      </button>
    </div>
  );
};
