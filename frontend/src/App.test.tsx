import { act } from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { afterEach, expect, test, vi } from 'vitest';
import App from './App';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | undefined;

afterEach(() => {
  act(() => root?.unmount());
  root = undefined;
  document.body.innerHTML = '';
  vi.unstubAllGlobals();
});

function serveAuthStatus(status: { has_users: boolean; registration_open: boolean }) {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(status), { status: 200, headers: { 'Content-Type': 'application/json' } })));
}

async function renderApp() {
  const container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
  await act(async () => root!.render(<App />));
  return container;
}

test('a fresh install offers to create the first (admin) account', async () => {
  serveAuthStatus({ has_users: false, registration_open: true });
  const container = await renderApp();
  await vi.waitFor(() => expect(container.textContent).toContain('Create the first account'));
  expect(container.querySelector('button[type="submit"]')?.textContent).toMatch(/create/i);
});

test('with registration closed only sign-in is offered', async () => {
  serveAuthStatus({ has_users: true, registration_open: false });
  const container = await renderApp();
  await vi.waitFor(() => expect(container.textContent).toContain('Sign in to continue'));
  expect(container.querySelector('[role="tablist"]')).toBeNull();
});
