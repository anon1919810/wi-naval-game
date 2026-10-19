import type {
  ProjectDocument, RunView, ShipDesign, Sps3b3Catalog, Sps3b3Design, Sps3b3Diagnostic, Sps3b3Field,
  Sps3b3Preview, Sps3b3Result,
} from '../types';

/**
 * The SpringSharp 3b3 compatibility model: the declaration's shape, the field
 * catalogue's shape, the edit commands, and the one serial queue every edit
 * travels through.
 *
 * Nothing in this module computes ship numbers. The derived readings — bulged
 * beam, freeboard geometry, displacement, power — are the core's business, and
 * the only thing this side does is send the reader's declared inputs in a fixed
 * order and hold the answers. In particular there is no imperial/metric
 * conversion here: a unit command is a command like any other, so the core
 * converts first and the later values are read under the scale that was actually
 * in force when they arrived.
 */

/** The project section the declaration lives in. */
export const SPS_SECTION = 'sps_3b3_design';
/** The declaration's schema id. */
export const SPS_SCHEMA = 'plimsoll-sps3b3-design-1';
/** The declaration's result schema id. */
export const SPS_RESULT_SCHEMA = 'plimsoll-sps3b3-result-1';
/** The recovered method version. */
export const SPS_METHOD_VERSION = 'sps-3b3-compat-v1';
/** The stage that produces the compatibility result. */
export const SPS_STAGE = 'sps_compat';
/** The digest of the original program assembly the method was recovered from. */
export const SPS_SOURCE_SHA256 = '82ecc3fedf76af222dd13ad68258f3ae92146e9fad7dc6a4a96f3270fccf71fc';

/** The one authoritative native section. */
export const SHIP_DESIGN_SECTION = 'ship_design';
/** The native declaration's schema id. */
export const SHIP_DESIGN_SCHEMA = 'plimsoll-ship-design-1';
/** The native result's schema id, saved as the `ship_design` stage's data. */
export const SHIP_DESIGN_RESULT_SCHEMA = 'plimsoll-ship-design-result-1';
/** The native analysis stage that produces the unified result. */
export const SHIP_DESIGN_STAGE = 'ship_design';
/** The native method version reported by the reply. */
export const SHIP_DESIGN_METHOD_VERSION = 'ship-design-native-v1';

/** One declared compatibility command. The canonical value key is `value`. */
export interface SpsCommand {
  kind: string;
  [key: string]: unknown;
}

/** The transport one queued request uses. */
export type Sps3b3Confirm = (request: { design: Sps3b3Design; command?: SpsCommand }) => Promise<Sps3b3Preview>;

/* ------------------------------------------------------------------ shapes */

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function text(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

/**
 * The declaration a project holds, or `null` when it holds none.
 *
 * A section with the wrong schema is treated as absent rather than repaired: a
 * declaration that is not this method's is not silently upgraded.
 */
export function sps3b3DesignOf(project: ProjectDocument | null | undefined): Sps3b3Design | null {
  if (!project) return null;
  const raw = (project as Record<string, unknown>)[SPS_SECTION];
  if (!isRecord(raw)) return null;
  if (raw.schema !== undefined && raw.schema !== null && raw.schema !== SPS_SCHEMA) return null;
  return {
    ...raw,
    schema: SPS_SCHEMA,
    source: text(raw.source),
    parameters: isRecord(raw.parameters) ? raw.parameters : {},
    editing: isRecord(raw.editing) ? raw.editing : {},
    notes: text(raw.notes),
  } as Sps3b3Design;
}

export function sps3b3Enabled(project: ProjectDocument | null | undefined): boolean {
  return sps3b3DesignOf(project) !== null;
}

/** A project with its declaration replaced (or removed, when `design` is null). */
export function withSps3b3Design(project: ProjectDocument, design: Sps3b3Design | null): ProjectDocument {
  const next: Record<string, unknown> = { ...(project as Record<string, unknown>) };
  if (design === null) delete next[SPS_SECTION];
  else {
    next[SPS_SECTION] = design;
    if (!project.loading_conditions.length) {
      next.loading_conditions=[{id:'sps-design',label:'SPS 3b3 design'}];
    }
  }
  return next as ProjectDocument;
}

/* ------------------------------------------------------------ native design */

/**
 * The one authoritative native declaration, or `null` when the project has none.
 *
 * A section with the wrong schema is treated as absent rather than repaired: a
 * document that is not this product's is not silently upgraded here.
 */
export function shipDesignOf(project: ProjectDocument | null | undefined): ShipDesign | null {
  if (!project) return null;
  const raw = (project as Record<string, unknown>)[SHIP_DESIGN_SECTION];
  if (!isRecord(raw)) return null;
  if (raw.schema !== undefined && raw.schema !== null && raw.schema !== SHIP_DESIGN_SCHEMA) return null;
  const bindings = isRecord(raw.mass_bindings) ? raw.mass_bindings as Record<string, ShipDesign['mass_bindings'][string]> : {};
  return {
    ...raw,
    schema: SHIP_DESIGN_SCHEMA,
    source: text(raw.source),
    parameters: isRecord(raw.parameters) ? raw.parameters : {},
    editing: isRecord(raw.editing) ? raw.editing : {},
    notes: text(raw.notes),
    condition_id: text(raw.condition_id),
    mass_bindings: bindings,
  } as ShipDesign;
}

/** True when the project declares the native design. */
export function shipDesignEnabled(project: ProjectDocument | null | undefined): boolean {
  return shipDesignOf(project) !== null;
}

/** A project with its native design replaced, keeping it in the same section. */
export function withShipDesign(project: ProjectDocument, design: ShipDesign | null): ProjectDocument {
  const next: Record<string, unknown> = { ...(project as Record<string, unknown>) };
  if (design === null) delete next[SHIP_DESIGN_SECTION];
  else next[SHIP_DESIGN_SECTION] = design;
  return next as ProjectDocument;
}

/**
 * The temporary source-view of a native declaration, for the existing widgets.
 *
 * It carries the same parameter names, units, editing flags and notes; it is a
 * read-only adapter that is never written back as a second declaration.
 */
export function sourceViewOfShipDesign(design: ShipDesign): Sps3b3Design {
  return {
    schema: SPS_SCHEMA,
    source: design.source ?? null,
    parameters: { ...design.parameters },
    editing: { ...design.editing },
    notes: design.notes ?? null,
  };
}

/** The only run request a native design makes: one stage, no physical hull. */
export function shipDesignRunOptions(): Record<string, unknown> {
  return { stages: [SHIP_DESIGN_STAGE] };
}

/** True when the stages describe the native-only request. */
export function stagesAreShipDesign(stages: readonly string[]): boolean {
  return stages.length === 1 && stages[0] === SHIP_DESIGN_STAGE;
}

/** Whether a saved run carries the native design stage. */
export function runMatchesShipDesign(run: RunView | null): boolean {
  if (!run) return false;
  return requestStages(run.result).includes(SHIP_DESIGN_STAGE);
}

/** The only run request an SPS 3b3 run makes: one stage, no physical hull. */
export function sps3b3RunOptions(): Record<string, unknown> {
  return { stages: [SPS_STAGE] };
}

/** The stages a request or a saved result asked for. */
export function requestStages(value: unknown): string[] {
  if (!isRecord(value)) return [];
  const direct = value.stages;
  if (Array.isArray(direct)) return direct.filter((s): s is string => typeof s === 'string');
  const request = (value as { request?: unknown }).request;
  if (isRecord(request) && Array.isArray(request.stages)) {
    return request.stages.filter((s): s is string => typeof s === 'string');
  }
  return [];
}

/** True when the stages describe the compatibility-only request. */
export function stagesAreCompat(stages: readonly string[]): boolean {
  return stages.length === 1 && stages[0] === SPS_STAGE;
}

/**
 * Whether a saved run belongs to the mode currently on screen.
 *
 * A compatibility run is never presented as the standard physical result, and a
 * standard run is never presented as the compatibility result: the two requests
 * answer different questions, so an old result can only be current in the mode
 * that produced it.
 */
export function runMatchesSps(run: RunView | null, spsActive: boolean): boolean {
  if (!run) return false;
  const stages = requestStages(run.result);
  const compat = stagesAreCompat(stages);
  if (spsActive) return compat;
  return !compat && !stages.includes(SPS_STAGE);
}

/* --------------------------------------------------------------- catalogue */

/** A page's fields, already resolved to field records. */
export interface Sps3b3Group {
  id: string;
  kind: 'page' | 'guns' | 'torpedo' | 'mine' | 'depthCharge' | 'misc' | 'armourThickness' | 'armourExtents';
  index?: number;
  fields: Sps3b3Field[];
  collapsible: boolean;
  openByDefault: boolean;
}

export interface Sps3b3Catalogue {
  entries: Sps3b3Field[];
  byName: Record<string, Sps3b3Field>;
  pageOrder: string[];
  pageLabels: Record<string, string>;
  pageFields: Record<string, string[]>;
  controls: Record<string, unknown>;
  fieldCount: number;
  scaleNames: ReadonlySet<string>;
}

function fieldFrom(raw: Record<string, unknown>, fallbackKey?: string): Sps3b3Field {
  const name = text(raw.name) ?? fallbackKey ?? '';
  const key = text(raw.key) ?? name;
  return {
    ...raw,
    key,
    name,
    source_index: typeof raw.source_index === 'number' ? raw.source_index : 0,
    page: text(raw.page) ?? 'hull',
    label: text(raw.label) ?? name.replace(/_/g, ' '),
    kind: text(raw.kind) ?? 'number',
    unit: text(raw.unit),
    unit_resolved: text(raw.unit_resolved),
    scale_ref: text(raw.scale_ref),
    unit_choices: Array.isArray(raw.unit_choices) ? raw.unit_choices.map(String) : null,
    choices: Array.isArray(raw.choices) ? raw.choices.map(String) : null,
    allows_unselected: raw.allows_unselected === true,
    min_value: typeof raw.min_value === 'number' ? raw.min_value : null,
    max_value: typeof raw.max_value === 'number' ? raw.max_value : null,
  } as Sps3b3Field;
}

/**
 * Coerce whatever the API returns into the one shape this screen uses.
 *
 * The core reports `fields` as a name-keyed record and `pages` as a record of
 * objects; a transport that flattens either into a list is accepted too, so the
 * screen does not depend on which of two equivalent writings the gateway picked.
 */
export function readSps3b3Catalog(raw: Sps3b3Catalog | Record<string, unknown>): Sps3b3Catalogue {
  const source = raw as Record<string, unknown>;
  const entries: Sps3b3Field[] = [];
  const rawFields = source.fields;
  if (Array.isArray(rawFields)) {
    for (const item of rawFields) if (isRecord(item)) entries.push(fieldFrom(item));
  } else if (isRecord(rawFields)) {
    for (const [key, item] of Object.entries(rawFields)) if (isRecord(item)) entries.push(fieldFrom(item, key));
  }

  const byName: Record<string, Sps3b3Field> = {};
  for (const field of entries) if (field.name && !(field.name in byName)) byName[field.name] = field;

  const rawPages = source.pages;
  const pageFields: Record<string, string[]> = {};
  const pageLabels: Record<string, string> = {};
  if (isRecord(rawPages)) {
    for (const [page, value] of Object.entries(rawPages)) {
      if (Array.isArray(value)) {
        pageFields[page] = value.map(String);
      } else if (isRecord(value)) {
        const names = Array.isArray(value.fields) ? value.fields.map(String) : [];
        pageFields[page] = names;
        if (typeof value.label === 'string') pageLabels[page] = value.label;
      }
    }
  }
  if (isRecord(source.page_labels)) {
    for (const [page, label] of Object.entries(source.page_labels)) if (typeof label === 'string') pageLabels[page] = label;
  }

  const pageOrder = Array.isArray(source.page_order)
    ? source.page_order.map(String).filter(page => page in pageFields || entries.some(f => f.page === page))
    : [];
  if (pageOrder.length === 0) {
    for (const field of entries) if (!pageOrder.includes(field.page)) pageOrder.push(field.page);
  }
  for (const page of pageOrder) {
    if (!pageFields[page]) pageFields[page] = entries.filter(f => f.page === page).map(f => f.name);
    if (!pageLabels[page]) pageLabels[page] = (page[0] ?? '').toUpperCase() + page.slice(1);
  }

  const controls = isRecord(source.controls) ? source.controls : {};
  const scaleNames = new Set<string>();
  const globalScale = isRecord((controls as Record<string, unknown>).global_scale)
    ? (controls as Record<string, unknown>).global_scale as Record<string, unknown> : null;
  if (globalScale && Array.isArray(globalScale.scale_fields)) {
    for (const name of globalScale.scale_fields) if (typeof name === 'string') scaleNames.add(name);
  } else {
    for (const field of entries) if (/_scale$/.test(field.name)) scaleNames.add(field.name);
  }

  return {
    entries,
    byName,
    pageOrder,
    pageLabels,
    pageFields,
    controls,
    fieldCount: typeof source.field_count === 'number' ? source.field_count : entries.length,
    scaleNames,
  };
}

export function catalogueFields(catalogue: Sps3b3Catalogue, page: string): Sps3b3Field[] {
  return (catalogue.pageFields[page] ?? []).map(name => catalogue.byName[name]).filter(Boolean);
}

/** The page-unit selectors a `set_scale` command touches, recovered from the page. */
export function scaleRefsOf(catalogue: Sps3b3Catalogue, page: string): string[] {
  const refs = new Set<string>();
  for (const field of catalogueFields(catalogue, page)) if (field.scale_ref) refs.add(field.scale_ref);
  return [...refs];
}

export function isScaleField(catalogue: Sps3b3Catalogue, field: Sps3b3Field): boolean {
  return catalogue.scaleNames.has(field.name);
}

/**
 * The unit a field currently shows, resolved from the declaration it belongs to.
 *
 * A scaled field's own saved value is a 0/1 selector; the metric member is the
 * second `unit_choices` entry, exactly as the catalogue resolves it. This is a
 * label choice, not a conversion, and it never rewrites a stored value.
 */
export function resolvedUnit(field: Sps3b3Field, design: Sps3b3Design | null): string | null {
  // The recovered catalogue files the bow angle with the hull page's scaled
  // length fields, but the source reads it in degrees and never scales it. The
  // name is authoritative here, whatever scale metadata the catalogue carries.
  if (field.name === 'freeboard_length_bow') return 'deg';
  if (!field.scale_ref || !field.unit_choices || field.unit_choices.length < 2) {
    return field.unit_resolved ?? field.unit;
  }
  if (!design) return field.unit;
  const scale = design.parameters?.[field.scale_ref];
  if (typeof scale === 'number' && Number.isInteger(scale) && scale === 1) return field.unit_choices[1];
  return field.unit_choices[0];
}

/** The grouping the editor draws for a page: guns in five gun groups, and so on. */
export function groupsForPage(catalogue: Sps3b3Catalogue, page: string): Sps3b3Group[] {
  const fields = catalogueFields(catalogue, page);
  if (page === 'guns') {
    return ['1', '2', '3', '4', '5'].map((n, i) => ({
      id: `gun${n}`,
      kind: 'guns' as const,
      index: i + 1,
      fields: fields.filter(f => f.name.startsWith(`gun${n}_`)),
      collapsible: true,
      openByDefault: i === 0,
    })).filter(group => group.fields.length > 0);
  }
  if (page === 'weapons') {
    const groups: Sps3b3Group[] = [
      { id: 'torpedo1', kind: 'torpedo', index: 1, fields: fields.filter(f => f.name.startsWith('torpedo1_')), collapsible: true, openByDefault: true },
      { id: 'torpedo2', kind: 'torpedo', index: 2, fields: fields.filter(f => f.name.startsWith('torpedo2_')), collapsible: true, openByDefault: false },
      { id: 'mine1', kind: 'mine', fields: fields.filter(f => f.name.startsWith('mine1_')), collapsible: true, openByDefault: false },
      { id: 'depthCharge1', kind: 'depthCharge', index: 1, fields: fields.filter(f => f.name.startsWith('deck_gun1_')), collapsible: true, openByDefault: false },
      { id: 'depthCharge2', kind: 'depthCharge', index: 2, fields: fields.filter(f => f.name.startsWith('deck_gun2_')), collapsible: true, openByDefault: false },
      { id: 'misc', kind: 'misc', fields: fields.filter(f => f.name.startsWith('misc_weight_')), collapsible: true, openByDefault: false },
    ];
    const grouped = new Set(groups.flatMap(g => g.fields.map(f => f.name)));
    const rest = fields.filter(f => !grouped.has(f.name));
    return [...groups.filter(g => g.fields.length > 0), ...(rest.length
      ? [{ id: 'weapons-rest', kind: 'page' as const, fields: rest, collapsible: false, openByDefault: true }] : [])];
  }
  if (page === 'armour') {
    const thickness = fields.filter(f => /_thickness$/.test(f.name));
    const extents = fields.filter(f => !/_thickness$/.test(f.name));
    return [
      { id: 'armour-thickness', kind: 'armourThickness' as const, fields: thickness, collapsible: true, openByDefault: true },
      { id: 'armour-extents', kind: 'armourExtents' as const, fields: extents, collapsible: true, openByDefault: false },
    ].filter(group => group.fields.length > 0);
  }
  return [{ id: page, kind: 'page', fields, collapsible: false, openByDefault: true }];
}

/* ---------------------------------------------------------------- commands */

export const parameterCommand = (name: string, value: unknown): SpsCommand => ({ kind: 'set_parameter', name, value });
export const scaleCommand = (page: string, value: 0 | 1): SpsCommand => ({ kind: 'set_scale', page, value });
export const allScalesCommand = (value: 0 | 1): SpsCommand => ({ kind: 'set_all_scales', value });
export const lengthDriverCommand = (value: 'waterline' | 'overall'): SpsCommand => ({ kind: 'set_length_driver', value });
export const displacementDriverCommand = (value: 'block' | 'displacement'): SpsCommand => ({ kind: 'set_displacement_driver', value });
export const depthLockCommand = (value: boolean): SpsCommand => ({ kind: 'set_depth_lock', value });
export const freeboardPresetCommand = (value: 'flush' | 'raised'): SpsCommand => ({ kind: 'freeboard_preset', value });
export const powerLockCommand = (value: boolean): SpsCommand => ({ kind: 'set_power_lock', value });
export const recalculatePowerCommand = (): SpsCommand => ({ kind: 'recalculate_power' });
export const lockShellsCommand = (): SpsCommand => ({ kind: 'lock_shells' });
export const unlockShellsCommand = (): SpsCommand => ({ kind: 'unlock_shells' });
export const armourDefaultsCommand = (): SpsCommand => ({ kind: 'armour_defaults' });
export const notesCommand = (notes: string | null): SpsCommand => ({ kind: 'set_notes', notes });

/**
 * Bind one role to the ledger items that carry it.
 *
 * `mode` decides how: `estimated` is the product's own managed estimate and
 * admits exactly one owned target, while `declared` is the reader's explicit
 * adoption and may accumulate several. `mass_t` is only meaningful for an
 * additional existing payload whose role differs from the estimated one.
 */
export const bindMassCommand = (role: string, item_ids: string[], mode: 'estimated' | 'declared', mass_t?: number): SpsCommand =>
  ({ kind: 'bind_mass', role, item_ids, mode, ...(mass_t === undefined ? {} : { mass_t }) });

/**
 * Set an explicit declared mass on one owned ledger item.
 *
 * This is the only command that writes a manual override, and it writes it to
 * the declaration's own basis condition. Switching a role back to `estimated`
 * keeps the mass that was in force at that moment, so no base exclusion-zero is
 * ever resurrected.
 */
export const setDeclaredMassCommand = (item_id: string, value: number | null): SpsCommand =>
  ({ kind: 'set_declared_mass', item_id, value });

/**
 * The command a field edit produces.
 *
 * A page-unit selector is not sent as a parameter: the hull page's own selector
 * goes through `set_scale` (its owner refuses it as a parameter), and every
 * other page's selector is an ordinary parameter of that page's owner. The
 * global "all metric / all imperial" pair is a separate action.
 */
export function commandForField(
  catalogue: Sps3b3Catalogue, field: Sps3b3Field, value: unknown,
): SpsCommand {
  if (isScaleField(catalogue, field) && field.name === 'hull_scale') {
    return scaleCommand('hull', value === 1 ? 1 : 0);
  }
  return parameterCommand(field.name, value);
}

/**
 * The local overlay of one command: only the inputs the command literally
 * declares, never a derived reading.
 *
 * This is what the reader sees while the core is still answering, and it is
 * deliberately incomplete — a set of bulged-beam endpoints or a converted
 * length appears only when the confirmed reply arrives. Recomputing any of it
 * here would be a second, unverified implementation of the method.
 */
export function overlayCommand(catalogue: Sps3b3Catalogue, design: Sps3b3Design, command: SpsCommand): Sps3b3Design {
  const withParameters = (changes: Record<string, unknown>): Sps3b3Design =>
    ({ ...design, parameters: { ...design.parameters, ...changes } });
  const withEditing = (base:Sps3b3Design,changes: Record<string, unknown>): Sps3b3Design =>
    ({ ...base, editing: { ...base.editing, ...changes } });

  switch (command.kind) {
    case 'set_parameter': {
      const name = typeof command.name === 'string' ? command.name : '';
      if (!name) return design;
      const next = withParameters({ [name]: command.value ?? null });
      if (name === 'block_coefficient_normal') return withEditing(next, { displacement_driver: 'block' });
      return next;
    }
    case 'set_scale': {
      const page = typeof command.page === 'string' ? command.page : '';
      const changes: Record<string, unknown> = {};
      for (const ref of scaleRefsOf(catalogue, page)) changes[ref] = command.value ?? null;
      return Object.keys(changes).length ? withParameters(changes) : design;
    }
    case 'set_all_scales': {
      const changes: Record<string, unknown> = {};
      for (const name of catalogue.scaleNames) changes[name] = command.value ?? null;
      return Object.keys(changes).length ? withParameters(changes) : design;
    }
    case 'set_length_driver':
      return withEditing(design, { length_driver: command.value ?? null });
    case 'set_displacement_driver':
      return withEditing(design, { displacement_driver: command.value ?? null });
    case 'set_depth_lock':
      return withEditing(design, { depth_locked: command.value ?? null });
    case 'set_power_lock':
      return withEditing(design, { power_locked: command.value ?? null });
    case 'set_notes':
      return { ...design, notes: text(command.notes) ?? text(command.value) ?? null };
    default:
      return design;
  }
}

/* ------------------------------------------------------------------- queue */

export interface Sps3b3QueueState {
  confirmed: Sps3b3Design | null;
  display: Sps3b3Design | null;
  preview: Sps3b3Result | null;
  diagnostics: Sps3b3Diagnostic[];
  status: string | null;
  /** Declared edits not yet confirmed. Save and run stay blocked while positive. */
  pending: number;
  /** A request is in flight, including a pure preview refresh. */
  busy: boolean;
  error: string | null;
}

interface QueueItem {
  /** A declared edit that changes the draft; a refresh is not one. */
  edit: boolean;
  optimistic: (design: Sps3b3Design) => Sps3b3Design;
  payload: (base: Sps3b3Design) => { design: Sps3b3Design; command?: SpsCommand };
}

export interface Sps3b3QueueOptions<R extends Sps3b3Preview = Sps3b3Preview> {
  confirm: (request: { design: Sps3b3Design; command?: SpsCommand }) => Promise<R>;
  /** The catalogue in force, read at overlay time because it loads asynchronously. */
  catalogue: () => Sps3b3Catalogue;
  scaleRefsOf: (page: string) => string[];
  allScaleNames: () => readonly string[];
  /**
   * Called with the whole reply after a request settles *inside its generation*.
   *
   * The source editor needs nothing here, because its declared section is the
   * reply's own `design`. A native host does: its reply also carries the whole
   * governed project, which must be applied only when it belongs to the
   * generation that is still current. A reply from a superseded baseline never
   * reaches this callback, so a stale projection cannot overwrite a newer draft.
   */
  onSettled?: (reply: R) => void;
}

/**
 * The bounded serial command queue.
 *
 * One request is in flight at a time, and each is asked against the last
 * *confirmed* declaration — not against a whole draft captured when the reader
 * clicked. That ordering is the point: a beam edit that makes the core write
 * back bulged-beam and fixed bulkhead values is confirmed before the next edit
 * is sent, so a speed edit arriving a few milliseconds later cannot resurrect a
 * draft that never contained the coupling. The screen meanwhile shows the
 * reader's own declared inputs optimistically, and nothing else.
 *
 * A new baseline (project switch, an external replacement of the design, or
 * unmount) invalidates everything in flight: a late reply from the old scope is
 * dropped rather than committed over the new one.
 */
export class Sps3b3Queue<R extends Sps3b3Preview = Sps3b3Preview> {
  private confirmed: Sps3b3Design | null = null;
  private preview: Sps3b3Result | null = null;
  private diagnostics: Sps3b3Diagnostic[] = [];
  private status: string | null = null;
  private error: string | null = null;
  private items: QueueItem[] = [];
  private running = false;
  private generation = 0;
  private disposed = false;
  private current: Sps3b3QueueState;
  private readonly listeners = new Set<(state: Sps3b3QueueState) => void>();

  constructor(private readonly options: Sps3b3QueueOptions<R>) {
    this.current = this.build();
  }

  private build(): Sps3b3QueueState {
    let display = this.confirmed;
    for (const item of this.items) if (display) display = item.optimistic(display);
    return {
      confirmed: this.confirmed,
      display,
      preview: this.preview,
      diagnostics: this.diagnostics,
      status: this.status,
      pending: this.items.filter(item => item.edit).length,
      busy: this.running,
      error: this.error,
    };
  }

  private emit(): void {
    this.current = this.build();
    for (const listener of this.listeners) listener(this.current);
  }

  getState(): Sps3b3QueueState {
    return this.current;
  }

  subscribe(listener: (state: Sps3b3QueueState) => void): () => void {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  }

  /** Adopt a new confirmed baseline; any request from the old one is dropped. */
  start(design: Sps3b3Design): void {
    if (this.disposed) return;
    this.generation += 1;
    this.items = [];
    this.running = false;
    this.error = null;
    this.confirmed = design;
    this.preview = null;
    this.diagnostics = [];
    this.status = null;
    this.emit();
    this.refresh();
  }

  /**
   * Drop the baseline and everything in flight.
   *
   * Used when the host's scope goes away — no project, or a project whose design
   * section was removed — so a reply for the old scope can never settle onto the
   * new one and the screen does not keep a declaration that no longer exists.
   */
  reset(): void {
    if (this.disposed) return;
    this.generation += 1;
    this.items = [];
    this.running = false;
    this.error = null;
    this.confirmed = null;
    this.preview = null;
    this.diagnostics = [];
    this.status = null;
    this.emit();
  }

  /** Re-derive the preview from the confirmed declaration without editing it. */
  refresh(): void {
    if (this.disposed || !this.confirmed) return;
    if (this.items.some(item => !item.edit)) return;
    this.items = [...this.items, { edit: false, optimistic: design => design, payload: base => ({ design: base }) }];
    this.emit();
    void this.pump();
  }

  /** Declare one edit. It joins the end of the serial queue. */
  submit(command: SpsCommand): void {
    if (this.disposed || !this.confirmed) return;
    this.items = [...this.items, {
      edit: true,
      optimistic: design => overlayCommand(this.catalogue(), design, command),
      payload: base => ({ design: base, command }),
    }];
    this.emit();
    void this.pump();
  }

  /**
   * Replace the declaration through a pure mutator, applied against whatever is
   * confirmed when the request is actually sent.
   *
   * This is for a field the command set cannot address on its own — the
   * declaration's own `source`. Because the mutator runs on the latest confirmed
   * declaration, it can never write back a stale draft.
   */
  replace(mutate: (design: Sps3b3Design) => Sps3b3Design): void {
    if (this.disposed || !this.confirmed) return;
    this.items = [...this.items, {
      edit: true,
      optimistic: mutate,
      payload: base => ({ design: mutate(base) }),
    }];
    this.emit();
    void this.pump();
  }

  dispose(): void {
    this.disposed = true;
    this.generation += 1;
    this.listeners.clear();
    this.items = [];
    this.running = false;
  }

  activate():void {
    this.disposed=false;
  }

  retry(): void {
    this.error=null;
    void this.pump();
  }

  private catalogue(): Sps3b3Catalogue {
    return this.options.catalogue();
  }

  private async pump(): Promise<void> {
    if (this.disposed || this.running || this.items.length === 0 || !this.confirmed) return;
    const generation = this.generation;
    const item = this.items[0];
    const request = item.payload(this.confirmed);
    this.running = true;
    this.emit();
    let reply: R;
    try {
      reply = await this.options.confirm(request);
    } catch (cause) {
      if (this.disposed || generation !== this.generation) return;
      this.running = false;
      this.error = cause instanceof Error ? cause.message : String(cause);
      this.emit();
      return;
    }
    if (this.disposed || generation !== this.generation) return;
    this.confirmed = reply.design;
    this.preview = reply.preview ?? null;
    this.diagnostics = Array.isArray(reply.diagnostics) ? reply.diagnostics : [];
    this.status = typeof reply.status === 'string' ? reply.status : null;
    this.error = null;
    this.items = this.items.slice(1);
    this.running = false;
    this.emit();
    // The whole reply is handed to a host only now, after the generation check
    // above and the state it belongs to are already committed. A host that
    // overlays the returned project therefore can never write a stale one.
    this.options.onSettled?.(reply);
    void this.pump();
  }
}

/* ---------------------------------------------------------------- readings */

export function sps3b3ResultOf(data: unknown): Sps3b3Result | null {
  if (!isRecord(data)) return null;
  return data as Sps3b3Result;
}

/** The native section a design page's derived readings live in. */
export function pageSectionId(page: string): string {
  switch (page) {
    case 'weapons': return 'auxiliary';
    case 'guns': return 'guns';
    case 'freeboard': return 'freeboard';
    case 'armour': return 'armour';
    case 'engine': return 'engine';
    case 'performance': return 'performance';
    default: return 'hull';
  }
}

export interface Sps3b3Reading { key: string; value: unknown }

/** The native field/value pairs of one section, in the core's own order. */
export function nativeReadings(result: Sps3b3Result | null, section: string): Sps3b3Reading[] {
  if (!result) return [];
  const bag = (result as Record<string, unknown>)[section];
  if (!isRecord(bag)) return [];
  return Object.entries(bag).map(([key, value]) => ({ key, value }));
}

export const NATIVE_SECTION_ORDER = ['hull', 'freeboard', 'guns', 'auxiliary', 'armour', 'engine', 'performance'] as const;

export function splitDiagnostics(diagnostics: readonly Sps3b3Diagnostic[]): { severe: Sps3b3Diagnostic[]; other: Sps3b3Diagnostic[] } {
  const severe: Sps3b3Diagnostic[] = [];
  const other: Sps3b3Diagnostic[] = [];
  for (const diagnostic of diagnostics) {
    if (diagnostic.blocking === true || diagnostic.severity === 'error' || diagnostic.severity === 'fatal') severe.push(diagnostic);
    else other.push(diagnostic);
  }
  return { severe, other };
}

export function sps3b3MethodVersion(result: Sps3b3Result | null): string {
  const provenance = result && isRecord(result.provenance) ? result.provenance : null;
  if (typeof result?.method_version === 'string') return result.method_version;
  if (provenance && typeof provenance.method_version === 'string') return provenance.method_version;
  return SPS_METHOD_VERSION;
}

export function sps3b3SourceSha(result: Sps3b3Result | null): string {
  const provenance = result && isRecord(result.provenance) ? result.provenance : null;
  if (provenance && typeof provenance.source_sha256 === 'string') return provenance.source_sha256;
  return SPS_SOURCE_SHA256;
}

export function sps3b3ReportText(result: Sps3b3Result | null): string | null {
  if (!result || !isRecord(result.report)) return null;
  return typeof result.report.text === 'string' ? result.report.text : null;
}

export interface Sps3b3ReportSection { id: string; title: string; lines: string[] }

export function sps3b3ReportSections(result: Sps3b3Result | null): Sps3b3ReportSection[] {
  if (!result || !isRecord(result.report) || !Array.isArray(result.report.sections)) return [];
  const sections: Sps3b3ReportSection[] = [];
  for (const item of result.report.sections) {
    if (!isRecord(item)) continue;
    sections.push({
      id: typeof item.id === 'string' ? item.id : '',
      title: typeof item.title === 'string' ? item.title : '',
      lines: Array.isArray(item.lines) ? item.lines.map(String) : [],
    });
  }
  return sections;
}

/** A cheap value comparison, used only to avoid writing an unchanged design back. */
export function sameDesign(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  try { return JSON.stringify(a) === JSON.stringify(b); } catch { return false; }
}
