import type { AuthConfig, DesignReply, MassProposalView, ProjectDocument, ProjectImportPreview, ProjectSummary, ProjectView, RunView, Sps3b3Catalog, Sps3b3DefaultReply, Sps3b3Design, Sps3b3ImportReply, Sps3b3MigrationReply, Sps3b3Preview, SshipProjectImportPreview, Theme, UserSession } from './types';

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
 *
 * `native` is always sent: the workspace reads the original file as one
 * first-class native design (3.0 and 2.0) rather than the legacy mapping. The
 * flag is deliberately not a user-facing mode; there is one way to read a file.
 */
export const previewSshipImport = (filename: string, content_base64: string) =>
  call<SshipProjectImportPreview>('/projects/sship-preview', {
    method: 'POST', body: JSON.stringify({ filename, content_base64, native: true }),
  });
/**
 * Save a SpringSharp source as a new project.
 *
 * `source_sha256` is the digest the preview reported for the bytes being sent:
 * the server re-reads the file and refuses anything that no longer hashes to it,
 * so a source replaced between preview and save cannot be saved behind the
 * reader's back. `native` matches the preview, so the saved project is the
 * native design the reader was shown.
 */
export const importSshipProject = (filename: string, content_base64: string,
                                    source_sha256: string, name: string) =>
  call<ProjectView>('/projects/sship-import', {
    method: 'POST', body: JSON.stringify({ filename, content_base64, source_sha256, name, native: true }),
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
/**
 * The run export formats.
 *
 * `sship`, `txt`, `rtf` and `ssr` are the SpringSharp 3b3 compatibility outputs;
 * they are only ever offered for a saved compatibility run, and the server
 * refuses them for any other request rather than substituting an empty file.
 */
export type ExportFormat = 'json' | 'csv' | 'sship' | 'txt' | 'rtf' | 'ssr';
export const exportUrl = (id: string, format: ExportFormat) => `/api/runs/${encodeURIComponent(id)}/export?format=${format}`;
/** Read an owned export before offering a download, so an error is never saved as a ship file. */
export async function exportBytes(id:string,format:ExportFormat):Promise<Blob> {
  const response=await fetch(exportUrl(id,format),{credentials:'same-origin'});
  if(!response.ok){
    let detail:unknown=await response.text();
    try{detail=JSON.parse(String(detail));}catch{/* Plain service errors remain readable. */}
    throw new ApiError(response.status,detail);
  }
  return response.blob();
}

/**
 * The compatibility catalogue: every editable source field, its page and kind.
 *
 * It is read once per screen and holds no project state; the field list is a
 * property of the recovered program, not of this project.
 */
export const sps3b3Catalog = () => call<Sps3b3Catalog>('/sps3b3/catalog');

/** The original program's fresh default declaration. */
export const sps3b3Default = () => call<Sps3b3DefaultReply>('/sps3b3/default');

/**
 * Confirm one declared edit against the previous confirmed declaration.
 *
 * The request carries the whole declaration the server should start from, so a
 * reply is a function of exactly the design that was sent: a late reply can
 * never be mistaken for the answer to a later edit.
 */
export const sps3b3Preview = (design: Sps3b3Design, command?: Record<string, unknown>) =>
  call<Sps3b3Preview>('/sps3b3/preview', {
    method: 'POST', body: JSON.stringify(command === undefined ? { design } : { design, command }),
  });

/** Read an original source file into a compatibility declaration, unsaved. */
export const sps3b3ImportPreview = (filename: string, content_base64: string) =>
  call<Sps3b3ImportReply>('/sps3b3/import-preview', {
    method: 'POST', body: JSON.stringify({ filename, content_base64 }),
  });

/** Build a compatibility declaration from a project's archived migration. */
export const sps3b3FromMigration = (migration: Record<string, unknown>) =>
  call<Sps3b3MigrationReply>('/sps3b3/from-migration', {
    method: 'POST', body: JSON.stringify({ migration }),
  });

/*
 * The native ship design. One declaration at `$.ship_design` is authoritative;
 * the temporary source-view rides along only so the existing field widgets can
 * print it. Every reply carries the whole governed project, so this side never
 * recomputes a hull or a ledger projection of its own.
 */

/** The same 222-field catalogue, read once per screen. */
export const designCatalog = () => call<Sps3b3Catalog>('/design/catalog');

/**
 * Initialize the native declaration for one project.
 *
 * A fresh project gets the product default; a project that still holds the old
 * `sps_3b3_design` section is upgraded here, returning a pending-save draft. The
 * old saved revisions and their runs are never rewritten.
 */
export const designInitialize = (project: ProjectDocument) =>
  call<DesignReply>('/design/initialize', { method: 'POST', body: JSON.stringify({ project }) });

/**
 * Confirm one declared edit against the current project and the last confirmed
 * source-view. The request carries the whole project, so the reply is a function
 * of exactly the document that was sent and a late answer can never be mistaken
 * for the answer to a later edit.
 */
export const designPreview = (project: ProjectDocument, command?: Record<string, unknown>, design?: Sps3b3Design) =>
  call<DesignReply>('/design/preview', {
    method: 'POST',
    body: JSON.stringify(command === undefined
      ? (design === undefined ? { project } : { project, design })
      : (design === undefined ? { project, command } : { project, command, design })),
  });

/** Read an original source file into a native design, unsaved. */
export const designImportPreview = (project: ProjectDocument, filename: string, content_base64: string) =>
  call<DesignReply>('/design/import-preview', {
    method: 'POST', body: JSON.stringify({ project, filename, content_base64 }),
  });

/** Build a native design from a project's archived migration, unsaved. */
export const designFromMigration = (project: ProjectDocument, migration: Record<string, unknown>) =>
  call<DesignReply>('/design/from-migration', {
    method: 'POST', body: JSON.stringify({ project, migration }),
  });
export const setTheme = (theme: Theme) => call<{ theme: Theme }>('/me/preferences', {
  method: 'PATCH', body: JSON.stringify({ theme }),
});
