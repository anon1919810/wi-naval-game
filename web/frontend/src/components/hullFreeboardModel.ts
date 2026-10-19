import {
  FREEBOARD_ENDPOINTS, readFreeboardGeometry, type FreeboardGeometry,
} from './freeboardProfileModel';
import { basisConditionId } from './shipDesign';
import { SHIP_DESIGN_METHOD_VERSION, SHIP_DESIGN_RESULT_SCHEMA, isRecord } from './sps3b3Model';
import type { HullFreeboardKey } from '../i18n/hullFreeboard';
import type { ShipDesignResult } from '../types';

/**
 * The one pure reading of a native hull and freeboard result.
 *
 * This module computes no ship number and reads no formula. It takes the
 * normalized feet and source long tons the native result already saved, states
 * the design's own driver and depth-lock declarations exactly as they are, and
 * lists the eight freeboard endpoints and four deck fractions in source order.
 *
 * The rules are deliberately narrow:
 *
 * - **Source units remain the source's own.** Lengths are the result's
 *   normalized feet, the source displacement is long tons and the ledger
 *   balance is tonnes. Nothing here converts or reconciles them.
 * - **A declaration is true, false or unknown.** A missing or malformed driver
 *   or lock is unknown; it is never replaced by the control's default and a
 *   missing target is never a zero.
 * - **Zero, unknown and change stay distinct.** A saved zero or a negative
 *   freeboard height is a fact. A missing value is unknown. A known value that
 *   became unknown is a change; two unknowns are not.
 * - **No outline is invented.** The legacy geometry helper has zero fallbacks
 *   for a missing bow angle or stern extension, so this reader validates every
 *   station input and the fraction domain before it calls the helper. When the
 *   outline cannot be drawn, the independent endpoint facts still survive.
 * - **Comparison is gated.** Values are marked changed only when both results
 *   are readable and share one known basis condition.
 */

export type HullFreeboardProblem = 'absent' | 'unsupported_schema' | 'unsupported_method' | 'unavailable';

export type HullFactUnit = 'length' | 'lt' | 'ratio';

export interface HullFact {
  key: string;
  label: HullFreeboardKey;
  value: number | null;
  unit: HullFactUnit;
  /** The real catalogue field the reading reveals, when one exists. */
  editField?: string;
  changed: boolean;
}

/** The result's own declared drivers and depth lock, strictly read. */
export interface HullDrivers {
  lengthDriver: string | null;
  displacementDriver: string | null;
  depthLocked: boolean | null;
  /** The saved overall target, in the hull page's own unit. */
  overallTarget: number | null;
  /** The saved displacement target, in source long tons. */
  displacementTargetLt: number | null;
}

export interface HullSection {
  facts: HullFact[];
  drivers: HullDrivers;
}

export type FreeboardEndpointKey = typeof FREEBOARD_ENDPOINTS[number];

export interface FreeboardEndpoint {
  key: FreeboardEndpointKey;
  label: HullFreeboardKey;
  value: number | null;
  unit: 'length';
  editField: string;
  /** True while the saved depth lock owns this FD/AD endpoint. */
  pinned: boolean;
  changed: boolean;
}

export type FreeboardFractionKey = 'fcLength' | 'fdLength' | 'adLength' | 'qdLength';

export interface FreeboardFraction {
  key: FreeboardFractionKey;
  label: HullFreeboardKey;
  value: number | null;
  percent: number | null;
  changed: boolean;
}

export type FreeboardGeometryProblem = 'length' | 'heights' | 'bow' | 'stern' | 'fraction';

export interface FreeboardSection {
  endpoints: FreeboardEndpoint[];
  fractions: FreeboardFraction[];
  geometry: FreeboardGeometry | null;
  geometryProblem: FreeboardGeometryProblem | null;
}

/** The unified ledger balance, always in tonnes. */
export interface HullBalance {
  selectedT: number | null;
  estimateT: number | null;
  targetT: number | null;
  differenceT: number | null;
}

export interface HullFreeboard {
  supported: boolean;
  problem: HullFreeboardProblem | null;
  schema: string | null;
  method: string | null;
  status: string | null;
  basisConditionId: string | null;
  /** True only when both readable results share one known basis. */
  comparable: boolean;
  hull: HullSection;
  freeboard: FreeboardSection;
  balance: HullBalance;
}

const ENDPOINT_FIELDS: Readonly<Record<FreeboardEndpointKey, string>> = {
  freeQDAft: 'freeboard_quarterdeck_aft',
  freeQDFor: 'freeboard_quarterdeck_fore',
  freeADAft: 'freeboard_afterdeck_aft',
  freeADFor: 'freeboard_afterdeck_fore',
  freeFDAft: 'freeboard_flat_deck_aft',
  freeFDFor: 'freeboard_flat_deck_fore',
  freeFCAft: 'freeboard_forecastle_aft',
  freeFCFor: 'freeboard_forecastle_fore',
};

const DEPTH_PINNED = new Set<FreeboardEndpointKey>(['freeFDAft', 'freeFDFor', 'freeADAft', 'freeADFor']);

const FRACTIONS: ReadonlyArray<{ key: FreeboardFractionKey; field: string; label: HullFreeboardKey }> = [
  { key: 'fcLength', field: 'fcLength', label: 'freeboard.fraction.fcLength' },
  { key: 'fdLength', field: 'fdLength', label: 'freeboard.fraction.fdLength' },
  { key: 'adLength', field: 'adLength', label: 'freeboard.fraction.adLength' },
  { key: 'qdLength', field: 'qdLength', label: 'freeboard.fraction.qdLength' },
];

const HULL_FACTS: ReadonlyArray<{
  key: string; field: string; label: HullFreeboardKey; unit: HullFactUnit; editField?: string;
}> = [
  { key: 'hull.length', field: 'length', label: 'hull.fact.length', unit: 'length', editField: 'length_waterline' },
  { key: 'hull.lengthOA', field: 'lengthOA', label: 'hull.fact.lengthOA', unit: 'length' },
  { key: 'hull.beam', field: 'beam', label: 'hull.fact.beam', unit: 'length', editField: 'beam_moulded' },
  { key: 'hull.beamBulges', field: 'beamBulges', label: 'hull.fact.beamBulges', unit: 'length', editField: 'beam_at_bulges' },
  { key: 'hull.draught', field: 'draught', label: 'hull.fact.draught', unit: 'length', editField: 'draught_normal' },
  { key: 'hull.block', field: 'block', label: 'hull.fact.block', unit: 'ratio', editField: 'block_coefficient_normal' },
  { key: 'hull.displacement', field: 'displacement', label: 'hull.fact.displacement', unit: 'lt' },
];

function numberAt(source: Record<string, unknown> | null, key: string): number | null {
  if (!source) return null;
  const value = source[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function recordAt(source: Record<string, unknown> | null, key: string): Record<string, unknown> | null {
  return isRecord(source?.[key]) ? source[key] as Record<string, unknown> : null;
}

function choice(value: unknown, allowed: readonly string[]): string | null {
  return typeof value === 'string' && allowed.includes(value) ? value : null;
}

function emptyHull(): HullSection {
  return {
    facts: HULL_FACTS.map(item => ({
      key: item.key, label: item.label, value: null, unit: item.unit, editField: item.editField, changed: false,
    })),
    drivers: {
      lengthDriver: null, displacementDriver: null, depthLocked: null,
      overallTarget: null, displacementTargetLt: null,
    },
  };
}

function readHull(hull: Record<string, unknown> | null, editing: Record<string, unknown> | null): HullSection {
  const facts = HULL_FACTS.map(item => ({
    key: item.key, label: item.label, value: numberAt(hull, item.field), unit: item.unit,
    editField: item.editField, changed: false,
  }));
  return {
    facts,
    drivers: {
      lengthDriver: choice(editing?.length_driver, ['waterline', 'overall']),
      displacementDriver: choice(editing?.displacement_driver, ['block', 'displacement']),
      depthLocked: typeof editing?.depth_locked === 'boolean' ? editing.depth_locked : null,
      overallTarget: numberAt(editing, 'overall_length'),
      displacementTargetLt: numberAt(editing, 'normal_displacement_lt'),
    },
  };
}

function emptyFreeboard(): FreeboardSection {
  return {
    endpoints: FREEBOARD_ENDPOINTS.map(key => ({
      key, label: `freeboard.point.${key}` as HullFreeboardKey, value: null, unit: 'length',
      editField: ENDPOINT_FIELDS[key], pinned: false, changed: false,
    })),
    fractions: FRACTIONS.map(item => ({
      key: item.key, label: item.label, value: null, percent: null, changed: false,
    })),
    geometry: null,
    geometryProblem: null,
  };
}

function readFreeboard(
  result: Record<string, unknown> | null,
  freeboard: Record<string, unknown> | null,
  depthLocked: boolean,
): FreeboardSection {
  const endpoints = FREEBOARD_ENDPOINTS.map(key => ({
    key,
    label: `freeboard.point.${key}` as HullFreeboardKey,
    value: numberAt(freeboard, key),
    unit: 'length' as const,
    editField: ENDPOINT_FIELDS[key],
    pinned: depthLocked && DEPTH_PINNED.has(key),
    changed: false,
  }));
  const fractions = FRACTIONS.map(item => {
    const value = numberAt(freeboard, item.field);
    return { key: item.key, label: item.label, value, percent: value === null ? null : value * 100, changed: false };
  });
  const { geometry, geometryProblem } = guardGeometry(result, freeboard);
  return { endpoints, fractions, geometry, geometryProblem };
}

/**
 * The geometry helper has two deliberate zero fallbacks of its own: a missing
 * bow angle and a missing stern extension both draw as zero. The new reader
 * refuses those inputs before calling it, and also refuses a fraction domain the
 * helper would otherwise clamp or silently fold into the drawing.
 */
function guardGeometry(
  result: Record<string, unknown> | null,
  freeboard: Record<string, unknown> | null,
): { geometry: FreeboardGeometry | null; geometryProblem: FreeboardGeometryProblem | null } {
  const hull = recordAt(result, 'hull');
  const length = numberAt(hull, 'length');
  if (length === null || length <= 0) return { geometry: null, geometryProblem: 'length' };
  if (FREEBOARD_ENDPOINTS.some(key => numberAt(freeboard, key) === null)) {
    return { geometry: null, geometryProblem: 'heights' };
  }
  if (numberAt(freeboard, 'lengthBow') === null) return { geometry: null, geometryProblem: 'bow' };
  const stern = numberAt(freeboard, 'lengthStern');
  if (stern === null || stern < 0) return { geometry: null, geometryProblem: 'stern' };
  const fc = numberAt(freeboard, 'fcLength');
  const fd = numberAt(freeboard, 'fdLength');
  const qd = numberAt(freeboard, 'qdLength');
  const ad = numberAt(freeboard, 'adLength');
  const inDomain = (value: number | null): boolean => value === null || (value >= 0 && value <= 1);
  // All four real source fractions share one domain. A missing afterdeck is not
  // invented as zero; when it is declared, its value joins the total.
  if (fc === null || fd === null || qd === null || !inDomain(fc) || !inDomain(fd) || !inDomain(qd)
    || (ad !== null && !inDomain(ad)) || fc + fd + qd + (ad ?? 0) > 1 + 1e-6) {
    return { geometry: null, geometryProblem: 'fraction' };
  }
  const geometry = readFreeboardGeometry(result as ShipDesignResult | null);
  return geometry
    ? { geometry, geometryProblem: null }
    : { geometry: null, geometryProblem: 'length' };
}

function readBalance(result: Record<string, unknown> | null): HullBalance {
  const balance = recordAt(result, 'balance');
  return {
    selectedT: numberAt(balance, 'selected_mass_t'),
    estimateT: numberAt(balance, 'estimated_mass_t'),
    targetT: numberAt(balance, 'target_displacement_t'),
    differenceT: numberAt(balance, 'difference_t'),
  };
}

function empty(problem: HullFreeboardProblem): HullFreeboard {
  return {
    supported: false, problem, schema: null, method: null, status: null, basisConditionId: null,
    comparable: false, hull: emptyHull(), freeboard: emptyFreeboard(), balance: readBalance(null),
  };
}

function readSide(raw: unknown): HullFreeboard {
  const result = isRecord(raw) ? raw : null;
  if (!result) return empty('absent');

  const schema = typeof result.schema === 'string' ? result.schema : null;
  const method = typeof result.method_version === 'string' ? result.method_version : null;
  const status = typeof result.status === 'string' ? result.status : null;
  const basis = basisConditionId(result as unknown as ShipDesignResult);
  const context = { schema, method, status, basisConditionId: basis };

  if (schema !== SHIP_DESIGN_RESULT_SCHEMA) return { ...empty('unsupported_schema'), ...context };
  if (method !== SHIP_DESIGN_METHOD_VERSION) return { ...empty('unsupported_method'), ...context };
  if (status !== 'available' && status !== 'partial') return { ...empty('unavailable'), ...context };

  const hull = isRecord(result.hull) ? result.hull : null;
  const freeboard = isRecord(result.freeboard) ? result.freeboard : null;
  if (!hull && !freeboard) return { ...empty('unavailable'), ...context };

  const design = recordAt(result, 'design');
  const editing = recordAt(design, 'editing');
  const hullSection = readHull(hull, editing);
  const freeboardSection = readFreeboard(result, freeboard, hullSection.drivers.depthLocked === true);

  return {
    supported: true, problem: null, ...context, comparable: false,
    hull: hullSection, freeboard: freeboardSection, balance: readBalance(result),
  };
}

function sameValue(current: number | null, baseline: number | null): boolean {
  return current === baseline;
}

/** Mark one side changed only when the comparison gate accepted both results. */
function changed(current: number | null, baseline: number | null, comparable: boolean): boolean {
  if (!comparable) return false;
  return !sameValue(current, baseline);
}

/**
 * The hull and freeboard reading of one native result, or the named reason it
 * cannot be read. The optional baseline is the host's already-fetched saved
 * result; values are marked changed only when both sides share one known basis.
 */
export function readHullFreeboard(raw: unknown, baselineRaw?: unknown): HullFreeboard {
  const reading = readSide(raw);
  if (!reading.supported || baselineRaw === undefined) return reading;

  const baseline = readSide(baselineRaw);
  const comparable = baseline.supported
    && reading.basisConditionId !== null
    && reading.basisConditionId === baseline.basisConditionId;
  if (!comparable) return reading;

  return {
    ...reading,
    comparable: true,
    hull: {
      ...reading.hull,
      facts: reading.hull.facts.map(fact => ({
        ...fact,
        changed: changed(fact.value, baseline.hull.facts.find(item => item.key === fact.key)?.value ?? null, true),
      })),
      drivers: reading.hull.drivers,
    },
    freeboard: {
      ...reading.freeboard,
      endpoints: reading.freeboard.endpoints.map(item => ({
        ...item,
        changed: changed(item.value, baseline.freeboard.endpoints.find(entry => entry.key === item.key)?.value ?? null, true),
      })),
      fractions: reading.freeboard.fractions.map(item => ({
        ...item,
        changed: changed(item.value, baseline.freeboard.fractions.find(entry => entry.key === item.key)?.value ?? null, true),
      })),
    },
  };
}
