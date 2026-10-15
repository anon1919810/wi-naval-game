import type { ProjectDocument, RunView, StageEnvelope } from '../types';
import { number, object, rows, stageData, type Raw } from './formModel';

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
  return out;
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
