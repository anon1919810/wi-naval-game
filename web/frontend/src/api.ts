import type { AuthConfig, MassProposalView, ProjectDocument, ProjectImportPreview, ProjectSummary, ProjectView, RunView, SshipProjectImportPreview, Theme, UserSession } from './types';

export class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(typeof detail === 'string' ? detail : `HTTP ${status}`);
  }
}

let csrfToken: string | null = null;

export async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
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
/** Validate a backup on the server without saving anything. */
export const previewProjectImport = (project: ProjectDocument) =>
  call<ProjectImportPreview>('/projects/import-preview', { method: 'POST', body: JSON.stringify({ project }) });
/** Save a backup as a new project. The name is the reader's, and optional. */
export const importProject = (project: ProjectDocument, name?: string) =>
  call<ProjectView>('/projects/import', {
    method: 'POST', body: JSON.stringify(name === undefined ? { project } : { project, name }),
  });
/**
 * Read a SpringSharp 3.0 source file without saving anything.
 *
 * The bytes travel exactly as the reader chose them, base64-encoded and never
 * decoded, so the server sees the same file and this browser asserts nothing
 * about its contents. The answer describes what the server read out of those
 * bytes; it is not a project and it is not trusted again on a save.
 */
export const previewSshipImport = (filename: string, content_base64: string) =>
  call<SshipProjectImportPreview>('/projects/sship-preview', {
    method: 'POST', body: JSON.stringify({ filename, content_base64 }),
  });
/**
 * Save a SpringSharp source as a new project.
 *
 * `source_sha256` is the digest the preview reported for the bytes being sent:
 * the server re-reads the file and refuses anything that no longer hashes to it,
 * so a source replaced between preview and save cannot be saved behind the
 * reader's back.
 */
export const importSshipProject = (filename: string, content_base64: string,
                                    source_sha256: string, name: string) =>
  call<ProjectView>('/projects/sship-import', {
    method: 'POST', body: JSON.stringify({ filename, content_base64, source_sha256, name }),
  });
export const saveProject = (id: string, body: { base_revision: number; project: ProjectDocument }) =>
  call<ProjectView>(`/projects/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify(body) });
export const deleteProject = (id: string) =>
  call<void>(`/projects/${encodeURIComponent(id)}`, { method: 'DELETE', body: '{}' });
export const enqueueRun = (id: string, body: { revision: number; condition_id: string; options: Record<string, unknown> }) =>
  call<RunView>(`/projects/${encodeURIComponent(id)}/runs`, { method: 'POST', body: JSON.stringify(body) });

/**
 * Apply one explicit batch of reviewed proposals and save exactly one revision.
 *
 * `current_options` is this browser's own assembly of the request, not the
 * normalized form the server stored; the server normalizes it again and requires
 * that it means the same thing as the request the named run was computed with.
 * The proposals travel exactly as the stored result presented them — the server
 * recomputes every one and refuses the batch if any of them differs.
 */
export const applyMassProposals = (id: string, body: {
  base_revision: number; run_id: string; condition_id: string;
  current_options: Record<string, unknown>; proposals: Array<Record<string, unknown>>;
}) => call<MassProposalView>(`/projects/${encodeURIComponent(id)}/mass-proposals`, {
  method: 'POST', body: JSON.stringify(body),
});
export const listRuns = (id: string) => call<RunView[]>(`/projects/${encodeURIComponent(id)}/runs`);
export const getRun = (id: string) => call<RunView>(`/runs/${encodeURIComponent(id)}`);
export const cancelRun = (id: string) => call<RunView>(`/runs/${encodeURIComponent(id)}/cancel`, { method: 'POST', body: '{}' });
export const exportUrl = (id: string, format: 'json' | 'csv') => `/api/runs/${encodeURIComponent(id)}/export?format=${format}`;
export const setTheme = (theme: Theme) => call<{ theme: Theme }>('/me/preferences', {
  method: 'PATCH', body: JSON.stringify({ theme }),
});
