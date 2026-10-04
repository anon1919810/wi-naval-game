import type { AuthConfig, ProjectDocument, ProjectSummary, ProjectView, RunView, Theme, UserSession } from './types';

export class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(typeof detail === 'string' ? detail : `HTTP ${status}`);
  }
}

let csrfToken: string | null = null;

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = init.method ?? 'GET';
  const headers = new Headers(init.headers);
  if (method !== 'GET' && method !== 'HEAD') {
    headers.set('Content-Type', 'application/json');
    if (csrfToken) headers.set('X-CSRF-Token', csrfToken);
  }
  const response = await fetch(`/api${path}`, { ...init, headers, credentials: 'same-origin' });
  const body = await response.text();
  let parsed: unknown = null;
  if (body) {
    try { parsed = JSON.parse(body); } catch { parsed = body; }
  }
  if (!response.ok) {
    const detail = parsed && typeof parsed === 'object' && 'detail' in parsed
      ? (parsed as { detail: unknown }).detail : parsed;
    throw new ApiError(response.status, detail);
  }
  return parsed as T;
}

export function setSession(session: UserSession | null): void {
  csrfToken = session?.csrf_token ?? null;
}

export async function me(): Promise<UserSession> {
  const user = await call<UserSession>('/me');
  setSession(user);
  return user;
}

export const authConfig = () => call<AuthConfig>('/auth/config');

let anonymousBootstrap: Promise<UserSession> | null = null;

/** Single-flight so a remount or retry never mints a second workspace. */
export function bootstrapAnonymous(): Promise<UserSession> {
  anonymousBootstrap ??= call<UserSession>('/auth/anonymous', { method: 'POST', body: '{}' })
    .then(session => { setSession(session); return session; })
    .catch((cause: unknown) => { anonymousBootstrap = null; throw cause; });
  return anonymousBootstrap;
}

export const requestCode = async (email: string): Promise<void> => {
  await call('/auth/request-code', { method: 'POST', body: JSON.stringify({ email }) });
};

export async function verifyCode(email: string, code: string): Promise<UserSession> {
  const session = await call<UserSession>('/auth/verify-code', {
    method: 'POST', body: JSON.stringify({ email, code }),
  });
  setSession(session);
  return session;
}

export async function logout(): Promise<void> {
  await call('/auth/logout', { method: 'POST', body: '{}' });
  setSession(null);
}

export const listProjects = () => call<ProjectSummary[]>('/projects');
export const createProject = (template: string | null, name: string) =>
  call<ProjectView>('/projects', { method: 'POST', body: JSON.stringify({ template, name }) });
export const getProject = (id: string) => call<ProjectView>(`/projects/${encodeURIComponent(id)}`);
export const saveProject = (id: string, body: { base_revision: number; project: ProjectDocument }) =>
  call<ProjectView>(`/projects/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify(body) });
export const deleteProject = (id: string) =>
  call<void>(`/projects/${encodeURIComponent(id)}`, { method: 'DELETE', body: '{}' });
export const enqueueRun = (id: string, body: { revision: number; condition_id: string; options: Record<string, unknown> }) =>
  call<RunView>(`/projects/${encodeURIComponent(id)}/runs`, { method: 'POST', body: JSON.stringify(body) });
export const listRuns = (id: string) => call<RunView[]>(`/projects/${encodeURIComponent(id)}/runs`);
export const getRun = (id: string) => call<RunView>(`/runs/${encodeURIComponent(id)}`);
export const cancelRun = (id: string) => call<RunView>(`/runs/${encodeURIComponent(id)}/cancel`, { method: 'POST', body: '{}' });
export const exportUrl = (id: string, format: 'json' | 'csv') => `/api/runs/${encodeURIComponent(id)}/export?format=${format}`;
export const setTheme = (theme: Theme) => call<{ theme: Theme }>('/me/preferences', {
  method: 'PATCH', body: JSON.stringify({ theme }),
});
