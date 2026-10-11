import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, errorMessage, fetchJson } from './api';
import { clearSession, getSessionToken, setSession } from '../utils/session';

function respond(status: number, body: unknown) {
  return Promise.resolve(new Response(typeof body === 'string' ? body : JSON.stringify(body), { status }));
}

describe('fetchJson', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
    setSession('tok-123', { id: 1, name: 'a', color: '#000000', is_active: true });
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
    clearSession();
  });

  it('goes through the same-origin /api prefix and keeps auth when callers pass headers', async () => {
    fetchMock.mockReturnValue(respond(200, { ok: true }));
    await fetchJson('/kpis', { method: 'POST', headers: { 'X-Extra': '1' } });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/kpis');
    expect(init.method).toBe('POST');
    expect(init.headers).toMatchObject({ Authorization: 'Bearer tok-123', 'Content-Type': 'application/json', 'X-Extra': '1' });
  });

  it('surfaces the server detail message', async () => {
    fetchMock.mockReturnValue(respond(400, { detail: 'Formula would create a dependency cycle' }));
    await expect(fetchJson('/kpis/1')).rejects.toMatchObject({ status: 400, message: 'Formula would create a dependency cycle' });
    fetchMock.mockReturnValue(respond(422, { detail: [{ loc: ['body', 'color'], msg: 'bad hex' }] }));
    await expect(fetchJson('/plants')).rejects.toThrow('color: bad hex');
  });

  it('only a 401 ends the session; server/network errors keep it', async () => {
    fetchMock.mockReturnValue(respond(500, { detail: 'boom' }));
    await expect(fetchJson('/kpis')).rejects.toBeInstanceOf(ApiError);
    expect(getSessionToken()).toBe('tok-123');

    fetchMock.mockReturnValue(Promise.reject(new TypeError('Failed to fetch')));
    const err = await fetchJson('/kpis').catch((e) => e);
    expect(errorMessage(err)).toMatch(/reach the server/);
    expect(getSessionToken()).toBe('tok-123');

    fetchMock.mockReturnValue(respond(401, { detail: 'Not authenticated' }));
    await expect(fetchJson('/kpis')).rejects.toMatchObject({ status: 401 });
    expect(getSessionToken()).toBeNull();
  });
});
