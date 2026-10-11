import type { User } from '../types';

const TOKEN_KEY = 'kpi_session_token';
const USER_KEY = 'kpi_session_user';
export const SESSION_EVENT = 'kpi-session-changed';

// In-memory fallback so login still works when localStorage is unavailable (private mode,
// blocked storage) -- the session just won't survive a reload.
let memoryToken: string | null = null;

export function getSessionToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? memoryToken;
  } catch {
    return memoryToken;
  }
}

export function setSession(token: string, user: User) {
  memoryToken = token;
  try {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } catch {
    // storage unavailable -- keep the in-memory token
  }
  window.dispatchEvent(new Event(SESSION_EVENT));
}

export function clearSession() {
  memoryToken = null;
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  } catch {
    // ignore
  }
  window.dispatchEvent(new Event(SESSION_EVENT));
}

/** Calls `listener` when the session changes in this tab or (via the storage event) another tab. */
export function subscribeToSession(listener: () => void): () => void {
  const onStorage = (e: StorageEvent) => {
    if (e.key === null || e.key === TOKEN_KEY) listener();
  };
  window.addEventListener(SESSION_EVENT, listener);
  window.addEventListener('storage', onStorage);
  return () => {
    window.removeEventListener(SESSION_EVENT, listener);
    window.removeEventListener('storage', onStorage);
  };
}
