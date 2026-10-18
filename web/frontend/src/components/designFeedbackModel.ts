import { number, object, type Raw } from './formModel';
import { balanceOf, basisConditionId, CHAPTER_SOURCE_PAGE, ledgerEntries } from './shipDesign';
import { SHIP_DESIGN_METHOD_VERSION, SHIP_DESIGN_RESULT_SCHEMA, SHIP_DESIGN_STAGE, shipDesignOf } from './sps3b3Model';
import { designFeedbackCopy, type DesignFeedbackKey } from '../i18n/designFeedback';
import type { Dimension } from './units';
import type { SiteLanguage } from '../portfolio/LanguageProvider';
import type { AnalysisResult, ProjectDocument, ShipDesign, ShipDesignResult } from '../types';

/**
 * The draft feedback readers: what a saved revision and a live draft differ by,
 * and what two frozen native results differ by.
 *
 * This module is pure. It reads only the values it is handed — a governed
 * project document, a native result, or a frozen analysis result — and it never
 * calls the preview endpoint, a formula or a converter. The sixteen readings are
 * exactly the saved paths the native report already prints; the changed inputs
 * are the recovered register names the declaration stores; the changed roles are
 * the ledger's own rows. Nothing here derives a number.
 *
 * Four rules run through every function below:
 *
 * - **A direction is an argument order.** `before` is the left column and `after`
 *   the right; every delta is `after − before`. The workbench passes the saved
 *   revision then the draft (draft − saved); the report passes the current run
 *   then the comparison run (comparison − current), which is the same sign the
 *   full comparison table already uses beside it.
 * - **Identity gates numbers.** A schema, method or basis mismatch withholds
 *   every numeric difference while leaving the reasons visible. An unestablished
 *   identity is not a matching one.
 * - **Absent is not zero.** A missing field, an explicit null and a non-finite
 *   value each stay unknown; a genuine zero is a reading. A zero baseline prints
 *   an absolute change and no percentage.
 * - **A stale preview is not the draft.** While an edit is pending or has
 *   failed, the current readings are withheld rather than presented as latest.
 */

/** One saved native field, with the label and the unit identity it is read in. */
interface ReadingSpec {
  key: string;
  label: DesignFeedbackKey;
  /** The native section the field sits in; `balance` reads the reconciled balance. */
  section: string;
  /**
   * The candidate fields, in preference order. The first field the result
   * actually carries supplies the reading; a field that is present but null is a
   * declared unknown and is not skipped over for a fallback.
   */
  fields: readonly string[];
  dimension?: Dimension;
  storedUnit?: string;
  canonicalUnit?: string;
}

/**
 * The sixteen readings, in one fixed order, all read from a saved native result.
 *
 * The recovered horsepower, the range, the empirical stability screen, the
 * source empirical height and the relative hull strengths have no convertible
 * reader unit, so they keep the unit the source saved. The stability score and
 * the three strength terms state their own name. The hull strength is the
 * composite figure and each of the cross-sectional and longitudinal figures
 * stands on its own: subtracting the composite from a component, or one
 * component from the other, would subtract two different quantities and call the
 * answer a change. When any one is absent its reading is unknown.
 */
const READING_SPECS: ReadonlyArray<ReadingSpec> = [
  { key: 'balance.selected_mass_t', label: 'feedback.reading.selectedMass',
    section: 'balance', fields: ['selected_mass_t'], dimension: 'mass', storedUnit: 't' },
  { key: 'balance.estimated_mass_t', label: 'feedback.reading.estimatedMass',
    section: 'balance', fields: ['estimated_mass_t'], dimension: 'mass', storedUnit: 't' },
  { key: 'balance.target_displacement_t', label: 'feedback.reading.targetDisplacement',
    section: 'balance', fields: ['target_displacement_t'], dimension: 'mass', storedUnit: 't' },
  { key: 'balance.difference_t', label: 'feedback.reading.difference',
    section: 'balance', fields: ['difference_t'], dimension: 'mass', storedUnit: 't' },
  { key: 'engine.speedMax', label: 'feedback.reading.speedMax',
    section: 'engine', fields: ['speedMax'], dimension: 'speed', storedUnit: 'kn' },
  { key: 'engine.speedCruise', label: 'feedback.reading.speedCruise',
    section: 'engine', fields: ['speedCruise'], dimension: 'speed', storedUnit: 'kn' },
  { key: 'engine.hpMax', label: 'feedback.reading.powerMax',
    section: 'engine', fields: ['hpMax'], canonicalUnit: 'source hp' },
  { key: 'engine.hpCruise', label: 'feedback.reading.powerCruise',
    section: 'engine', fields: ['hpCruise'], canonicalUnit: 'source hp' },
  { key: 'engine.range', label: 'feedback.reading.range',
    section: 'engine', fields: ['range'], canonicalUnit: 'nmi' },
  { key: 'performance.stability', label: 'feedback.reading.stability',
    section: 'performance', fields: ['stability'], canonicalUnit: 'empirical score' },
  { key: 'performance.metacentre', label: 'feedback.reading.metacentre',
    section: 'performance', fields: ['metacentre'], canonicalUnit: 'ft' },
  { key: 'performance.rollPeriod', label: 'feedback.reading.rollPeriod',
    section: 'performance', fields: ['rollPeriod'], canonicalUnit: 's' },
  { key: 'performance.strength', label: 'feedback.reading.hullStrength',
    section: 'performance', fields: ['strengthComp'], canonicalUnit: 'empirical score' },
  { key: 'performance.strengthCross', label: 'feedback.reading.hullStrengthCross',
    section: 'performance', fields: ['strengthCross'], canonicalUnit: 'empirical score' },
  { key: 'performance.strengthLong', label: 'feedback.reading.hullStrengthLong',
    section: 'performance', fields: ['strengthLong'], canonicalUnit: 'empirical score' },
  { key: 'performance.seakeeping', label: 'feedback.reading.seakeeping',
    section: 'performance', fields: ['seakeeping'], canonicalUnit: 'empirical score' },
];

/** Which side of the comparison a native result came from. */
export type DraftSideState = 'loading' | 'failed' | 'absent' | 'pending' | 'ready';

/**
 * One side of a workbench comparison: the saved revision or the live draft.
 *
 * `state` is the reading itself — an answer that has not arrived, an answer that
 * declared no design, an edit still in flight, a refusal — and it is what the
 * panel turns into words. `project` is the governing document that side's
 * declared inputs are read from, so a changed input is visible even when a
 * preview is still settling.
 */
export interface DraftSide {
  result: ShipDesignResult | null;
  project: ProjectDocument | null;
  state: DraftSideState;
}

/** One recovered field's reader-facing label, unit and source page. */
export interface FieldMeta {
  label: string;
  unit: string | null;
  page: string | null;
}

/**
 * How a caller labels recovered register names; anything unresolved stays a key.
 *
 * The reader is asked per side because a scaled field's unit is resolved from
 * that side's own declaration: an imperial → metric change must not label both
 * stored values with one unit.
 */
export interface FeedbackLabels {
  field?: (key: string, side: 'before' | 'after') => FieldMeta | null;
  role?: (role: string) => string;
}

/** One of the sixteen readings, on both sides. */
export interface FeedbackReading {
  key: string;
  label: string;
  before: number | null;
  after: number | null;
  delta: number | null;
  /** The change as a share of the saved value; null when the baseline is zero or unknown. */
  percent: number | null;
  dimension?: Dimension;
  storedUnit?: string;
  canonicalUnit?: string;
  /** Which saved field actually supplied each side, for evidence. */
  beforeField: string | null;
  afterField: string | null;
  state: 'known' | 'unknown';
  reason: string | null;
}

/** One recovered design input whose declared value changed. */
export interface ChangedInput {
  key: string;
  label: string;
  before: unknown;
  after: unknown;
  /**
   * The unit each side's own declaration resolves for this field. They differ
   * when a scale selector changed; the two raw values are then printed with
   * their own units and no conversion is invented between them.
   */
  beforeUnit: string | null;
  afterUnit: string | null;
  /** True when the two declarations resolve different units (a scale change). */
  unitChanged: boolean;
  /** The chapter whose source page owns this field, when the mapping knows one. */
  chapter: string | null;
}

/** One ledger role whose managed mass or policy changed. */
export interface ChangedRole {
  role: string;
  label: string;
  beforeMode: string | null;
  afterMode: string | null;
  beforeSelected: number | null;
  afterSelected: number | null;
  beforeEstimate: number | null;
  afterEstimate: number | null;
  delta: number | null;
}

/**
 * The whole comparison: whether numbers may be shown, why not when they may not,
 * the sixteen readings, the changed inputs and the changed roles, and any scope
 * note the comparison needs (the report's optional physical stages).
 */
export interface DesignFeedback {
  comparable: boolean;
  warnings: string[];
  readings: FeedbackReading[];
  inputs: ChangedInput[];
  roles: ChangedRole[];
  scopeNote: string | null;
}

/* --------------------------------------------------------------- primitives */

const finite = (value: unknown): number | null => typeof value === 'number' && Number.isFinite(value) ? value : null;

function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical);
  const record = value && typeof value === 'object' ? value as Record<string, unknown> : null;
  if (!record) return value;
  return Object.fromEntries(Object.entries(record)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, item]) => [key, canonical(item)]));
}

const same = (a: unknown, b: unknown): boolean => JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));

/** The chapter whose source page is `page`, drawn from the one existing mapping. */
export function chapterForSourcePage(page: string | null | undefined): string | null {
  if (!page) return null;
  for (const [chapter, sourcePage] of Object.entries(CHAPTER_SOURCE_PAGE)) {
    if (sourcePage === page) return chapter;
  }
  return null;
}

/* ------------------------------------------------------------------- readings */

interface SpecRead { value: number | null; field: string | null }

function readSpec(result: ShipDesignResult, spec: ReadingSpec): SpecRead {
  const scope: Raw | null = spec.section === 'balance'
    ? balanceOf(result) as Raw | null
    : object((result as Raw)[spec.section]);
  if (!scope) return { value: null, field: null };
  for (const field of spec.fields) {
    if (!(field in scope)) continue;
    // The first field the result actually carries decides the reading, whatever
    // it holds: an explicit null is a declared unknown, not a missing field.
    return { value: finite(scope[field]), field };
  }
  return { value: null, field: null };
}

function readingReason(d: Copy, before: SpecRead, after: SpecRead): string | null {
  if (before.value === null && after.value === null) return d('feedback.reason.bothUnknown');
  if (before.value === null) return d('feedback.reason.beforeUnknown');
  if (after.value === null) return d('feedback.reason.afterUnknown');
  return null;
}

type Copy = (key: DesignFeedbackKey, params?: Record<string, string | number>) => string;

function computeReadings(before: ShipDesignResult, after: ShipDesignResult, d: Copy): FeedbackReading[] {
  return READING_SPECS.map(spec => {
    const saved = readSpec(before, spec);
    const draft = readSpec(after, spec);
    const delta = saved.value !== null && draft.value !== null ? draft.value - saved.value : null;
    const percent = delta !== null && saved.value !== null && saved.value !== 0 ? (delta / saved.value) * 100 : null;
    return {
      key: spec.key, label: d(spec.label),
      before: saved.value, after: draft.value, delta, percent,
      dimension: spec.dimension, storedUnit: spec.storedUnit, canonicalUnit: spec.canonicalUnit,
      beforeField: saved.field, afterField: draft.field,
      state: delta !== null ? 'known' : 'unknown',
      reason: delta !== null ? null : readingReason(d, saved, draft),
    };
  });
}

/* --------------------------------------------------------------- changed input */

function changedInputs(before: ShipDesign, after: ShipDesign, labels: FeedbackLabels): ChangedInput[] {
  const saved = object(before.parameters);
  const draft = object(after.parameters);
  const keys = [...new Set([...Object.keys(draft), ...Object.keys(saved)])];
  const found: ChangedInput[] = [];
  for (const key of keys) {
    const beforeValue = saved[key];
    const afterValue = draft[key];
    if (same(afterValue, beforeValue)) continue;
    const beforeMeta = labels.field?.(key, 'before') ?? null;
    const afterMeta = labels.field?.(key, 'after') ?? null;
    const beforeUnit = beforeMeta?.unit ?? null;
    const afterUnit = afterMeta?.unit ?? null;
    found.push({
      key,
      label: afterMeta?.label || beforeMeta?.label || key,
      before: beforeValue === undefined ? null : beforeValue,
      after: afterValue === undefined ? null : afterValue,
      beforeUnit,
      afterUnit,
      unitChanged: beforeUnit !== afterUnit,
      chapter: chapterForSourcePage(afterMeta?.page ?? beforeMeta?.page),
    });
  }
  return found;
}

/* ------------------------------------------------------------------ roles */

function changedRoles(before: ShipDesignResult, after: ShipDesignResult, labels: FeedbackLabels): ChangedRole[] {
  const saved = new Map(ledgerEntries(before).map(entry => [String(entry.role), entry]));
  const draft = new Map(ledgerEntries(after).map(entry => [String(entry.role), entry]));
  const roles = [...new Set([...draft.keys(), ...saved.keys()])];
  const rows: ChangedRole[] = [];
  for (const role of roles) {
    const left = saved.get(role);
    const right = draft.get(role);
    const beforeMode = left?.mode ?? null;
    const afterMode = right?.mode ?? null;
    const beforeSelected = finite(left?.selected_mass_t);
    const afterSelected = finite(right?.selected_mass_t);
    const beforeEstimate = finite(left?.estimate_t);
    const afterEstimate = finite(right?.estimate_t);
    const delta = beforeSelected !== null && afterSelected !== null ? afterSelected - beforeSelected : null;
    // Two unknown masses are the same unknown, not a change; only a known value
    // differing, or an unknown becoming known, is a change. A null `delta` is
    // therefore never evidence of one.
    const changed = beforeMode !== afterMode
      || beforeSelected !== afterSelected
      || beforeEstimate !== afterEstimate
      || finite(left?.target_mass_t) !== finite(right?.target_mass_t)
      || finite(left?.difference_t) !== finite(right?.difference_t);
    if (!changed) continue;
    rows.push({
      role, label: labels.role?.(role) ?? role, beforeMode, afterMode,
      beforeSelected, afterSelected, beforeEstimate, afterEstimate, delta,
    });
  }
  // Up to five changed role masses are ranked by the size of the change, with the
  // rest behind the disclosure; the role name breaks ties so the order is stable.
  rows.sort((a, b) => Math.abs(b.delta ?? 0) - Math.abs(a.delta ?? 0) || a.role.localeCompare(b.role));
  return rows;
}

/* ------------------------------------------------------------------ identity */

const supportedSchema = (value: unknown): boolean => value === SHIP_DESIGN_RESULT_SCHEMA;
const supportedMethod = (value: unknown): boolean => value === SHIP_DESIGN_METHOD_VERSION;

/**
 * Whether a native payload's own status word permits its numbers to be quoted.
 *
 * The one reader the two comparison surfaces share: the saved native result
 * declares `available` or `partial`, and only those may be subtracted. A
 * residual payload under `unavailable`, a failed word or a missing one is
 * unreadable even when its schema and method are intact, so a leftover number
 * can never be quoted as a reading. `partial` is positive: its reconciled values
 * are still read.
 */
const readableStatus = (value: unknown): boolean => value === 'available' || value === 'partial';

function isNative(result: ShipDesignResult | null): result is ShipDesignResult {
  const raw = result as Raw | null;
  return !!raw && supportedSchema(raw.schema) && supportedMethod(raw.method_version) && readableStatus(raw.status);
}

/** A settled side's readable native result, or null when it is absent or foreign. */
function nativeDraft(side: DraftSide): ShipDesignResult | null {
  return side.state === 'ready' && isNative(side.result) ? side.result : null;
}

/**
 * Why a single result is not a supported native reading, in the panel's words.
 *
 * The three checks are reported in the order they are read: a foreign shape, a
 * foreign method and — when both are intact — a status whose own word forbids
 * quoting the residual numbers. A status refusal is never reported as a method
 * refusal.
 */
function resultProblem(result: ShipDesignResult | null): DesignFeedbackKey {
  const raw = result as Raw | null;
  if (!supportedSchema(raw?.schema)) return 'feedback.incompatible.schema';
  if (!supportedMethod(raw?.method_version)) return 'feedback.incompatible.method';
  return 'feedback.incompatible.status';
}

interface NativeIdentity { schema: unknown; method: unknown; basis: string | null }

function identityOf(result: ShipDesignResult): NativeIdentity {
  const raw = result as Raw;
  return { schema: raw.schema ?? null, method: raw.method_version ?? null, basis: basisConditionId(result) };
}

/**
 * Why two native results may not be subtracted, or null when they may.
 *
 * An unestablished identity is never a matching one: both sides must declare the
 * supported schema and method, and both must name the same known, non-empty
 * basis. Two results that merely both omit the method or the basis do not agree
 * on anything the panel can quote.
 */
function identityProblem(before: ShipDesignResult, after: ShipDesignResult): DesignFeedbackKey | null {
  const left = identityOf(before);
  const right = identityOf(after);
  if (!supportedSchema(left.schema) || !supportedSchema(right.schema)) return 'feedback.incompatible.schema';
  if (!supportedMethod(left.method) || !supportedMethod(right.method)) return 'feedback.incompatible.method';
  if (!left.basis || !right.basis) return 'feedback.incompatible.basis';
  if (left.basis !== right.basis) return 'feedback.incompatible.basis';
  return null;
}

/**
 * The native declared condition and the result's own basis are one fact.
 *
 * A result whose saved basis is not the condition its own project declares is
 * not a reading of that declaration, so it cannot be quoted either.
 */
function declaredProblem(project: ProjectDocument | null, result: ShipDesignResult): DesignFeedbackKey | null {
  const design = shipDesignOf(project);
  if (design && design.condition_id !== basisConditionId(result)) return 'feedback.incompatible.basis';
  return null;
}

/* --------------------------------------------------------------- workbench */

/**
 * The draft against the saved revision, read from what the workbench already
 * holds. A pending or failed draft preview withholds the readings and the roles
 * while leaving the changed inputs, because the inputs are the draft's own
 * declaration rather than a preview of it.
 */
export function compareDraft(before: DraftSide, after: DraftSide, language: SiteLanguage, labels: FeedbackLabels = {}): DesignFeedback {
  const d: Copy = (key, params) => designFeedbackCopy(language, key, params);
  const warnings: string[] = [];
  const beforeDesign = shipDesignOf(before.project);
  const afterDesign = shipDesignOf(after.project);
  const inputs = beforeDesign && afterDesign ? changedInputs(beforeDesign, afterDesign, labels) : [];

  const beforeNative = nativeDraft(before);
  const afterNative = nativeDraft(after);

  if (after.state === 'pending') warnings.push(d('feedback.current.pending'));
  else if (after.state === 'failed') warnings.push(d('feedback.current.failed'));
  else if (!after.result) warnings.push(d('feedback.current.empty'));
  else if (!afterNative) warnings.push(d(resultProblem(after.result)));

  if (before.state === 'loading') warnings.push(d('feedback.baseline.loading'));
  else if (before.state === 'failed') warnings.push(d('feedback.baseline.failed'));
  else if (before.state === 'absent') warnings.push(d('feedback.baseline.absent'));
  else if (!before.result) warnings.push(d('feedback.baseline.empty'));
  else if (!beforeNative) warnings.push(d(resultProblem(before.result)));

  // Native preview payloads have no project id. Their owning saved/draft
  // documents establish this identity; frozen analyses use their outer envelope.
  const sameProject = !!before.project?.id && !!after.project?.id
    && before.project.id === after.project.id;
  const projectProblem = beforeNative && afterNative && !sameProject
    ? 'feedback.incompatible.project' as const : null;
  const conditionProblem = beforeNative && afterNative
    ? declaredProblem(before.project, beforeNative) ?? declaredProblem(after.project, afterNative)
    : null;
  const problem = beforeNative && afterNative
    ? projectProblem ?? conditionProblem ?? identityProblem(beforeNative, afterNative)
    : null;
  if (problem) warnings.push(d(problem));

  const comparable = !!beforeNative && !!afterNative && problem === null;
  return {
    comparable, warnings: [...new Set(warnings)], inputs, scopeNote: null,
    readings: comparable ? computeReadings(beforeNative!, afterNative!, d) : [],
    roles: comparable ? changedRoles(beforeNative!, afterNative!, labels) : [],
  };
}

/* ------------------------------------------------------------------- report */

interface FrozenRead {
  result: ShipDesignResult | null;
  project: ProjectDocument | null;
  revision: number | null;
  requested: boolean;
  /** Why this side cannot be quoted, when it cannot. */
  problem: DesignFeedbackKey | null;
}

/** One frozen run's native side, as the report summary and its config table read it. */
export type FrozenPairSide = FrozenRead;

/** The two frozen native sides and the one verdict that gates every number. */
export interface FrozenPair {
  current: FrozenPairSide;
  comparison: FrozenPairSide;
  /** Whether either run requested the native design stage at all. */
  requested: boolean;
  /** The same gate `compareFrozen` applies before it subtracts anything. */
  comparable: boolean;
  /** Every reason the pair may not be quoted, in the summary's own order. */
  problems: DesignFeedbackKey[];
}

/**
 * One frozen run's native side: its readable `ship_design` data, its input
 * snapshot and its revision.
 *
 * The gate is the one the native report readings already use — the stage must
 * have been requested and completed or partial, its data must declare the native
 * schema and method version, and a stage that declares a kernel identity must
 * agree with the payload it carries. The saved snapshot must also be the run's
 * own project, and the snapshot's declared condition must be the basis the
 * result names. A run that requested no native stage is distinguished from one
 * whose stage is unreadable so the summary can say which.
 */
function frozenRead(result: AnalysisResult): FrozenRead {
  const stage = object(object((result as Raw).stages)[SHIP_DESIGN_STAGE]);
  const requested = stage.requested === true;
  const statement = stage.status === 'completed' || stage.status === 'partial';
  const data = requested && statement ? object(stage.data) : null;
  const snapshot = (result as Raw).input_snapshot;
  const project = snapshot && typeof snapshot === 'object' && !Array.isArray(snapshot) ? snapshot as ProjectDocument : null;
  const revision = typeof result.input_snapshot?.revision === 'number' ? result.input_snapshot.revision : null;
  const native = data && data.schema === SHIP_DESIGN_RESULT_SCHEMA && data.method_version === SHIP_DESIGN_METHOD_VERSION
    && readableStatus((data as Raw).status)
    ? data as ShipDesignResult : null;

  let problem: DesignFeedbackKey | null = null;
  if (requested && statement) {
    if (!native) {
      if (data?.schema !== SHIP_DESIGN_RESULT_SCHEMA) problem = 'feedback.frozen.schema';
      else if (data?.method_version !== SHIP_DESIGN_METHOD_VERSION) problem = 'feedback.frozen.method';
      else problem = 'feedback.frozen.status';
    } else {
      const kernel = object(stage.method_versions).kernel;
      const snapshotId = typeof (snapshot as Raw | null)?.id === 'string' ? (snapshot as Raw).id as string : null;
      if (typeof kernel === 'string' && kernel !== native.method_version) problem = 'feedback.frozen.method';
      else if (!snapshotId || !result.project_id || snapshotId !== result.project_id) problem = 'feedback.frozen.snapshot';
      else problem = declaredProblem(project, native);
    }
  }

  return { result: problem ? null : native, project, revision, requested, problem };
}

/** The names of the optional physical stages each run asked for, sorted. */
function physicalStages(result: AnalysisResult): string {
  return Object.entries(object((result as Raw).stages))
    .filter(([name, stage]) => name !== SHIP_DESIGN_STAGE && object(stage).requested === true)
    .map(([name]) => name).sort().join(',');
}

/**
 * The frozen native summary of two runs, in the same direction as the full
 * report comparison beside it: `current` is the left column and `comparison`
 * the right, so every delta is comparison − current.
 *
 * `identity` carries the report's own identity verdict for each run. The report
 * already refuses a run whose saved envelope does not agree with its result, and
 * this summary must not quote numbers that verdict has withheld. Optional
 * physical stages are deliberately not part of that verdict: a different
 * optional scope is named, not treated as an identity mismatch.
 *
 * Returns `null` when neither run requested a native design stage, so a report
 * with no native design keeps exactly the comparison it always had. Only the two
 * immutable results are read; no live preview is fetched.
 */
export interface FrozenIdentity {
  currentValid?: boolean;
  comparisonValid?: boolean;
}

export function frozenNativeSides(current: AnalysisResult, comparison: AnalysisResult,
  identity: FrozenIdentity = {}): FrozenPair {
  const left = frozenRead(current);
  const right = frozenRead(comparison);
  const problems: DesignFeedbackKey[] = [];
  if (!left.result) problems.push(left.problem ?? 'feedback.frozen.currentUnreadable');
  if (!right.result) problems.push(right.problem ?? 'feedback.frozen.comparisonUnreadable');
  const projectProblem = left.result && right.result
    && (!current.project_id || current.project_id !== comparison.project_id)
    ? 'feedback.incompatible.project' as const : null;
  if (projectProblem) problems.push(projectProblem);
  const identityVerdict = identity.currentValid === false || identity.comparisonValid === false
    ? 'feedback.frozen.identity' as const : null;
  if (identityVerdict) problems.push(identityVerdict);
  const basisProblem = left.result && right.result ? identityProblem(left.result, right.result) : null;
  if (basisProblem) problems.push(basisProblem);
  return {
    current: left, comparison: right,
    requested: left.requested || right.requested,
    comparable: !!left.result && !!right.result && !projectProblem && !identityVerdict && !basisProblem,
    problems,
  };
}

export function compareFrozen(current: AnalysisResult, comparison: AnalysisResult, language: SiteLanguage,
  labels: FeedbackLabels = {}, identity: FrozenIdentity = {}): DesignFeedback | null {
  const pair = frozenNativeSides(current, comparison, identity);
  if (!pair.requested) return null;
  const d: Copy = (key, params) => designFeedbackCopy(language, key, params);
  const left = pair.current;
  const right = pair.comparison;
  const warnings = [...new Set(pair.problems.map(problem => d(problem)))];
  const leftDesign = shipDesignOf(left.project);
  const rightDesign = shipDesignOf(right.project);
  // A project or identity refusal withholds the declared inputs too, exactly as
  // it withholds every reading: the snapshots belong to the runs it rejected.
  const blocked = pair.problems.includes('feedback.incompatible.project') || pair.problems.includes('feedback.frozen.identity');
  const inputs = leftDesign && rightDesign && !blocked ? changedInputs(leftDesign, rightDesign, labels) : [];
  const scopeNote = physicalStages(current) === physicalStages(comparison) ? null : d('feedback.frozen.optionalScope');
  return {
    comparable: pair.comparable, warnings, inputs, scopeNote,
    readings: pair.comparable ? computeReadings(left.result!, right.result!, d) : [],
    roles: pair.comparable ? changedRoles(left.result!, right.result!, labels) : [],
  };
}

/** True when a frozen run requested the native design stage. */
export function requestsNativeDesign(result: AnalysisResult): boolean {
  return object(object((result as Raw).stages)[SHIP_DESIGN_STAGE]).requested === true;
}

/** Include ledger and loading facts too: declared mass lives outside ship_design. */
export function designFingerprint(project: ProjectDocument | null | undefined): string {
  const design = shipDesignOf(project);
  return design ? JSON.stringify(canonical(project)) : '';
}

/** The reading specs, for a test that needs to prove the sixteen paths are read. */
export const FEEDBACK_READING_KEYS: readonly string[] = READING_SPECS.map(spec => spec.key);
