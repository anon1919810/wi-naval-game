import { declaredSource } from './InputTrace';
import { number, object, rows, type Raw } from './formModel';
import { stageLabel, STAGE_ORDER } from './StageStatus';
import type { AnalysisResult, StageEnvelope } from '../types';
import type { Dimension } from './units';
import type { SiteLanguage } from '../portfolio/LanguageProvider';
import { workspaceCopy, type WorkspaceKey } from '../i18n/workspace';

/**
 * Saved-result readings, shared by the run and report pages.
 *
 * Every number here is projected from one saved path of `result.stages` — the
 * same paths the coordinator writes — and from nothing else. Nothing is derived
 * in the browser: no draught inferred from the waterline, no first resistance
 * row picked out of a list, no average or interpolation, no fallback to the input
 * snapshot or to a historical propulsion figure. A stage that did not deliver a
 * result reports why instead of a number, even when its envelope still carries
 * residual values, and a genuine zero is a value like any other.
 *
 * The overall result status is deliberately not consulted: a `partial` or
 * `canceled` run still shows the stages that did finish, because those stages
 * are saved facts. Units follow the existing `Dimension` vocabulary so the
 * reader's display preference can convert a stored number without changing what
 * was saved; a range stays in nmi because it has no convertible reader unit. A
 * structured `source` is carried through as declared; it is a statement about
 * where a number came from, never historical confirmation.
 *
 * The language is a parameter, not a hidden global: the same saved result yields
 * the same values, the same states and the same order in either language, and a
 * change of language re-reads the words without touching a single number.
 */

export type ReadingState = 'known' | 'unknown' | 'not_requested' | 'unavailable' | 'model_limit' | 'failed' | 'canceled' | 'multiple';

export interface ReportReading {
  key: string;
  stage: string;
  label: string;
  value: number | null;
  dimension?: Dimension;
  storedUnit?: string;
  canonicalUnit?: string;
  state: ReadingState;
  reason: string | null;
  context: string | null;
  source: string | null;
  estimate: boolean | null;
}

/**
 * Either the stage that may be read, or the reason it may not. The stage is
 * only ever reachable through the `ok` branch, so no reader can touch a stage
 * it has not been cleared for.
 */
type StageAccess = { ok: true; stage: StageEnvelope } | { ok: false; state: ReadingState; reason: string };

const STATUS_STATE: Record<string, ReadingState> = {
  not_requested: 'not_requested', unavailable: 'unavailable', model_limit: 'model_limit',
  failed: 'failed', canceled: 'canceled',
};

const STATUS_REASON: Record<string, WorkspaceKey> = {
  not_requested: 'reading.reason.notRequested', unavailable: 'reading.reason.unavailable',
  model_limit: 'reading.reason.modelLimit', failed: 'reading.reason.failed', canceled: 'reading.reason.canceled',
};

/** One saved scalar of one stage, projected only through the stage gate. */
type ScalarSpec = { key: string; stage: string; label: WorkspaceKey; dimension: Dimension; storedUnit: string; path: string };

/** The stage that carries both nested results, and so gates both readings. */
const HYDROSTAGE = 'hydrostatics';

/**
 * The upright geometric GM, declared once so the report list and every other
 * surface that shows it cannot drift apart: the same spec, and so the same
 * requested/completed gate, everywhere.
 */
const UPRIGHT_GM: ScalarSpec = { key: 'hydrostatics.gm_t_m', stage: HYDROSTAGE, label: 'reading.gm', dimension: 'length', storedUnit: 'm', path: 'values.gm_t_m' };

/** The only saved paths the first-screen readings are allowed to read. */
const SCALARS: ScalarSpec[] = [
  { key: 'loading.total_mass_t', stage: 'loading', label: 'reading.mass', dimension: 'mass', storedUnit: 't', path: 'values.total_mass_t' },
  { key: 'equilibrium.waterline_above_keel_m', stage: 'equilibrium', label: 'reading.waterline', dimension: 'length', storedUnit: 'm', path: 'waterline_above_keel_m' },
  { key: 'equilibrium.heel_deg', stage: 'equilibrium', label: 'reading.heel', dimension: 'angle', storedUnit: 'deg', path: 'heel_deg' },
  UPRIGHT_GM,
];

/**
 * The two metacentric heights are separate readings of separate saved paths.
 *
 * `values.gm_t_m` is the upright geometric KM minus the effective KG and is
 * null by definition for an inclined or contacting state. The equilibrium
 * equivalent GM is the restoring slope the core solved at the free-trim
 * equilibrium heel, saved under `small_angle_stability`. Neither number stands
 * in for the other: an old saved result simply has no second reading, and the
 * first keeps the meaning it always had.
 */
export const EQUILIBRIUM_GM_KEY = 'hydrostatics.small_angle_stability.equilibrium_gm_m';
/** The saved roll period. A scalar estimate, not a full dynamic solution. */
export const ROLL_PERIOD_KEY = 'hydrostatics.loaded_roll.period_s';

function stageOf(result: AnalysisResult | null | undefined, name: string): StageEnvelope | null {
  const stage = object(object(result?.stages)[name]);
  return Object.keys(stage).length ? stage as StageEnvelope : null;
}

function flag(value: unknown): boolean | null {
  return typeof value === 'boolean' ? value : null;
}

function readPath(data: Raw, path: string): unknown {
  return path.split('.').reduce<unknown>((node, key) => object(node)[key], data);
}

/**
 * A reading is possible only for a stage that was requested and finished.
 * Anything else is blocked before a single field is touched, so a residual
 * value inside a failed, unavailable, model-limited or canceled envelope can
 * never reach the reader.
 */
function stageAccess(stage: StageEnvelope | null, language: SiteLanguage): StageAccess {
  if (!stage) return { ok: false, state: 'not_requested', reason: workspaceCopy(language, 'reading.reason.missingStage') };
  if (!stage.requested) return { ok: false, state: 'not_requested', reason: workspaceCopy(language, 'reading.reason.notRequested') };
  if (stage.status === 'completed') return { ok: true, stage };
  const state = STATUS_STATE[stage.status] ?? 'failed';
  const label = workspaceCopy(language, STATUS_REASON[stage.status] ?? STATUS_REASON.failed);
  // The stage's own stop reason is the core's saved text and is passed through
  // verbatim; only the sentence around it is localized.
  return { ok: false, state, reason: stage.reason ? workspaceCopy(language, 'reading.reason.withReason', { label, reason: stage.reason }) : label };
}

/** A missing field, an explicit null and a non-finite value stay three facts. */
function scalarReason(language: SiteLanguage, field: string, raw: unknown): string {
  if (raw === undefined) return workspaceCopy(language, 'reading.reason.noField');
  if (raw === null) return workspaceCopy(language, 'reading.reason.nullField', { field });
  return workspaceCopy(language, 'reading.reason.notFiniteField', { field });
}

function stageContext(language: SiteLanguage, name: string): string {
  return workspaceCopy(language, 'reading.stageContext', { name: stageLabel(key => workspaceCopy(language, key), name) });
}

/** The stage's own context plus one sentence of saved-method explanation. */
function notedContext(language: SiteLanguage, name: string, note: WorkspaceKey): string {
  return workspaceCopy(language, 'reading.context.note', { context: stageContext(language, name), note: workspaceCopy(language, note) });
}

/**
 * One nested result inside a stage that must itself be readable.
 *
 * Both the small-angle stability result and the loaded-roll study are saved
 * under a stage of their own, so both are gated twice: the parent stage has to
 * be requested and completed, and the nested result has to declare `completed`
 * for itself. Either gate blocks the reading before a single field is touched,
 * so a residual scalar inside a failed, unavailable, model-limited, cancelled
 * or unrequested envelope never reaches the reader.
 *
 * A nested result the run never saved is `unknown` with its own reason. It is
 * not a zero, not the parent stage's other scalar and not another run's value.
 */
function nestedReading(language: SiteLanguage, stage: StageEnvelope | null, spec: {
  key: string; label: WorkspaceKey; nested: string; field: string; dimension?: Dimension; storedUnit?: string;
  canonicalUnit?: string; note: WorkspaceKey; absent: WorkspaceKey;
}): ReportReading {
  const base: ReportReading = {
    key: spec.key, stage: HYDROSTAGE, label: workspaceCopy(language, spec.label), value: null,
    dimension: spec.dimension, storedUnit: spec.storedUnit, canonicalUnit: spec.canonicalUnit ?? spec.storedUnit,
    state: 'unknown', reason: null, context: notedContext(language, HYDROSTAGE, spec.note),
    source: null, estimate: null,
  };
  const access = stageAccess(stage, language);
  if (!access.ok) return { ...base, state: access.state, reason: access.reason };
  const study = object(readPath(object(access.stage.data), spec.nested));
  const status = typeof study.status === 'string' ? study.status : null;
  if (status === null) return { ...base, reason: workspaceCopy(language, spec.absent) };
  const source = declaredSource(study.source);
  const estimate = flag(study.estimate);
  if (status !== 'completed') {
    const label = workspaceCopy(language, STATUS_REASON[status] ?? STATUS_REASON.failed);
    const saved = study.reason == null ? '' : String(study.reason);
    // The nested stop reason is the core's saved text and stays verbatim; only
    // the sentence around it is localized. Its number, if any, is never read.
    return { ...base, state: STATUS_STATE[status] ?? 'failed', source, estimate,
      reason: saved ? workspaceCopy(language, 'reading.reason.withReason', { label, reason: saved }) : label };
  }
  const raw = study[spec.field];
  const value = number(raw);
  // A finite negative and a genuine zero are results like any other; they are
  // never folded into a positive number or into a safe-looking fallback.
  if (value === null) return { ...base, reason: scalarReason(language, spec.field, raw), source, estimate };
  return { ...base, state: 'known', value, reason: null, source, estimate };
}

/**
 * The upright geometric GM, behind the same gate as every other reading.
 *
 * It is a plain saved scalar rather than a nested result, so it is exactly the
 * one a surface is most likely to read straight out of `stage.data`. Exported so
 * that the overview, the run and report readings and the performance results all
 * answer for it through one projection: a hydrostatics stage that failed or was
 * never requested cannot leak the value it happens to carry.
 */
export function uprightGmReading(language: SiteLanguage, stage: StageEnvelope | null): ReportReading {
  return scalarReading(language, UPRIGHT_GM, stage);
}

/**
 * The equilibrium equivalent GM of the saved small-angle stability result.
 *
 * Read only when hydrostatics completed and that nested result declared
 * `completed`: a saved run that predates the nested result stays unknown with a
 * missing-result reason instead of borrowing the upright GM.
 */
export function equilibriumGmReading(language: SiteLanguage, stage: StageEnvelope | null): ReportReading {
  return nestedReading(language, stage, {
    key: EQUILIBRIUM_GM_KEY, label: 'reading.equilibriumGm', nested: 'small_angle_stability',
    field: 'equilibrium_gm_m', dimension: 'length', storedUnit: 'm',
    note: 'reading.equilibriumGmNote', absent: 'reading.reason.noSmallAngle',
  });
}

/**
 * The saved roll period, or the saved reason there is none.
 *
 * The eligibility behind an unavailable period — trim, an inertia axis, a
 * sourced gyration coefficient, the sign of the restoring slope — is the
 * core's decision and is never re-made here. Seconds have no convertible reader
 * unit, exactly like the nmi of a steady range.
 */
export function rollPeriodReading(language: SiteLanguage, stage: StageEnvelope | null): ReportReading {
  return nestedReading(language, stage, {
    key: ROLL_PERIOD_KEY, label: 'reading.rollPeriod', nested: 'loaded_roll', field: 'period_s',
    canonicalUnit: 's', note: 'reading.rollPeriodNote', absent: 'reading.reason.noLoadedRoll',
  });
}

function scalarReading(language: SiteLanguage, spec: typeof SCALARS[number], stage: StageEnvelope | null): ReportReading {
  const base: ReportReading = {
    key: spec.key, stage: spec.stage, label: workspaceCopy(language, spec.label), value: null,
    dimension: spec.dimension, storedUnit: spec.storedUnit, canonicalUnit: spec.storedUnit,
    state: 'unknown', reason: null, context: stageContext(language, spec.stage), source: null, estimate: null,
  };
  const access = stageAccess(stage, language);
  if (!access.ok) return { ...base, state: access.state, reason: access.reason };
  const data = object(access.stage.data);
  const source = declaredSource(data.source);
  const estimate = flag(data.estimate);
  const raw = readPath(data, spec.path);
  const value = number(raw);
  if (value === null) return { ...base, reason: scalarReason(language, spec.path, raw), source, estimate };
  return { ...base, state: 'known', value, reason: null, source, estimate };
}

/**
 * The power work point. Only a single complete, primary and in-scope row may
 * speak for the stage; several rows stay several work points and the first one
 * is never chosen on the reader's behalf.
 */
function powerReading(language: SiteLanguage, stage: StageEnvelope | null): ReportReading {
  const base: ReportReading = {
    key: 'resistance.shaft_power_kw', stage: 'resistance', label: workspaceCopy(language, 'reading.powerPoint'), value: null,
    dimension: 'power', storedUnit: 'kW', canonicalUnit: 'kW',
    state: 'unknown', reason: null, context: stageContext(language, 'resistance'), source: null, estimate: null,
  };
  const access = stageAccess(stage, language);
  if (!access.ok) return { ...base, state: access.state, reason: access.reason };
  const data = object(access.stage.data);
  const power = rows(data.power_rows);
  if (power.length === 0) return { ...base, reason: workspaceCopy(language, 'reading.reason.noPower') };
  if (power.length > 1) {
    return { ...base, state: 'multiple', reason: workspaceCopy(language, 'reading.reason.multiple'),
      context: workspaceCopy(language, 'reading.context.workpoints', { context: stageContext(language, 'resistance'), count: power.length }) };
  }
  const row = power[0];
  const source = declaredSource(object(row.qpc).source) ?? declaredSource(row.source);
  const estimate = flag(row.estimate);
  const speed = number(row.speed_kn);
  const shaft = number(row.shaft_power_kw);
  if (speed === null || shaft === null) {
    return { ...base, reason: workspaceCopy(language, 'reading.reason.incompletePoint'), source, estimate };
  }
  const context = workspaceCopy(language, 'reading.context.workpoint', { context: stageContext(language, 'resistance'), speed });
  // The envelope's own validity speaks for the row it carries, so an
  // out-of-scope stage cannot be quoted through an in-scope looking row.
  const outOfScope = access.stage.validity?.model_applicable === false
    || object(data.validity).model_applicable === false
    || row.model_applicable === false;
  if (row.complete !== true) return { ...base, reason: workspaceCopy(language, 'reading.reason.incompletePoint'), context, source, estimate };
  if (outOfScope) return { ...base, reason: workspaceCopy(language, 'reading.reason.outOfScopePoint'), context, source, estimate };
  if (row.primary_result === false || data.primary_result === false) {
    return { ...base, reason: workspaceCopy(language, 'reading.reason.nonPrimaryPoint'), context, source, estimate };
  }
  const primary = row.primary_result === true || data.primary_result === true;
  const applicable = row.model_applicable === true || object(data.validity).model_applicable === true
    || access.stage.validity?.model_applicable === true;
  if (!primary || !applicable) {
    return { ...base, reason: workspaceCopy(language, 'reading.reason.undeclaredPoint'), context, source, estimate };
  }
  return { ...base, state: 'known', value: shaft, reason: null, context, source, estimate };
}

/** Steady endurance stays in nautical miles: a range has no reader unit to convert. */
function enduranceReading(language: SiteLanguage, stage: StageEnvelope | null): ReportReading {
  const base: ReportReading = {
    key: 'endurance.range_nm', stage: 'endurance', label: workspaceCopy(language, 'reading.endurance'), value: null, canonicalUnit: 'nmi',
    state: 'unknown', reason: null, context: stageContext(language, 'endurance'), source: null, estimate: null,
  };
  const access = stageAccess(stage, language);
  if (!access.ok) return { ...base, state: access.state, reason: access.reason };
  const values = object(object(access.stage.data).values);
  const source = declaredSource(values.source);
  const estimate = flag(values.estimate);
  const speed = number(values.speed_kn);
  const context = speed === null ? base.context ?? null
    : workspaceCopy(language, 'reading.context.workpoint', { context: stageContext(language, 'endurance'), speed });
  const raw = values.range_nm;
  const value = number(raw);
  if (value === null) return { ...base, reason: scalarReason(language, 'range_nm', raw), context, source, estimate };
  return { ...base, state: 'known', value, reason: null, context, source, estimate };
}

/**
 * The stages this result actually asked for, in the canonical order. A stage
 * name the interface does not know yet keeps its saved position after the known
 * ones instead of being dropped by the sort.
 */
export function requestedStages(result: AnalysisResult | null | undefined): Array<{ name: string; stage: StageEnvelope }> {
  const entries = Object.entries(object(result?.stages))
    .filter(([, stage]) => stage && typeof stage === 'object' && (stage as StageEnvelope).requested === true)
    .map(([name, stage], index) => ({ name, stage: stage as StageEnvelope, index }));
  const rank = (name: string): number => {
    const known = STAGE_ORDER.indexOf(name);
    return known === -1 ? STAGE_ORDER.length : known;
  };
  return entries
    .sort((a, b) => rank(a.name) - rank(b.name) || a.index - b.index)
    .map(entry => ({ name: entry.name, stage: entry.stage }));
}

/** The first-screen readings, in a fixed reading order, in one language. */
export function reportReadings(result: AnalysisResult | null | undefined, language: SiteLanguage): ReportReading[] {
  const readings: ReportReading[] = [];
  for (const spec of SCALARS) readings.push(scalarReading(language, spec, stageOf(result, spec.stage)));
  // The equilibrium GM and the roll period sit beside the upright GM they
  // accompany: same stage, same gate, their own saved paths.
  const hydrostatics = stageOf(result, HYDROSTAGE);
  readings.push(equilibriumGmReading(language, hydrostatics));
  readings.push(rollPeriodReading(language, hydrostatics));
  readings.push(powerReading(language, stageOf(result, 'resistance')));
  readings.push(enduranceReading(language, stageOf(result, 'endurance')));
  return readings;
}

/**
 * A stage address that keeps the tool route intact: `#/runs/{runId}` and
 * `#/reports/{runId}` still resolve to the same page, because the run id stays
 * the second segment and only a `/stages/{name}` tail is added.
 */
export function stageHref(page: 'runs' | 'reports', runId: string, stageName: string): string {
  return `#/${page}/${encodeURIComponent(runId)}/stages/${encodeURIComponent(stageName)}`;
}

function safeDecode(segment: string): string | null {
  try { return decodeURIComponent(segment); } catch { return null; }
}

/**
 * The stage named by `hash`, or null when the hash is not this page's stage
 * address. An old `#/reports/{id}` link, another page, another id, a missing
 * `stages` segment, a broken percent-escape or an unknown tail is ignored
 * rather than guessed at, and the reader stays where they are.
 */
export function readStageTarget(hash: string, page: 'runs' | 'reports', runId: string): string | null {
  const path = String(hash ?? '').replace(/^#/, '').replace(/^\/+/, '').split('/');
  if (path.length !== 4 || path[0] !== page || path[2] !== 'stages') return null;
  const id = safeDecode(path[1]);
  const stage = safeDecode(path[3]);
  if (id === null || stage === null || id !== runId || stage === '') return null;
  return stage;
}