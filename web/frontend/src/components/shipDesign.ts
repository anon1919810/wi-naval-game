import type {
  ProjectDocument, ShipDesign, ShipDesignBalance, ShipDesignLedger, ShipDesignLedgerEntry,
  ShipDesignMassBinding, ShipDesignResult, Sps3b3Design,
} from '../types';
import { SHIP_DESIGN_SECTION, SPS_SECTION, isRecord, shipDesignOf, withShipDesign } from './sps3b3Model';

/**
 * The ordinary/native bridge: which chapter shows which source page, how a
 * reply's ledger reads, and how a returned projection is merged.
 *
 * Nothing here computes a ship value. The core owns the ledger, the balance and
 * the SI hull projection; this module only reads them and decides, for one
 * returned reply, which of the reader's own local edits must survive it.
 */

/**
 * The ordinary chapters that host native source fields, and the source page each
 * presents.
 *
 * The native product has one set of chapters; the recovered field catalogue
 * still groups its fields into seven source pages. This map is the whole bridge:
 * a chapter shows the fields of its page, and no page is its own product mode.
 */
export const CHAPTER_SOURCE_PAGE: Readonly<Record<string, string>> = {
  hull: 'hull',
  freeboard: 'freeboard',
  guns: 'guns',
  weapons: 'weapons',
  armour: 'armour',
  propulsion: 'engine',
  performance: 'performance',
};

/** The source page a chapter presents, or `null` when the chapter is not native. */
export function sourcePageForChapter(chapterId: string): string | null {
  return CHAPTER_SOURCE_PAGE[chapterId] ?? null;
}

/**
 * The ordinary SI hull values a native reply is authoritative for.
 *
 * A field edit can move the design's principal dimensions, so the governed hull
 * is overlaid from the reply. Everything else in the local draft — geometry,
 * weight items and their positions and sources, damage — is the reader's own
 * and is preserved.
 */
export const GOVERNED_HULL_KEYS = [
  'lwl_m', 'loa_m', 'beam_m', 'beam_bulges_m', 'draught_normal_m', 'draught_deep_m',
  'block_coeff', 'waterplane_coeff',
] as const;

/* ------------------------------------------------------------------ ledger */

/** Ledger keys that are not role rows. */
const LEDGER_SCALARS = new Set([
  'schema', 'owner', 'condition_id', 'basis_condition_id', 'roles',
  'selected_mass_t', 'estimated_mass_t', 'target_displacement_t', 'difference_t',
  'needs_binding', 'complete',
]);

function normalizeEntry(raw: Record<string, unknown>, role: string): ShipDesignLedgerEntry {
  const ids = Array.isArray(raw.item_ids)
    ? raw.item_ids.filter((value): value is string => typeof value === 'string')
    : undefined;
  return {
    ...(raw as ShipDesignLedgerEntry),
    role: typeof raw.role === 'string' ? raw.role : role,
    ...(ids ? { item_ids: ids } : {}),
  };
}

/** The one managed ledger a reply carries, or `null`. */
export function ledgerOf(result: ShipDesignResult | null | undefined): ShipDesignLedger | null {
  const raw = result?.ledger;
  return isRecord(raw) ? raw as ShipDesignLedger : null;
}

/**
 * The role table of one reply, always as an ordered list of entries.
 *
 * The ledger is `{roles: {...}}`; a bare role-keyed object is also read, so a
 * reply from an older shape still names its roles instead of printing `schema`
 * and `owner` as if they were roles.
 */
export function ledgerEntries(result: ShipDesignResult | null | undefined): ShipDesignLedgerEntry[] {
  const ledger = ledgerOf(result);
  if (!ledger) return [];
  const roles = ledger.roles;
  if (isRecord(roles)) {
    return Object.entries(roles).map(([role, row]) => normalizeEntry(isRecord(row) ? row : {}, role));
  }
  return Object.entries(ledger)
    .filter(([key, value]) => !LEDGER_SCALARS.has(key) && isRecord(value))
    .map(([role, row]) => normalizeEntry(row as Record<string, unknown>, role));
}

/** The unified balance of one reply, read from the ledger when it carries it. */
export function balanceOf(result: ShipDesignResult | null | undefined): ShipDesignBalance | null {
  if (result?.balance) return result.balance;
  const ledger = ledgerOf(result);
  if (!ledger) return null;
  return {
    selected_mass_t: ledger.selected_mass_t ?? null,
    estimated_mass_t: ledger.estimated_mass_t ?? null,
    target_displacement_t: ledger.target_displacement_t ?? null,
    difference_t: ledger.difference_t ?? null,
  };
}

/** The ledger items still without an owner. */
export function needsBinding(result: ShipDesignResult | null | undefined): string[] {
  const raw = ledgerOf(result)?.needs_binding;
  return Array.isArray(raw) ? raw.filter((value): value is string => typeof value === 'string') : [];
}

/** Whether every role of the ledger is bound. */
export function ledgerComplete(result: ShipDesignResult | null | undefined): boolean {
  return ledgerOf(result)?.complete === true;
}

/** The explicit basis condition the balance belongs to, or `null`. */
export function basisConditionId(result: ShipDesignResult | null | undefined): string | null {
  if (result?.basis_condition_id) return result.basis_condition_id;
  const ledger = ledgerOf(result);
  return ledger?.basis_condition_id ?? ledger?.condition_id ?? null;
}

/** The condition label a balance is honestly reported under. */
export function conditionLabel(project: ProjectDocument | null | undefined, conditionId: string | null): string | null {
  if (!conditionId) return null;
  const condition = (project?.loading_conditions ?? []).find(entry => entry.id === conditionId);
  return condition?.label ?? conditionId;
}

/**
 * A ledger row's own unresolved state, from whatever the core reported.
 *
 * The core's `mode` is the only authority: a role is unbound when the core
 * reported no mode for it. A role that legitimately carries no ledger item — the
 * optional `other` classification — is *not* therefore pending, which is why the
 * unbound *items* line is read from the ledger's own `needs_binding` list and not
 * inferred from an empty `item_ids`.
 */
export function isUnresolved(entry: ShipDesignLedgerEntry): boolean {
  if (entry.role === 'other' && !entry.mode && !(entry.item_ids?.length)) return false;
  if (typeof entry.bound === 'boolean') return !entry.bound;
  if (typeof entry.resolved === 'boolean') return !entry.resolved;
  return !(entry.mode === 'estimated' || entry.mode === 'declared');
}

/** The ledger rows still needing a binding. */
export function unresolvedEntries(entries: readonly ShipDesignLedgerEntry[]): ShipDesignLedgerEntry[] {
  return entries.filter(isUnresolved);
}

/* ---------------------------------------------------------------- bindings */

/** The recorded binding of one role, or `null`. */
export function bindingOf(design: ShipDesign | null | undefined, role: string): ShipDesignMassBinding | null {
  return design?.mass_bindings?.[role] ?? null;
}

/** The role that already claims one ledger item, if any. */
export function roleOwnerOfItem(design: ShipDesign | null | undefined, itemId: string): string | null {
  if (!design) return null;
  for (const [role, binding] of Object.entries(design.mass_bindings ?? {})) {
    if (Array.isArray(binding.item_ids) && binding.item_ids.includes(itemId)) return role;
  }
  return null;
}

/** Every ledger item claimed by more than one role — a projection that must be refused. */
export function duplicateItemIds(design: ShipDesign | null | undefined): string[] {
  const owners = new Map<string, Set<string>>();
  for (const [role, binding] of Object.entries(design?.mass_bindings ?? {})) {
    for (const id of binding.item_ids ?? []) {
      const roles = owners.get(id) ?? new Set<string>();
      roles.add(role);
      owners.set(id, roles);
    }
  }
  return [...owners.entries()].filter(([, roles]) => roles.size > 1).map(([id]) => id);
}

export type BindingProblem = 'empty' | 'estimated_multiple' | 'already_bound';

/**
 * Why a proposed binding cannot be accepted yet, or `null` when it can.
 *
 * This only encodes the core's own rules — one owned target for an `estimated`
 * role, no item claimed by two roles — so the reader is told before a request is
 * sent. It is never a local substitute for the core's answer.
 */
export function bindingProblem(
  design: ShipDesign | null | undefined, role: string, itemIds: readonly string[],
  mode: 'estimated' | 'declared',
): BindingProblem | null {
  if (itemIds.length === 0) return 'empty';
  if (mode === 'estimated' && itemIds.length > 1) return 'estimated_multiple';
  for (const id of itemIds) {
    const owner = roleOwnerOfItem(design, id);
    if (owner !== null && owner !== role) return 'already_bound';
  }
  return null;
}

/* -------------------------------------------------------------- projection */

/** The ledger item fields the core manages; every other field is the reader's. */
const MANAGED_ITEM_FIELDS = ['design_mass'] as const;

/**
 * Merge the reply's weight groups into the latest draft's.
 *
 * The reply's `weight_groups` is the governed ledger: its managed `design_mass`
 * is authoritative for an item the reader and the core both know, and it may add
 * a new automatic row or group the reader has never seen. Everything the reader
 * owns on a surviving item — its position, its source, any manual field — is
 * theirs and is kept; an item or a whole group the draft still has but the reply
 * did not answer for (a group added while this request was in flight) is kept too.
 *
 * This is what makes a save after *any* edit coherent: the draft never keeps a
 * stale managed estimate, and it never loses the reader's own manual rows.
 */
function mergeWeightGroups(
  latest: ProjectDocument, source: Record<string, unknown>,
): Array<Record<string, unknown>> | null {
  if (!Array.isArray(source.weight_groups)) return null;
  const latestGroups = Array.isArray(latest.weight_groups) ? latest.weight_groups as Array<Record<string, unknown>> : [];
  const latestById = new Map<string, Record<string, unknown>>();
  for (const group of latestGroups) latestById.set(String(group.id), group);
  const seenGroups = new Set<string>();
  const merged: Array<Record<string, unknown>> = (source.weight_groups as Array<Record<string, unknown>>).map(replyGroup => {
    seenGroups.add(String(replyGroup.id));
    const local = latestById.get(String(replyGroup.id));
    const replyItems = Array.isArray(replyGroup.items) ? replyGroup.items as Array<Record<string, unknown>> : [];
    const localItems = local && Array.isArray(local.items) ? local.items as Array<Record<string, unknown>> : [];
    const localItemById = new Map<string, Record<string, unknown>>();
    localItems.forEach((item, index) => localItemById.set(String(item.id ?? index), item));
    const seen = new Set<string>();
    const items = replyItems.map((replyItem, index) => {
      const key = String(replyItem.id ?? index);
      seen.add(key);
      const localItem = localItemById.get(key);
      if (!localItem) return replyItem;
      const mergedItem: Record<string, unknown> = { ...localItem };
      for (const field of MANAGED_ITEM_FIELDS) {
        if (field in replyItem) mergedItem[field] = replyItem[field];
        else delete mergedItem[field];
      }
      return mergedItem;
    });
    // An item only the draft still has is the reader's and stays.
    for (const item of localItems) {
      const key = String(item.id ?? '');
      if (key && !seen.has(key)) items.push(item);
    }
    return { ...(local ?? {}), ...replyGroup, items };
  });
  // A whole group the draft added while this request was in flight is the
  // reader's, and is never dropped because the reply predates it.
  for (const group of latestGroups) {
    if (!seenGroups.has(String(group.id))) merged.push(group);
  }
  return merged;
}

/**
 * The server-authored managed mass overrides of one condition.
 *
 * A `bind_mass` switch to declared writes the then-effective mass into the basis
 * condition's `overrides[item].mass_t`, and `set_declared_mass` writes the new
 * value — both with a provenance whose `source.owner` is `ship_design`. Only
 * those server-authored mass entries are adopted: any other override field, and
 * every other condition, is the reader's and stays.
 */
function authoredMassOverrides(
  condition: Record<string, unknown>,
): { overrides: Record<string, Record<string, unknown>>; provenance: Record<string, Record<string, unknown>> } | null {
  const overrides = isRecord(condition.overrides) ? condition.overrides : null;
  if (!overrides) return null;
  const provenance = isRecord(condition.override_provenance) ? condition.override_provenance : null;
  const chosen: Record<string, Record<string, unknown>> = {};
  const chosenProvenance: Record<string, Record<string, unknown>> = {};
  for (const [itemId, entry] of Object.entries(overrides)) {
    if (!isRecord(entry) || !('mass_t' in entry)) continue;
    const itemProvenance = provenance && isRecord(provenance[itemId]) ? provenance[itemId] as Record<string, unknown> : null;
    const massProvenance = itemProvenance && isRecord(itemProvenance.mass_t) ? itemProvenance.mass_t as Record<string, unknown> : null;
    const owner = massProvenance && isRecord(massProvenance.source) ? (massProvenance.source as Record<string, unknown>).owner : null;
    if (owner !== 'ship_design') continue;
    chosen[itemId] = { mass_t: entry.mass_t };
    if (massProvenance) chosenProvenance[itemId] = { mass_t: massProvenance };
  }
  if (Object.keys(chosen).length === 0) return null;
  return { overrides: chosen, provenance: chosenProvenance };
}

/**
 * Merge the reply's conditions into the latest draft's by id.
 *
 * A condition the draft already has keeps the reader's own fields, and only the
 * reply's server-authored managed mass is adopted — so switching a role to
 * declared retains its effective mass instead of falling back to a managed row's
 * exclusion zero, while no other local override field is overwritten. A condition
 * the reply introduces is appended, and the basis condition the ledger names is
 * therefore never lost.
 */
function mergeConditions(
  latest: ProjectDocument, source: Record<string, unknown>,
): ProjectDocument['loading_conditions'] | null {
  if (!Array.isArray(source.loading_conditions)) return null;
  const merged = [...latest.loading_conditions];
  const indexById = new Map(merged.map((condition, index) => [condition.id, index]));
  for (const replyCondition of source.loading_conditions as Array<Record<string, unknown>>) {
    const id = replyCondition.id;
    if (typeof id !== 'string') continue;
    const at = indexById.get(id);
    if (at === undefined) {
      merged.push(replyCondition as { id: string; label: string; [key: string]: unknown });
      indexById.set(id, merged.length - 1);
      continue;
    }
    const authored = authoredMassOverrides(replyCondition);
    if (!authored) continue;
    const local = merged[at];
    const overrides = isRecord(local.overrides) ? { ...local.overrides } : {};
    for (const [itemId, entry] of Object.entries(authored.overrides)) {
      overrides[itemId] = { ...(isRecord(overrides[itemId]) ? overrides[itemId] as Record<string, unknown> : {}), ...entry };
    }
    const provenance = isRecord(local.override_provenance) ? { ...local.override_provenance } : {};
    for (const [itemId, entry] of Object.entries(authored.provenance)) {
      provenance[itemId] = { ...(isRecord(provenance[itemId]) ? provenance[itemId] as Record<string, unknown> : {}), ...entry };
    }
    merged[at] = { ...local, overrides, override_provenance: provenance };
  }
  return merged;
}

/**
 * Overlay the governed part of a reply onto the latest draft, keeping the rest.
 *
 * `ship_design` and the eight SI hull values are the reply's; the weight ledger
 * merges managed masses onto the reader's own rows; the conditions merge by id.
 * A reply that carries the native section also retires the legacy
 * `sps_3b3_design` section: the upgrade is one declaration, not two.
 */
export function mergeDesignReply(latest: ProjectDocument, reply: ProjectDocument): ProjectDocument {
  const next: Record<string, unknown> = { ...(latest as Record<string, unknown>) };
  const source = reply as Record<string, unknown>;
  if (SHIP_DESIGN_SECTION in source) {
    next[SHIP_DESIGN_SECTION] = source[SHIP_DESIGN_SECTION];
    delete next[SPS_SECTION];
  }
  const hull = source.hull;
  if (isRecord(hull)) {
    const merged = isRecord(next.hull) ? { ...(next.hull as Record<string, unknown>) } : {};
    for (const key of GOVERNED_HULL_KEYS) if (key in hull) merged[key] = hull[key];
    next.hull = merged;
  }
  const groups = mergeWeightGroups(latest, source);
  if (groups) next.weight_groups = groups;
  const conditions = mergeConditions(latest, source);
  if (conditions) next.loading_conditions = conditions;
  return next as ProjectDocument;
}

/**
 * The draft a settled field-edit reply produces.
 *
 * The reply's projection is authoritative for the declared inputs the command
 * touched, so the governed part is overlaid on the latest draft — never adopted
 * wholesale, which would drop a local edit to an item's position or source. The
 * queue's `display` is the confirmed declaration plus every edit still queued
 * behind it, so it is what the source inputs are read from; the bindings and the
 * basis condition, which the source view cannot carry, come from the reply.
 */
export function projectSettledReply(
  latest: ProjectDocument, reply: ProjectDocument, display: Sps3b3Design | null,
): ProjectDocument {
  const merged = mergeDesignReply(latest, reply);
  const backend = shipDesignOf(merged);
  if (!backend || !display) return merged;
  const projected: ShipDesign = {
    ...backend,
    source: display.source ?? null,
    parameters: { ...backend.parameters, ...display.parameters },
    editing: { ...backend.editing, ...display.editing },
    notes: display.notes ?? null,
  };
  return withShipDesign(merged, projected);
}

/* ------------------------------------------------------------------ readers */

/** Every ledger item id the project declares, in document order. */
export function projectItemIds(project: ProjectDocument | null | undefined): string[] {
  const groups = project?.weight_groups ?? [];
  const ids: string[] = [];
  for (const group of groups) {
    for (const item of group.items ?? []) {
      if (typeof item.id === 'string' && item.id !== '') ids.push(item.id);
    }
  }
  return ids;
}

/**
 * The one weight item with this id, wherever it sits in the document.
 */
export function findWeightItem(
  project: ProjectDocument | null | undefined, itemId: string,
): Record<string, unknown> | null {
  for (const group of project?.weight_groups ?? []) {
    for (const item of group.items ?? []) if (item.id === itemId) return item;
  }
  return null;
}

/**
 * The effective mass the core currently gives one ledger item.
 *
 * Read in the order the loading resolver applies it — the core's managed
 * `design_mass` overlay, then the design-owned override for the basis condition,
 * then the item's own base mass — so a declared role shows its own declared mass
 * and an estimated role shows the managed estimate. Nothing is computed here:
 * these are the core's own numbers, in the core's own order.
 */
export function effectiveItemMass(
  project: ProjectDocument | null | undefined, itemId: string,
): number | null {
  const item = findWeightItem(project, itemId);
  if (!item) return null;
  const managed = isRecord(item.design_mass) ? item.design_mass : null;
  if (managed && 'mass_t' in managed) return typeof managed.mass_t === 'number' && Number.isFinite(managed.mass_t) ? managed.mass_t : null;
  const design = shipDesignOf(project);
  const conditionId = design?.condition_id ?? null;
  if (conditionId) {
    const condition = (project?.loading_conditions ?? []).find(entry => entry.id === conditionId);
    const override = condition && isRecord(condition.overrides) ? condition.overrides[itemId] : undefined;
    if (isRecord(override) && 'mass_t' in override) return typeof override.mass_t === 'number' && Number.isFinite(override.mass_t) ? override.mass_t : null;
  }
  return typeof item.mass_t === 'number' && Number.isFinite(item.mass_t) ? item.mass_t : null;
}

/**
 * True when the governed part of two drafts is the same.
 *
 * A settled reply is only written back when it actually changes something, so a
 * pure preview refresh never marks an untouched draft as edited.
 */
function sameValue(a: unknown, b: unknown): boolean {
  const canonical = (value: unknown): unknown => Array.isArray(value) ? value.map(canonical)
    : isRecord(value) ? Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])])) : value;
  return JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
}

export function sameGovernedSlice(left: ProjectDocument, right: ProjectDocument): boolean {
  const leftDesign = shipDesignOf(left);
  const rightDesign = shipDesignOf(right);
  if (!leftDesign || !rightDesign) return leftDesign === rightDesign;
  if (!sameValue(sourceViewOfDesign(leftDesign), sourceViewOfDesign(rightDesign))) return false;
  if (!sameValue(leftDesign.mass_bindings ?? {}, rightDesign.mass_bindings ?? {})) return false;
  if ((leftDesign.condition_id ?? null) !== (rightDesign.condition_id ?? null)) return false;
  const leftHull = left.hull ?? {};
  const rightHull = right.hull ?? {};
  for (const key of GOVERNED_HULL_KEYS) {
    if ((leftHull[key] ?? null) !== (rightHull[key] ?? null)) return false;
  }
  const leftGroups = left.weight_groups ?? [];
  const rightGroups = right.weight_groups ?? [];
  if (!sameValue(managedMasses(leftGroups), managedMasses(rightGroups))) return false;
  if (left.loading_conditions.length !== right.loading_conditions.length) return false;
  for (let index = 0; index < left.loading_conditions.length; index += 1) {
    if (left.loading_conditions[index].id !== right.loading_conditions[index].id) return false;
  }
  // A declared mass is written into the basis condition's own overrides. Without
  // this the second `set_declared_mass` on an already-declared role would read as
  // a no-change reply and never reach the draft.
  if (!sameValue(ownedConditionMass(left.loading_conditions), ownedConditionMass(right.loading_conditions))) return false;
  return true;
}

function sourceViewOfDesign(design: ShipDesign): { source: string | null; parameters: unknown; editing: unknown; notes: string | null } {
  return { source: design.source ?? null, parameters: design.parameters, editing: design.editing, notes: design.notes ?? null };
}

/** The managed masses of a whole ledger, keyed by item id, for an equality read. */
function managedMasses(groups: ProjectDocument['weight_groups']): Record<string, unknown> {
  const found: Record<string, unknown> = {};
  for (const group of groups) {
    for (const item of group.items ?? []) {
      if (typeof item.id === 'string' && 'design_mass' in item) found[item.id] = item.design_mass ?? null;
    }
  }
  return found;
}

/**
 * The design-owned mass overrides of a whole condition list, keyed by condition
 * id then item id, for an equality read.
 *
 * Only an override whose recorded mass provenance names `ship_design` as its
 * owner is read, so a changed declared mass is a governed change while the
 * reader's own unrelated override fields are never mistaken for one.
 */
function ownedConditionMass(
  conditions: ProjectDocument['loading_conditions'],
): Record<string, Record<string, unknown>> {
  const found: Record<string, Record<string, unknown>> = {};
  for (const condition of conditions) {
    if (!isRecord(condition.overrides)) continue;
    const provenance = isRecord(condition.override_provenance) ? condition.override_provenance : null;
    const authored: Record<string, unknown> = {};
    for (const [itemId, entry] of Object.entries(condition.overrides)) {
      if (!isRecord(entry) || !('mass_t' in entry)) continue;
      const itemProvenance = provenance && isRecord(provenance[itemId]) ? provenance[itemId] as Record<string, unknown> : null;
      const massProvenance = itemProvenance && isRecord(itemProvenance.mass_t) ? itemProvenance.mass_t as Record<string, unknown> : null;
      const owner = massProvenance && isRecord(massProvenance.source) ? (massProvenance.source as Record<string, unknown>).owner : null;
      if (owner !== 'ship_design') continue;
      authored[itemId] = entry.mass_t ?? null;
    }
    if (Object.keys(authored).length > 0) found[condition.id] = authored;
  }
  return found;
}
