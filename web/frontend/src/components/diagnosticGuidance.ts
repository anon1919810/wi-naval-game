import type { Chapter } from './ProjectNav';
import type { ProjectDocument, StageEnvelope } from '../types';
import type { WorkspaceKey } from '../i18n/workspace';

/**
 * Where one saved diagnostic can be followed to, and what it can honestly claim.
 *
 * A diagnostic carries a path into the project that was analysed, never into the
 * project on screen. This resolver therefore reads the *source snapshot* first:
 * an indexed ledger path such as `$.weight_groups[2].items[1].mass_t` names a
 * group and an item **by the ids the source run actually saw**, and only those
 * ids are looked up in the live project. A path is never followed by live index,
 * because editing a ledger reorders it, and a reader would be sent to another
 * vessel's item — or to an item that has since been removed.
 *
 * Nothing here decides whether a project *can* be calculated. It resolves where
 * a field lives, or states truthfully that there is nothing to focus. Paths that
 * point at generated output (`$.stages.*`, `$.diagnostics[...]`), at result
 * metadata, or at anything unrecognised stay plain evidence: a fabricated link
 * to a field that does not exist is worse than no link at all.
 *
 * Every sentence this module writes is application-owned prose, so the words are
 * looked up rather than embedded. The lookup is a parameter and not a hidden
 * global: the same path resolves to the same control, the same chapter and the
 * same evidence in either language, and the diagnostic's own `path` is passed
 * through verbatim because it is the record the reader is checking.
 */

/** The resolver's dictionary, passed in so this module stays a pure function. */
export type Copy = (key: WorkspaceKey, params?: Readonly<Record<string, string | number>>) => string;

/** A diagnostic as the saved result stores it. */
export type Diagnostic = StageEnvelope['diagnostics'][number];

/**
 * - `control` — a real editable control exists and takes focus.
 * - `section`  — a real chapter area exists and takes focus (request area,
 *   ledger, project JSON).
 * - `evidence` — nothing on screen corresponds to this path.
 */
export type GuidanceKind = 'control' | 'section' | 'evidence';

export interface DiagnosticLocation {
  kind: GuidanceKind;
  /** The chapter a jump selects; null when there is nothing to jump to. */
  chapter: Chapter | null;
  /** Id of the element that takes focus; null when there is nothing to focus. */
  target: string | null;
  /** What the reader is being taken to, in the reader's own words. */
  label: string;
  /** The diagnostic's original path, verbatim. */
  path: string;
  /** One truthful sentence about what this location can and cannot do. */
  note: string;
}

export interface DiagnosticSource {
  /** The saved input snapshot the diagnostic was computed against. */
  snapshot: ProjectDocument | null;
  /** The live project the reader is editing now. */
  live: ProjectDocument | null;
}

/** Chapter-level targets. Each id is mounted by the workspace itself. */
export const LEDGER_SECTION = 'guidance-ledger';
export const REQUEST_PERFORMANCE = 'guidance-request-performance';
export const REQUEST_DAMAGE = 'guidance-request-damage';
/** The project document editor every chapter owns; focus lands in its textarea. */
export const PROJECT_JSON = 'chapter-json';
export const CHAPTER_HEAD = 'guidance-chapter-head';

/** The six hull scalars the workspace edits as their own controls. */
const HULL_LABELS: Record<string, WorkspaceKey> = {
  loa_m: 'field.loa_m', length_m: 'field.loa_m', lwl_m: 'field.lwl_m', beam_m: 'field.beam_m',
  draught_normal_m: 'field.draught_normal_m', draft_m: 'field.draught_normal_m',
  block_coeff: 'field.block_coeff', waterplane_coeff: 'field.waterplane_coeff',
};

/** The legacy spellings one control answers to, never a second control. */
const HULL_ALTERNATES: Record<string, string> = { length_m: 'loa_m', draft_m: 'draught_normal_m' };

/** The three ledger facts each ledger row owns as its own control. */
const LEDGER_LABELS: Record<string, WorkspaceKey> = {
  mass_t: 'editor.ledger.mass', x_m: 'editor.ledger.position', source: 'editor.ledger.source',
};

/** Project roots the JSON chapter edits in full; nothing else is claimed here. */
const PROJECT_JSON_ROOTS = new Set([
  'geometry', 'deck', 'systems', 'compartments', 'openings', 'loading_conditions',
  'flooding_scenarios', 'resistance_scenarios', 'endurance_scenarios', 'damage_presets',
  'display_preferences', 'metadata',
]);

/**
 * Control identity. Group and item ids are project data, so the whole tuple is
 * encoded as one value: a separator-joined form collides for ids that contain
 * the separator, and two different ledger rows must never share one id.
 */
export function ledgerGuidanceId(groupId: string, itemId: string, field: string): string {
  return `guidance-ledger-${encodeURIComponent(JSON.stringify([groupId, itemId, field]))}`;
}

export function hullGuidanceId(key: string): string {
  return `guidance-hull-${key}`;
}

type Segment = { key: string } | { index: number };

/**
 * A strict reader for the `$`-rooted paths the coordinator writes. Anything it
 * does not fully understand returns null instead of a partial reading, so a
 * malformed path degrades to evidence rather than to a wrong field.
 */
export function parseDiagnosticPath(path: string): Segment[] | null {
  let rest = String(path ?? '').trim();
  if (!rest.startsWith('$')) return null;
  rest = rest.slice(1);
  const segments: Segment[] = [];
  while (rest.length > 0) {
    if (rest[0] === '.') {
      const name = /^\.([A-Za-z_][A-Za-z0-9_]*)/.exec(rest);
      if (!name) return null;
      segments.push({ key: name[1] });
      rest = rest.slice(name[0].length);
    } else if (rest[0] === '[') {
      const index = /^\[(\d+)\]/.exec(rest);
      if (index) { segments.push({ index: Number(index[1]) }); rest = rest.slice(index[0].length); continue; }
      const quoted = /^\["([^"\\]*)"\]/.exec(rest);
      if (quoted) { segments.push({ key: quoted[1] }); rest = rest.slice(quoted[0].length); continue; }
      return null;
    } else return null;
  }
  return segments;
}

function keyOf(segment: Segment | undefined): string | undefined {
  return segment && 'key' in segment ? segment.key : undefined;
}

function indexOf(segment: Segment | undefined): number | undefined {
  return segment && 'index' in segment ? segment.index : undefined;
}

function entries(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.filter(entry => !!entry && typeof entry === 'object' && !Array.isArray(entry)) as Record<string, unknown>[] : [];
}

function entryAt(list: Record<string, unknown>[], index: number | undefined): Record<string, unknown> | undefined {
  return index === undefined ? undefined : list[index];
}

function idOf(entry: Record<string, unknown> | undefined): string | null {
  return typeof entry?.id === 'string' && entry.id !== '' ? entry.id : null;
}

function evidence(path: string, note: string): DiagnosticLocation {
  return { kind: 'evidence', chapter: null, target: null, label: '', path, note };
}

function control(path: string, chapter: Chapter, target: string, label: string, note: string): DiagnosticLocation {
  return { kind: 'control', chapter, target, label, path, note };
}

function section(path: string, chapter: Chapter, target: string, label: string, note: string): DiagnosticLocation {
  return { kind: 'section', chapter, target, label, path, note };
}

function hullLocation(w: Copy, path: string, segments: Segment[]): DiagnosticLocation {
  const field = keyOf(segments[1]);
  const label = field ? w(HULL_LABELS[field]) : undefined;
  const control = field ? HULL_ALTERNATES[field] ?? field : undefined;
  // Only the number itself is a control, and one spelling of it. A declared
  // source has no editor of its own in the workspace, so it is never dressed up
  // as the dimension: typing a number would not repair missing provenance.
  if (label && control && segments.length === 2) return hullControl(w, path, control, label);
  if (field === 'warnings') return evidence(path, w('guidance.hullWarnings'));
  return section(path, 'json', PROJECT_JSON, w('guidance.label.projectData'), w('guidance.hullJson', { path }));
}

function hullControl(w: Copy, path: string, key: string, label: string): DiagnosticLocation {
  return { kind: 'control', chapter: 'hull', target: hullGuidanceId(key), label, path,
    note: w('guidance.hullControl', { label }) };
}

function ledgerLocation(w: Copy, path: string, segments: Segment[], source: DiagnosticSource): DiagnosticLocation {
  // The indices are read against the source snapshot, never against the live
  // ledger: only the ids that run actually saw may be looked up now.
  const groupIndex = indexOf(segments[1]);
  const snapshotGroup = entryAt(entries(source.snapshot?.weight_groups), groupIndex);
  const groupId = idOf(snapshotGroup);
  if (groupIndex === undefined || !groupId) {
    // A whole ledger, a group or a group list has no editor anywhere: the
    // workspace only edits rows that already exist, so the document is the only
    // honest place to go.
    return section(path, 'json', PROJECT_JSON, w('guidance.label.projectData'), w('guidance.ledgerWhole', { path }));
  }
  if (keyOf(segments[2]) !== 'items') {
    return section(path, 'json', PROJECT_JSON, w('guidance.label.projectData'), w('guidance.ledgerGroup', { path }));
  }
  const itemIndex = indexOf(segments[3]);
  if (itemIndex === undefined) {
    return section(path, 'json', PROJECT_JSON, w('guidance.label.projectData'), w('guidance.ledgerItems', { path }));
  }
  const snapshotItem = entryAt(entries(snapshotGroup?.items), itemIndex);
  const itemId = idOf(snapshotItem);
  if (!itemId) {
    return evidence(path, w('guidance.ledgerNoId'));
  }
  // Removal is checked before any fallback: an item that is gone is not
  // something the reader can edit anywhere, least of all in the document.
  const liveGroups = entries(source.live?.weight_groups);
  const liveGroupIndex = liveGroups.findIndex(entry => entry.id === groupId);
  const liveGroup = liveGroups[liveGroupIndex];
  const liveItems = entries(liveGroup?.items);
  const liveItemIndex = liveItems.findIndex(entry => entry.id === itemId);
  if (liveGroupIndex === -1 || liveItemIndex === -1) {
    return evidence(path, w('guidance.ledgerRemoved', { group: groupId, item: itemId, path }));
  }
  const currentPath = `$.weight_groups[${liveGroupIndex}].items[${liveItemIndex}]`;
  const field = keyOf(segments[4]);
  const fieldLabel = field ? w(LEDGER_LABELS[field]) : undefined;
  // A scalar control exists for exactly `…items[i].mass_t|x_m|source` and nothing
  // longer: `…mass_t.value` is not that control.
  if (segments.length === 5 && field && fieldLabel) {
    return control(path, 'weights', ledgerGuidanceId(groupId, itemId, field), `${groupId} · ${itemId} · ${fieldLabel}`,
      w('guidance.ledgerField', { group: groupId, item: itemId, field: fieldLabel }));
  }
  if (segments.length === 4) {
    return section(path, 'weights', LEDGER_SECTION, w('guidance.label.weights'),
      w('guidance.ledgerRow', { path: currentPath, group: groupId, item: itemId }));
  }
  return section(path, 'json', PROJECT_JSON, w('guidance.label.projectData'),
    w('guidance.ledgerRowMoved', { group: groupId, item: itemId, path: currentPath, original: path }));
}

function conditionsLocation(w: Copy, path: string, segments: Segment[], source: DiagnosticSource): DiagnosticLocation {
  const index = indexOf(segments[1]);
  const snapshot = entryAt(entries(source.snapshot?.loading_conditions), index);
  const conditionId = idOf(snapshot);
  if (conditionId === null) {
    return section(path, 'json', PROJECT_JSON, w('guidance.label.projectData'), w('guidance.conditionsList', { path }));
  }
  const live = entries(source.live?.loading_conditions);
  const current = live.findIndex(entry => entry.id === conditionId);
  if (current === -1) {
    return evidence(path, w('guidance.conditionRemoved', { condition: conditionId, path }));
  }
  return section(path, 'json', PROJECT_JSON, w('guidance.label.projectData'),
    w('guidance.conditionMoved', { condition: conditionId, index: current, path }));
}

function optionsLocation(w: Copy, path: string, segments: Segment[]): DiagnosticLocation {
  const head = keyOf(segments[1]);
  // The flooding request — including the shared environment density — is the
  // damage chapter's own request area; everything else is the performance one.
  if (head === 'flooding' || (head === 'equilibrium' && keyOf(segments[2]) === 'rho_t_m3')) {
    return section(path, 'damage', REQUEST_DAMAGE, w('guidance.label.damageRequest'), w('guidance.requestDamage', { path }));
  }
  return section(path, 'performance', REQUEST_PERFORMANCE, w('guidance.label.performanceRequest'), w('guidance.requestPerformance', { path }));
}

/**
 * The one resolver both surfaces share. It returns null only when there is no
 * path at all; a path it cannot place is still returned, as evidence, so the
 * caller can say so instead of quietly dropping the finding.
 */
export function resolveDiagnosticPath(path: unknown, source: DiagnosticSource, w: Copy): DiagnosticLocation | null {
  if (typeof path !== 'string' || path.trim() === '') return null;
  const literal = path.trim();
  const segments = parseDiagnosticPath(literal);
  if (!segments || segments.length === 0) {
    return evidence(literal, w('guidance.unparseable'));
  }
  const root = keyOf(segments[0]);
  if (!root) return evidence(literal, w('guidance.noRoot'));
  if (root === 'hull') return hullLocation(w, literal, segments);
  if (root === 'weight_groups') return ledgerLocation(w, literal, segments, source);
  if (root === 'loading_conditions') return conditionsLocation(w, literal, segments, source);
  if (root === 'options') return optionsLocation(w, literal, segments);
  if (PROJECT_JSON_ROOTS.has(root)) {
    return section(literal, 'json', PROJECT_JSON, w('guidance.label.projectData'), w('guidance.knownRoot', { path }));
  }
  return evidence(literal, w('guidance.notEditable'));
}

/**
 * The finding's own location, preferring a path that can actually be followed.
 * Both the diagnostic's `path` and its `source_path` are evidence and both stay
 * on screen; only the navigation is chosen here.
 */
export function resolveDiagnosticLocation(diagnostic: Diagnostic, source: DiagnosticSource, w: Copy): DiagnosticLocation | null {
  const found = [diagnostic.path, diagnostic.source_path]
    .map(candidate => resolveDiagnosticPath(candidate, source, w))
    .filter((entry): entry is DiagnosticLocation => entry !== null);
  if (found.length === 0) return null;
  return found.find(entry => entry.kind !== 'evidence') ?? found[0];
}

/**
 * A native address back into the project, in the tool's own hash route. The run
 * id stays in the address because every diagnostic belongs to the run that
 * produced it; refreshing, copying and Back/Forward all resolve to the same
 * project and the same source run.
 */
export function diagnosticHref(projectId: string, runId: string, path: string): string {
  return `#/projects/${encodeURIComponent(projectId)}/diagnostics/${encodeURIComponent(runId)}/${encodeURIComponent(path)}`;
}

function safeDecode(segment: string): string | null {
  try { return decodeURIComponent(segment); } catch { return null; }
}

/**
 * What the address says, in three honest parts. `none` is an ordinary project
 * address; `target` is a usable diagnostic link; `malformed` is a diagnostic
 * address that cannot be trusted — a foreign project, a missing segment, a
 * broken percent-escape or a path that is not a path. The third is reported to
 * the reader instead of being passed off as a normal arrival.
 */
export type DiagnosticTail =
  | { kind: 'none' }
  | { kind: 'target'; runId: string; path: string }
  | { kind: 'malformed'; reason: string };

export function readDiagnosticTail(hash: string, projectId: string, w: Copy): DiagnosticTail {
  const parts = String(hash ?? '').replace(/^#/, '').replace(/^\/+/, '').split('/');
  // An ordinary project address carries nothing to do; a `…/diagnostics/…` tail
  // is one, and is judged rather than assumed.
  if (parts[0] !== 'projects' || parts[2] !== 'diagnostics') return { kind: 'none' };
  if (parts.length !== 5) return { kind: 'malformed', reason: w('guidance.tail.incomplete') };
  const id = safeDecode(parts[1]);
  const runId = safeDecode(parts[3]);
  const path = safeDecode(parts[4]);
  if (id === null || runId === null || path === null) return { kind: 'malformed', reason: w('guidance.tail.undecodable') };
  if (id !== projectId) return { kind: 'malformed', reason: w('guidance.tail.foreign') };
  if (runId === '') return { kind: 'malformed', reason: w('guidance.tail.noRun') };
  if (!path.startsWith('$')) return { kind: 'malformed', reason: w('guidance.tail.notPath') };
  return { kind: 'target', runId, path };
}

/**
 * The diagnostic named by `hash`, or null when it is not this project's own
 * diagnostic address. The reader stays where they are instead of being sent to
 * a wrong field.
 */
export function readDiagnosticTarget(hash: string, projectId: string, w: Copy): { runId: string; path: string } | null {
  const tail = readDiagnosticTail(hash, projectId, w);
  return tail.kind === 'target' ? { runId: tail.runId, path: tail.path } : null;
}