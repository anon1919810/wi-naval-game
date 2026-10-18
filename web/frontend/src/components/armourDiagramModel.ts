import { readFreeboardGeometry, type FreeboardGeometry } from './freeboardProfileModel';
import { balanceOf, basisConditionId, ledgerEntries } from './shipDesign';
import { SHIP_DESIGN_METHOD_VERSION, SHIP_DESIGN_RESULT_SCHEMA, isRecord } from './sps3b3Model';
import type { ShipDesignBalance, ShipDesignLedgerEntry, ShipDesignResult } from '../types';

/**
 * The one pure reading behind the armour diagram.
 *
 * This module computes no ship number. It reads the saved native result that the
 * ordinary workbench and the frozen report already hold — hull length and beam,
 * the shared freeboard endpoints, the armour block, the managed ledger and the
 * unified balance — and reports exactly what is there. Everything a drawing needs
 * to be honest lives here, with no React and no copy:
 *
 * - **Unknown stays unknown.** A value that is absent, null, non-finite or out
 *   of domain is reported as unknown, never as zero; a saved zero is a fact and
 *   is reported as zero.
 * - **Nothing is clamped into a plausible shape.** A belt longer than the hull,
 *   a non-positive hull length, a negative deck fraction or fractions that do not
 *   fit the hull each carry an explicit problem instead of a silently trimmed
 *   band. The saved freeboard fractions round in single precision, so the one
 *   documented tolerance (`FRACTION_TOLERANCE`) accepts that rounding and nothing
 *   larger.
 * - **Mass is the ledger's alone.** The armour block's `weight*` values are long
 *   tons, not the ledger's tonnes, so they are never read as masses; every shown
 *   mass is the per-role ledger's own selected or estimated tonnes.
 * - **Placement is never invented.** A belt's length and height say nothing about
 *   where along the hull it sits; the drawing states its own convention and the
 *   reader leaves placement alone. The bulkhead's declared type and beam are kept
 *   as source facts, not translated into a known torpedo arrangement.
 * - **Changes are comparisons of known facts only.** A region is highlighted only
 *   when a known dimension, coverage, bulkhead type or ledger reading differs
 *   from the saved revision, or an unknown became known; two unchanged unknowns
 *   are never a change.
 */

export type ArmourBandRole = 'belt_main' | 'belt_ends' | 'belt_upper' | 'bulkhead' | 'bulge';
export type ArmourRegionRole = ArmourBandRole | 'deck' | 'conning';
export type ArmourProblem = 'absent' | 'unsupported_schema' | 'unsupported_method' | 'unavailable';
export type LengthProblem = 'missing' | 'negative' | 'overlong' | 'nohull';
export type DeckSegmentKey = 'quarterdeck' | 'afterdeck' | 'flatDeck' | 'forecastle';

/** The belts, bulkheads and bulges, in the order the diagram reads them. */
export const ARMOUR_BAND_ORDER: readonly ArmourBandRole[] = ['belt_main', 'belt_ends', 'belt_upper', 'bulkhead', 'bulge'];
/** Every selectable region, bands first, then the deck and the conning towers. */
export const ARMOUR_REGION_ORDER: readonly ArmourRegionRole[] = [...ARMOUR_BAND_ORDER, 'deck', 'conning'];
/** The four declared deck-partition fractions, aft to fore. */
export const DECK_SEGMENT_ORDER: readonly DeckSegmentKey[] = ['quarterdeck', 'afterdeck', 'flatDeck', 'forecastle'];

/**
 * The tolerance the saved deck fractions are read with.
 *
 * The native fractions are single-precision floats, so the four forecastle,
 * flat-deck, afterdeck and quarterdeck lengths can total 1.0000000149… on a real
 * reply. A part-per-million tolerance accepts that rounding; anything larger is
 * reported as an overlong, unplottable declaration rather than trimmed.
 */
export const FRACTION_TOLERANCE = 1e-6;

export interface ArmourLedgerReading {
  role: ArmourRegionRole;
  mode: string | null;
  estimateT: number | null;
  selectedT: number | null;
}

export interface ArmourBand {
  role: ArmourBandRole;
  lengthFt: number | null;
  heightFt: number | null;
  thicknessIn: number | null;
  inclinationDeg: number | null;
  /** The declared bulkhead beam, in feet; only a bulkhead carries one. */
  beamFt: number | null;
  /** Whether this band's length can be drawn to proportion at all. */
  lengthValid: boolean;
  lengthProblem: LengthProblem | null;
  /** The source field the explicit Edit opens and focuses. */
  editField: string;
}

export interface ArmourDeckSegment {
  key: DeckSegmentKey;
  fraction: number | null;
  /** The fraction's own start and end along the hull, when every earlier one is known. */
  start: number | null;
  end: number | null;
  valid: boolean;
}

export interface ArmourDeck {
  segments: ArmourDeckSegment[];
  totalFraction: number | null;
  totalValid: boolean;
  overlong: boolean;
  /** A declared fraction is negative or greater than one. */
  invalid: boolean;
  thicknessIn: number | null;
  forecastleThicknessIn: number | null;
  quarterdeckThicknessIn: number | null;
  /** The source selector index, 0..6, or null when it is absent. */
  coverageIndex: number | null;
  editField: string;
}

export interface ArmourTower {
  role: 'conning_for' | 'conning_aft';
  thicknessIn: number | null;
  editField: string;
}

export interface ArmourContext {
  schema: string | null;
  method: string | null;
  status: string | null;
  basisConditionId: string | null;
  hullLengthFt: number | null;
  beamFt: number | null;
  /** The source bulkhead selector index, 0 or 1, or null when it is absent. */
  bulkheadTypeIndex: number | null;
  sourceName: string | null;
  armourWarn: boolean;
  beltCover: number | null;
  maxBeltHeightFt: number | null;
}

export interface ArmourDiagram {
  supported: boolean;
  problem: ArmourProblem | null;
  context: ArmourContext;
  bands: ArmourBand[];
  deck: ArmourDeck | null;
  towers: ArmourTower[];
  /** The saved freeboard endpoints, read through the one shared geometry reader. */
  freeboard: FreeboardGeometry | null;
  /** One reading per region, always present (a missing role reads as null). */
  ledger: Record<ArmourRegionRole, ArmourLedgerReading | null>;
  balance: ShipDesignBalance | null;
  /** Whether a compatible saved revision was supplied to compare against. */
  comparable: boolean;
  changed: Partial<Record<ArmourRegionRole, boolean>>;
}

/** The source parameter behind each region's Edit. */
const BAND_FIELDS: Record<ArmourBandRole, string> = {
  belt_main: 'armour_belt_main_length',
  belt_ends: 'armour_belt_ends_length',
  belt_upper: 'armour_belt_upper_length',
  bulkhead: 'armour_bulkhead_length',
  bulge: 'armour_bulge_length',
};

/** The raw armour keys that describe each band, for both the reading and the comparison. */
const BAND_KEYS: Record<ArmourBandRole, { length: string; height: string; thickness: string; inclination: string | null; beam: string | null; type: string | null }> = {
  belt_main: { length: 'beltMainLength', height: 'beltMainHeight', thickness: 'beltMain', inclination: 'beltsIncline', beam: null, type: null },
  belt_ends: { length: 'beltEndsLength', height: 'beltEndsHeight', thickness: 'beltEnds', inclination: null, beam: null, type: null },
  belt_upper: { length: 'beltUpperLength', height: 'beltUpperHeight', thickness: 'beltUpper', inclination: null, beam: null, type: null },
  bulkhead: { length: 'bulkheadLength', height: 'bulkheadHeight', thickness: 'bulkhead', inclination: null, beam: 'bulkheadBeam', type: 'bulkheadType' },
  bulge: { length: 'bulgeLength', height: 'bulgeHeight', thickness: 'bulge', inclination: null, beam: null, type: null },
};

function emptyLedger(): Record<ArmourRegionRole, ArmourLedgerReading | null> {
  return { belt_main: null, belt_ends: null, belt_upper: null, bulkhead: null, bulge: null, deck: null, conning: null };
}

function numberAt(source: Record<string, unknown> | null, key: string): number | null {
  if (!source) return null;
  const raw = source[key];
  return typeof raw === 'number' && Number.isFinite(raw) ? raw : null;
}

function stringAt(source: Record<string, unknown> | null, key: string): string | null {
  if (!source) return null;
  const raw = source[key];
  return typeof raw === 'string' && raw !== '' ? raw : null;
}

function lengthReading(lengthFt: number | null, hullLengthFt: number | null): { valid: boolean; problem: LengthProblem | null } {
  if (lengthFt === null) return { valid: false, problem: 'missing' };
  if (lengthFt < 0) return { valid: false, problem: 'negative' };
  if (hullLengthFt === null || hullLengthFt <= 0) return { valid: false, problem: 'nohull' };
  if (lengthFt > hullLengthFt + FRACTION_TOLERANCE) return { valid: false, problem: 'overlong' };
  return { valid: true, problem: null };
}

function ledgerReading(entries: ShipDesignLedgerEntry[], role: ArmourRegionRole): ArmourLedgerReading | null {
  const entry = entries.find(item => item.role === role);
  if (!entry) return null;
  return {
    role,
    mode: typeof entry.mode === 'string' ? entry.mode : null,
    estimateT: typeof entry.estimate_t === 'number' && Number.isFinite(entry.estimate_t) ? entry.estimate_t : null,
    selectedT: typeof entry.selected_mass_t === 'number' && Number.isFinite(entry.selected_mass_t) ? entry.selected_mass_t : null,
  };
}

function ledgerFacts(reading: ArmourLedgerReading | null): Array<string | number | null> {
  return reading ? [reading.mode, reading.estimateT, reading.selectedT] : [null, null, null];
}

/** Whether two readings differ, treating an absent reading and an unknown as the same. */
function differs(left: unknown, right: unknown): boolean {
  const a = left === undefined ? null : left;
  const b = right === undefined ? null : right;
  return a !== b;
}

function anyDiffers(left: Array<unknown>, right: Array<unknown>): boolean {
  return left.some((value, index) => differs(value, right[index]));
}

/** Same schema, same method and the same declared basis, or the comparison is not offered. */
function compatible(raw: Record<string, unknown>, before: unknown): boolean {
  if (!isRecord(before)) return false;
  if (before.schema !== SHIP_DESIGN_RESULT_SCHEMA || raw.schema !== SHIP_DESIGN_RESULT_SCHEMA) return false;
  if (before.method_version !== SHIP_DESIGN_METHOD_VERSION || raw.method_version !== SHIP_DESIGN_METHOD_VERSION) return false;
  const rawBasis = basisConditionId(raw as unknown as ShipDesignResult);
  const beforeBasis = basisConditionId(before as unknown as ShipDesignResult);
  return Boolean(rawBasis) && Boolean(beforeBasis) && rawBasis === beforeBasis;
}

function deckSegments(freeboard: Record<string, unknown> | null): ArmourDeckSegment[] {
  const fractions: Record<DeckSegmentKey, string> = {
    quarterdeck: 'qdLength', afterdeck: 'adLength', flatDeck: 'fdLength', forecastle: 'fcLength',
  };
  let cursor: number | null = 0;
  return DECK_SEGMENT_ORDER.map(key => {
    const fraction = numberAt(freeboard, fractions[key]);
    const valid = fraction !== null && fraction >= 0 && fraction <= 1 + FRACTION_TOLERANCE;
    let start: number | null = null;
    let end: number | null = null;
    if (fraction === null || cursor === null) {
      cursor = null;
    } else {
      start = cursor;
      end = cursor + fraction;
      cursor = end;
    }
    return { key, fraction, start, end, valid };
  });
}

/** The known dimension facts of one band, in the order both the reading and the comparison use. */
function bandFacts(record: Record<string, unknown> | null, role: ArmourBandRole): Array<number | null> {
  const keys = BAND_KEYS[role];
  const facts = [numberAt(record, keys.length), numberAt(record, keys.height), numberAt(record, keys.thickness)];
  facts.push(keys.inclination ? numberAt(record, keys.inclination) : null);
  facts.push(keys.beam ? numberAt(record, keys.beam) : null);
  facts.push(keys.type ? numberAt(record, keys.type) : null);
  return facts;
}

export function buildArmourDiagram(raw: unknown, before?: unknown): ArmourDiagram {
  const context: ArmourContext = {
    schema: null, method: null, status: null, basisConditionId: null, hullLengthFt: null, beamFt: null,
    bulkheadTypeIndex: null, sourceName: null, armourWarn: false, beltCover: null, maxBeltHeightFt: null,
  };
  const result = isRecord(raw) ? raw : null;
  const empty: ArmourDiagram = {
    supported: false, problem: 'absent', context, bands: [], deck: null, towers: [], freeboard: null,
    ledger: emptyLedger(), balance: null, comparable: false, changed: {},
  };
  if (!result) return empty;

  context.schema = stringAt(result, 'schema');
  context.method = stringAt(result, 'method_version');
  context.status = stringAt(result, 'status');
  context.basisConditionId = basisConditionId(result as unknown as ShipDesignResult);

  if (context.schema !== SHIP_DESIGN_RESULT_SCHEMA) return { ...empty, problem: 'unsupported_schema' };
  if (context.method !== SHIP_DESIGN_METHOD_VERSION) return { ...empty, problem: 'unsupported_method' };

  const armour = isRecord(result.armour) ? result.armour : null;
  const hull = isRecord(result.hull) ? result.hull : null;
  const freeboardRecord = isRecord(result.freeboard) ? result.freeboard : null;
  const sourceDesign = isRecord(result.source_design) ? result.source_design : null;
  const parameters = isRecord(sourceDesign?.parameters) ? sourceDesign.parameters : null;

  context.hullLengthFt = numberAt(hull, 'length');
  context.beamFt = numberAt(hull, 'beam');
  context.bulkheadTypeIndex = numberAt(armour, 'bulkheadType');
  context.sourceName = stringAt(parameters, 'ship_name');
  context.armourWarn = armour?.armourWarn === true;
  context.beltCover = numberAt(armour, 'beltCover');
  context.maxBeltHeightFt = numberAt(armour, 'maxBeltHeight');

  if (!armour) return { ...empty, problem: 'unavailable', context };
  if (context.status === 'unavailable') return { ...empty, problem: 'unavailable', context };

  const entries = ledgerEntries(result as unknown as ShipDesignResult);
  const ledger = emptyLedger();
  for (const role of ARMOUR_REGION_ORDER) ledger[role] = ledgerReading(entries, role);

  const bands: ArmourBand[] = ARMOUR_BAND_ORDER.map(role => {
    const keys = BAND_KEYS[role];
    const lengthFt = numberAt(armour, keys.length);
    const reading = lengthReading(lengthFt, context.hullLengthFt);
    return {
      role, lengthFt, heightFt: numberAt(armour, keys.height), thicknessIn: numberAt(armour, keys.thickness),
      inclinationDeg: keys.inclination ? numberAt(armour, keys.inclination) : null,
      beamFt: keys.beam ? numberAt(armour, keys.beam) : null,
      lengthValid: reading.valid, lengthProblem: reading.problem, editField: BAND_FIELDS[role],
    };
  });

  const segments = deckSegments(freeboardRecord);
  const known = segments.every(segment => segment.fraction !== null);
  const invalid = segments.some(segment => segment.fraction !== null && !segment.valid);
  const totalFraction = known ? segments.reduce((sum, segment) => sum + (segment.fraction ?? 0), 0) : null;
  const overlong = totalFraction !== null && totalFraction > 1 + FRACTION_TOLERANCE;
  const deck: ArmourDeck = {
    segments, totalFraction, totalValid: known && !overlong && !invalid, overlong, invalid,
    thicknessIn: numberAt(armour, 'deck'),
    forecastleThicknessIn: numberAt(armour, 'deckFC'),
    quarterdeckThicknessIn: numberAt(armour, 'deckQD'),
    coverageIndex: numberAt(armour, 'deckCoverage'),
    editField: 'armour_deck_thickness',
  };

  const towers: ArmourTower[] = [
    { role: 'conning_for', thicknessIn: numberAt(armour, 'conningFor'), editField: 'armour_conning_forward_thickness' },
    { role: 'conning_aft', thicknessIn: numberAt(armour, 'conningAft'), editField: 'armour_conning_aft_thickness' },
  ];

  const diagram: ArmourDiagram = {
    supported: true, problem: null, context, bands, deck, towers,
    // The freeboard strip is drawn only when the deck declaration itself is a
    // usable proportion; an invalid or overflowing set of fractions would place
    // the endpoints at reversed or off-hull stations, so the context is withheld
    // rather than painted. The standalone freeboard profile keeps its own
    // arithmetic exactly as it was.
    freeboard: deck.totalValid ? readFreeboardGeometry(result as unknown as ShipDesignResult) : null,
    ledger, balance: balanceOf(result as unknown as ShipDesignResult), comparable: false, changed: {},
  };

  if (!compatible(result, before)) return diagram;
  const saved = before as Record<string, unknown>;
  const savedArmour = isRecord(saved.armour) ? saved.armour : null;
  const savedFreeboard = isRecord(saved.freeboard) ? saved.freeboard : null;
  const savedEntries = ledgerEntries(saved as unknown as ShipDesignResult);
  const changed: Partial<Record<ArmourRegionRole, boolean>> = {};
  for (const band of bands) {
    const current = [...bandFacts(armour, band.role), ...ledgerFacts(ledger[band.role])];
    const savedFacts = [...bandFacts(savedArmour, band.role), ...ledgerFacts(ledgerReading(savedEntries, band.role))];
    changed[band.role] = anyDiffers(current, savedFacts);
  }
  const currentDeck = [
    deck.thicknessIn, deck.forecastleThicknessIn, deck.quarterdeckThicknessIn, deck.coverageIndex,
    ...segments.map(segment => segment.fraction), ...ledgerFacts(ledger.deck),
  ];
  const savedSegments = deckSegments(savedFreeboard);
  const savedDeck = [
    numberAt(savedArmour, 'deck'), numberAt(savedArmour, 'deckFC'), numberAt(savedArmour, 'deckQD'), numberAt(savedArmour, 'deckCoverage'),
    ...savedSegments.map(segment => segment.fraction), ...ledgerFacts(ledgerReading(savedEntries, 'deck')),
  ];
  changed.deck = anyDiffers(currentDeck, savedDeck);
  const savedTowers = [numberAt(savedArmour, 'conningFor'), numberAt(savedArmour, 'conningAft'), ...ledgerFacts(ledgerReading(savedEntries, 'conning'))];
  changed.conning = anyDiffers([towers[0].thicknessIn, towers[1].thicknessIn, ...ledgerFacts(ledger.conning)], savedTowers);

  return { ...diagram, comparable: true, changed };
}
