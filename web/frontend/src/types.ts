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

/**
 * The result of one accepted proposal batch: the saved project at its new
 * revision, and the changes that were written to the selected condition. The
 * changes are the record of what was accepted and from which method; the
 * project is the whole document, because a reviewable apply must not be a
 * partial write a reader has to reconstruct.
 */
export interface MassProposalView extends ProjectView {
  changes: Array<{
    target: string;
    condition_id: string;
    item_id: string;
    old_mass_t: number | null;
    new_mass_t: number | null;
    estimate: boolean;
    source: Record<string, unknown>;
    [key: string]: unknown;
  }>;
}

export interface ProjectSummary {
  project_id: string;
  name: string;
  revision: number;
  updated_at: string;
}

/** One canonical validator finding, in the server's own words. */
export interface ProjectDiagnostic {
  code: string;
  severity: 'error' | 'warning' | string;
  path: string;
  message: string;
  blocking?: boolean;
}

/** What a backup holds, counted rather than reproduced. */
export interface ProjectImportCounts {
  loading_conditions: number;
  weight_groups: number;
  weight_items: number;
  damage_scenarios: number;
  compartments: number;
  openings: number;
}

/**
 * The server's reading of one backup. It carries the source's own identity so
 * a reader can see which file they chose, and never carries the document.
 */
export interface ProjectImportPreview {
  source_id: string;
  name: string;
  source_revision: number;
  geometry_kind: string | null;
  counts: ProjectImportCounts;
  diagnostics: ProjectDiagnostic[];
}

/**
 * One SpringSharp 3.0 positional field, exactly as the core read it.
 *
 * `disposition` is what the reader is asked to confirm before anything is saved:
 * a field the migration used as an active value (`mapped`), one kept only as
 * evidence (`preserved`, `duplicate`), or the source file's trailing padding,
 * which the original reader ignored and this import preserves without treating
 * it as a parameter (`reserved`).
 */
export interface SshipMigrationField {
  index: number;
  line: number;
  name: string;
  raw: string;
  disposition: 'mapped' | 'preserved' | 'duplicate' | 'reserved' | string;
  destinations: string[];
  reason: string | null;
}

/** The source file as it was sent, identified rather than interpreted. */
export interface SshipSourceInfo {
  filename: string;
  sha256: string;
  byte_length: number;
  encoding: string;
  header: string;
  version: string;
  decimal_separator: string;
}

/**
 * What the migration read out of one source file.
 *
 * This is evidence about the file, not a converted project: the browser needs
 * the counts and the field list to explain itself, and nothing here is trusted
 * back on a save — the server parses the original bytes again.
 */
export interface SshipMigration {
  method_version: string;
  source: SshipSourceInfo;
  fields: SshipMigrationField[];
  /** Disposition counts, which together account for all 280 fields. */
  counts: Record<string, number>;
  diagnostics: ProjectDiagnostic[];
  /** What this migration cannot give the reader, in the core's own words. */
  limitations: Array<string | { code?: string; message?: string }>;
}

export interface SshipProjectImportPreview extends ProjectImportPreview {
  migration?: SshipMigration;
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
  diagnostics: Array<{ code?: string; severity?: string; /** Set when the diagnostic decides whether this stage may show a result. */ blocking?: boolean; path?: string; message?: string; stage?: string; source_path?: string }>;
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
