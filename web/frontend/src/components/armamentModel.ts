import { balanceOf, basisConditionId, ledgerEntries } from './shipDesign';
import { SHIP_DESIGN_METHOD_VERSION, SHIP_DESIGN_RESULT_SCHEMA, isRecord } from './sps3b3Model';
import type { ShipDesignBalance, ShipDesignLedgerEntry, ShipDesignResult } from '../types';

/**
 * The one pure reading behind the armament composition.
 *
 * This module computes no ship number and reads no formula. It reads the saved
 * native `guns` block the way the source declared it and reports exactly what is
 * there, under five rules:
 *
 * - **Bank identity is declared, not positional.** `guns.groups` is keyed by the
 *   explicit integer `bank` 1..5 and its id `gunN`. A group whose bank is not
 *   1..5, whose id does not name its own bank, or that appears twice is
 *   *ambiguous*: it is reported as such and never silently assigned to another
 *   bank. A bank with no group is *missing*, which is not the same as a declared
 *   zero.
 * - **Zero, unknown and invalid stay distinct.** A saved zero is a fact; a
 *   missing field is unknown; a selector outside its own table is unknown, never
 *   the table's last entry. A negative count is kept as declared, never rounded
 *   into a plausible arrangement.
 * - **Selectors and actual counts stay separate.** The 15-way `selectorG*` and
 *   the returned `perMountG*` are read independently: two selectors with the
 *   same barrel count can still mean different mounts, so the reader never
 *   derives one from the other and never rebuilds the source event chain.
 * - **Units are the source's own.** Normalized calibre and the three armour
 *   thicknesses are inches; the declared/effective shell weights and the
 *   broadside weight are pounds; the returned gun, mount, magazine, mount-armour
 *   and total masses are long tons. None is converted here.
 * - **Mass authority is the ledger's.** The five source masses are estimates.
 *   The only selected masses are the global `ledger.roles` rows in tonnes, and
 *   they are never split across the five batteries.
 *
 * `superSuper` and `subSub` are read as declarations and stay nullable: an
 * undeclared flag is unknown and is never printed as an explicit false. No
 * station, arc, clearance or centre of gravity is inferred from any field.
 */

export type ArmamentProblem = 'absent' | 'unsupported_schema' | 'unsupported_method' | 'unavailable';
export type BankState = 'declared' | 'zero' | 'missing' | 'ambiguous';
export type ArmamentGroupKey = 'G1' | 'G2';

/** The two mount groups of one battery, in the source's own order. */
export const ARMAMENT_GROUP_ORDER: readonly ArmamentGroupKey[] = ['G1', 'G2'];
/** The five declared batteries, by the explicit bank integer. */
export const ARMAMENT_BANK_ORDER: readonly number[] = [1, 2, 3, 4, 5];
/** The four armament ledger roles the composition reads, in the source's order. */
export const ARMAMENT_LEDGER_ROLES = ['guns', 'mounts', 'ammunition', 'gun_armour'] as const;
export type ArmamentLedgerRole = typeof ARMAMENT_LEDGER_ROLES[number];

/** The fifteen 15-way selector choices, for range validation only. */
const SELECTOR_COUNT = 15;
/** The nineteen arrangement labels, index 18 being the explicit `None`. */
const LAYOUT_COUNT = 19;
/** The seven gun types and seven mount types. */
const GUN_TYPE_COUNT = 7;
const MOUNT_TYPE_COUNT = 7;

/**
 * The declared count a drawing may turn into glyphs, or null.
 *
 * A count is drawable only when it is a declared, non-negative integer. A
 * negative or fractional count is kept as raw text and never rounded into a
 * plausible whole arrangement.
 */
export function integralCount(value: number | null): number | null {
  return value !== null && Number.isInteger(value) && value >= 0 ? value : null;
}

export interface ArmamentGroup {
  key: ArmamentGroupKey;
  /** The declared guns-in-mount selector index 0..14, or null when missing/invalid. */
  selector: number | null;
  /** The declared arrangement index 0..18 (18 = None), or null when missing/invalid. */
  layout: number | null;
  /** The actual barrels-per-mount count the source returned, or null. */
  perMount: number | null;
  /** The mounts this group returns, or null. */
  mounts: number | null;
  /** Elevated mounts, deck mounts and depressed mounts, as returned. */
  elevated: number | null;
  deck: number | null;
  depressed: number | null;
}

export interface ArmamentBank {
  bank: number;
  id: string;
  state: BankState;
  barrels: number | null;
  mounts: number | null;
  calibreIn: number | null;
  gunType: number | null;
  mountType: number | null;
  year: number | null;
  calLength: number | null;
  magazine: number | null;
  groups: ArmamentGroup[];
  armFaceIn: number | null;
  armBackIn: number | null;
  armBottomIn: number | null;
  shellWeightDeclaredLb: number | null;
  shellWeightLb: number | null;
  autoShellWeightLb: number | null;
  broadsideWeightLb: number | null;
  gunWeightLt: number | null;
  mountWeightLt: number | null;
  magazineWeightLt: number | null;
  armWeightLt: number | null;
  totalWeightLt: number | null;
  /** The declared double-elevation and double-depression flags, or null when not declared. */
  superSuper: boolean | null;
  subSub: boolean | null;
  /** The source field the explicit Edit opens and focuses. */
  editField: string;
  /** Whether a compatible saved revision differs on any read fact. */
  changed: boolean;
}

export interface ArmamentLedgerRow {
  role: ArmamentLedgerRole;
  mode: string | null;
  selectedT: number | null;
  estimateT: number | null;
  changed: boolean;
}

export interface Armament {
  supported: boolean;
  problem: ArmamentProblem | null;
  schema: string | null;
  method: string | null;
  status: string | null;
  basisConditionId: string | null;
  /** Always five rows, in bank order 1..5. */
  banks: ArmamentBank[];
  /** Whether at least one bank is declared. */
  anyDeclared: boolean;
  /** One reading per armament role, always present. */
  ledger: Record<ArmamentLedgerRole, ArmamentLedgerRow>;
  balance: ShipDesignBalance | null;
  comparable: boolean;
}

/* ------------------------------------------------------------------ reading */

function numberAt(source: Record<string, unknown> | null, key: string): number | null {
  if (!source) return null;
  const raw = source[key];
  return typeof raw === 'number' && Number.isFinite(raw) ? raw : null;
}

function integerAt(source: Record<string, unknown> | null, key: string): number | null {
  const value = numberAt(source, key);
  return value !== null && Number.isInteger(value) ? value : null;
}

function enumAt(source: Record<string, unknown> | null, key: string, size: number): number | null {
  const value = integerAt(source, key);
  return value !== null && value >= 0 && value < size ? value : null;
}

function booleanOrNull(source: Record<string, unknown> | null, key: string): boolean | null {
  const raw = source?.[key];
  return typeof raw === 'boolean' ? raw : null;
}

/** Field names of one group, G1 and G2, read through the same helper. */
const GROUP_FIELDS: Record<ArmamentGroupKey, { selector: string; layout: string; perMount: string; mounts: string; elevated: string; deck: string; depressed: string }> = {
  G1: { selector: 'selectorG1', layout: 'layoutG1', perMount: 'perMountG1', mounts: 'mountsG1', elevated: 'mountSuperG1', deck: 'mountDeckG1', depressed: 'mountSubG1' },
  G2: { selector: 'selectorG2', layout: 'layoutG2', perMount: 'perMountG2', mounts: 'mountsG2', elevated: 'mountSuperG2', deck: 'mountDeckG2', depressed: 'mountSubG2' },
};

function readGroup(record: Record<string, unknown>, key: ArmamentGroupKey): ArmamentGroup {
  const fields = GROUP_FIELDS[key];
  return {
    key,
    selector: enumAt(record, fields.selector, SELECTOR_COUNT),
    layout: enumAt(record, fields.layout, LAYOUT_COUNT),
    perMount: numberAt(record, fields.perMount),
    mounts: numberAt(record, fields.mounts),
    elevated: numberAt(record, fields.elevated),
    deck: numberAt(record, fields.deck),
    depressed: numberAt(record, fields.depressed),
  };
}

function emptyBank(bank: number, state: BankState): ArmamentBank {
  return {
    bank, id: `gun${bank}`, state,
    barrels: null, mounts: null, calibreIn: null, gunType: null, mountType: null, year: null,
    calLength: null, magazine: null,
    groups: ARMAMENT_GROUP_ORDER.map(key => readGroup({}, key)),
    armFaceIn: null, armBackIn: null, armBottomIn: null,
    shellWeightDeclaredLb: null, shellWeightLb: null, autoShellWeightLb: null, broadsideWeightLb: null,
    gunWeightLt: null, mountWeightLt: null, magazineWeightLt: null, armWeightLt: null, totalWeightLt: null,
    superSuper: null, subSub: null, editField: `gun${bank}_calibre`, changed: false,
  };
}

function readBank(record: Record<string, unknown>, bank: number): ArmamentBank {
  const barrels = numberAt(record, 'barrels');
  const mounts = numberAt(record, 'mounts');
  // A present record whose own declared barrels and mounts are both exactly zero
  // is an explicit zero battery, not an unknown one.
  const state: BankState = barrels === 0 && mounts === 0 ? 'zero' : 'declared';
  return {
    bank, id: `gun${bank}`, state, barrels, mounts,
    calibreIn: numberAt(record, 'calibre'),
    gunType: enumAt(record, 'gunType', GUN_TYPE_COUNT),
    mountType: enumAt(record, 'mountType', MOUNT_TYPE_COUNT),
    year: numberAt(record, 'dateGun'),
    calLength: numberAt(record, 'calLength'),
    magazine: numberAt(record, 'magazine'),
    groups: ARMAMENT_GROUP_ORDER.map(key => readGroup(record, key)),
    armFaceIn: numberAt(record, 'armFace'),
    armBackIn: numberAt(record, 'armBack'),
    armBottomIn: numberAt(record, 'armBottom'),
    shellWeightDeclaredLb: numberAt(record, 'shellWeightDeclared'),
    shellWeightLb: numberAt(record, 'shellWeight'),
    autoShellWeightLb: numberAt(record, 'autoShellWeight'),
    broadsideWeightLb: numberAt(record, 'broadsideWeight'),
    gunWeightLt: numberAt(record, 'gunWeight'),
    mountWeightLt: numberAt(record, 'mountWeight'),
    magazineWeightLt: numberAt(record, 'magazineWeight'),
    armWeightLt: numberAt(record, 'armWeight'),
    totalWeightLt: numberAt(record, 'totalWeight'),
    superSuper: booleanOrNull(record, 'superSuper'),
    subSub: booleanOrNull(record, 'subSub'),
    editField: `gun${bank}_calibre`,
    changed: false,
  };
}

/**
 * The five banks, by explicit identity.
 *
 * A group is adopted for a bank only when its `bank` is 1..5 and its `id` names
 * that same bank. A malformed group, or a second group for an already-adopted
 * bank, makes that bank ambiguous rather than reassigned; a bank with no group is
 * missing. The returned list is always five entries, in bank order.
 */
function readBanks(guns: Record<string, unknown> | null): ArmamentBank[] {
  const groups = guns && Array.isArray(guns.groups) ? guns.groups : null;
  const adopted = new Map<number, Record<string, unknown>>();
  const ambiguous = new Set<number>();
  for (const entry of groups ?? []) {
    if (!isRecord(entry)) continue;
    const bank = integerAt(entry, 'bank');
    const id = typeof entry.id === 'string' ? entry.id : null;
    if (bank === null || bank < 1 || bank > 5 || id !== `gun${bank}`) {
      // A malformed identity belongs to no bank at all; it never becomes a bank.
      if (bank !== null && bank >= 1 && bank <= 5) ambiguous.add(bank);
      continue;
    }
    if (adopted.has(bank)) {
      // Two groups claim the same bank: neither is trusted.
      adopted.delete(bank);
      ambiguous.add(bank);
      continue;
    }
    adopted.set(bank, entry);
  }
  return ARMAMENT_BANK_ORDER.map(bank => {
    if (ambiguous.has(bank)) return emptyBank(bank, 'ambiguous');
    const record = adopted.get(bank);
    return record ? readBank(record, bank) : emptyBank(bank, 'missing');
  });
}

/* --------------------------------------------------------------- comparison */

/** The declared facts of one bank both the reading and the comparison read. */
function bankFacts(bank: ArmamentBank | null): Array<number | boolean | null> {
  if (!bank) return [null];
  const facts: Array<number | boolean | null> = [
    bank.barrels, bank.mounts, bank.calibreIn, bank.gunType, bank.mountType, bank.year, bank.calLength,
    bank.magazine, bank.armFaceIn, bank.armBackIn, bank.armBottomIn,
    bank.shellWeightDeclaredLb, bank.shellWeightLb, bank.autoShellWeightLb, bank.broadsideWeightLb,
    bank.gunWeightLt, bank.mountWeightLt, bank.magazineWeightLt, bank.armWeightLt, bank.totalWeightLt,
    bank.superSuper, bank.subSub,
  ];
  for (const group of bank.groups) {
    facts.push(group.selector, group.layout, group.perMount, group.mounts, group.elevated, group.deck, group.depressed);
  }
  return facts;
}

/** Whether two readings differ, treating an absent reading and an unknown alike. */
function differs(left: unknown, right: unknown): boolean {
  return (left === undefined ? null : left) !== (right === undefined ? null : right);
}

/** Same schema, same method and the same declared basis, or no highlight is offered. */
function compatible(raw: Record<string, unknown>, before: unknown): boolean {
  if (!isRecord(before)) return false;
  if (raw.schema !== SHIP_DESIGN_RESULT_SCHEMA || before.schema !== SHIP_DESIGN_RESULT_SCHEMA) return false;
  if (raw.method_version !== SHIP_DESIGN_METHOD_VERSION || before.method_version !== SHIP_DESIGN_METHOD_VERSION) return false;
  const rawBasis = basisConditionId(raw as unknown as ShipDesignResult);
  const beforeBasis = basisConditionId(before as unknown as ShipDesignResult);
  return Boolean(rawBasis) && Boolean(beforeBasis) && rawBasis === beforeBasis;
}

function ledgerRows(entries: ShipDesignLedgerEntry[]): Record<ArmamentLedgerRole, ArmamentLedgerRow> {
  const readOne = (role: ArmamentLedgerRole): ArmamentLedgerRow => {
    const entry = entries.find(item => item.role === role);
    return {
      role,
      mode: typeof entry?.mode === 'string' ? entry.mode : null,
      selectedT: typeof entry?.selected_mass_t === 'number' && Number.isFinite(entry.selected_mass_t) ? entry.selected_mass_t : null,
      estimateT: typeof entry?.estimate_t === 'number' && Number.isFinite(entry.estimate_t) ? entry.estimate_t : null,
      changed: false,
    };
  };
  return {
    guns: readOne('guns'), mounts: readOne('mounts'),
    ammunition: readOne('ammunition'), gun_armour: readOne('gun_armour'),
  };
}

function ledgerFacts(row: ArmamentLedgerRow): Array<string | number | null> {
  return [row.mode, row.selectedT, row.estimateT];
}

/**
 * The armament reading of one native result, optionally highlighted against a
 * compatible saved revision.
 */
export function buildArmament(raw: unknown, before?: unknown): Armament {
  const emptyLedger = ledgerRows([]);
  const empty: Armament = {
    supported: false, problem: 'absent', schema: null, method: null, status: null, basisConditionId: null,
    banks: ARMAMENT_BANK_ORDER.map(bank => emptyBank(bank, 'missing')),
    anyDeclared: false, ledger: emptyLedger, balance: null, comparable: false,
  };
  const result = isRecord(raw) ? raw : null;
  if (!result) return empty;

  const schema = typeof result.schema === 'string' ? result.schema : null;
  const method = typeof result.method_version === 'string' ? result.method_version : null;
  const status = typeof result.status === 'string' ? result.status : null;
  const basis = basisConditionId(result as unknown as ShipDesignResult);
  const context = { schema, method, status, basisConditionId: basis };

  if (schema !== SHIP_DESIGN_RESULT_SCHEMA) return { ...empty, problem: 'unsupported_schema', ...context };
  if (method !== SHIP_DESIGN_METHOD_VERSION) return { ...empty, problem: 'unsupported_method', ...context };

  const guns = isRecord(result.guns) ? result.guns : null;
  if (!guns || status === 'unavailable') return { ...empty, problem: 'unavailable', ...context };

  const banks = readBanks(guns);
  const ledger = ledgerRows(ledgerEntries(result as unknown as ShipDesignResult));
  const armament: Armament = {
    supported: true, problem: null, ...context,
    banks, anyDeclared: banks.some(bank => bank.state === 'declared' || bank.state === 'zero'),
    ledger, balance: balanceOf(result as unknown as ShipDesignResult), comparable: false,
  };

  if (!compatible(result, before)) return armament;
  const saved = before as Record<string, unknown>;
  const savedGuns = isRecord(saved.guns) ? saved.guns : null;
  const savedBanks = readBanks(savedGuns);
  const savedLedger = ledgerRows(ledgerEntries(saved as unknown as ShipDesignResult));
  const changedBanks = new Set<number>();
  for (const bank of banks) {
    if (bank.state === 'missing' || bank.state === 'ambiguous') continue;
    const savedBank = savedBanks.find(item => item.bank === bank.bank) ?? null;
    const current = bankFacts(bank);
    const previous = bankFacts(savedBank);
    if (current.some((value, index) => differs(value, previous[index]))) changedBanks.add(bank.bank);
  }
  const changedLedger: Record<ArmamentLedgerRole, boolean> = {
    guns: false, mounts: false, ammunition: false, gun_armour: false,
  };
  for (const role of ARMAMENT_LEDGER_ROLES) {
    changedLedger[role] = ledgerFacts(ledger[role]).some((value, index) => differs(value, ledgerFacts(savedLedger[role])[index]));
  }
  return {
    ...armament, comparable: true,
    banks: banks.map(bank => changedBanks.has(bank.bank) ? { ...bank, changed: true } : bank),
    ledger: ARMAMENT_LEDGER_ROLES.reduce((all, role) => {
      all[role] = changedLedger[role] ? { ...ledger[role], changed: true } : ledger[role];
      return all;
    }, { ...ledger } as Record<ArmamentLedgerRole, ArmamentLedgerRow>),
  };
}
