import { basisConditionId, isUnresolved, ledgerEntries } from './shipDesign';
import { SHIP_DESIGN_METHOD_VERSION, SHIP_DESIGN_RESULT_SCHEMA, isRecord } from './sps3b3Model';
import type { PropulsionPerformanceKey } from '../i18n/propulsionPerformance';
import type { ShipDesignResult } from '../types';

/**
 * The one pure reader behind the propulsion and performance chapters.
 *
 * This module computes no ship number and reads no formula. It reads the saved
 * native `engine` and `performance` sections the way the source declared them and
 * reports exactly what is there, under five rules:
 *
 * - **Source units are the source's own.** Horsepower is source horsepower,
 *   range is source nautical miles and the source machinery mass and the two
 *   bunker weights are source long tons; none of them is converted or relabelled.
 *   The metacentric height and
 *   the roll period keep the units the source saved, because both are the
 *   method's own empirical figures rather than modern physical definitions.
 * - **The ledger is the only mass authority.** The two whole-ship roles
 *   `machinery` and `fuel` are read from the global ledger in tonnes and are
 *   never split across a declared fuel or engine type; the source bunker weights
 *   beside them never become a ledger mass.
 * - **The lock is a declaration, not a live solve.** `power_locked`, `power_hp`
 *   and `locked_bunker_lt` come from the result's own `design.editing`. A missing
 *   flag is unknown, never an explicit false; a missing locked value is unknown,
 *   never a zero.
 * - **Zero, unknown and false stay distinct.** A saved zero is a fact; a missing
 *   or non-finite field is unknown; a malformed selector array is unknown and is
 *   never reported as none-selected.
 * - **Warnings are the source's own.** The eight boolean flags are read strictly
 *   and stay `true`/`false`/unknown; no threshold is restated here and a false
 *   flag is never turned into a general pass.
 *
 * The whole reader is immutable: it never writes back to the result it reads.
 */

export type PropulsionProblem = 'absent' | 'unsupported_schema' | 'unsupported_method' | 'unavailable';

/** The fixed reading units the two chapters print. */
export type ReadingUnit =
  | 'speed' | 'source-hp' | 'range-nmi' | 'count' | 'percent' | 'long-ton' | 'foot' | 'second' | 'score';

/** One engine reading, in the source's own unit. */
export interface PropulsionFact {
  key: string;
  label: PropulsionPerformanceKey;
  value: number | null;
  unit: ReadingUnit;
  /** The real source field this reading reveals and focuses, when it names one. */
  editField?: string;
  editLabel?: PropulsionPerformanceKey;
}

/** The declared fuel, engine and drive selector indices, or null when not declared. */
export interface PropulsionDeclaration {
  fuel: number[] | null;
  engine: number[] | null;
  drive: number[] | null;
}

/** The result's own declared power lock, strictly read. */
export interface PropulsionLock {
  locked: boolean | null;
  powerHp: number | null;
  bunkerLt: number | null;
}

export const PROPULSION_LEDGER_ROLES = ['machinery', 'fuel'] as const;
export type PropulsionLedgerRole = typeof PROPULSION_LEDGER_ROLES[number];

/** One whole-ship machinery or fuel role, in tonnes. */
export interface PropulsionLedgerRow {
  role: PropulsionLedgerRole;
  mode: string | null;
  selectedT: number | null;
  estimateT: number | null;
  unresolved: boolean;
}

export interface PropulsionSection {
  declaration: PropulsionDeclaration;
  screws: number | null;
  /** Speed, power, range, coal share and bunker, in the source's own units. */
  facts: PropulsionFact[];
  lock: PropulsionLock;
  /** Always both roles, in the source's own order. */
  ledger: PropulsionLedgerRow[];
}

export type PerformanceGroupId = 'stability' | 'strength' | 'seakeeping';

export interface PerformanceGroup {
  id: PerformanceGroupId;
  label: PropulsionPerformanceKey;
  readings: PropulsionFact[];
}

/** One source warning or rating flag: true, false or unknown, never coerced. */
export interface PerformanceFlag {
  key: string;
  label: PropulsionPerformanceKey;
  value: boolean | null;
}

export interface PerformanceSection {
  groups: PerformanceGroup[];
  flags: PerformanceFlag[];
}

export interface PropulsionPerformance {
  supported: boolean;
  problem: PropulsionProblem | null;
  schema: string | null;
  method: string | null;
  status: string | null;
  basisConditionId: string | null;
  engine: PropulsionSection;
  performance: PerformanceSection;
}

/* ------------------------------------------------------------------ reading */

function numberAt(source: Record<string, unknown> | null, key: string): number | null {
  if (!source) return null;
  const raw = source[key];
  return typeof raw === 'number' && Number.isFinite(raw) ? raw : null;
}

/** A boolean exactly as declared, or null when the field is absent or not a boolean. */
function booleanAt(source: Record<string, unknown> | null, key: string): boolean | null {
  const raw = source?.[key];
  return typeof raw === 'boolean' ? raw : null;
}

/**
 * The declared indices of one boolean selector array, or null when the array is
 * absent or malformed.
 *
 * An array only states a declaration when it is present, of exactly the expected
 * length, and every entry is a boolean. A shorter, longer or partly numeric array
 * cannot assert "none selected", so it is unknown (null); an exact array with no
 * true entry is the explicit none-selected list.
 */
function selectorIndices(source: Record<string, unknown> | null, key: string, size: number): number[] | null {
  const raw = source?.[key];
  if (!Array.isArray(raw) || raw.length !== size || !raw.every(value => typeof value === 'boolean')) return null;
  const indices: number[] = [];
  raw.forEach((value, index) => { if (value === true) indices.push(index); });
  return indices;
}

function engineFacts(engine: Record<string, unknown> | null): PropulsionFact[] {
  const scalar = (key: string, label: PropulsionPerformanceKey, field: string, unit: ReadingUnit,
    editField?: string, editLabel?: PropulsionPerformanceKey): PropulsionFact =>
    ({ key, label, value: numberAt(engine, field), unit, editField, editLabel });
  return [
    scalar('engine.speedMax', 'propulsion.fact.speedMax', 'speedMax', 'speed', 'speed_max_kn', 'propulsion.edit.speed'),
    scalar('engine.speedCruise', 'propulsion.fact.speedCruise', 'speedCruise', 'speed', 'speed_cruise_kn', 'propulsion.edit.speed'),
    scalar('engine.hpMax', 'propulsion.fact.hpMax', 'hpMax', 'source-hp'),
    scalar('engine.hpCruise', 'propulsion.fact.hpCruise', 'hpCruise', 'source-hp'),
    scalar('engine.range', 'propulsion.fact.range', 'range', 'range-nmi', 'range_nm', 'propulsion.edit.range'),
    scalar('engine.screws', 'propulsion.fact.screws', 'screws', 'count', 'shafts', 'propulsion.edit.screws'),
    scalar('engine.pctCoal', 'propulsion.fact.pctCoal', 'pctCoal', 'percent', 'coal_percentage', 'propulsion.edit.coal'),
    scalar('engine.bunker', 'propulsion.fact.bunker', 'bunker', 'long-ton'),
    scalar('engine.bunkerMax', 'propulsion.fact.bunkerMax', 'bunkerMax', 'long-ton'),
    scalar('engine.engineWeight', 'propulsion.fact.engineWeight', 'engineWeight', 'long-ton'),
  ];
}

function ledgerRows(result: ShipDesignResult): PropulsionLedgerRow[] {
  const entries = ledgerEntries(result);
  return PROPULSION_LEDGER_ROLES.map(role => {
    const entry = entries.find(item => item.role === role);
    return {
      role,
      mode: typeof entry?.mode === 'string' ? entry.mode : null,
      selectedT: numberAt(entry ?? null, 'selected_mass_t'),
      estimateT: numberAt(entry ?? null, 'estimate_t'),
      unresolved: entry ? isUnresolved(entry) : true,
    };
  });
}

function performanceGroups(performance: Record<string, unknown> | null): PerformanceGroup[] {
  const reading = (key: string, label: PropulsionPerformanceKey, field: string, unit: ReadingUnit): PropulsionFact =>
    ({ key, label, value: numberAt(performance, field), unit });
  return [
    { id: 'stability', label: 'performance.group.stability', readings: [
      reading('performance.stability', 'performance.fact.stability', 'stability', 'score'),
      reading('performance.stabilityAdj', 'performance.fact.stabilityAdj', 'stabilityAdj', 'score'),
      reading('performance.metacentre', 'performance.fact.metacentre', 'metacentre', 'foot'),
      reading('performance.rollPeriod', 'performance.fact.rollPeriod', 'rollPeriod', 'second'),
    ] },
    { id: 'strength', label: 'performance.group.strength', readings: [
      reading('performance.strengthCross', 'performance.fact.strengthCross', 'strengthCross', 'score'),
      reading('performance.strengthLong', 'performance.fact.strengthLong', 'strengthLong', 'score'),
      reading('performance.strengthComp', 'performance.fact.strengthComp', 'strengthComp', 'score'),
    ] },
    { id: 'seakeeping', label: 'performance.group.seakeeping', readings: [
      reading('performance.seaboat', 'performance.fact.seaboat', 'seaboat', 'score'),
      reading('performance.seakeeping', 'performance.fact.seakeeping', 'seakeeping', 'score'),
      reading('performance.steadiness', 'performance.fact.steadiness', 'steadiness', 'score'),
      reading('performance.steadinessAdj', 'performance.fact.steadinessAdj', 'steadinessAdj', 'score'),
    ] },
  ];
}

/** The eight source flags, in the source's own order, each strictly a boolean or unknown. */
function performanceFlags(performance: Record<string, unknown> | null): PerformanceFlag[] {
  const flag = (key: string, label: PropulsionPerformanceKey, field: string): PerformanceFlag =>
    ({ key, label, value: booleanAt(performance, field) });
  return [
    flag('flag.tenderWarn', 'performance.flags.tenderWarn', 'tenderWarn'),
    flag('flag.capsizeWarn', 'performance.flags.capsizeWarn', 'capsizeWarn'),
    flag('flag.steady', 'performance.flags.steady', 'steady'),
    flag('flag.unsteady', 'performance.flags.unsteady', 'unsteady'),
    flag('flag.badSea', 'performance.flags.badSea', 'badSea'),
    flag('flag.poorSea', 'performance.flags.poorSea', 'poorSea'),
    flag('flag.goodSea', 'performance.flags.goodSea', 'goodSea'),
    flag('flag.fineSea', 'performance.flags.fineSea', 'fineSea'),
  ];
}

function emptyEngine(): PropulsionSection {
  return {
    declaration: { fuel: null, engine: null, drive: null },
    screws: null,
    facts: engineFacts(null),
    lock: { locked: null, powerHp: null, bunkerLt: null },
    ledger: PROPULSION_LEDGER_ROLES.map(role => ({ role, mode: null, selectedT: null, estimateT: null, unresolved: true })),
  };
}

function emptyPerformance(): PerformanceSection {
  return { groups: performanceGroups(null), flags: performanceFlags(null) };
}

function empty(problem: PropulsionProblem): PropulsionPerformance {
  return {
    supported: false, problem, schema: null, method: null, status: null, basisConditionId: null,
    engine: emptyEngine(), performance: emptyPerformance(),
  };
}

/**
 * Whether one frozen native stage's envelope may supply the two readers.
 *
 * A standalone reader validates its own schema, method and status and needs no
 * envelope, so an absent one is allowed through here. When the report mounts the
 * readers through the stage card, the parent envelope must have been requested,
 * must have completed or finished partial, and — when it declares a kernel
 * identity — that identity must agree with the payload's own method version. A
 * failed or mismatched envelope therefore reveals no residual fact.
 */
export function propulsionEnvelopeGate(envelope: unknown, result: unknown): boolean {
  const stage = isRecord(envelope) ? envelope : null;
  if (!stage) return true;
  if (stage.requested !== true) return false;
  if (stage.status !== 'completed' && stage.status !== 'partial') return false;
  const methodVersions = isRecord(stage.method_versions) ? stage.method_versions : null;
  const kernel = methodVersions ? methodVersions.kernel : null;
  const method = isRecord(result) && typeof result.method_version === 'string' ? result.method_version : null;
  if (typeof kernel === 'string' && kernel !== method) return false;
  return true;
}

/**
 * The propulsion and performance reading of one native result, or the named
 * reason it cannot be read.
 *
 * A result of another shape or method says so and carries no facts. The source's
 * own status must be `available` or `partial`; any other word, including a
 * missing one, is unavailable and carries no facts. A supported result with
 * neither an engine nor a performance section is unavailable. A supported result
 * always yields both sections, with every undeclared value unknown.
 */
export function readPropulsionPerformance(raw: unknown): PropulsionPerformance {
  const result = isRecord(raw) ? raw : null;
  if (!result) return empty('absent');

  const schema = typeof result.schema === 'string' ? result.schema : null;
  const method = typeof result.method_version === 'string' ? result.method_version : null;
  const status = typeof result.status === 'string' ? result.status : null;
  const basis = basisConditionId(result as unknown as ShipDesignResult);
  const context = { schema, method, status, basisConditionId: basis };

  if (schema !== SHIP_DESIGN_RESULT_SCHEMA) return { ...empty('unsupported_schema'), ...context };
  if (method !== SHIP_DESIGN_METHOD_VERSION) return { ...empty('unsupported_method'), ...context };

  const engine = isRecord(result.engine) ? result.engine : null;
  const performance = isRecord(result.performance) ? result.performance : null;
  // The source's own status is the only authority on whether the residual
  // sections may be read. The native result declares `available` or `partial`;
  // any other word — `unavailable`, a failed status or a missing one — withholds
  // every number rather than letting a leftover payload read as valid.
  if (status !== 'available' && status !== 'partial') return { ...empty('unavailable'), ...context };
  if (!engine && !performance) return { ...empty('unavailable'), ...context };

  const design = isRecord(result.design) ? result.design : null;
  const editing = isRecord(design?.editing) ? design.editing : null;

  const propulsion: PropulsionSection = {
    declaration: {
      fuel: selectorIndices(engine, 'fuelArray', 5),
      engine: selectorIndices(engine, 'engineArray', 3),
      drive: selectorIndices(engine, 'driveArray', 4),
    },
    screws: numberAt(engine, 'screws'),
    facts: engineFacts(engine),
    lock: {
      locked: booleanAt(editing, 'power_locked'),
      powerHp: numberAt(editing, 'power_hp'),
      bunkerLt: numberAt(editing, 'locked_bunker_lt'),
    },
    ledger: ledgerRows(result as unknown as ShipDesignResult),
  };

  const perf: PerformanceSection = { groups: performanceGroups(performance), flags: performanceFlags(performance) };

  return { supported: true, problem: null, ...context, engine: propulsion, performance: perf };
}
