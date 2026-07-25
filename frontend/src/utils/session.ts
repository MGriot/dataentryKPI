import type { User } from '../types';

const TOKEN_KEY = 'kpi_session_token';
const USER_KEY = 'kpi_session_user';
export const SESSION_EVENT = 'kpi-session-changed';

export function getSessionToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function getSessionUser(): User | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setSession(token: string, user: User) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    window.dispatchEvent(new Event(SESSION_EVENT));
  } catch {
    // localStorage unavailable (e.g. private browsing) -- session just won't persist across reloads
  }
}

export function clearSession() {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  } catch {
    // ignore
  }
  window.dispatchEvent(new Event(SESSION_EVENT));
}
