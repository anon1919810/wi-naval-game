import { balanceOf } from './shipDesign';
import { SHIP_DESIGN_METHOD_VERSION, SHIP_DESIGN_RESULT_SCHEMA, isRecord } from './sps3b3Model';
import {
  ARMAMENT_BANK_ORDER, ARMAMENT_LEDGER_ROLES, buildArmament,
  type ArmamentBank, type ArmamentLedgerRole,
} from './armamentModel';
import type { VesselLabelTable, VesselOverviewKey } from '../i18n/vesselOverview';
import type { ShipDesignBalance, ShipDesignResult } from '../types';

/**
 * The one pure reading behind the vessel design overview.
 *
 * The overview states independent known facts and names every unknown as
 * unknown; it makes no aggregate completeness claim and computes no ship number.
 * It reads the same saved native result the workbench and the frozen report
 * already hold and shapes it into six chapter sections:
 *
 * - **Hull** — the normalized waterline length, beam and draught in feet.
 * - **Freeboard** — the saved freeboard reading in feet.
 * - **Armament** — the five declared batteries, by identity, through the one
 *   armament reader (never a second reading, never a per-battery ledger split).
 * - **Armour** — the declared main-belt and deck thicknesses in inches and the
 *   deck-coverage choice through the same seven-option reader the diagram uses.
 * - **Propulsion** — the source speed, power and range, plus the localized fuel,
 *   engine and drive selector arrays. Source horsepower and nautical miles keep
 *   the unit the source saved; they are never relabelled.
 * - **Weight** — the unified balance in tonnes and the four global armament
 *   ledger roles in tonnes, with their policy and their estimate beside the
 *   selected mass. No selected mass is split across a battery.
 *
 * Every fact carries an explicit unit identity (or an enum table and index), so
 * the caller formats it in the reader's own units; nothing here converts.
 */

export type VesselProblem = 'absent' | 'unsupported_schema' | 'unsupported_method' | 'unavailable';
export type VesselSectionId = 'hull' | 'freeboard' | 'armament' | 'armour' | 'propulsion' | 'weight';

/**
 * The unit identity a fact must be shown in.
 *
 * `power-hp` and `range-nmi` are deliberately not convertible the way power and
 * length are: the source saved a horsepower figure and a nautical-mile range, and
 * the reader keeps them as labelled source facts.
 */
export type VesselFactKind =
  | 'length' | 'mass' | 'speed' | 'power-hp' | 'range-nmi' | 'inches'
  | 'count' | 'enum' | 'flags' | 'bank' | 'ledger' | 'text';

/** The compact per-battery summary the armament section states. */
export interface VesselBankFact {
  bank: number;
  id: string;
  state: ArmamentBank['state'];
  calibreIn: number | null;
  barrels: number | null;
  mounts: number | null;
}

/** The compact per-role armament ledger reading the weight section states. */
export interface VesselLedgerFact {
  role: ArmamentLedgerRole;
  mode: string | null;
  selectedT: number | null;
  estimateT: number | null;
}

export interface VesselFact {
  /** Stable identity for keys and tests. */
  key: string;
  /** The dictionary key of the fact's label. */
  label: VesselOverviewKey;
  /** The slots the label's own template needs (a battery number, say). */
  labelParams?: Record<string, string | number>;
  kind: VesselFactKind;
  /** The scalar value for the numeric kinds, or null when unknown. */
  value: number | null;
  /** The unit the scalar value is stored in, for the convertible kinds. */
  storedUnit?: string;
  /** The enum index for `enum` facts. */
  index?: number | null;
  /** The label table an `enum` or `flags` fact reads. */
  table?: VesselLabelTable;
  /** The declared selector indices for a `flags` fact, or null when not declared. */
  flags?: number[] | null;
  bank?: VesselBankFact;
  ledger?: VesselLedgerFact;
  /** A literal source string for a `text` fact. */
  text?: string | null;
  /** The chapter a navigation button opens. */
  chapter: string;
}

export interface VesselSection {
  id: VesselSectionId;
  /** The dictionary key of the section heading. */
  label: VesselOverviewKey;
  /** The chapter this section's button opens. */
  chapter: string;
  note: VesselOverviewKey | null;
  facts: VesselFact[];
}

export interface VesselOverview {
  supported: boolean;
  problem: VesselProblem | null;
  sections: VesselSection[];
}

/* ------------------------------------------------------------------ reading */

function numberAt(source: Record<string, unknown> | null, key: string): number | null {
  if (!source) return null;
  const raw = source[key];
  return typeof raw === 'number' && Number.isFinite(raw) ? raw : null;
}

function indexAt(source: Record<string, unknown> | null, key: string): number | null {
  const value = numberAt(source, key);
  return value !== null && Number.isInteger(value) ? value : null;
}

/**
 * The declared indices of one boolean selector array, or null when the array is
 * absent or malformed.
 *
 * An array only states a declaration when it is present, of exactly the
 * expected length, and every entry is a boolean. A shorter, longer or partly
 * numeric array cannot assert "none selected", so it is reported as unknown
 * (null); an exact array with no true entry is the explicit none-selected list.
 */
function selectorIndices(source: Record<string, unknown> | null, key: string, size: number): number[] | null {
  const raw = source?.[key];
  if (!Array.isArray(raw) || raw.length !== size || !raw.every(value => typeof value === 'boolean')) return null;
  const indices: number[] = [];
  raw.forEach((value, index) => { if (value === true) indices.push(index); });
  return indices;
}

function hullFacts(hull: Record<string, unknown> | null): VesselFact[] {
  const fact = (key: string, label: VesselOverviewKey, field: string): VesselFact =>
    ({ key, label, kind: 'length', value: numberAt(hull, field), storedUnit: 'ft', chapter: 'hull' });
  return [
    fact('hull.length', 'vessel.fact.length', 'length'),
    fact('hull.beam', 'vessel.fact.beam', 'beam'),
    fact('hull.draught', 'vessel.fact.draught', 'draught'),
  ];
}

function freeboardFacts(freeboard: Record<string, unknown> | null): VesselFact[] {
  return [{ key: 'freeboard.freeboard', label: 'vessel.fact.freeboard', kind: 'length', value: numberAt(freeboard, 'freeboard'), storedUnit: 'ft', chapter: 'freeboard' }];
}

function armamentFacts(banks: ReadonlyArray<Pick<ArmamentBank, 'bank' | 'id' | 'state' | 'calibreIn' | 'barrels' | 'mounts'>>): VesselFact[] {
  return banks.map(bank => ({
    key: `armament.bank${bank.bank}`, label: 'armament.bank.label', labelParams: { bank: bank.bank },
    kind: 'bank', value: null, chapter: 'guns',
    bank: { bank: bank.bank, id: bank.id, state: bank.state, calibreIn: bank.calibreIn, barrels: bank.barrels, mounts: bank.mounts },
  }));
}

function armourFacts(armour: Record<string, unknown> | null): VesselFact[] {
  return [
    { key: 'armour.beltMain', label: 'vessel.fact.beltMain', kind: 'inches', value: numberAt(armour, 'beltMain'), chapter: 'armour' },
    { key: 'armour.deck', label: 'vessel.fact.deck', kind: 'inches', value: numberAt(armour, 'deck'), chapter: 'armour' },
    { key: 'armour.deckCoverage', label: 'vessel.fact.deckCoverage', kind: 'enum', value: null, index: indexAt(armour, 'deckCoverage'), table: 'deckCoverage', chapter: 'armour' },
  ];
}

function propulsionFacts(engine: Record<string, unknown> | null): VesselFact[] {
  const scalar = (key: string, label: VesselOverviewKey, kind: VesselFactKind, field: string, storedUnit?: string): VesselFact =>
    ({ key, label, kind, value: numberAt(engine, field), storedUnit, chapter: 'propulsion' });
  const flags = (key: string, label: VesselOverviewKey, table: VesselLabelTable, field: string, size: number): VesselFact =>
    ({ key, label, kind: 'flags', value: null, table, flags: selectorIndices(engine, field, size), chapter: 'propulsion' });
  return [
    scalar('propulsion.speedMax', 'vessel.fact.speedMax', 'speed', 'speedMax', 'kn'),
    scalar('propulsion.speedCruise', 'vessel.fact.speedCruise', 'speed', 'speedCruise', 'kn'),
    scalar('propulsion.hpMax', 'vessel.fact.hpMax', 'power-hp', 'hpMax'),
    scalar('propulsion.range', 'vessel.fact.range', 'range-nmi', 'range'),
    flags('propulsion.fuel', 'vessel.fact.fuel', 'fuel', 'fuelArray', 5),
    flags('propulsion.engine', 'vessel.fact.engine', 'engine', 'engineArray', 3),
    flags('propulsion.drive', 'vessel.fact.drive', 'drive', 'driveArray', 4),
  ];
}

function weightFacts(balance: ShipDesignBalance | null, rows: Record<ArmamentLedgerRole, { mode: string | null; selectedT: number | null; estimateT: number | null }>): VesselFact[] {
  const mass = (key: string, label: VesselOverviewKey, value: number | null): VesselFact =>
    ({ key, label, kind: 'mass', value, storedUnit: 't', chapter: 'weights' });
  const facts: VesselFact[] = [
    mass('weight.selected', 'vessel.fact.balanceSelected', balance?.selected_mass_t ?? null),
    mass('weight.estimate', 'vessel.fact.balanceEstimate', balance?.estimated_mass_t ?? null),
    mass('weight.target', 'vessel.fact.balanceTarget', balance?.target_displacement_t ?? null),
    mass('weight.difference', 'vessel.fact.balanceDifference', balance?.difference_t ?? null),
  ];
  const ledgerLabels: Record<ArmamentLedgerRole, VesselOverviewKey> = {
    guns: 'vessel.fact.ledgerGuns', mounts: 'vessel.fact.ledgerMounts',
    ammunition: 'vessel.fact.ledgerAmmunition', gun_armour: 'vessel.fact.ledgerGunArmour',
  };
  for (const role of ARMAMENT_LEDGER_ROLES) {
    facts.push({
      key: `weight.ledger.${role}`, label: ledgerLabels[role], kind: 'ledger', value: null, chapter: 'weights',
      ledger: { role, mode: rows[role]?.mode ?? null, selectedT: rows[role]?.selectedT ?? null, estimateT: rows[role]?.estimateT ?? null },
    });
  }
  return facts;
}

function emptySections(): VesselSection[] {
  return [
    { id: 'hull', label: 'vessel.section.hull', chapter: 'hull', note: null, facts: hullFacts(null) },
    { id: 'freeboard', label: 'vessel.section.freeboard', chapter: 'freeboard', note: 'vessel.fact.freeboardNote', facts: freeboardFacts(null) },
    { id: 'armament', label: 'vessel.section.armament', chapter: 'guns', note: 'vessel.fact.armamentNote', facts: armamentFacts(ARMAMENT_BANK_ORDER.map(bank => ({ bank, id: `gun${bank}`, state: 'missing' as const, calibreIn: null, barrels: null, mounts: null }))) },
    { id: 'armour', label: 'vessel.section.armour', chapter: 'armour', note: null, facts: armourFacts(null) },
    { id: 'propulsion', label: 'vessel.section.propulsion', chapter: 'propulsion', note: 'vessel.fact.propulsionNote', facts: propulsionFacts(null) },
    { id: 'weight', label: 'vessel.section.weight', chapter: 'weights', note: 'vessel.fact.ledgerNote', facts: weightFacts(null, {} as never) },
  ];
}

/**
 * The overview of one native result, or the named reason it cannot be drawn.
 *
 * A result that declares another shape or method says so and carries no facts; a
 * result that carries none of the native sections is unavailable. A supported
 * result always yields all six sections, with every undeclared value unknown.
 */
export function buildVesselOverview(raw: unknown): VesselOverview {
  const result = isRecord(raw) ? raw : null;
  if (!result) return { supported: false, problem: 'absent', sections: [] };
  const schema = typeof result.schema === 'string' ? result.schema : null;
  const method = typeof result.method_version === 'string' ? result.method_version : null;
  if (schema !== SHIP_DESIGN_RESULT_SCHEMA) return { supported: false, problem: 'unsupported_schema', sections: [] };
  if (method !== SHIP_DESIGN_METHOD_VERSION) return { supported: false, problem: 'unsupported_method', sections: [] };

  const native = result as ShipDesignResult;
  const hull = isRecord(result.hull) ? result.hull : null;
  const freeboard = isRecord(result.freeboard) ? result.freeboard : null;
  const armour = isRecord(result.armour) ? result.armour : null;
  const engine = isRecord(result.engine) ? result.engine : null;
  const armament = buildArmament(result);
  const balance = balanceOf(native);
  if (!hull && !freeboard && !armour && !engine && !armament.supported && !balance) {
    return { supported: false, problem: 'unavailable', sections: [] };
  }

  const sections: VesselSection[] = [
    { id: 'hull', label: 'vessel.section.hull', chapter: 'hull', note: null, facts: hullFacts(hull) },
    { id: 'freeboard', label: 'vessel.section.freeboard', chapter: 'freeboard', note: 'vessel.fact.freeboardNote', facts: freeboardFacts(freeboard) },
    { id: 'armament', label: 'vessel.section.armament', chapter: 'guns', note: 'vessel.fact.armamentNote', facts: armamentFacts(armament.banks) },
    { id: 'armour', label: 'vessel.section.armour', chapter: 'armour', note: null, facts: armourFacts(armour) },
    { id: 'propulsion', label: 'vessel.section.propulsion', chapter: 'propulsion', note: 'vessel.fact.propulsionNote', facts: propulsionFacts(engine) },
    { id: 'weight', label: 'vessel.section.weight', chapter: 'weights', note: 'vessel.fact.ledgerNote', facts: weightFacts(balance, armament.ledger) },
  ];
  return { supported: true, problem: null, sections };
}

/** The empty overview, for the one test that needs the six-section skeleton. */
export function emptyVesselOverviewSections(): VesselSection[] {
  return emptySections();
}
