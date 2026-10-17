import type { ProjectDocument, RunView, StageEnvelope } from '../types';
import type { ConceptKey } from '../i18n/concept';
import { number, object, rows, stageData, stringList, type Raw } from './formModel';

/**
 * The declared concept design, as the workbench edits it.
 *
 * Everything here is a pure read or a pure rewrite of the draft. Nothing in this
 * module computes a mass, a ratio or a score: the server owns every number, and a
 * component that needed one would immediately be a second, disagreeing source of
 * truth. What this module owns is *shape* — which keys exist, which enum value
 * is legal, what an explicit empty means, and which request a given draft asks
 * for.
 */

export const CONCEPT_SCHEMA = 'plimsoll-concept-design-1';
export const CONCEPT_METHOD = 'sps-3b3-adapted-v1';
export const DESIGN_BALANCE_STAGE = 'design_balance';

export const STERN_TYPES = ['cruiser', 'small_transom', 'large_transom', 'round'] as const;
export const GUN_TYPES = ['muzzle_loading', 'breech_loading', 'quick_firing', 'anti_air',
  'dual_purpose', 'automatic', 'machine_gun'] as const;
export const MOUNT_TYPES = ['broadside', 'coles_turret', 'open_barbette', 'turret_barbette',
  'deck_hoist', 'deck', 'casemate'] as const;
export const ENGINE_KINDS = ['simple', 'compound', 'turbine'] as const;

export const ROLES = ['structure', 'guns', 'mounts', 'ammunition', 'machinery', 'fuel',
  'belt_main', 'belt_upper', 'belt_ends', 'armour_bulge', 'armour_deck', 'conning', 'bulkhead',
  'rotating_armour', 'gun_mount_armour', 'misc_vital', 'misc_hull', 'misc_deck', 'misc_above',
  'misc_void', 'other'] as const;
export type Role = typeof ROLES[number];

/**
 * The role a bound component must carry, so the editor can offer it directly.
 *
 * `armour` is deliberately not `rotating_armour`: a barbette is fixed structure,
 * and labelling the whole estimate as rotating armour would be a different
 * claim from the one the kernel makes.
 */
export const COMPONENT_ROLES: Readonly<Record<string, Role>> = {
  guns: 'guns', mounts: 'mounts', ammunition: 'ammunition',
  armour: 'gun_mount_armour',
  machinery: 'machinery', fuel: 'fuel',
};

/**
 * The declared value → dictionary key of each enum.
 *
 * They live here because more than one editor prints these enums: the rows own
 * them, and a referenced row's own facts are printed beside a mount group. The
 * stored identifier is never shown to a reader.
 */
export const STERN_LABELS: Readonly<Record<string, ConceptKey>> = {
  cruiser: 'concept.stern.cruiser', small_transom: 'concept.stern.small_transom',
  large_transom: 'concept.stern.large_transom', round: 'concept.stern.round',
};
export const GUN_TYPE_LABELS: Readonly<Record<string, ConceptKey>> = {
  muzzle_loading: 'concept.gunType.muzzle_loading', breech_loading: 'concept.gunType.breech_loading',
  quick_firing: 'concept.gunType.quick_firing', anti_air: 'concept.gunType.anti_air',
  dual_purpose: 'concept.gunType.dual_purpose', automatic: 'concept.gunType.automatic',
  machine_gun: 'concept.gunType.machine_gun',
};
export const MOUNT_TYPE_LABELS: Readonly<Record<string, ConceptKey>> = {
  broadside: 'concept.mountType.broadside', coles_turret: 'concept.mountType.coles_turret',
  open_barbette: 'concept.mountType.open_barbette', turret_barbette: 'concept.mountType.turret_barbette',
  deck_hoist: 'concept.mountType.deck_hoist', deck: 'concept.mountType.deck',
  casemate: 'concept.mountType.casemate',
};
export const ENGINE_KIND_LABELS: Readonly<Record<string, ConceptKey>> = {
  simple: 'concept.kind.simple', compound: 'concept.kind.compound', turbine: 'concept.kind.turbine',
};

/** The optional armour block's own keys, in the order the editor writes them. */
export const ARMOUR_FIELDS = ['system_id', 'item_id', 'face_mm', 'rear_roof_mm',
  'barbette_mm', 'freeboard_m', 'super_factor'] as const;

/**
 * The starting estimates the contract allows the GUI to offer.
 *
 * They are written into the document explicitly and labelled as editable
 * estimates everywhere they are shown, because a number that appears in the
 * project without a visible origin is indistinguishable from a reader's own
 * figure. They are never applied to a weight or a centre of gravity.
 */
export const DEFAULT_ASSUMPTIONS: Readonly<Record<string, number>> = {
  steadiness: 50, space_hull_fraction: 0, space_deck_fraction: 0,
  super_factor: 1, super_factor_long: 1, concentration: 1, strength_target: 1,
};

export const BALANCE_ASSUMPTION_KEYS = Object.keys(DEFAULT_ASSUMPTIONS);

/** The draft's declared section, or `{}` when the screen is not enabled. */
export function conceptOf(project: ProjectDocument | null): Raw {
  const value = (project as Raw | null)?.concept_design;
  return object(value);
}

export function conceptEnabled(project: ProjectDocument | null): boolean {
  return Object.keys(conceptOf(project)).length > 0;
}

/** A fresh, enabled configuration. Everything is empty until it is declared. */
export function newConcept(): Raw {
  return {
    schema: CONCEPT_SCHEMA, method: CONCEPT_METHOD, source: '', estimate: true,
    target_displacement_t: null, hull_year: null, freeboard_m: null, stern: null, screws: null,
    batteries: [],
    machinery: null, fuel: null,
    balance: { roles: {}, assumption_source: '', bulkhead_beam_m: null, ...DEFAULT_ASSUMPTIONS },
  };
}

export function withConcept(project: ProjectDocument, config: Raw): ProjectDocument {
  return { ...project, concept_design: structuredClone(config) };
}

/** Disabling removes the section entirely, which is exactly the old behaviour. */
export function withoutConcept(project: ProjectDocument): ProjectDocument {
  const next = { ...project } as Raw;
  delete next.concept_design;
  return next as ProjectDocument;
}

export function patchConcept(project: ProjectDocument, patch: Raw): ProjectDocument {
  return withConcept(project, { ...conceptOf(project), ...patch });
}

// --- batteries --------------------------------------------------------------

export function batteries(config: Raw): Raw[] {
  return rows(config.batteries);
}

/** A new row with no numbers in it: an empty input stays empty and editable. */
export function newBattery(existing: Raw[]): Raw {
  let n = existing.length + 1;
  let id = `battery_${n}`;
  while (existing.some(row => row.id === id)) { n += 1; id = `battery_${n}`; }
  return {
    id, system_id: null, guns_item_id: null, mounts_item_id: null, ammunition_item_id: null,
    calibre_mm: null, barrel_calibres: null, year: null, gun_type: null, mount_type: null,
    mount_count: null, barrels_per_mount: null, shared_cradle: false,
    rounds_per_gun: null, shell_mass_kg: null, broadside_guns: null,
  };
}

export function patchBattery(config: Raw, index: number, patch: Raw): Raw {
  const next = batteries(config);
  next[index] = { ...object(next[index]), ...patch };
  return { ...config, batteries: next };
}

export function removeBattery(config: Raw, index: number): Raw {
  const next = batteries(config).filter((_, i) => i !== index);
  return { ...config, batteries: next };
}

/**
 * The three bindings of one row, and whether they are still distinct items.
 */
export function batteryTargets(battery: Raw): { guns: string | null; mounts: string | null; ammunition: string | null; distinct: boolean } {
  const guns = typeof battery.guns_item_id === 'string' ? battery.guns_item_id : null;
  const mounts = typeof battery.mounts_item_id === 'string' ? battery.mounts_item_id : null;
  const ammunition = typeof battery.ammunition_item_id === 'string' ? battery.ammunition_item_id : null;
  const chosen = [guns, mounts, ammunition].filter((id): id is string => id !== null);
  return { guns, mounts, ammunition, distinct: new Set(chosen).size === chosen.length };
}

// --- the optional armour block ----------------------------------------------

/** A block with nothing declared in it: empty inputs stay empty and editable. */
export function newBatteryArmour(): Raw {
  return {
    system_id: null, item_id: null, face_mm: null, rear_roof_mm: null,
    barbette_mm: null, freeboard_m: null, super_factor: null,
  };
}

/** The row's armour block, or `undefined` when it has never been turned on. */
export function armourOf(config: Raw, index: number): Raw | undefined {
  const value = batteries(config)[index]?.armour;
  return value === null || value === undefined ? undefined : object(value);
}

export function armourEnabled(config: Raw, index: number): boolean {
  return armourOf(config, index) !== undefined;
}

/**
 * Merge one field into the row's armour block.
 *
 * The base is the block as it stands, so editing one input never silently drops
 * another; a block that has never been turned on starts from the empty one.
 */
export function patchArmour(config: Raw, index: number, patchValue: Raw): Raw {
  return patchBattery(config, index,
    { armour: { ...(armourOf(config, index) ?? newBatteryArmour()), ...patchValue } });
}

/** Turning the block on writes an empty, editable block. */
export function addArmour(config: Raw, index: number): Raw {
  return patchBattery(config, index, { armour: newBatteryArmour() });
}

/** Switching the block off removes only its inputs; the ledger mass stays. */
export function removeArmour(config: Raw, index: number): Raw {
  return patchBattery(config, index, { armour: undefined });
}

// --- the optional two-group mount layouts ------------------------------------

/** The contract's own limit on how many layouts one configuration may declare. */
export const MAX_BATTERY_LAYOUTS = 50;
/** The recovered guns-in-mount selector table is 0..14. */
export const MOUNT_SELECTOR_COUNT = 15;
/** The recovered eighteen-way arrangement reading is 0..17. */
export const LAYOUT_INDEX_COUNT = 18;

export function batteryLayouts(config: Raw): Raw[] {
  return rows(config.battery_layouts);
}

/** A group's own keys, in the order the editor writes them. */
export const LAYOUT_GROUP_FIELDS = ['battery_id', 'mount_selector', 'layout_index',
  'elevated_mounts', 'deck_mounts', 'depressed_mounts'] as const;
export const DECK_PROFILE_FIELDS = ['forecastle_fraction', 'forward_deck_fraction',
  'forward_fore_m', 'forward_aft_m', 'aft_fore_m', 'aft_aft_m'] as const;
export const LAYOUT_ARMOUR_FIELDS = ['system_id', 'item_id', 'face_mm',
  'rear_roof_mm', 'barbette_mm'] as const;

/**
 * A new layout that declares nothing yet.
 *
 * Both groups are `null` because a group the source never had is absent, not
 * empty; both doubled flags are `null` because unknown is not false; the deck
 * profile holds six nulls rather than plausible values; and there is no armour
 * block until the reader turns one on. An unfinished layout is a legal draft,
 * and it is never completed by a default this file could invent.
 */
export function newBatteryLayout(existing: Raw[]): Raw {
  let n = existing.length + 1;
  let id = `layout_${n}`;
  while (existing.some(row => row.id === id)) { n += 1; id = `layout_${n}`; }
  return {
    id, source: '',
    group1: null, group2: null,
    group2_double_elevation: null, group2_double_depression: null,
    deck_profile: newDeckProfile(), armour: null,
  };
}

/** A group that names no battery row and derives nothing. */
export function newLayoutGroup(): Raw {
  return {
    battery_id: null, mount_selector: null, layout_index: null,
    elevated_mounts: null, deck_mounts: null, depressed_mounts: null,
  };
}

export function newDeckProfile(): Raw {
  return {
    forecastle_fraction: null, forward_deck_fraction: null,
    forward_fore_m: null, forward_aft_m: null, aft_fore_m: null, aft_aft_m: null,
  };
}

export function patchBatteryLayout(config: Raw, index: number, patchValue: Raw): Raw {
  const next = batteryLayouts(config);
  next[index] = { ...object(next[index]), ...patchValue };
  return { ...config, battery_layouts: next };
}

/**
 * Merge one field into a group, or clear the group outright.
 *
 * A group the reader has not configured stays absent: writing `{}` instead of
 * `null` would turn "not configured" into a declared empty group, which is a
 * different fact.
 */
export function patchLayoutGroup(config: Raw, index: number,
  group: 'group1' | 'group2', patchValue: Raw | null): Raw {
  const current = layoutGroupOf(config, index, group);
  const next = patchValue === null ? null : { ...(current ?? newLayoutGroup()), ...patchValue };
  return patchBatteryLayout(config, index, { [group]: next });
}

/** One group's declared keys, or `null` when the group is absent. */
export function layoutGroupOf(config: Raw, index: number, group: 'group1' | 'group2'): Raw | null {
  const value = batteryLayouts(config)[index]?.[group];
  return value === null || value === undefined ? null : object(value);
}

export function patchDeckProfile(config: Raw, index: number, patchValue: Raw): Raw {
  const current = deckProfileOf(config, index);
  return patchBatteryLayout(config, index,
    { deck_profile: { ...(current ?? newDeckProfile()), ...patchValue } });
}

export function deckProfileOf(config: Raw, index: number): Raw {
  return object(batteryLayouts(config)[index]?.deck_profile);
}

/** Removing a layout touches nothing else: no row, no ledger item, no mass. */
export function removeBatteryLayout(config: Raw, index: number): Raw {
  return { ...config, battery_layouts: batteryLayouts(config).filter((_, i) => i !== index) };
}

/** The layout's own armour block, or `undefined` when it was never turned on. */
export function layoutArmourOf(config: Raw, index: number): Raw | undefined {
  const value = batteryLayouts(config)[index]?.armour;
  return value === null || value === undefined ? undefined : object(value);
}

export function layoutArmourEnabled(config: Raw, index: number): boolean {
  return layoutArmourOf(config, index) !== undefined;
}

export function newLayoutArmour(): Raw {
  return { system_id: null, item_id: null, face_mm: null, rear_roof_mm: null, barbette_mm: null };
}

export function patchLayoutArmour(config: Raw, index: number, patchValue: Raw): Raw {
  return patchBatteryLayout(config, index,
    { armour: { ...(layoutArmourOf(config, index) ?? newLayoutArmour()), ...patchValue } });
}

export function addLayoutArmour(config: Raw, index: number): Raw {
  return patchBatteryLayout(config, index, { armour: newLayoutArmour() });
}

/** Switching the block off removes only this layout's inputs. */
export function removeLayoutArmour(config: Raw, index: number): Raw {
  return patchBatteryLayout(config, index, { armour: null });
}

/** The battery rows one group names, across every declared layout. */
export function layoutGroupBatteryIds(config: Raw): string[] {
  return batteryLayouts(config).flatMap(layoutGroupIdsOf);
}

function layoutGroupIdsOf(layout: Raw): string[] {
  const ids: string[] = [];
  for (const group of ['group1', 'group2']) {
    const battery = layout[group] === null || layout[group] === undefined
      ? null : object(layout[group]).battery_id;
    if (typeof battery === 'string' && battery !== '') ids.push(battery);
  }
  return ids;
}

/**
 * The layouts that still point at one battery row.
 *
 * Deleting a referenced row has to be refused with these names beside it: a
 * layout that points at a row which no longer exists is a dangling reference,
 * and the contract forbids making one.
 */
export function batteryLayoutReferences(config: Raw, batteryId: unknown): string[] {
  if (typeof batteryId !== 'string' || batteryId === '') return [];
  return batteryLayouts(config)
    .filter(layout => layoutGroupIdsOf(layout).includes(batteryId))
    .map(layout => String(layout.id ?? ''));
}

/** Rows named more than once, whether inside one layout or across two. */
export function duplicateLayoutReferences(config: Raw): string[] {
  const seen = new Set<string>();
  const twice = new Set<string>();
  for (const id of layoutGroupBatteryIds(config)) {
    if (seen.has(id)) twice.add(id); else seen.add(id);
  }
  return [...twice];
}

/**
 * Referenced rows that keep their own single-group armour estimate.
 *
 * The complete two-group estimate and a row's own estimate of the same guns
 * would weigh them twice, so the screen refuses the pair. The reader has to
 * decide which one goes; nothing here is removed for them.
 */
export function layoutArmourConflicts(config: Raw, index: number): string[] {
  const layout = batteryLayouts(config)[index];
  if (!layout) return [];
  const byId = new Map(batteries(config).map(battery => [String(battery.id ?? ''), battery]));
  return layoutGroupIdsOf(layout).filter(id => {
    const battery = byId.get(id);
    return battery !== undefined && battery.armour !== null && battery.armour !== undefined;
  });
}

// --- the optional fixed (non-rotating) armour declarations --------------------

/**
 * The recovered seven fixed armour regions, as the seven explicit choices.
 *
 * This is a *shape* module: it owns which key exists, which enum value is legal,
 * what an explicit empty means and which balance role a kind's own target must
 * carry. It computes no mass — the recovered `weightBeltMainCalc` … `weightConningCalc`
 * expressions live in the core and their readings arrive in a saved result. The
 * seven regions are deliberately never merged: a conning tower is not a belt and
 * a bulge is not a bulkhead, and one target under two components is refused by
 * the core rather than resolved here.
 */
export const FIXED_ARMOUR_KINDS = ['belt_main', 'belt_upper', 'belt_ends', 'bulkhead',
  'bulge', 'deck', 'conning'] as const;
export type FixedArmourKind = typeof FIXED_ARMOUR_KINDS[number];

/**
 * The one balance role each recovered region's own target must carry.
 *
 * `belt_main` and `belt_upper` keep their own names: the original kept two belts,
 * so one role for both would merge two declared masses into one classification.
 */
export const FIXED_ARMOUR_ROLE_BY_KIND: Readonly<Record<FixedArmourKind, Role>> = {
  belt_main: 'belt_main', belt_upper: 'belt_upper', belt_ends: 'belt_ends',
  bulkhead: 'bulkhead', bulge: 'armour_bulge', deck: 'armour_deck', conning: 'conning',
};

/** The recovered seven-way deck coverage switch, as labels rather than indices. */
export const FIXED_ARMOUR_COVERAGE_KEYS: ReadonlyArray<ConceptKey> = [
  'concept.fixedArmour.coverage.0', 'concept.fixedArmour.coverage.1',
  'concept.fixedArmour.coverage.2', 'concept.fixedArmour.coverage.3',
  'concept.fixedArmour.coverage.4', 'concept.fixedArmour.coverage.5',
  'concept.fixedArmour.coverage.6',
];

export const FIXED_ARMOUR_KIND_LABELS: Readonly<Record<string, ConceptKey>> = {
  belt_main: 'concept.fixedArmour.kind.belt_main', belt_upper: 'concept.fixedArmour.kind.belt_upper',
  belt_ends: 'concept.fixedArmour.kind.belt_ends', bulkhead: 'concept.fixedArmour.kind.bulkhead',
  bulge: 'concept.fixedArmour.kind.bulge', deck: 'concept.fixedArmour.kind.deck',
  conning: 'concept.fixedArmour.kind.conning',
};

/** The contract's own limit on how many fixed regions one configuration may declare. */
export const MAX_FIXED_ARMOUR_RECORDS = 50;
/** The recovered planar plates, all read by the same doubled/single area expression. */
export const FIXED_ARMOUR_PLATE_KINDS = ['belt_main', 'belt_upper', 'belt_ends',
  'bulkhead', 'bulge'] as const;

export const FIXED_ARMOUR_COMMON_FIELDS = ['system_id', 'item_id', 'source'] as const;
export const FIXED_ARMOUR_PLATE_FIELDS = ['thickness_mm', 'length_m', 'height_m'] as const;
export const FIXED_ARMOUR_DECK_FIELDS = ['thickness_mm', 'coverage_index',
  'forecastle_fraction', 'quarterdeck_fraction', 'forecastle_mm', 'quarterdeck_mm'] as const;
export const FIXED_ARMOUR_CONNING_FIELDS = ['thickness_mm', 'aft_mm'] as const;

/** Every engineering field any kind may declare, so an undeclared kind drops them all. */
export const FIXED_ARMOUR_ALL_FIELDS: readonly string[] = [
  ...new Set([...FIXED_ARMOUR_PLATE_FIELDS, ...FIXED_ARMOUR_DECK_FIELDS,
    ...FIXED_ARMOUR_CONNING_FIELDS]),
];

/** The engineering fields that belong to one kind, and only to that kind. */
export const FIXED_ARMOUR_FIELDS_BY_KIND: Readonly<Record<FixedArmourKind, readonly string[]>> = {
  belt_main: FIXED_ARMOUR_PLATE_FIELDS, belt_upper: FIXED_ARMOUR_PLATE_FIELDS,
  belt_ends: FIXED_ARMOUR_PLATE_FIELDS, bulkhead: FIXED_ARMOUR_PLATE_FIELDS,
  bulge: FIXED_ARMOUR_PLATE_FIELDS, deck: FIXED_ARMOUR_DECK_FIELDS,
  conning: FIXED_ARMOUR_CONNING_FIELDS,
};

/**
 * The one identifier shape every declared component shares.
 *
 * The battery layouts, the fixed armour regions and the auxiliary weapons all
 * take their identifiers from the recovered source's own names, so this is the
 * ASCII letter/digit/underscore/dot/hyphen rule of 1..80 characters rather than
 * three separate ones that could drift apart.
 */
const DECLARATION_ID = /^[A-Za-z0-9_.-]{1,80}$/;

export function fixedArmourKind(value: unknown): FixedArmourKind | null {
  return typeof value === 'string' && (FIXED_ARMOUR_KINDS as readonly string[]).includes(value)
    ? value as FixedArmourKind : null;
}

export function fixedArmour(config: Raw): Raw[] {
  return rows(config.fixed_armour);
}

/**
 * The balance role one fixed region's target must carry, or `null` while no kind
 * is chosen: an unconfigured region has no role, and none is invented for it.
 */
export function fixedArmourRole(record: Raw): Role | null {
  const kind = fixedArmourKind(record.kind);
  return kind === null ? null : FIXED_ARMOUR_ROLE_BY_KIND[kind];
}

/**
 * A new region that declares nothing yet.
 *
 * `belt_main` is the editor's initial choice for an otherwise empty record, and
 * nothing else is written: every thickness, extent, selector and fraction is an
 * explicit unknown rather than a plausible default. An unfinished declaration is
 * a legal draft and is never completed by a number this module could invent.
 */
export function newFixedArmour(existing: Raw[]): Raw {
  let n = existing.length + 1;
  let id = `fixed_armour_${n}`;
  while (existing.some(row => row.id === id)) { n += 1; id = `fixed_armour_${n}`; }
  return {
    id, kind: 'belt_main', system_id: null, item_id: null, source: '',
    thickness_mm: null, length_m: null, height_m: null,
  };
}

export function patchFixedArmour(config: Raw, index: number, patchValue: Raw): Raw {
  const next = fixedArmour(config);
  next[index] = { ...object(next[index]), ...patchValue };
  return { ...config, fixed_armour: next };
}

/**
 * Put one region back exactly as `changeFixedArmourKind` returned it.
 *
 * This replaces rather than merges, and the difference matters: merging would
 * bring back the geometry the new kind does not have, which is precisely what a
 * kind change has to drop.
 */
export function replaceFixedArmour(config: Raw, index: number, record: Raw): Raw {
  const next = fixedArmour(config);
  next[index] = { ...record };
  return { ...config, fixed_armour: next };
}

/** Removing a region touches nothing else: no ledger item, no role and no mass. */
export function removeFixedArmour(config: Raw, index: number): Raw {
  return { ...config, fixed_armour: fixedArmour(config).filter((_, i) => i !== index) };
}

/**
 * Choose a different recovered region for one declaration.
 *
 * The identity survives — `id`, the declared `source` and the `system_id`/`item_id`
 * binding are the reader's own facts and are carried across unchanged. The
 * geometry does not: only a field that is legal in *both* the old and the new
 * kind keeps its value, every other field is set to an explicit unknown and every
 * field the new kind does not have is dropped. A hand-edited deck record carrying
 * a stray `length_m` therefore cannot become a declared belt length, and nothing
 * is ever *adopted*: no thickness, extent, selector or fraction is moved from one
 * field to another, and no value is invented for the new kind.
 */
export function changeFixedArmourKind(record: Raw, kind: FixedArmourKind): Raw {
  const previous = fixedArmourKind(record.kind);
  const wanted = FIXED_ARMOUR_FIELDS_BY_KIND[kind];
  const keep = new Set(previous === null ? [] : FIXED_ARMOUR_FIELDS_BY_KIND[previous]);
  const next: Raw = { id: typeof record.id === 'string' ? record.id : '',
    kind, system_id: record.system_id ?? null, item_id: record.item_id ?? null,
    source: record.source ?? '' };
  for (const field of wanted) {
    next[field] = keep.has(field) && field in record ? record[field] ?? null : null;
  }
  return next;
}

/** Whether one declared identifier is the contract's own identifier shape. */
export function fixedArmourIdValid(id: unknown): boolean {
  return typeof id === 'string' && DECLARATION_ID.test(id);
}

/**
 * Identifiers more than one region declares.
 *
 * The core refuses a duplicate outright, so this is the editor saying so next to
 * the second row rather than a second, disagreeing implementation of the rule.
 */
export function duplicateFixedArmourIds(config: Raw): string[] {
  const seen = new Set<string>();
  const twice = new Set<string>();
  for (const record of fixedArmour(config)) {
    const id = record.id;
    if (typeof id !== 'string' || id === '') continue;
    if (seen.has(id)) twice.add(id); else seen.add(id);
  }
  return [...twice];
}

/** The ledger item one fixed region names, or `null` while the binding is a draft. */
export function fixedArmourTarget(record: Raw): string | null {
  return typeof record.item_id === 'string' && record.item_id !== '' ? record.item_id : null;
}

// --- the optional auxiliary (non-battery) weapons ---------------------------

/**
 * The recovered auxiliary weapon families, as the three explicit choices.
 *
 * The original's weapon page held two torpedo descriptions, one mine
 * description and two depth-charge/AS-mortar descriptions. Each is an
 * *independent* declaration here, with its own identifier, its own owned ledger
 * target and its own recovered expression — never merged into a gun battery and
 * never derived from one. A torpedo reads a diameter, a length and a count; a
 * mine and a depth charge read a whole-unit mass and a count, and they do not
 * share a formula.
 *
 * This module owns shape only. The recovered `sizeNweight` expressions, the
 * `dateHull < 1907` year branch and the per-location mount factors all live in
 * the core, and the readings arrive in a saved result.
 */
export const AUXILIARY_WEAPON_KINDS = ['torpedo', 'mine', 'depth_charge'] as const;
export type AuxiliaryWeaponKind = typeof AUXILIARY_WEAPON_KINDS[number];

/**
 * The balance role a bound auxiliary target carries.
 *
 * The combined weapon-plus-mount mass is an *other* weight: it is not a bare gun
 * mass, not an ammunition mass, and not a structural or space contribution. A
 * reader who wants it inside the gun or ammunition budget must allocate it there
 * explicitly; this screen never relabels it.
 */
export const AUXILIARY_WEAPON_ROLE: Role = 'other';

export const AUXILIARY_WEAPON_KIND_LABELS: Readonly<Record<string, ConceptKey>> = {
  torpedo: 'concept.auxiliary.kind.torpedo', mine: 'concept.auxiliary.kind.mine',
  depth_charge: 'concept.auxiliary.kind.depth_charge',
};

/** The contract's own limit on how many auxiliary records one configuration may declare. */
export const MAX_AUXILIARY_WEAPONS = 50;

/**
 * The engineering fields each kind declares, and only those.
 *
 * `count`, `loads` and `location_index` are common to all three: the source's
 * form declared all of them on every one of its five descriptions, and its
 * `sizeNweight` reads them all three. `diameter_mm`/`length_m` belong to a
 * torpedo and `unit_mass_kg` to a mine and a depth charge, because a mine's
 * "size" in the original is a whole-unit mass and not a length.
 */
export const AUXILIARY_WEAPON_FIELDS_BY_KIND: Readonly<Record<AuxiliaryWeaponKind, readonly string[]>> = {
  torpedo: ['count', 'loads', 'location_index', 'diameter_mm', 'length_m'],
  mine: ['count', 'loads', 'location_index', 'unit_mass_kg'],
  depth_charge: ['count', 'loads', 'location_index', 'unit_mass_kg'],
};

export const AUXILIARY_WEAPON_COMMON_FIELDS = ['count', 'loads', 'location_index'] as const;
export const AUXILIARY_WEAPON_ALL_FIELDS: readonly string[] = [
  ...new Set(Object.values(AUXILIARY_WEAPON_FIELDS_BY_KIND).flat()),
];

/**
 * The recovered location choices, as their own names rather than as indices.
 *
 * Nine for a torpedo, four for a mine and four for a depth charge. The mount
 * factor the recovered expressions apply differs per choice and per family, so a
 * stored index is a real declaration of a real place, and an empty picker stays
 * unknown: a positive weapon with an unknown location cannot produce a complete
 * estimate and this screen must not pick one for the reader.
 */
export const AUXILIARY_WEAPON_LOCATION_KEYS: Readonly<Record<AuxiliaryWeaponKind, readonly ConceptKey[]>> = {
  torpedo: ['concept.auxiliary.location.torpedo.0', 'concept.auxiliary.location.torpedo.1',
    'concept.auxiliary.location.torpedo.2', 'concept.auxiliary.location.torpedo.3',
    'concept.auxiliary.location.torpedo.4', 'concept.auxiliary.location.torpedo.5',
    'concept.auxiliary.location.torpedo.6', 'concept.auxiliary.location.torpedo.7',
    'concept.auxiliary.location.torpedo.8'],
  mine: ['concept.auxiliary.location.mine.0', 'concept.auxiliary.location.mine.1',
    'concept.auxiliary.location.mine.2', 'concept.auxiliary.location.mine.3'],
  depth_charge: ['concept.auxiliary.location.depth_charge.0', 'concept.auxiliary.location.depth_charge.1',
    'concept.auxiliary.location.depth_charge.2', 'concept.auxiliary.location.depth_charge.3'],
};

/** How many location choices each recovered family offers. */
export function auxiliaryWeaponLocationCount(kind: AuxiliaryWeaponKind): number {
  return AUXILIARY_WEAPON_LOCATION_KEYS[kind].length;
}

export function auxiliaryWeaponKind(value: unknown): AuxiliaryWeaponKind | null {
  return typeof value === 'string' && (AUXILIARY_WEAPON_KINDS as readonly string[]).includes(value)
    ? value as AuxiliaryWeaponKind : null;
}

export function auxiliaryWeapons(config: Raw): Raw[] {
  return rows(config.auxiliary_weapons);
}

/**
 * The balance role this record's target carries.
 *
 * `null` only while no kind is chosen: an unconfigured record is not a component,
 * and no role is invented for it.
 */
export function auxiliaryWeaponRole(record: Raw): Role | null {
  return auxiliaryWeaponKind(record.kind) === null ? null : AUXILIARY_WEAPON_ROLE;
}

/**
 * A new record that declares nothing yet.
 *
 * `torpedo` is the editor's initial choice for an otherwise empty record. Every
 * count, reload, location, diameter, length and unit mass is an explicit unknown
 * rather than a plausible default: the recovered expressions treat a declared
 * zero as a determined zero, so a filled-in default would be a different fact and
 * not a friendlier one.
 */
export function newAuxiliaryWeapon(existing: Raw[]): Raw {
  let n = existing.length + 1;
  let id = `auxiliary_${n}`;
  while (existing.some(row => row.id === id)) { n += 1; id = `auxiliary_${n}`; }
  return { id, kind: 'torpedo', system_id: null, item_id: null, source: '',
    count: null, loads: null, location_index: null, diameter_mm: null, length_m: null };
}

export function patchAuxiliaryWeapon(config: Raw, index: number, patchValue: Raw): Raw {
  const next = auxiliaryWeapons(config);
  next[index] = { ...object(next[index]), ...patchValue };
  return { ...config, auxiliary_weapons: next };
}

/**
 * Put one record back exactly as `changeAuxiliaryWeaponKind` returned it.
 *
 * Replacing rather than merging, because merging would bring back the field the
 * new kind does not have — a mine's whole-unit mass is not a torpedo's diameter.
 */
export function replaceAuxiliaryWeapon(config: Raw, index: number, record: Raw): Raw {
  const next = auxiliaryWeapons(config);
  next[index] = { ...record };
  return { ...config, auxiliary_weapons: next };
}

/** Removing a record touches nothing else: no ledger item, no role and no mass. */
export function removeAuxiliaryWeapon(config: Raw, index: number): Raw {
  return { ...config, auxiliary_weapons: auxiliaryWeapons(config).filter((_, i) => i !== index) };
}

/**
 * Choose a different recovered family for one declaration.
 *
 * The identity survives — `id`, the declared `source` and the `system_id`/`item_id`
 * binding are the reader's own facts. Only a field legal in *both* families keeps
 * its value; every other field becomes an explicit unknown and every field the new
 * family does not have is dropped. A location index is deliberately *not* carried
 * across: torpedo location 4 and mine location 4 are different places with
 * different mount factors, and the new family's own choices are shorter, so a
 * carried index would be an adopted one.
 *
 * Nothing is moved from one field to another and nothing is invented: a mine's
 * whole-unit mass is never derived from a torpedo's diameter.
 */
export function changeAuxiliaryWeaponKind(record: Raw, kind: AuxiliaryWeaponKind): Raw {
  const previous = auxiliaryWeaponKind(record.kind);
  const keep = new Set<string>(previous === kind ? AUXILIARY_WEAPON_FIELDS_BY_KIND[kind]
    : previous === null ? [] : ['count', ...(previous !== 'torpedo' && kind !== 'torpedo'
      ? ['loads', 'unit_mass_kg'] : [])]);
  const next: Raw = { id: typeof record.id === 'string' ? record.id : '',
    kind, system_id: record.system_id ?? null, item_id: record.item_id ?? null,
    source: record.source ?? '' };
  for (const field of AUXILIARY_WEAPON_FIELDS_BY_KIND[kind]) {
    next[field] = keep.has(field) && field in record ? record[field] ?? null : null;
  }
  return next;
}

/** Every engineering field of one record, set to unknown. */
export function withoutAuxiliaryFields(): Raw {
  const next: Raw = {};
  for (const field of AUXILIARY_WEAPON_ALL_FIELDS) next[field] = null;
  return next;
}

/** Whether one declared identifier is the contract's own identifier shape. */
export function auxiliaryWeaponIdValid(id: unknown): boolean {
  return typeof id === 'string' && DECLARATION_ID.test(id);
}

/** Identifiers more than one auxiliary record declares. */
export function duplicateAuxiliaryWeaponIds(config: Raw): string[] {
  const seen = new Set<string>();
  const twice = new Set<string>();
  for (const record of auxiliaryWeapons(config)) {
    const id = record.id;
    if (typeof id !== 'string' || id === '') continue;
    if (seen.has(id)) twice.add(id); else seen.add(id);
  }
  return [...twice];
}

/** The ledger item one auxiliary record names, or `null` while the binding is a draft. */
export function auxiliaryWeaponTarget(record: Raw): string | null {
  return typeof record.item_id === 'string' && record.item_id !== '' ? record.item_id : null;
}

/** The auxiliary records that name one ledger item more than once. */
export function auxiliaryWeaponTargetConflicts(config: Raw): string[] {
  const counts = new Map<string, number>();
  for (const record of auxiliaryWeapons(config)) {
    const item = auxiliaryWeaponTarget(record);
    if (item !== null) counts.set(item, (counts.get(item) ?? 0) + 1);
  }
  return [...counts].filter(([, count]) => count > 1).map(([item]) => item).sort();
}

// --- the optional empirical cost reading -------------------------------------

/**
 * The cost section, or `null` when the screen is not enabled.
 *
 * Absent and `null` are the same disabled state and neither adds a field
 * anywhere, which is what keeps a project that never enabled cost byte-for-byte
 * the project it already was. Money is a *reading*: this section owns no ledger
 * target, has no proposal and no adoption path, and the editor offers none.
 */
export function costOf(config: Raw): Raw | null {
  const value = config.cost;
  return value === null || value === undefined ? null : object(value);
}

export function costEnabled(config: Raw): boolean {
  return costOf(config) !== null;
}

/** The enabled section: one source field, and nothing else. */
export function newCost(): Raw {
  return { source: null };
}

export function patchCost(config: Raw, patchValue: Raw): Raw {
  return { ...config, cost: { ...(costOf(config) ?? newCost()), ...patchValue } };
}

/** Switching it off removes only the declaration; no ledger mass is touched. */
export function removeCost(config: Raw): Raw {
  return { ...config, cost: null };
}

// --- the optional whole-battery and armour mass summary ---------------------

/**
 * The mass-summary section, or `null` when it was never declared.
 *
 * It is a *declaration of scope* and nothing else: one source text and one
 * complete-scope flag. It owns no ledger target and has no mass of its own, and
 * it adds no field anywhere while it is absent — which is what keeps a project
 * that never enabled it byte-for-byte the project it already was. The readings
 * it turns on — the whole-battery totals and the armour totals — are the
 * server's own and are read-only: adopting a mass is a separate, explicit act
 * this screen does not offer.
 */
export function massSummaryOf(config: Raw): Raw | null {
  const value = config.mass_summary;
  return value === null || value === undefined ? null : object(value);
}

export function massSummaryEnabled(config: Raw): boolean {
  return massSummaryOf(config) !== null;
}

/**
 * The enabled section: one source field and one complete-scope flag.
 *
 * `armour_scope_complete` is `null` until the reader confirms it, because an
 * empty or unknown flag is *not* a claim of completeness: only `true` says the
 * declarations cover every armour category and every category left out is a
 * declared zero. A null or unchecked flag keeps the known subtotal readable but
 * never produces a complete estimated total.
 */
export function newMassSummary(): Raw {
  return { source: null, armour_scope_complete: null };
}

export function patchMassSummary(config: Raw, patchValue: Raw): Raw {
  return { ...config, mass_summary: { ...(massSummaryOf(config) ?? newMassSummary()), ...patchValue } };
}

/** Switching it off removes only the declaration; no ledger mass is touched. */
export function removeMassSummary(config: Raw): Raw {
  return { ...config, mass_summary: null };
}

// --- the optional whole-battery mount allocation ----------------------------

/**
 * The product allocation method and policy.
 *
 * They are the product's own names, kept distinct from the source SPS total's
 * method: the source total is an empirical estimate and the allocation is the
 * product's proportional policy, and a reader must be able to tell which figure
 * is which. Nothing here evaluates either of them.
 */
export const BATTERY_ALLOCATION_METHOD = 'plimsoll-battery-mount-allocation-v1';
export const BATTERY_ALLOCATION_POLICY = 'proportional-row-mounts-v1';

/**
 * The declared whole-battery mount allocation, or `null` when never declared.
 *
 * It is an ordinary optional declaration of *scope*: one source text and one
 * explicit layout selection. It owns no ledger target, computes no mass and adds
 * no field while it is absent — which is what keeps a project that never enabled
 * it byte-for-byte the project it already was. The source total and the per-row
 * allocations are the server's own readings and are never adopted from here.
 */
export function batteryMassAllocationOf(config: Raw): Raw | null {
  const value = config.battery_mass_allocation;
  return value === null || value === undefined ? null : object(value);
}

export function batteryMassAllocationEnabled(config: Raw): boolean {
  return batteryMassAllocationOf(config) !== null;
}

/**
 * The enabled section, declaring nothing yet.
 *
 * `layout_ids` starts `null` on purpose: an unknown selection is a different
 * fact from an explicit empty one, and no layout is ever selected for the
 * reader. Only an explicit array opts in, and `[]` declares a known empty scope.
 */
export function newBatteryMassAllocation(): Raw {
  return { source: null, layout_ids: null };
}

export function patchBatteryMassAllocation(config: Raw, patchValue: Raw): Raw {
  return { ...config, battery_mass_allocation: { ...(batteryMassAllocationOf(config) ?? newBatteryMassAllocation()), ...patchValue } };
}

/** Switching it off removes only the declaration; no ledger mass is touched. */
export function removeBatteryMassAllocation(config: Raw): Raw {
  return { ...config, battery_mass_allocation: null };
}

/**
 * The explicit layout selection, or `null` while it is still unknown.
 *
 * A declared empty array stays an empty array: "no layout is selected, so the
 * scope is a known zero" is not the same statement as "the reader has not
 * chosen", and the allocation result depends on the difference.
 */
export function allocationLayoutIds(config: Raw): string[] | null {
  const value = batteryMassAllocationOf(config)?.layout_ids;
  return Array.isArray(value) ? stringList(value) : null;
}

/**
 * Selected layout ids that do not name exactly one declared layout.
 *
 * The allocation is evaluated from the layout ids as stored, so a selected id
 * that no longer resolves is a dangling reference: it is named precisely and
 * nothing is cleared for the reader.
 */
export function invalidAllocationLayoutIds(config: Raw): string[] {
  const ids = allocationLayoutIds(config);
  if (ids === null) return [];
  const counts = new Map<string, number>();
  for (const layout of batteryLayouts(config)) {
    const id = String(layout.id ?? '');
    if (id !== '') counts.set(id, (counts.get(id) ?? 0) + 1);
  }
  return ids.filter(id => (counts.get(id) ?? 0) !== 1);
}

/** The declared layout ids the allocation selection names, for the reference guard. */
export function allocationLayoutReferences(config: Raw): string[] {
  return allocationLayoutIds(config) ?? [];
}

/** The saved whole-battery allocation readings, one per selected layout. */
export function batteryMassAllocationReadings(run: RunView | null): Raw[] {
  return rows(balanceData(run).battery_mass_allocation);
}

/**
 * The supported allocation model a proposal carries, read from `model.inputs`.
 *
 * A proposal is a member of a whole-battery allocation cohort only when its
 * inputs declare the supported allocation method *and* a nonempty group id. Any
 * other proposal — including one that merely mentions the method — is an
 * ordinary proposal and keeps the ordinary selection rules.
 */
export interface AllocationProposal {
  supported: boolean;
  group_id: string;
  policy: string;
  target_ids: string[];
}

export function allocationProposal(proposal: Raw): AllocationProposal {
  const inputs = object(object(proposal.model).inputs);
  const method = typeof inputs.method_version === 'string' ? inputs.method_version : '';
  const group = typeof inputs.allocation_group_id === 'string' ? inputs.allocation_group_id : '';
  const supported = method === BATTERY_ALLOCATION_METHOD && group !== '';
  return {
    supported,
    group_id: supported ? group : '',
    policy: supported && typeof inputs.allocation_policy === 'string' ? inputs.allocation_policy : '',
    target_ids: supported ? stringList(inputs.allocation_target_ids) : [],
  };
}

// --- the optional geometric armour panels -----------------------------------

/**
 * The rectangular panel method.
 *
 * This is not another recovered SPS expression: it is the product's own flat-plate
 * geometry, and it is deliberately kept apart from the recovered empirical method
 * each fixed region already carries. A reader must be able to tell which of the
 * two produced a number, so the two methods are never merged under one name.
 */
export const ARMOUR_GEOMETRY_METHOD = 'plimsoll-armour-panels-v1';

/**
 * The fixed-region kinds the rectangular model accepts.
 *
 * Curved bulges and conning towers are outside this first geometry unit; their
 * recovered empirical capability is preserved untouched by declaring no geometry
 * for them.
 */
export const ARMOUR_GEOMETRY_KINDS = ['belt_main', 'belt_ends', 'belt_upper',
  'bulkhead', 'deck'] as const;

/** How a declared plate width is developed. `null` is an unknown basis. */
export const ARMOUR_GEOMETRY_WIDTH_BASES = ['developed', 'projected'] as const;
export type ArmourWidthBasis = typeof ARMOUR_GEOMETRY_WIDTH_BASES[number];

export const ARMOUR_GEOMETRY_WIDTH_BASIS_LABELS: Readonly<Record<ArmourWidthBasis, ConceptKey>> = {
  developed: 'concept.armourGeometry.basis.developed',
  projected: 'concept.armourGeometry.basis.projected',
};

/** The contract's own limits on one geometry declaration. */
export const MAX_ARMOUR_GEOMETRY_REGIONS = 50;
export const MAX_ARMOUR_GEOMETRY_PLATES = 100;

export function armourGeometryEligibleKind(value: unknown): boolean {
  return typeof value === 'string' && (ARMOUR_GEOMETRY_KINDS as readonly string[]).includes(value);
}

/** Whether one declared identifier is the contract's own identifier shape. */
export function armourGeometryIdValid(id: unknown): boolean {
  return typeof id === 'string' && DECLARATION_ID.test(id);
}

/**
 * The declared geometry, or `null` when never declared.
 *
 * Absent or null preserves the complete old shape and every empirical model:
 * a project that never enabled geometry is byte-for-byte what it already was.
 * Once present, `regions: []` is an explicit "this run opts in no region", which
 * is a different fact from the section being absent.
 */
export function armourGeometryOf(config: Raw): Raw | null {
  const value = config.armour_geometry;
  return value === null || value === undefined ? null : object(value);
}

export function armourGeometryEnabled(config: Raw): boolean {
  return armourGeometryOf(config) !== null;
}

/** The enabled section, selecting no region and inventing no density or size. */
export function newArmourGeometry(): Raw {
  return { source: null, regions: [] };
}

export function patchArmourGeometry(config: Raw, patchValue: Raw): Raw {
  return { ...config, armour_geometry: { ...(armourGeometryOf(config) ?? newArmourGeometry()), ...patchValue } };
}

/** Switching it off removes only the declaration; no ledger mass is touched. */
export function removeArmourGeometry(config: Raw): Raw {
  return { ...config, armour_geometry: null };
}

export function armourGeometryRegions(config: Raw): Raw[] {
  return rows(armourGeometryOf(config)?.regions);
}

/** A new region that references no fixed record yet and declares no plate. */
export function newArmourGeometryRegion(): Raw {
  return { fixed_armour_id: null, source: null, plates: [] };
}

export function patchArmourGeometryRegion(config: Raw, index: number, patchValue: Raw): Raw {
  const regions = armourGeometryRegions(config);
  regions[index] = { ...object(regions[index]), ...patchValue };
  return patchArmourGeometry(config, { regions });
}

export function removeArmourGeometryRegion(config: Raw, index: number): Raw {
  return patchArmourGeometry(config, { regions: armourGeometryRegions(config).filter((_, i) => i !== index) });
}

export function armourGeometryPlates(region: Raw): Raw[] {
  return rows(region.plates);
}

/** A new plate that declares nothing: every dimension, count and basis is unknown. */
export function newArmourGeometryPlate(): Raw {
  return { id: '', source: null, density_source: null, length_m: null, width_m: null,
    thickness_mm: null, density_kg_m3: null, count: null, width_basis: null, inclination_deg: null };
}

export function patchArmourGeometryPlate(config: Raw, regionIndex: number, plateIndex: number, patchValue: Raw): Raw {
  const regions = armourGeometryRegions(config);
  const region = object(regions[regionIndex]);
  const plates = armourGeometryPlates(region);
  plates[plateIndex] = { ...object(plates[plateIndex]), ...patchValue };
  regions[regionIndex] = { ...region, plates };
  return patchArmourGeometry(config, { regions });
}

export function removeArmourGeometryPlate(config: Raw, regionIndex: number, plateIndex: number): Raw {
  const regions = armourGeometryRegions(config);
  const region = object(regions[regionIndex]);
  regions[regionIndex] = { ...region, plates: armourGeometryPlates(region).filter((_, i) => i !== plateIndex) };
  return patchArmourGeometry(config, { regions });
}

/** Every fixed-region id the geometry names, whether or not it resolves. */
export function armourGeometryReferences(config: Raw): string[] {
  const ids: string[] = [];
  for (const region of armourGeometryRegions(config)) {
    const id = region.fixed_armour_id;
    if (typeof id === 'string' && id !== '') ids.push(id);
  }
  return ids;
}

/**
 * Referenced fixed ids that name no single eligible declared region.
 *
 * A reference to a missing record, a duplicated one, or one whose kind the
 * rectangular model does not accept is a dangling reference. It is named
 * precisely and nothing is cleared for the reader.
 */
export function invalidArmourGeometryReferences(config: Raw): string[] {
  const counts = new Map<string, number>();
  for (const record of fixedArmour(config)) {
    const id = String(record.id ?? '');
    if (id !== '' && armourGeometryEligibleKind(record.kind)) counts.set(id, (counts.get(id) ?? 0) + 1);
  }
  return armourGeometryReferences(config).filter(id => (counts.get(id) ?? 0) !== 1);
}

/** Fixed ids named by more than one geometry region. Each may appear once. */
export function duplicateArmourGeometryRegions(config: Raw): string[] {
  const seen = new Set<string>(); const twice = new Set<string>();
  for (const id of armourGeometryReferences(config)) {
    if (seen.has(id)) twice.add(id); else seen.add(id);
  }
  return [...twice];
}

/** Plate ids declared more than once within one region. */
export function duplicateArmourGeometryPlateIds(region: Raw): string[] {
  const seen = new Set<string>(); const twice = new Set<string>();
  for (const plate of armourGeometryPlates(region)) {
    const id = plate.id;
    if (typeof id !== 'string' || id === '') continue;
    if (seen.has(id)) twice.add(id); else seen.add(id);
  }
  return [...twice];
}

/**
 * The angle convention a projected width is measured in, by region kind.
 *
 * Belts and bulkheads are signed from the vertical; a deck is signed from the
 * horizontal. A developed basis reads no angle at all. This is a *convention
 * label* for the reader, never an evaluated number.
 */
export function armourGeometryAngleBasis(kind: unknown): 'vertical' | 'horizontal' | null {
  if (kind === 'deck') return 'horizontal';
  if (kind === 'belt_main' || kind === 'belt_ends' || kind === 'belt_upper' || kind === 'bulkhead') {
    return 'vertical';
  }
  return null;
}

/** The saved geometric panel readings, one per declared region. */
export function armourGeometryReadings(run: RunView | null): Raw[] {
  return rows(balanceData(run).armour_geometry);
}

// --- roles ------------------------------------------------------------------

export function roles(config: Raw): Raw {
  return object(object(config.balance).roles);
}

export function patchRole(config: Raw, itemId: string, role: Role | null): Raw {
  const balance = object(config.balance);
  const next = { ...roles(config) };
  if (role === null) delete next[itemId]; else next[itemId] = role;
  return { ...config, balance: { ...balance, roles: next } };
}

/** Item ids a declared component already binds, with the role each must carry. */
export function componentBindings(config: Raw): Record<string, Role> {
  const out: Record<string, Role> = {};
  for (const battery of batteries(config)) {
    for (const [field, role] of [['guns_item_id', 'guns'], ['mounts_item_id', 'mounts'],
      ['ammunition_item_id', 'ammunition']] as Array<[string, Role]>) {
      const item = battery[field];
      if (typeof item === 'string' && item !== '') out[item] = role;
    }
    // The armour block carries its own binding, separate from the row's three.
    const armourItem = object(battery.armour).item_id;
    if (typeof armourItem === 'string' && armourItem !== '') out[armourItem] = 'gun_mount_armour';
  }
  for (const [field, role] of [['machinery', 'machinery'], ['fuel', 'fuel']] as const) {
    const item = object(config[field]).item_id;
    if (typeof item === 'string' && item !== '') out[item] = role;
  }
  // A layout's complete two-group armour is a whole battery's armour, so it
  // carries the same complete-armour role as a single-row estimate and nothing
  // else; a barbette is fixed structure, not rotating armour.
  for (const layout of batteryLayouts(config)) {
    const armourItem = object(layout.armour).item_id;
    if (typeof armourItem === 'string' && armourItem !== '') out[armourItem] = 'gun_mount_armour';
  }
  // A fixed region carries the role of its own recovered kind, and each of the
  // seven keeps its own: a conning tower is fixed structure, not a belt and not
  // rotating armour, and two declared belts are two declared masses.
  for (const record of fixedArmour(config)) {
    const item = fixedArmourTarget(record);
    const role = fixedArmourRole(record);
    if (item !== null && role !== null) out[item] = role;
  }
  // An auxiliary weapon's combined weapon-plus-mount mass is one *other* weight.
  // It is deliberately not bare guns, not ammunition and not structure: a reader
  // who wants it inside one of those budgets allocates it there themselves.
  for (const record of auxiliaryWeapons(config)) {
    const item = auxiliaryWeaponTarget(record);
    const role = auxiliaryWeaponRole(record);
    // A conflicting draft is refused by validation. It cannot reclassify an
    // existing component while the reader is correcting that conflict.
    if (item !== null && role !== null && !(item in out)) out[item] = role;
  }
  return out;
}

/**
 * Every ledger item a declared component — or the balance's own adjustable
 * structure item — already binds.
 *
 * One target under two components is refused by the core, so a binding picker
 * offers only what nothing else has claimed. This is the *global* claim: a fixed
 * region's item is excluded from a battery row's picker exactly as that row's
 * guns are excluded from the layout's. Nothing here removes an existing binding
 * or an adopted mass when two would collide; the collision is named instead.
 */
export function claimedTargetIds(config: Raw): string[] {
  return componentTargetClaims(config).map(claim => claim.item);
}

/**
 * Every binding a declared component names, in declaration order and with the
 * owner named, so a collision can be *seen* rather than silently collapsed.
 *
 * `componentBindings` maps item to role and therefore keeps only one claimant
 * per item; this list keeps every occurrence, which is what makes "two components
 * name one item" detectable at all.
 */
export function componentTargetClaims(config: Raw): Array<{ item: string; owner: string }> {
  const claims: Array<{ item: string; owner: string }> = [];
  const name = (item: unknown, owner: string) => {
    if (typeof item === 'string' && item !== '') claims.push({ item, owner });
  };
  for (const battery of batteries(config)) {
    const id = String(battery.id ?? '');
    name(battery.guns_item_id, `battery ${id} guns`);
    name(battery.mounts_item_id, `battery ${id} mounts`);
    name(battery.ammunition_item_id, `battery ${id} ammunition`);
    name(object(battery.armour).item_id, `battery ${id} armour`);
  }
  for (const layout of batteryLayouts(config)) {
    name(object(layout.armour).item_id, `layout ${String(layout.id ?? '')} armour`);
  }
  name(object(config.machinery).item_id, 'machinery');
  name(object(config.fuel).item_id, 'fuel');
  for (const record of fixedArmour(config)) {
    name(fixedArmourTarget(record), `fixed armour ${String(record.id ?? '')}`);
  }
  for (const record of auxiliaryWeapons(config)) {
    name(auxiliaryWeaponTarget(record), `auxiliary weapon ${String(record.id ?? '')}`);
  }
  name(object(config.balance).structure_item_id, 'balance structure');
  return claims;
}

/** Ledger items more than one component names, which the core refuses. */
export function duplicateTargets(config: Raw): string[] {
  const counts = new Map<string, number>();
  for (const claim of componentTargetClaims(config)) {
    counts.set(claim.item, (counts.get(claim.item) ?? 0) + 1);
  }
  return [...counts].filter(([, count]) => count > 1).map(([item]) => item).sort();
}

/** The fixed regions that name one ledger item more than once. */
export function fixedArmourTargetConflicts(config: Raw): string[] {
  const counts = new Map<string, number>();
  for (const record of fixedArmour(config)) {
    const item = fixedArmourTarget(record);
    if (item !== null) counts.set(item, (counts.get(item) ?? 0) + 1);
  }
  return [...counts].filter(([, count]) => count > 1).map(([item]) => item).sort();
}

/** Bindings whose current role is not the one their component requires. */
export function mismatchedRoles(config: Raw): string[] {
  const current = roles(config);
  return Object.entries(componentBindings(config))
    .filter(([item, role]) => current[item] !== role)
    .map(([item]) => item);
}

// --- the request ------------------------------------------------------------

/**
 * Whether this draft asks for the concept screen.
 *
 * The stage is requested only when the section exists, so a project that never
 * enabled it keeps the old request defaults and the old results exactly. The
 * stage name is compared against the *assembled* stage list rather than added to
 * it, so re-deriving the options can never duplicate it.
 */
export function requestDesignBalance(draft: ProjectDocument | null): boolean {
  return conceptEnabled(draft);
}

/** The stages this draft requests: the request's own, plus the screen if enabled. */
export function withDesignBalance(stages: string[], draft: ProjectDocument | null): string[] {
  if (!requestDesignBalance(draft)) return stages;
  return stages.includes(DESIGN_BALANCE_STAGE) ? stages : [...stages, DESIGN_BALANCE_STAGE];
}

// --- the saved result -------------------------------------------------------

/** The stored bound proposals of the systems stage, in the server's own order. */
export function proposalsOf(run: RunView | null): Raw[] {
  return rows(object(stageData(run, 'systems')).update_proposals);
}

/**
 * The identity a proposal selection belongs to.
 *
 * Selection is only meaningful against one saved result of one revision and one
 * condition. Anything that changes those retires it, so a checkbox can never be
 * read as approving a proposal it was not set for.
 */
export function resultIdentity(run: RunView | null | undefined, projectId: string,
  revision: number, conditionId: string): string {
  if (!run || !run.result) return '';
  return [projectId, revision, conditionId, run.id, run.request_fingerprint].join('|');
}

/** One proposal's own identity, for the at-most-one-per-item rule. */
export function proposalKey(proposal: Raw): string {
  return `${String(proposal.item_id ?? '')}|${String(proposal.source_system_id ?? '')}|${String(proposal.source_model_id ?? '')}`;
}

export function conceptComponent(proposal: Raw): string {
  return String(object(proposal.model).concept_component ?? '');
}

/** The stage envelope for the concept screen, whatever its status. */
export function balanceStage(run: RunView | null): StageEnvelope | null {
  const envelope = run?.result?.stages[DESIGN_BALANCE_STAGE];
  return envelope ?? null;
}

export function balanceData(run: RunView | null): Raw {
  return object(stageData(run, DESIGN_BALANCE_STAGE));
}

/**
 * The saved component readings of the concept screen.
 *
 * Each is absent rather than empty when the screen declares no such feature, so
 * a project that never enabled fixed armour or cost keeps the previous result
 * structure exactly. Nothing here computes a mass or a price: these are the
 * server's own returned readings, with their own method, source and status.
 */
export function layoutReadings(run: RunView | null): Raw[] {
  return rows(balanceData(run).battery_layouts);
}

export function fixedArmourReadings(run: RunView | null): Raw[] {
  return rows(balanceData(run).fixed_armour);
}

export function auxiliaryWeaponReadings(run: RunView | null): Raw[] {
  return rows(balanceData(run).auxiliary_weapons);
}

export function costReading(run: RunView | null): Raw | null {
  const value = balanceData(run).cost;
  return value === null || value === undefined ? null : object(value);
}

/**
 * The whole-battery source estimates and the selected ledger figures beside them.
 *
 * One entry per declared layout, each with its own stable layout id, its own
 * method and its own two value objects: the recovered whole-battery estimate and
 * the current condition's selected figures. Absent rather than empty when no
 * layout is declared, so an optional feature nobody turned on stays absent.
 */
export function batteryTotalReadings(run: RunView | null): Raw[] {
  return rows(balanceData(run).battery_totals);
}

/** The one armour-totals reading, or `null` when it was never declared. */
export function armourTotalReading(run: RunView | null): Raw | null {
  const value = balanceData(run).armour_totals;
  return value === null || value === undefined ? null : object(value);
}

/** A number or null; anything else is unknown, never zero. */
export function metric(value: unknown): number | null {
  return number(value);
}

/** Long tons, the unit the recovered balance screen speaks. */
export const LONG_TON_LABEL = 'balance.unit.lt';

// --- the apply workflow -----------------------------------------------------

/**
 * What the apply button is actually waiting on.
 *
 * `saved` and `queueFailed` are separate states on purpose. Once the batch has
 * been saved the change is real, and no later failure may be described as
 * rolling it back. The only question left is whether the follow-up calculation
 * got queued, and the panel answers exactly that question.
 */
export type ApplyPhase =
  'idle' | 'applying' | 'saved' | 'queueing' | 'queueFailed' | 'failed' | 'conflict';

export interface ApplyState {
  phase: ApplyPhase;
  /** The revision the accepted batch was saved as, once it was. */
  revision: number | null;
  /** The server's own reason, or the queue failure's own reason. */
  reason: string | null;
}

export const IDLE_APPLY: ApplyState = { phase: 'idle', revision: null, reason: null };

/** Compare GUI options with saved normalized options; the server revalidates on apply. */
export function requestOptionsKey(value: unknown): string {
  const raw = object(value);
  const eq = object(raw.equilibrium);
  const equilibrium = {
    rho_t_m3: 1.025, heel_bounds_deg: [-85, 85], trim_bounds_deg: [-45, 45],
    max_iterations: 50, liquid_loads: [], ...eq,
    initial: { heel_deg: 0, trim_deg: 0, ...object(eq.initial) },
  };
  const options: Raw = { ...raw, equilibrium,
    stages: Array.isArray(raw.stages) ? [...raw.stages].sort() : null };
  for (const key of ['gz_angles_deg', 'hydrostatic_waterlines_above_keel_m',
    'bonjean_waterlines_above_keel_m', 'resistance', 'endurance_scenario_id', 'flooding']) {
    options[key] = raw[key] ?? null;
  }
  if (options.resistance) options.resistance = { mode: 'predict_power', ...object(options.resistance) };
  if (options.flooding) {
    const flood = object(options.flooding);
    const { liquid_loads: _liquids, ...floodEquilibrium } = equilibrium;
    options.flooding = { ...flood, options: { max_steps: 10000, max_step_halvings: 40,
      gravity_m_s2: 9.80665, remaining_gz_snapshot: 'final', ...object(flood.options),
      equilibrium: floodEquilibrium } };
  }
  const stable = (row: unknown): unknown => Array.isArray(row) ? row.map(stable)
    : row !== null && typeof row === 'object'
      ? Object.fromEntries(Object.entries(row).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, stable(item)]))
      : row;
  return JSON.stringify(stable(options));
}

export function requestOptionsMatch(run: RunView | null, options: unknown): boolean {
  const saved = object(run?.result?.request).options;
  return saved !== undefined && requestOptionsKey(saved) === requestOptionsKey(options);
}
