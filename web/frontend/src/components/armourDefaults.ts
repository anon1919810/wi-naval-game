import type { ConceptKey } from '../i18n/concept';
import type { RunView } from '../types';
import {
  balanceData, duplicateFixedArmourIds, fixedArmour, fixedArmourIdValid, fixedArmourKind,
} from './conceptDesign';
import { object, type Raw } from './formModel';

/**
 * The recovered default armour sizes: a declaration, a preview, and one pure copy.
 *
 * The eight dimensions are the recovered expression's own, evaluated by the core
 * and returned in a saved result. Nothing here evaluates a formula, converts a
 * foot, or invents a size: this module reads the server's preview, refuses to
 * touch anything the reader did not explicitly choose, and writes the armed
 * suggestion into the *existing* fixed-armour records in one atomic step.
 *
 * A copy is a plain draft edit, not an adoption. It preserves every record's id,
 * its kind, its binding, its thickness, the dimensions the reader did not select
 * and the source text already written there, and it appends one ordinary
 * annotation naming the method and the source run. That annotation is a statement
 * of where the numbers came from — it is not a signed mass receipt, it overwrites
 * nothing, and it is never truncated to a fixed width.
 */

export const ARMOUR_DEFAULTS_METHOD = 'sps-3b3-armour-defaults-v1';

/** The one family key the payload and the stage's method map use. */
export const ARMOUR_DEFAULTS_FAMILY = 'armour_defaults';

/**
 * The four recovered regions a default may ever fill.
 *
 * A deck, a conning tower and a bulge carry no recovered default length or
 * height, so they are never targets here: a size with no source is not a default.
 */
export const ARMOUR_DEFAULT_KINDS = ['belt_main', 'belt_ends', 'belt_upper', 'bulkhead'] as const;
export type ArmourDefaultKind = typeof ARMOUR_DEFAULT_KINDS[number];

/** The two declared dimensions a default may write, and no others. */
export const ARMOUR_DEFAULT_FIELDS = ['length_m', 'height_m'] as const;
export type ArmourDefaultField = typeof ARMOUR_DEFAULT_FIELDS[number];

/**
 * The eight canonical keys the server returns, in the recovered order, each with
 * the region and dimension it belongs to. The mapping is data, so the preview,
 * the reading and the comparison all name the same field the same way.
 */
export const ARMOUR_DEFAULT_VALUE_KEYS: ReadonlyArray<
readonly [ArmourDefaultKind, ArmourDefaultField, string]> = [
  ['belt_main', 'length_m', 'main_length_m'],
  ['belt_main', 'height_m', 'main_height_m'],
  ['belt_ends', 'length_m', 'ends_length_m'],
  ['belt_ends', 'height_m', 'ends_height_m'],
  ['belt_upper', 'length_m', 'upper_length_m'],
  ['belt_upper', 'height_m', 'upper_height_m'],
  ['bulkhead', 'length_m', 'bulkhead_length_m'],
  ['bulkhead', 'height_m', 'bulkhead_height_m'],
];

/** The wording each preview dimension prints under, shared by the panel and the reading. */
export const ARMOUR_DEFAULT_LABELS: Readonly<
Record<ArmourDefaultKind, Readonly<Record<ArmourDefaultField, ConceptKey>>>> = {
  belt_main: { length_m: 'concept.armourDefaults.mainLength', height_m: 'concept.armourDefaults.mainHeight' },
  belt_ends: { length_m: 'concept.armourDefaults.endsLength', height_m: 'concept.armourDefaults.endsHeight' },
  belt_upper: { length_m: 'concept.armourDefaults.upperLength', height_m: 'concept.armourDefaults.upperHeight' },
  bulkhead: { length_m: 'concept.armourDefaults.bulkheadLength', height_m: 'concept.armourDefaults.bulkheadHeight' },
};

/**
 * The domain the editor already enforces on these two declared dimensions.
 *
 * A suggestion outside it is never copied: the recovered expression's own
 * out-of-range answer is a reason to withhold, not a number to save and let the
 * editor refuse afterwards.
 */
export const ARMOUR_DEFAULT_DOMAIN: Readonly<Record<ArmourDefaultField, { min: number; max: number }>> = {
  length_m: { min: 0, max: 5000 }, height_m: { min: 0, max: 100 },
};

function valueKey(kind: ArmourDefaultKind, field: ArmourDefaultField): string {
  const row = ARMOUR_DEFAULT_VALUE_KEYS.find(([k, f]) => k === kind && f === field);
  return row === undefined ? '' : row[2];
}

/** Whether an unknown value is one of the two fields a default may write. */
function isField(value: unknown): value is ArmourDefaultField {
  return typeof value === 'string' && (ARMOUR_DEFAULT_FIELDS as readonly string[]).includes(value);
}

/** Whether an unknown value is one of the four regions a default may fill. */
export function isArmourDefaultKind(value: unknown): value is ArmourDefaultKind {
  return typeof value === 'string' && (ARMOUR_DEFAULT_KINDS as readonly string[]).includes(value);
}

// --- the declaration --------------------------------------------------------

/** The optional declaration, or `null` while the reader has not enabled it. */
export function armourDefaultsOf(config: Raw): Raw | null {
  const value = config.armour_defaults;
  return value === null || value === undefined ? null : object(value);
}

export function armourDefaultsEnabled(config: Raw): boolean {
  return armourDefaultsOf(config) !== null;
}

/**
 * A fresh declaration: one source and two optional fractions, all explicit nulls.
 *
 * Nothing is filled in. The fractions are the reader's own inputs to the core's
 * expression, and an unfinished declaration stays unfinished until they write it.
 */
export function newArmourDefaults(): Raw {
  return { source: null, forecastle_fraction: null, quarterdeck_fraction: null };
}

export function patchArmourDefaults(config: Raw, patch: Raw): Raw {
  return { ...config,
    armour_defaults: { ...(armourDefaultsOf(config) ?? newArmourDefaults()), ...patch } };
}

/** Disabling writes an explicit null; the feature stays absent from a new project. */
export function removeArmourDefaults(config: Raw): Raw {
  return { ...config, armour_defaults: null };
}

// --- the saved reading ------------------------------------------------------

/** The one `design_balance.armour_defaults` reading, or `null` when never declared. */
export function armourDefaultsReading(run: RunView | null): Raw | null {
  const value = balanceData(run).armour_defaults;
  return value === null || value === undefined ? null : object(value);
}

export interface ArmourDefaultAvailability {
  state: 'available' | 'unavailable';
  reason: string | null;
}

/**
 * One field's own availability, read exactly as the core wrote it.
 *
 * The record publishes a `state` per key; a documented `status` is accepted as the
 * same fact so a core that names it either way is read, not guessed at. Anything
 * that is not an explicit `available` is unavailable — the safe reading.
 */
export function armourDefaultAvailability(reading: Raw | null, key: string): ArmourDefaultAvailability {
  const entry = object(object(reading?.availability)[key]);
  const state = entry.state ?? entry.status;
  return { state: state === 'available' ? 'available' : 'unavailable',
    reason: typeof entry.reason === 'string' && entry.reason !== '' ? entry.reason : null };
}

/** One canonical number, or `null` when it is absent or not finite. */
export function armourDefaultValue(reading: Raw | null, key: string): number | null {
  const value = object(reading?.values)[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

export interface ArmourDefaultCandidate {
  kind: ArmourDefaultKind;
  field: ArmourDefaultField;
  key: string;
  value: number | null;
  available: boolean;
  reason: string | null;
  /** A finite value the editor's own domain accepts: the only thing selectable. */
  selectable: boolean;
}

/** One region's one dimension, as a preview the reader may or may not choose. */
export function armourDefaultCandidate(reading: Raw | null, kind: ArmourDefaultKind,
  field: ArmourDefaultField): ArmourDefaultCandidate {
  const key = valueKey(kind, field);
  const availability = armourDefaultAvailability(reading, key);
  const value = armourDefaultValue(reading, key);
  const domain = ARMOUR_DEFAULT_DOMAIN[field];
  const inDomain = value !== null && value >= domain.min && value <= domain.max;
  return { kind, field, key, value, available: availability.state === 'available',
    reason: availability.reason, selectable: availability.state === 'available' && inDomain };
}

// --- the copy ---------------------------------------------------------------

/** One record the reader explicitly chose, and the dimensions to fill in it. */
export interface ArmourDefaultSelection {
  record_id: string;
  fields: ArmourDefaultField[];
}

export type ArmourDefaultRefusal =
  | 'no-run' | 'method-conflict' | 'no-selection' | 'repeated-record'
  | 'missing-record' | 'duplicate-record' | 'invalid-id' | 'illegal-kind'
  | 'no-fields' | 'duplicate-field' | 'illegal-field'
  | 'unavailable' | 'unknown-value' | 'out-of-domain';

export interface ArmourDefaultPlan {
  ok: boolean;
  reason: ArmourDefaultRefusal | null;
  /** The updated draft when `ok`, otherwise the untouched input configuration. */
  config: Raw;
}

/**
 * The one plain annotation a copy appends to a record's own source text.
 *
 * It names the method and the run the suggestion came from, and nothing else: it
 * does not claim a server mass, a signature or an adoption.
 */
export function armourDefaultAnnotation(sourceRunId: string): string {
  return `[${ARMOUR_DEFAULTS_METHOD} · run ${sourceRunId}]`;
}

/**
 * Plan the whole copy before writing any of it.
 *
 * The entire selection is validated first — a current run, this method's own
 * preview, and every chosen record and dimension — so a plan either returns one
 * fully updated draft or leaves the input configuration exactly as it was. There
 * is no half-applied record: the caller can commit the returned `config` without
 * ever seeing a partially written one.
 */
export function planArmourDefaults(config: Raw, preview: Raw | null,
  selections: ReadonlyArray<unknown>, sourceRunId: string | null): ArmourDefaultPlan {
  const refused = (reason: ArmourDefaultRefusal): ArmourDefaultPlan => ({ ok: false, reason, config });
  // A copy may only be attributed to a current saved run. With no run there is
  // nothing to name, and an unnamed suggestion is never written.
  if (typeof sourceRunId !== 'string' || sourceRunId === '') return refused('no-run');
  // The preview must be this method's own result. Absent or mismatched is a
  // conflict, never a guess at what produced the numbers.
  if (preview === null || preview.method_version !== ARMOUR_DEFAULTS_METHOD) {
    return refused('method-conflict');
  }
  if (!Array.isArray(selections) || selections.length === 0) return refused('no-selection');

  const records = fixedArmour(config);
  const duplicates = new Set(duplicateFixedArmourIds(config));
  const resolved: Array<{ record: Raw; fields: Array<[ArmourDefaultField, number]> }> = [];
  const chosen = new Set<string>();
  for (const raw of selections) {
    const selection = object(raw);
    const id = selection.record_id;
    if (typeof id !== 'string' || !fixedArmourIdValid(id)) return refused('invalid-id');
    // The same record chosen twice is two intentions for one field; refuse.
    if (chosen.has(id)) return refused('repeated-record');
    chosen.add(id);
    if (duplicates.has(id)) return refused('duplicate-record');
    const record = records.find(row => row.id === id);
    if (record === undefined) return refused('missing-record');
    const kind = fixedArmourKind(record.kind);
    if (kind === null || !isArmourDefaultKind(kind)) return refused('illegal-kind');
    const fields = selection.fields;
    if (!Array.isArray(fields) || fields.length === 0) return refused('no-fields');
    const seenFields = new Set<string>();
    const pairs: Array<[ArmourDefaultField, number]> = [];
    for (const field of fields) {
      if (!isField(field)) return refused('illegal-field');
      if (seenFields.has(field)) return refused('duplicate-field');
      seenFields.add(field);
      const candidate = armourDefaultCandidate(preview, kind, field);
      if (!candidate.available) return refused('unavailable');
      if (candidate.value === null) return refused('unknown-value');
      if (!candidate.selectable) return refused('out-of-domain');
      pairs.push([field, candidate.value]);
    }
    resolved.push({ record, fields: pairs });
  }

  // Only now is anything written: one clone per record, so the input is untouched.
  const next = records.map(record => ({ ...record }));
  const byId = new Map<string, Raw>();
  for (const record of next) {
    if (typeof record.id === 'string' && record.id !== '') byId.set(record.id, record);
  }
  const annotation = armourDefaultAnnotation(sourceRunId);
  for (const { record, fields } of resolved) {
    const target = byId.get(String(record.id));
    if (target === undefined) return refused('missing-record');
    for (const [field, value] of fields) target[field] = value;
    const existing = typeof target.source === 'string' ? target.source : '';
    // Appended once: an identical annotation already there is not repeated, and
    // the existing text is neither overwritten nor truncated.
    if (!existing.includes(annotation)) {
      target.source = existing === '' ? annotation : `${existing} ${annotation}`;
    }
  }
  return { ok: true, reason: null, config: { ...config, fixed_armour: next } };
}

/**
 * The pure copy, as one configuration in and one configuration out.
 *
 * Returns the untouched input when the selection is invalid, so a caller that
 * commits the result can never store a partial edit.
 */
export function applyArmourDefaults(config: Raw, preview: Raw | null,
  selections: ReadonlyArray<unknown>, sourceRunId: string | null): Raw {
  return planArmourDefaults(config, preview, selections, sourceRunId).config;
}
