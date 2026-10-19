import { basisConditionId, isUnresolved, ledgerEntries } from './shipDesign';
import { SHIP_DESIGN_METHOD_VERSION, SHIP_DESIGN_RESULT_SCHEMA, isRecord } from './sps3b3Model';
import type { ShipDesignLedgerEntry, ShipDesignResult } from '../types';

/**
 * The one pure reading of the managed weight ledger, and the frozen role union.
 *
 * This module computes no ship number and reads no formula. It takes the ledger
 * the native result already saved, states each role's own source estimate and
 * adopted mass exactly as they are, sums the six presentation groups from the
 * roles they contain, and reads the authoritative balance straight from the
 * ledger's own four totals. The frozen comparison reads the ordered union of the
 * roles of two saved results.
 *
 * The rules are deliberately narrow:
 *
 * - **The authoritative balance is read, never rebuilt.** The group sums below
 *   are an explanation of where the balance comes from; the balance difference
 *   is always the saved value, even when it disagrees with the group sums. A
 *   determinate group sum that disagrees with the balance is reported as a
 *   mismatch, never used to override the saved totals.
 * - **Unknown, zero and negative stay distinct, and the two mass dimensions stay
 *   independent.** A missing value is unknown; a saved zero or negative mass is
 *   a fact. An unknown estimate never discards a known adopted sum, and an
 *   unknown adopted mass never discards a known estimate sum.
 * - **A repeated role identity is one explicit conflict.** The ledger is read as
 *   its own rows; when the same source identity is saved more than once — even
 *   when the repeated values happen to match — the rows collapse to one conflict
 *   whose quantities, policy and binding are unknown. Nothing is first-won,
 *   summed or half-shown, and its group total stays unknown. The raw ledger
 *   remains auditable elsewhere.
 * - **Coverage is stated, not assumed.** A group that is missing one of its
 *   fixed expected roles is incomplete even when the roles it does carry are all
 *   known; only the optional aggregate stays optional.
 * - **A change needs a gate.** Values are marked changed only when both readable
 *   results share one known (non-blank) basis; a known value that became unknown
 *   is a change and two unknowns are not.
 */

export type WeightGroupKey = 'structure' | 'armament' | 'armour' | 'machinery' | 'fuel' | 'other';

export type WeightBreakdownProblem = 'absent' | 'unsupported_schema' | 'unsupported_method' | 'unavailable';

/** One presentation group and the source roles it collects, in the spec's order. */
export const WEIGHT_GROUPS: ReadonlyArray<{ key: WeightGroupKey; roles: readonly string[] }> = [
  { key: 'structure', roles: ['structure'] },
  { key: 'armament', roles: ['guns', 'mounts', 'gun_armour', 'ammunition', 'auxiliary'] },
  { key: 'armour', roles: ['belt_main', 'belt_ends', 'belt_upper', 'bulkhead', 'bulge', 'deck', 'conning'] },
  { key: 'machinery', roles: ['machinery'] },
  { key: 'fuel', roles: ['fuel'] },
  { key: 'other', roles: ['stores', 'misc_vital', 'misc_hull', 'misc_deck', 'misc_above', 'misc_void', 'other'] },
];

const ROLE_GROUP = new Map<string, WeightGroupKey>();
for (const group of WEIGHT_GROUPS) for (const role of group.roles) ROLE_GROUP.set(role, group.key);

/** The group a source role belongs to; an unlisted future role survives as other. */
export function groupOfRole(role: string): WeightGroupKey {
  return ROLE_GROUP.get(role) ?? 'other';
}

/** One managed role, as the ledger saved it, or one explicit conflict. */
export interface WeightRole {
  role: string;
  group: WeightGroupKey;
  /** True when the source identity appears more than once and is therefore unknown. */
  conflict: boolean;
  estimateT: number | null;
  selectedT: number | null;
  mode: 'estimated' | 'declared' | null;
  itemIds: string[];
  /** `selected − estimate`, only when both are known. */
  adoptionDeltaT: number | null;
  /** The ledger's own unresolved reading, false for a conflict. */
  unresolved: boolean;
  /** True only when a comparable baseline changed this role. */
  changed: boolean;
}

/** One presentation group, with its own totals and an honest coverage state. */
export interface WeightGroup {
  key: WeightGroupKey;
  roles: WeightRole[];
  /** The sum of the known estimates, or null when any estimate is unknown. */
  estimateT: number | null;
  /** The sum of the known adopted masses, or null when any adopted mass is unknown. */
  selectedT: number | null;
  /** `selected − estimate`, only when both group totals are known. */
  adoptionDeltaT: number | null;
  /** True when the group has at least one role. */
  populated: boolean;
  /** True when every role's estimate and adopted mass are known and none conflict. */
  allKnown: boolean;
  /** True when the group is populated, all known, and no fixed expected role is missing. */
  complete: boolean;
  /** True for the aggregate that may legitimately hold no role. */
  optional: boolean;
  /** Fixed expected roles absent from the saved ledger (empty for the optional aggregate). */
  missing: string[];
  changed: boolean;
}

/** The ledger's own four totals, always in tonnes. */
export interface WeightBalance {
  selectedT: number | null;
  estimateT: number | null;
  targetT: number | null;
  differenceT: number | null;
}

/**
 * The reconciliation between the determinate role sums and the ledger's own
 * balance. It is a report, never an override: a mismatch names the disagreement
 * and the balance still stands.
 */
export interface WeightReconciliation {
  /** The all-roles estimate sum, only when every role's estimate is known. */
  roleEstimateT: number | null;
  /** The all-roles adopted sum, only when every role's adopted mass is known. */
  roleSelectedT: number | null;
  balanceEstimateT: number | null;
  balanceSelectedT: number | null;
  estimateMatches: boolean | null;
  selectedMatches: boolean | null;
  /** True when every role is non-conflicting with both masses known. */
  determinate: boolean;
  verdict: 'match' | 'mismatch' | 'unknown';
}

export interface WeightBreakdown {
  supported: boolean;
  problem: WeightBreakdownProblem | null;
  schema: string | null;
  method: string | null;
  status: string | null;
  basisConditionId: string | null;
  /** True only when both readable results share one known basis. */
  comparable: boolean;
  /** The ledger's own strict boolean, or null when it never declared one. */
  complete: boolean | null;
  groups: WeightGroup[];
  roles: WeightRole[];
  balance: WeightBalance;
  reconciliation: WeightReconciliation;
}

const finite = (value: unknown): number | null => typeof value === 'number' && Number.isFinite(value) ? value : null;

function recordAt(source: Record<string, unknown> | null, key: string): Record<string, unknown> | null {
  return isRecord(source?.[key]) ? source[key] as Record<string, unknown> : null;
}

/** A basis is known only when it is a non-blank string; blank is not a basis. */
function normalizeBasis(value: unknown): string | null {
  return typeof value === 'string' && value.trim() !== '' ? value.trim() : null;
}

/** Almost-equality for two saved totals, tolerant only to floating point noise. */
function nearlyEqual(left: number, right: number): boolean {
  return Math.abs(left - right) <= Math.max(1e-6, Math.abs(left) * 1e-9, Math.abs(right) * 1e-9);
}

function readMode(entry: ShipDesignLedgerEntry): 'estimated' | 'declared' | null {
  return entry.mode === 'estimated' || entry.mode === 'declared' ? entry.mode : null;
}

function readItemIds(entry: ShipDesignLedgerEntry): string[] {
  return Array.isArray(entry.item_ids)
    ? entry.item_ids.filter((value): value is string => typeof value === 'string')
    : [];
}

function conflictRole(role: string): WeightRole {
  return {
    role, group: groupOfRole(role), conflict: true,
    estimateT: null, selectedT: null, mode: null, itemIds: [],
    adoptionDeltaT: null, unresolved: false, changed: false,
  };
}

function readRole(entry: ShipDesignLedgerEntry): WeightRole {
  const role = String(entry.role);
  const estimateT = finite(entry.estimate_t);
  const selectedT = finite(entry.selected_mass_t);
  return {
    role, group: groupOfRole(role), conflict: false,
    estimateT, selectedT, mode: readMode(entry), itemIds: readItemIds(entry),
    adoptionDeltaT: estimateT !== null && selectedT !== null ? selectedT - estimateT : null,
    unresolved: isUnresolved(entry), changed: false,
  };
}

/**
 * The one row per source identity: a duplicated identity becomes a single
 * conflict, in the position its first occurrence held.
 */
function readRoles(result: ShipDesignResult): WeightRole[] {
  const entries = ledgerEntries(result);
  const counts = new Map<string, number>();
  for (const entry of entries) {
    const role = String(entry.role);
    counts.set(role, (counts.get(role) ?? 0) + 1);
  }
  const rows: WeightRole[] = [];
  const seen = new Set<string>();
  for (const entry of entries) {
    const role = String(entry.role);
    if (seen.has(role)) continue;
    seen.add(role);
    rows.push((counts.get(role) ?? 0) > 1 ? conflictRole(role) : readRole(entry));
  }
  return rows;
}

/**
 * The group's two sums, each independent of the other: an unknown estimate does
 * not discard a known adopted sum, and vice versa. `allKnown` is the group's
 * honest "both dimensions determinate" state.
 */
function groupTotals(roles: readonly WeightRole[]): {
  estimateT: number | null; selectedT: number | null; allKnown: boolean;
} {
  if (roles.length === 0) return { estimateT: null, selectedT: null, allKnown: false };
  let estimate = 0;
  let selected = 0;
  let estimateKnown = true;
  let selectedKnown = true;
  for (const role of roles) {
    // A conflict row is unknown in both dimensions; a negative or zero is a fact.
    if (role.conflict || role.estimateT === null) estimateKnown = false;
    else estimate += role.estimateT;
    if (role.conflict || role.selectedT === null) selectedKnown = false;
    else selected += role.selectedT;
  }
  return {
    estimateT: estimateKnown ? estimate : null,
    selectedT: selectedKnown ? selected : null,
    allKnown: estimateKnown && selectedKnown,
  };
}

/** The six groups, each built from the roles it collects in a fixed order. */
function buildGroups(roles: readonly WeightRole[]): WeightGroup[] {
  return WEIGHT_GROUPS.map(group => {
    const indexOf = (role: string): number => {
      const at = group.roles.indexOf(role);
      return at === -1 ? group.roles.length : at;
    };
    const members = roles
      .filter(role => role.group === group.key)
      .map((role, index) => ({ role, index }))
      .sort((a, b) => indexOf(a.role.role) - indexOf(b.role.role) || a.index - b.index)
      .map(entry => entry.role);
    const totals = groupTotals(members);
    const optional = group.key === 'other';
    const present = new Set(members.map(role => role.role));
    const missing = optional ? [] : group.roles.filter(role => !present.has(role));
    return {
      key: group.key, roles: members,
      estimateT: totals.estimateT, selectedT: totals.selectedT,
      adoptionDeltaT: totals.estimateT !== null && totals.selectedT !== null ? totals.selectedT - totals.estimateT : null,
      populated: members.length > 0,
      allKnown: totals.allKnown,
      complete: members.length > 0 && totals.allKnown && missing.length === 0,
      optional, missing, changed: false,
    };
  });
}

function readBalance(result: Record<string, unknown> | null): WeightBalance {
  if (!result) return { selectedT: null, estimateT: null, targetT: null, differenceT: null };
  // The ledger is the authoritative home of the four totals; the result-level
  // balance is only a fallback for a key the ledger did not declare. Neither is
  // ever rebuilt from the group sums above.
  const ledger = recordAt(result, 'ledger');
  const top = recordAt(result, 'balance');
  const pick = (key: string): number | null => finite(ledger?.[key]) ?? finite(top?.[key]);
  return {
    selectedT: pick('selected_mass_t'),
    estimateT: pick('estimated_mass_t'),
    targetT: pick('target_displacement_t'),
    differenceT: pick('difference_t'),
  };
}

/**
 * The ledger's own completeness declaration, kept strict: only a real boolean is
 * a statement. A missing or malformed flag is unknown rather than an invented
 * false verdict.
 */
function readComplete(result: Record<string, unknown> | null): boolean | null {
  const ledger = recordAt(result, 'ledger');
  return typeof ledger?.complete === 'boolean' ? ledger.complete : null;
}

function noReconciliation(): WeightReconciliation {
  return {
    roleEstimateT: null, roleSelectedT: null, balanceEstimateT: null, balanceSelectedT: null,
    estimateMatches: null, selectedMatches: null, determinate: false, verdict: 'unknown',
  };
}

function reconcile(roles: readonly WeightRole[], balance: WeightBalance): WeightReconciliation {
  const determinate = roles.length > 0
    && roles.every(role => !role.conflict && role.estimateT !== null && role.selectedT !== null);
  const roleEstimateT = determinate ? roles.reduce((sum, role) => sum + (role.estimateT ?? 0), 0) : null;
  const roleSelectedT = determinate ? roles.reduce((sum, role) => sum + (role.selectedT ?? 0), 0) : null;
  const estimateMatches = roleEstimateT !== null && balance.estimateT !== null
    ? nearlyEqual(roleEstimateT, balance.estimateT) : null;
  const selectedMatches = roleSelectedT !== null && balance.selectedT !== null
    ? nearlyEqual(roleSelectedT, balance.selectedT) : null;
  const verdict = estimateMatches === false || selectedMatches === false ? 'mismatch'
    : estimateMatches === true && selectedMatches === true ? 'match' : 'unknown';
  return {
    roleEstimateT, roleSelectedT,
    balanceEstimateT: balance.estimateT, balanceSelectedT: balance.selectedT,
    estimateMatches, selectedMatches, determinate, verdict,
  };
}

function empty(problem: WeightBreakdownProblem): WeightBreakdown {
  const balance = readBalance(null);
  return {
    supported: false, problem, schema: null, method: null, status: null, basisConditionId: null,
    comparable: false, complete: null, groups: buildGroups([]), roles: [], balance,
    reconciliation: reconcile([], balance),
  };
}

function readSide(raw: unknown): WeightBreakdown {
  const result = isRecord(raw) ? raw : null;
  if (!result) return empty('absent');

  const schema = typeof result.schema === 'string' ? result.schema : null;
  const method = typeof result.method_version === 'string' ? result.method_version : null;
  const status = typeof result.status === 'string' ? result.status : null;
  const context = {
    schema, method, status,
    basisConditionId: normalizeBasis(basisConditionId(result as unknown as ShipDesignResult)),
  };

  if (schema !== SHIP_DESIGN_RESULT_SCHEMA) return { ...empty('unsupported_schema'), ...context };
  if (method !== SHIP_DESIGN_METHOD_VERSION) return { ...empty('unsupported_method'), ...context };
  if (status !== 'available' && status !== 'partial') return { ...empty('unavailable'), ...context };
  // A ledger-less result must not leak a residual number from the balance alone.
  if (!isRecord(result.ledger)) return { ...empty('unavailable'), ...context };

  const roles = readRoles(result as unknown as ShipDesignResult);
  const balance = readBalance(result);
  return {
    supported: true, problem: null, ...context,
    comparable: false,
    complete: readComplete(result),
    groups: buildGroups(roles), roles, balance,
    reconciliation: reconcile(roles, balance),
  };
}

const sameValue = (current: number | null, baseline: number | null): boolean => current === baseline;

/** Mark one role changed only when the comparison gate accepted both results. */
function markRole(role: WeightRole, baseline: WeightRole | undefined, comparable: boolean): WeightRole {
  if (!comparable) return role;
  if (role.conflict) {
    // A duplicated identity is unknown now; a preceding known value is a
    // known-to-unknown change, while two unknowns are not.
    const changed = !!baseline && !baseline.conflict
      && (baseline.estimateT !== null || baseline.selectedT !== null);
    return { ...role, changed };
  }
  const before = baseline && !baseline.conflict ? baseline : undefined;
  const changed = !before
    ? role.estimateT !== null || role.selectedT !== null || role.mode !== null || role.itemIds.length > 0
    : !sameValue(role.estimateT, before.estimateT)
      || !sameValue(role.selectedT, before.selectedT)
      || role.mode !== before.mode
      || role.itemIds.join('\u0000') !== before.itemIds.join('\u0000');
  return { ...role, changed };
}

/**
 * Mark a group changed when its membership, either total, or any member role
 * changed. A policy or binding change therefore marks the group even when its
 * masses are identical.
 */
function markGroup(group: WeightGroup, baseline: WeightGroup | undefined, comparable: boolean): WeightGroup {
  if (!comparable) return group;
  if (!baseline) return { ...group, changed: group.populated };
  const beforeRoles = new Set(baseline.roles.map(role => role.role));
  const afterRoles = new Set(group.roles.map(role => role.role));
  const membershipChanged = beforeRoles.size !== afterRoles.size
    || [...afterRoles].some(role => !beforeRoles.has(role));
  const changed = membershipChanged
    || !sameValue(group.estimateT, baseline.estimateT)
    || !sameValue(group.selectedT, baseline.selectedT)
    || group.roles.some(role => role.changed);
  return { ...group, changed };
}

/**
 * The weight breakdown of one native result, or the named reason it cannot be
 * read. The optional baseline is the host's already-fetched saved result; values
 * are marked changed only when both sides share one known basis.
 */
export function readWeightBreakdown(raw: unknown, baselineRaw?: unknown): WeightBreakdown {
  const reading = readSide(raw);
  if (!reading.supported || baselineRaw === undefined) return reading;

  const baseline = readSide(baselineRaw);
  const comparable = baseline.supported
    && reading.basisConditionId !== null
    && reading.basisConditionId === baseline.basisConditionId;
  if (!comparable) return reading;

  const baselineRoles = new Map(baseline.roles.map(role => [role.role, role]));
  const baselineGroups = new Map(baseline.groups.map(group => [group.key, group]));
  // The marked roles are the ones the UI reads, and the groups are rebuilt from
  // them, so a role-level change is visible in the group it belongs to.
  const roles = reading.roles.map(role => markRole(role, baselineRoles.get(role.role), true));
  const groups = buildGroups(roles).map(group => markGroup(group, baselineGroups.get(group.key), true));
  return { ...reading, comparable: true, roles, groups };
}

/* ---------------------------------------------------------- frozen comparison */

/** One side of a frozen role row: the role on this run, or its honest absence. */
export interface WeightComparisonSide {
  present: boolean;
  conflict: boolean;
  estimateT: number | null;
  selectedT: number | null;
  mode: 'estimated' | 'declared' | null;
  itemIds: string[];
}

export interface WeightComparisonRow {
  role: string;
  group: WeightGroupKey;
  conflict: boolean;
  current: WeightComparisonSide;
  comparison: WeightComparisonSide;
  /** `comparison − current`, only when both sides declare the role and both estimates are known. */
  estimateDeltaT: number | null;
  /** `comparison − current`, only when both sides declare the role and both adopted masses are known. */
  selectedDeltaT: number | null;
  modeChanged: boolean;
  bindingChanged: boolean;
  changed: boolean;
}

export type WeightComparisonProblem = WeightBreakdownProblem | 'incompatible';

export interface WeightComparison {
  comparable: boolean;
  problem: WeightComparisonProblem | null;
  current: { basisConditionId: string | null; status: string | null };
  comparison: { basisConditionId: string | null; status: string | null };
  rows: WeightComparisonRow[];
}

function absentSide(): WeightComparisonSide {
  return { present: false, conflict: false, estimateT: null, selectedT: null, mode: null, itemIds: [] };
}

function sideOf(role: WeightRole | undefined): WeightComparisonSide {
  if (!role) return absentSide();
  return {
    present: true, conflict: role.conflict,
    estimateT: role.estimateT, selectedT: role.selectedT, mode: role.mode, itemIds: role.itemIds,
  };
}

/**
 * The ordered union of two frozen ledgers: every role either run declares, in
 * the group order the reader uses, each side stated as saved and the difference
 * as comparison − current. A role absent on one side is unknown there, never a
 * zero; a policy or binding change is a categorical change, never a mass delta;
 * and an unknown estimate never suppresses a known adopted difference (or vice
 * versa). No numeric difference is exposed unless the pair is comparable.
 */
export function weightComparisonRows(currentRaw: unknown, comparisonRaw: unknown): WeightComparison {
  const current = readSide(currentRaw);
  const comparison = readSide(comparisonRaw);
  const comparable = current.supported && comparison.supported
    && current.basisConditionId !== null
    && current.basisConditionId === comparison.basisConditionId;
  const problem = current.problem ?? comparison.problem
    ?? (current.supported && comparison.supported ? 'incompatible' : null);

  const currentRoles = new Map(current.roles.map(role => [role.role, role]));
  const comparisonRoles = new Map(comparison.roles.map(role => [role.role, role]));
  const order: string[] = [];
  const seen = new Set<string>();
  for (const role of current.roles) { if (!seen.has(role.role)) { seen.add(role.role); order.push(role.role); } }
  for (const role of comparison.roles) { if (!seen.has(role.role)) { seen.add(role.role); order.push(role.role); } }

  const rank = new Map<string, number>();
  WEIGHT_GROUPS.forEach((group, groupIndex) => group.roles.forEach((role, roleIndex) => rank.set(role, groupIndex * 100 + roleIndex)));

  const ranked = order.map((role, index) => {
    const left = sideOf(currentRoles.get(role));
    const right = sideOf(comparisonRoles.get(role));
    const conflict = left.conflict || right.conflict;
    const bothPresent = left.present && right.present;
    // Each mass dimension is compared on its own: one unknown does not hide the
    // other's known difference.
    const estimateKnown = !conflict && bothPresent && left.estimateT !== null && right.estimateT !== null;
    const selectedKnown = !conflict && bothPresent && left.selectedT !== null && right.selectedT !== null;
    // A policy or binding change is only meaningful when the role is on both
    // sides; a role absent on one side is a presence change, not a policy change.
    const modeChanged = bothPresent && !conflict && left.mode !== right.mode;
    const bindingChanged = bothPresent && !conflict && left.itemIds.join('\u0000') !== right.itemIds.join('\u0000');
    const changed = comparable && !conflict && (
      left.present !== right.present
      || left.estimateT !== right.estimateT
      || left.selectedT !== right.selectedT
      || modeChanged || bindingChanged
    );
    const row: WeightComparisonRow = {
      role, group: groupOfRole(role), conflict, current: left, comparison: right,
      estimateDeltaT: estimateKnown ? right.estimateT! - left.estimateT! : null,
      selectedDeltaT: selectedKnown ? right.selectedT! - left.selectedT! : null,
      modeChanged, bindingChanged, changed,
    };
    return { row, rank: rank.get(role) ?? WEIGHT_GROUPS.length * 100, index };
  });
  ranked.sort((a, b) => a.rank - b.rank || a.index - b.index);
  const rows = ranked.map(entry => entry.row);

  return {
    comparable, problem: comparable ? null : problem,
    current: { basisConditionId: current.basisConditionId, status: current.status },
    comparison: { basisConditionId: comparison.basisConditionId, status: comparison.status },
    rows: comparable ? rows : [],
  };
}
