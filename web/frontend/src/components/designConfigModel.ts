import { buildArmament, type ArmamentBank } from './armamentModel';
import { formatNumber } from './units';
import { vesselLabel, vesselOverviewCopy, type VesselLabelTable, type VesselOverviewKey } from '../i18n/vesselOverview';
import { isRecord } from './sps3b3Model';
import type { SiteLanguage } from '../portfolio/LanguageProvider';
import type { ShipDesignResult } from '../types';

/**
 * The configuration-changes rows of the frozen native comparison.
 *
 * This module is pure and reads only the two frozen results the report already
 * holds. It computes no ship number and invents no delta: a row is either a
 * physical quantity with a real numeric change, or a categorical declaration
 * printed as a current → comparison pair of labels with no numeric difference at
 * all. The direction is the one the reading table beside it uses — `current` is
 * the left column and `comparison` the right — so the two surfaces can never be
 * read as each other.
 *
 * The five battery rows are read through the one armament reader, so a battery
 * with a missing or ambiguous declaration says so rather than borrowing another
 * battery's configuration. Enum labels come from the same static tables the
 * overview and composition use; a value the table does not name stays unknown.
 */

export type ConfigGroup = 'battery' | 'hull' | 'armour' | 'propulsion';
export type ConfigKind = 'categorical' | 'number' | 'thickness';

export interface ConfigRow {
  /** Stable identity for keys and tests. */
  key: string;
  group: ConfigGroup;
  /** The dictionary key of the row's fact name. */
  label: VesselOverviewKey;
  /** The declared battery number, for a battery row. */
  bank?: number;
  kind: ConfigKind;
  /** The categorical text for each side (current → comparison). */
  beforeText: string;
  afterText: string;
  /** The numeric reading for each side when the row is a physical quantity. */
  before?: number | null;
  after?: number | null;
  /** The reader dimension the numeric value converts through, and its stored unit. */
  dimension?: 'length' | 'speed';
  storedUnit?: string;
  /**
   * The source's own unit for a numeric row the reader never converts, printed
   * as saved. An empty string is a plain count with no unit at all. A row with a
   * canonical unit carries no `dimension`, so the two are never both present.
   */
  canonical?: string;
}

function numberAt(source: Record<string, unknown> | null, key: string): number | null {
  if (!source) return null;
  const raw = source[key];
  return typeof raw === 'number' && Number.isFinite(raw) ? raw : null;
}

function section(result: ShipDesignResult, name: string): Record<string, unknown> | null {
  const raw = (result as unknown as Record<string, unknown>)[name];
  return isRecord(raw) ? raw : null;
}

/** One battery's declared configuration, or the reason it cannot be read. */
function bankText(bank: ArmamentBank, language: SiteLanguage): string {
  const w = (key: VesselOverviewKey, params?: Record<string, string | number>): string => vesselOverviewCopy(language, key, params);
  if (bank.state === 'missing' || bank.state === 'ambiguous') return w('vessel.config.unavailable');
  const label = (table: VesselLabelTable, index: number | null): string => vesselLabel(language, table, index) ?? w('vessel.unknown');
  const count = (value: number | null): string => value === null ? w('vessel.unknown') : formatNumber(value);
  const group = (index: number, table: VesselLabelTable): string => label(table, bank.groups[index]?.selector ?? null);
  return [
    label('gunType', bank.gunType),
    label('mountType', bank.mountType),
    bank.calibreIn === null ? w('vessel.unknown') : `${formatNumber(bank.calibreIn)} in`,
    `${w('armament.fact.barrels')} ${count(bank.barrels)}`,
    `${w('armament.fact.mounts')} ${count(bank.mounts)}`,
    `${label('layout', bank.groups[0]?.layout ?? null)} / ${label('layout', bank.groups[1]?.layout ?? null)}`,
    `${group(0, 'selector')} / ${group(1, 'selector')}`,
  ].join(' · ');
}

/** One boolean selector array as its declared labels, or the reason it is not read. */
function flagsText(source: Record<string, unknown> | null, key: string, size: number,
  table: VesselLabelTable, language: SiteLanguage): string {
  const raw = source?.[key];
  const w = (index: VesselOverviewKey): string => vesselOverviewCopy(language, index);
  if (!Array.isArray(raw) || raw.length !== size || !raw.every(value => typeof value === 'boolean')) return w('armament.flags.unknown');
  const indices: number[] = [];
  raw.forEach((value, index) => { if (value === true) indices.push(index); });
  if (indices.length === 0) return w('armament.flags.none');
  return indices.map(index => vesselLabel(language, table, index) ?? w('vessel.unknown')).join(' · ');
}

function thicknessText(value: number | null, language: SiteLanguage): string {
  if (value === null) return vesselOverviewCopy(language, 'vessel.unknown');
  return `${formatNumber(value)} in (${formatNumber(value * 25.4)} mm)`;
}

function enumText(table: VesselLabelTable, source: Record<string, unknown> | null, key: string, language: SiteLanguage): string {
  const raw = source?.[key];
  const index = typeof raw === 'number' && Number.isInteger(raw) ? raw : null;
  return vesselLabel(language, table, index) ?? vesselOverviewCopy(language, 'vessel.unknown');
}

/** The result's own `design.editing` block, or null when it is not a record. */
function editingOf(result: ShipDesignResult): Record<string, unknown> | null {
  const design = section(result, 'design');
  return isRecord(design?.editing) ? design.editing : null;
}

/**
 * The declared power lock, strictly: true says locked, false says unlocked and a
 * missing or non-boolean flag says the declaration itself is not saved. A missing
 * flag is never printed as the explicit unlocked wording.
 */
function lockText(editing: Record<string, unknown> | null, language: SiteLanguage): string {
  const flag = editing?.power_locked;
  if (typeof flag !== 'boolean') return vesselOverviewCopy(language, 'vessel.config.lock.undeclared');
  return flag
    ? vesselOverviewCopy(language, 'vessel.config.lock.locked')
    : vesselOverviewCopy(language, 'vessel.config.lock.unlocked');
}

/**
 * The locked power and bunker target, in the source's own horsepower and long
 * tons, only while the lock is declared true. An unlocked or undeclared lock has
 * no target in force, so the row says unknown rather than borrowing a residual
 * number; a declared lock that omits one value shows unknown for that value
 * alone and never a zero.
 */
function lockTargetText(editing: Record<string, unknown> | null, language: SiteLanguage): string {
  if (editing?.power_locked !== true) return '';
  const unknown = vesselOverviewCopy(language, 'vessel.unknown');
  const powerHp = numberAt(editing, 'power_hp');
  const bunkerLt = numberAt(editing, 'locked_bunker_lt');
  const power = powerHp === null ? unknown : `${formatNumber(powerHp)} source hp`;
  const bunker = bunkerLt === null ? unknown : `${formatNumber(bunkerLt)} LT`;
  return `${power} · ${bunker}`;
}

/**
 * The configuration rows, current → comparison, with no invented numeric delta.
 *
 * A categorical row carries only its two label texts; a physical quantity carries
 * its two numbers and the unit identity it is read in, so the caller formats it
 * in the reader's own units. Every row is always present, so a fact that is not
 * declared reads as unknown on its own side rather than disappearing.
 */
export function configChangeRows(current: ShipDesignResult, comparison: ShipDesignResult, language: SiteLanguage): ConfigRow[] {
  const w = (key: VesselOverviewKey): string => vesselOverviewCopy(language, key);
  const currentArmament = buildArmament(current);
  const comparisonArmament = buildArmament(comparison);
  const rows: ConfigRow[] = [];

  for (const bank of currentArmament.banks) {
    const other = comparisonArmament.banks.find(item => item.bank === bank.bank) ?? null;
    rows.push({
      key: `battery.${bank.bank}`, group: 'battery', label: 'vessel.config.battery', bank: bank.bank,
      kind: 'categorical',
      beforeText: bankText(bank, language),
      afterText: other ? bankText(other, language) : w('vessel.config.unavailable'),
    });
  }

  const currentHull = section(current, 'hull');
  const comparisonHull = section(comparison, 'hull');
  for (const [key, label] of [['length', 'vessel.fact.length'], ['beam', 'vessel.fact.beam'], ['draught', 'vessel.fact.draught']] as const) {
    rows.push({
      key: `hull.${key}`, group: 'hull', label, kind: 'number', dimension: 'length', storedUnit: 'ft',
      before: numberAt(currentHull, key), after: numberAt(comparisonHull, key),
      beforeText: '', afterText: '',
    });
  }

  const currentArmour = section(current, 'armour');
  const comparisonArmour = section(comparison, 'armour');
  for (const [key, label] of [['beltMain', 'vessel.fact.beltMain'], ['deck', 'vessel.fact.deck']] as const) {
    rows.push({
      key: `armour.${key}`, group: 'armour', label, kind: 'thickness',
      before: numberAt(currentArmour, key), after: numberAt(comparisonArmour, key),
      beforeText: thicknessText(numberAt(currentArmour, key), language),
      afterText: thicknessText(numberAt(comparisonArmour, key), language),
    });
  }
  rows.push({
    key: 'armour.deckCoverage', group: 'armour', label: 'vessel.fact.deckCoverage', kind: 'categorical',
    beforeText: enumText('deckCoverage', currentArmour, 'deckCoverage', language),
    afterText: enumText('deckCoverage', comparisonArmour, 'deckCoverage', language),
  });

  const currentEngine = section(current, 'engine');
  const comparisonEngine = section(comparison, 'engine');
  for (const [key, label] of [['speedMax', 'vessel.fact.speedMax'], ['speedCruise', 'vessel.fact.speedCruise']] as const) {
    rows.push({
      key: `propulsion.${key}`, group: 'propulsion', label, kind: 'number', dimension: 'speed', storedUnit: 'kn',
      before: numberAt(currentEngine, key), after: numberAt(comparisonEngine, key),
      beforeText: '', afterText: '',
    });
  }
  rows.push({
    key: 'propulsion.range', group: 'propulsion', label: 'vessel.fact.range', kind: 'number', canonical: 'nmi',
    before: numberAt(currentEngine, 'range'), after: numberAt(comparisonEngine, 'range'),
    beforeText: '', afterText: '',
  });
  rows.push({
    key: 'propulsion.screws', group: 'propulsion', label: 'vessel.fact.screws', kind: 'number', canonical: '',
    before: numberAt(currentEngine, 'screws'), after: numberAt(comparisonEngine, 'screws'),
    beforeText: '', afterText: '',
  });
  for (const [key, label, size, table] of [
    ['fuelArray', 'vessel.fact.fuel', 5, 'fuel'],
    ['engineArray', 'vessel.fact.engine', 3, 'engine'],
    ['driveArray', 'vessel.fact.drive', 4, 'drive'],
  ] as const) {
    rows.push({
      key: `propulsion.${key}`, group: 'propulsion', label, kind: 'categorical',
      beforeText: flagsText(currentEngine, key, size, table, language),
      afterText: flagsText(comparisonEngine, key, size, table, language),
    });
  }
  const currentEditing = editingOf(current);
  const comparisonEditing = editingOf(comparison);
  rows.push({
    key: 'propulsion.powerLock', group: 'propulsion', label: 'vessel.fact.powerLock', kind: 'categorical',
    beforeText: lockText(currentEditing, language), afterText: lockText(comparisonEditing, language),
  });
  rows.push({
    key: 'propulsion.lockTarget', group: 'propulsion', label: 'vessel.fact.lockTarget', kind: 'categorical',
    beforeText: lockTargetText(currentEditing, language), afterText: lockTargetText(comparisonEditing, language),
  });

  return rows;
}

/** The dictionary key of one configuration group's heading. */
export function configGroupLabel(group: ConfigGroup): VesselOverviewKey {
  return `vessel.config.group.${group}` as VesselOverviewKey;
}
