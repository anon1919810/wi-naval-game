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

export type StageStatus = 'completed' | 'partial' | 'not_requested' | 'unavailable' | 'failed' | 'canceled' | 'model_limit';
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

/**
 * One compatibility finding, exactly as the core wrote it.
 *
 * `field` and `path` are addresses the core chose; `code` and `message` are its
 * own words. Nothing here is translated: a reader is looking at the source
 * method's finding, so the finding is shown as saved.
 */
export interface Sps3b3Diagnostic {
  code?: string;
  severity?: string;
  field?: string;
  path?: string;
  blocking?: boolean;
  message?: string;
  [key: string]: unknown;
}

/**
 * The compatibility declaration stored at `$.sps_3b3_design`.
 *
 * `parameters` holds source page positions by their register names and keeps
 * the source page's own unit; `null` is an unfilled field, never a zero.
 * `editing` holds the edit sovereignty the source file never saved.
 */
export interface Sps3b3Design {
  schema: string;
  source: string | null;
  parameters: Record<string, unknown>;
  editing: Record<string, unknown>;
  notes: string | null;
  [key: string]: unknown;
}

/** One editable compatibility field, as the catalogue reports it. */
export interface Sps3b3Field {
  key: string;
  name: string;
  source_index: number;
  page: string;
  label: string;
  kind: string;
  unit: string | null;
  unit_resolved?: string | null;
  unit_choices?: string[] | null;
  choices?: string[] | null;
  scale_ref?: string | null;
  allows_unselected?: boolean;
  min_value?: number | null;
  max_value?: number | null;
  aliases?: string[];
  [key: string]: unknown;
}

/** The 222-field catalogue, with its page grouping. */
export interface Sps3b3Catalog {
  fields: Sps3b3Field[];
  pages: Partial<Record<string, string[]>>;
  page_order: string[];
  page_labels: Record<string, string>;
  controls?: Record<string, unknown>;
  [key: string]: unknown;
}

/**
 * The compatibility compute result, written into the saved stage's `data`.
 *
 * `report` is the one chapter model the core builds for every output; it is
 * optional here because a result saved before the report existed carries none,
 * and this interface must not fabricate the paragraphs a missing report lacks.
 */
export interface Sps3b3Result {
  schema?: string;
  method_version?: string;
  status?: string;
  design?: Sps3b3Design | null;
  hull?: Record<string, unknown> | null;
  freeboard?: Record<string, unknown> | null;
  guns?: Record<string, unknown> | null;
  auxiliary?: Record<string, unknown> | null;
  armour?: Record<string, unknown> | null;
  engine?: Record<string, unknown> | null;
  performance?: Record<string, unknown> | null;
  diagnostics?: Sps3b3Diagnostic[];
  provenance?: Record<string, unknown> | null;
  report?: { sections?: Array<{ id: string; title: string; lines: string[] }>; text?: string } | null;
  [key: string]: unknown;
}

/** One preview reply: the new declaration, its preview and the diagnostics. */
export interface Sps3b3Preview {
  design: Sps3b3Design;
  preview: Sps3b3Result | null;
  diagnostics: Sps3b3Diagnostic[];
  status: string;
}

/** `GET /api/sps3b3/default` — the original fresh declaration. */
export interface Sps3b3DefaultReply { design: Sps3b3Design }

/** `POST /api/sps3b3/import-preview` — the source and what it became. */
export interface Sps3b3ImportReply {
  design: Sps3b3Design;
  source: SshipSourceInfo | null;
  diagnostics: Sps3b3Diagnostic[];
}

/** `POST /api/sps3b3/from-migration` — a declaration from an archived migration. */
export interface Sps3b3MigrationReply { design: Sps3b3Design }

/* ------------------------------------------------------------------ native */
/* The one authoritative ship design and its managed ledger.                  */

/**
 * One managed mass binding of a design role.
 *
 * `item_ids` names the ledger items that carry the role and `mode` says how:
 * `estimated` is the product's own managed estimate and admits exactly one owned
 * target, while `declared` is the reader's explicit adoption and may accumulate
 * several. A blank binding is `null` on the design, not an empty entry here.
 */
export interface ShipDesignMassBinding {
  item_ids: string[];
  mode: 'estimated' | 'declared';
  [key: string]: unknown;
}

/**
 * The one authoritative declaration stored at `$.ship_design`.
 *
 * `parameters` reuses the recovered 222-field names and their source units;
 * `null` is an unfilled field, never a zero. `condition_id` is the explicit,
 * non-derived basis condition the managed estimate serves, and `mass_bindings`
 * records which ledger items carry each role. There is one editable fact: a
 * source-view (`Sps3b3Design`) is a temporary adapter, never a second source.
 */
export interface ShipDesign {
  schema: string;
  source: string | null;
  parameters: Record<string, unknown>;
  editing: Record<string, unknown>;
  notes: string | null;
  condition_id: string | null;
  mass_bindings: Record<string, ShipDesignMassBinding>;
  [key: string]: unknown;
}

/** One role's managed estimate and its binding state in the native ledger. */
export interface ShipDesignLedgerEntry {
  role: string;
  estimate_t?: number | null;
  selected_mass_t?: number | null;
  target_mass_t?: number | null;
  difference_t?: number | null;
  mode?: 'estimated' | 'declared' | null;
  item_ids?: string[];
  resolved?: boolean;
  bound?: boolean;
  [key: string]: unknown;
}

/**
 * The one managed ledger a native result carries.
 *
 * `roles` is the whole role table and `needs_binding` names the ledger items
 * still without an owner. The scalar balance sits on the ledger itself so the
 * selected, estimated and target figures are read from one place.
 */
export interface ShipDesignLedger {
  schema?: string;
  owner?: string;
  condition_id?: string | null;
  basis_condition_id?: string | null;
  roles?: Record<string, Omit<ShipDesignLedgerEntry, 'role'>>;
  selected_mass_t?: number | null;
  estimated_mass_t?: number | null;
  target_displacement_t?: number | null;
  difference_t?: number | null;
  needs_binding?: string[];
  complete?: boolean;
  [key: string]: unknown;
}

/** The unified balance: selected, estimated and target, all in tonnes. */
export interface ShipDesignBalance {
  selected_mass_t?: number | null;
  estimated_mass_t?: number | null;
  target_displacement_t?: number | null;
  difference_t?: number | null;
  [key: string]: unknown;
}

/**
 * The native compute result, saved as the `ship_design` stage's `data`.
 *
 * It carries the usual reported sections plus the one ledger, the unified
 * balance, the source-view it was adapted from and the basis condition its
 * balance belongs to. `basis_condition_id` is what labels this balance; a
 * physical run selected under another condition never relabels it.
 */
export interface ShipDesignResult extends Sps3b3Result {
  ledger?: ShipDesignLedger | null;
  balance?: ShipDesignBalance | null;
  source_design?: Sps3b3Design | null;
  basis_condition_id?: string | null;
  review?: Record<string, unknown> | null;
}

/**
 * One native design reply.
 *
 * `project` is the whole governed document: its `ship_design` is authoritative
 * and its `hull` carries the SI projection the existing kernels read. `design`
 * is the temporary source-view for the existing field widgets, and it is never
 * written back as a second source.
 */
export interface DesignReply {
  project: ProjectDocument;
  design: Sps3b3Design;
  preview: ShipDesignResult | null;
  status: string;
  diagnostics: Sps3b3Diagnostic[];
}
