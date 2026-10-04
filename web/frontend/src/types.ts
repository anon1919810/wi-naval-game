export type Theme = 'light' | 'dark';
export type AuthMode = 'email' | 'anonymous';

export interface AuthConfig {
  mode: AuthMode;
}

export interface UserSession {
  id: string;
  email: string;
  theme: Theme;
  csrf_token: string;
  mode?: AuthMode;
  label?: string;
}

export interface ProjectDocument {
  schema: 'plimsoll-project-1';
  id: string;
  name: string;
  revision: number;
  hull: Record<string, unknown>;
  geometry: Record<string, unknown> | null;
  loading_conditions: Array<{ id: string; label: string; [key: string]: unknown }>;
  weight_groups: Array<{ id: string; label: string; items: Array<Record<string, unknown>>; [key: string]: unknown }>;
  [key: string]: unknown;
}

export interface ProjectView {
  project_id: string;
  revision: number;
  project: ProjectDocument;
}

export interface ProjectSummary {
  project_id: string;
  name: string;
  revision: number;
  updated_at: string;
}

export type StageStatus = 'completed' | 'not_requested' | 'unavailable' | 'failed' | 'canceled' | 'model_limit';
export type RunStatus = 'queued' | 'running' | 'completed' | 'partial' | 'canceled' | 'failed';

export interface StageEnvelope {
  status: StageStatus;
  requested: boolean;
  reason: string | null;
  validity: { complete: boolean; converged: boolean | null; model_applicable: boolean | null; historical_validated: boolean | null };
  method_versions: Record<string, unknown>;
  assumptions: unknown[];
  diagnostics: Array<{ code?: string; severity?: string; path?: string; message?: string; stage?: string; source_path?: string }>;
  data: Record<string, unknown> | null;
  [key: string]: unknown;
}

export interface AnalysisResult {
  schema: 'plimsoll-analysis-1';
  status: 'completed' | 'partial' | 'canceled';
  project_id: string;
  condition_id: string;
  project_fingerprint: string;
  input_fingerprint: string;
  request_fingerprint: string;
  request: Record<string, unknown>;
  input_snapshot: ProjectDocument;
  units: Record<string, unknown>;
  method_versions: Record<string, unknown>;
  sources: Record<string, unknown>;
  diagnostics: StageEnvelope['diagnostics'];
  validity: StageEnvelope['validity'];
  stages: Record<string, StageEnvelope>;
  [key: string]: unknown;
}

export interface RunView {
  id: string;
  project_id: string;
  revision: number;
  condition_id: string;
  status: RunStatus;
  request_fingerprint: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  cancel_requested: boolean;
  result: AnalysisResult | null;
  error: { code: string; message: string; [key: string]: unknown } | null;
}
